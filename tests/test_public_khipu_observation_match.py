"""Exact public observations must survive compiler and real invoke boundaries."""
import asyncio
import copy
import hashlib
import json
from dataclasses import replace

import httpx
import pytest
from fastapi import HTTPException

from test_evidence_resolution import SCOPE
# Import the fixture dependencies too, so this file can run independently.
from test_public_khipu_integration import ledger, public_runtime, reply, request, runtime


EXPECTED = "BTC/USD spot 65000.0; unverified observation, human review."


def _rehash_reply(k, value):
    """Keep unsigned consistency valid so only the observation rule can fail."""
    record = value["szl_provenance"]["execution_record"]
    text = value["choices"][0]["message"]["content"]
    record["output_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    record["record_sha256"] = k.digest({
        key: item for key, item in record.items() if key != "record_sha256"
    })


def _mock_provider(public_runtime, monkeypatch, mutate=None):
    real_client = httpx.AsyncClient
    seen = []

    def response(provider_request):
        assert str(provider_request.url) == public_runtime.public_khipu.ENDPOINT
        sent = json.loads(provider_request.content)
        assert sent["messages"][1]["content"] == EXPECTED
        value = reply(public_runtime.public_khipu, sent)
        original_request_hash = value["szl_provenance"]["execution_record"]["canonical_request_sha256"]
        if mutate is not None:
            mutate(value)
        _rehash_reply(public_runtime.public_khipu, value)
        record = value["szl_provenance"]["execution_record"]
        assert record["canonical_request_sha256"] == original_request_hash
        assert record["signature_status"] == "UNSIGNED" and record["signature"] is None
        seen.append(value)
        return httpx.Response(200, json=value)

    monkeypatch.setattr(public_runtime.httpx, "AsyncClient", lambda **kwargs:
                        real_client(transport=httpx.MockTransport(response), **kwargs))
    return seen


@pytest.mark.parametrize("mutation", [
    "wrong-value", "appended-forecast", "appended-advice", "extra-choice",
    "length", "time_budget",
])
def test_self_consistent_non_observation_reply_is_withheld_on_invoke(
    public_runtime, monkeypatch, mutation,
):
    def mutate(value):
        choice = value["choices"][0]
        if mutation == "wrong-value":
            choice["message"]["content"] = EXPECTED.replace("65000.0", "65001.0")
        elif mutation == "appended-forecast":
            choice["message"]["content"] += " BTC will rise tomorrow."
        elif mutation == "appended-advice":
            choice["message"]["content"] += " Buy BTC now."
        elif mutation == "extra-choice":
            extra = copy.deepcopy(choice)
            extra["message"]["content"] = "SECOND_CHOICE_PROVIDER_TEXT_MUST_BE_WITHHELD"
            value["choices"].append(extra)
        else:
            # Exact text and consistent provider labels still cannot make an
            # incomplete response eligible for display.
            assert choice["message"]["content"] == EXPECTED
            choice["finish_reason"] = "length"
            record = value["szl_provenance"]["execution_record"]
            record["termination"] = {
                "reason": mutation, "time_budget_reached": mutation == "time_budget",
            }
            record["usage"]["completion_tokens"] = 32
            record["usage"]["total_tokens"] = record["usage"]["prompt_tokens"] + 32
            value["usage"] = copy.deepcopy(record["usage"])

    seen = _mock_provider(public_runtime, monkeypatch, mutate)
    with pytest.raises(HTTPException) as error:
        asyncio.run(public_runtime.vertical_intelligence_invoke(
            "finance", request(public_runtime), SCOPE))

    assert error.value.status_code == 502
    assert len(seen) == 1, "the regression must reach the provider response boundary"
    exposed = json.dumps(error.value.detail) + str(error.value)
    for choice in seen[0]["choices"]:
        assert choice["message"]["content"] not in exposed
    assert "BTC/USD" not in exposed
    assert "65001.0" not in exposed
    assert "BTC will rise tomorrow" not in exposed
    assert "Buy BTC now" not in exposed


def test_completed_exact_observation_reports_limited_verification(public_runtime, monkeypatch):
    seen = _mock_provider(public_runtime, monkeypatch)
    result = asyncio.run(public_runtime.vertical_intelligence_invoke(
        "finance", request(public_runtime), SCOPE))

    assert len(seen) == 1
    assert result["output"] == EXPECTED
    assert result["output_sha256"] == hashlib.sha256(EXPECTED.encode("utf-8")).hexdigest()
    verified = result["provider_verification"]
    assert verified["observation_match_verified"] is True
    assert verified["observation_match_scope"] == "LOCALLY_COMPILED_PUBLIC_VALUE_ONLY"
    assert verified["output_complete"] is True
    assert verified["finish_reason"] == "stop"
    assert verified["time_budget_reached"] is False
    assert verified["signature_status"] == "UNSIGNED"
    assert verified["authenticity_established"] is False
    assert result["human_approval_required"] is True
    assert result["effectors_enabled"] is False
    assert result["truth_label"] == "MODELED"


def _compiler_records(public_runtime, payload, first="coinbase-spot"):
    evidence = public_runtime._resolve_plan_evidence("finance", payload, SCOPE)
    assert evidence.state == "COMPLETE"
    records = json.loads(evidence.records_json)
    assert {row["connector_id"] for row in records} == {
        "coinbase-spot", "treasury-average-rates",
    }
    records.sort(key=lambda row: row["connector_id"] != first)
    return evidence, records


@pytest.mark.parametrize("first", ["coinbase-spot", "treasury-average-rates"])
def test_compiler_selects_typed_coinbase_sentence_in_either_record_order(public_runtime, first):
    payload = request(public_runtime, objective="PRIVATE_OBJECTIVE_DO_NOT_FORWARD")
    evidence, records = _compiler_records(public_runtime, payload, first)
    for row in records:
        row["summary"]["arbitrary_text"] = "ARBITRARY_LEDGER_INSTRUCTIONS_DO_NOT_FORWARD"
        row["summary"]["private_text"] = "PRIVATE_LEDGER_TEXT_DO_NOT_FORWARD"
    reordered = replace(evidence, records_json=json.dumps(records))

    system, user = public_runtime.public_khipu.messages(payload, reordered)

    assert user == EXPECTED
    assert "Treasury observed rate" not in user
    outbound = system + user
    for private_text in (
        payload.objective, "must-never-be-forwarded",
        "ARBITRARY_LEDGER_INSTRUCTIONS_DO_NOT_FORWARD", "PRIVATE_LEDGER_TEXT_DO_NOT_FORWARD",
    ):
        assert private_text not in outbound


@pytest.mark.parametrize("field, invalid", [
    ("latest_record_date", "PRIVATE_TREASURY_DATE_DO_NOT_FORWARD"),
    ("rate_min_pct", "PRIVATE_TREASURY_RATE_DO_NOT_FORWARD"),
    ("rate_max_pct", True),
], ids=["arbitrary-date", "text-rate", "boolean-rate"])
def test_compiler_validates_unselected_treasury_fields(public_runtime, field, invalid):
    payload = request(public_runtime)
    evidence, records = _compiler_records(public_runtime, payload)
    assert records[0]["connector_id"] == "coinbase-spot"
    assert public_runtime.public_khipu.messages(
        payload, replace(evidence, records_json=json.dumps(records)))[1] == EXPECTED
    records[1]["summary"][field] = invalid

    with pytest.raises(ValueError) as error:
        public_runtime.public_khipu.messages(
            payload, replace(evidence, records_json=json.dumps(records)))
    assert "PRIVATE_TREASURY" not in str(error.value)


def test_compiler_refuses_arbitrary_text_in_coinbase_numeric_field(public_runtime):
    payload = request(public_runtime)
    evidence, records = _compiler_records(public_runtime, payload)
    records[0]["summary"]["amount"] = "65000.0 PRIVATE_AMOUNT_DO_NOT_FORWARD"

    with pytest.raises(ValueError) as error:
        public_runtime.public_khipu.messages(
            payload, replace(evidence, records_json=json.dumps(records)))
    assert "PRIVATE_AMOUNT_DO_NOT_FORWARD" not in str(error.value)
