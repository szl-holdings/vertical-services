"""Public demo admission and provider reply consistency using the real ledger."""
import asyncio
import copy
import hashlib
import json

import httpx
import pytest
from fastapi import HTTPException

from test_intelligence_evidence_admission import runtime
from test_evidence_resolution import CLOCK, DIGESTS, SCOPE, ledger


@pytest.fixture
def public_runtime(runtime, ledger, monkeypatch):
    from szl_verticals.connector_specs import CONNECTORS
    from szl_verticals.official_connectors import _receipt
    monkeypatch.setattr(runtime, "CONNECTORS", CONNECTORS)
    samples = [
        ("coinbase-spot", "https://api.coinbase.com/v2/prices/BTC-USD/spot",
         {"base": "BTC", "currency": "USD", "amount": 65000.0,
          "ignored_private_text": "must-never-be-forwarded"}),
        ("treasury-average-rates", "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates?sort=-record_date",
         {"latest_record_date": "2026-09-30", "rate_min_pct": 3.1, "rate_max_pct": 4.5}),
    ]
    for index, (connector, source, summary) in enumerate(samples):
        receipt = _receipt(spec=CONNECTORS[connector], session_scope=SCOPE,
                           query_hash="c" * 64, source_url=source, http_status=200,
                           payload_sha256=DIGESTS[index], observed_at=CLOCK - 10,
                           state="OBSERVED")
        ledger.put(receipt, summary)
    return runtime


def request(runtime, **overrides):
    values = dict(task="risk-summary", objective="Local objective not sent to the public demo",
                  context="", axes={"evidence": .95, "freshness": .95},
                  evidence_sha256=DIGESTS[:2], preferred_model="khipu-gguf-public",
                  public_demo_consent=True, max_new_tokens=32, temperature=0.0)
    values.update(overrides)
    return runtime.IntelligenceInvokeRequest(**values)


def reply(k, sent):
    text = "Market observations require cautious human review."
    usage = {"prompt_tokens": 300, "completion_tokens": 8, "total_tokens": 308}
    basis = {"schema": "szl.openai-chat-request/v1", "model": k.MODEL_ID,
             "messages": sent["messages"], "max_completion_tokens": 32,
             "temperature": 0.0, "top_p": 1.0, "n": 1, "stream": False, "tools": None}
    record = {"schema": "szl.unsigned-execution-record/v1",
              "canonical_request_sha256": k.digest(basis),
              "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
              "model": {"id": k.MODEL_ID, "repo": k.REPO, "revision": k.REVISION,
                        "file": k.MODEL_FILE, "sha256": k.MODEL_SHA256},
              "source": {"space_id": "SZLHOLDINGS/szl-model-inference-lab"},
              "usage": usage, "signature_status": "UNSIGNED", "signature": None,
              "termination": {"reason": "stop", "time_budget_reached": False},
              "authenticity_not_established": True}
    record["record_sha256"] = k.digest(record)
    return {"model": k.MODEL_ID, "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
            "usage": usage, "szl_provenance": {"execution_record": record}}


def test_actual_invoke_uses_exact_pin_public_projection_and_no_credentials(public_runtime, monkeypatch):
    runtime = public_runtime
    payload = request(runtime)
    plan = runtime.build_intelligence_plan("finance", payload, SCOPE)
    assert plan["decision"] == "READY_FOR_INFERENCE"
    real_client = httpx.AsyncClient
    seen = []
    def response(req):
        assert str(req.url) == runtime.public_khipu.ENDPOINT
        assert "authorization" not in req.headers
        sent = json.loads(req.content)
        assert sent["model"] == runtime.public_khipu.MODEL_ID
        assert sent["max_tokens"] == 32 and sent["temperature"] == 0
        assert len(req.content) <= 8192
        assert sum(len(m["content"]) for m in sent["messages"]) <= 1200
        assert "must-never-be-forwarded" not in req.content.decode()
        assert payload.objective not in req.content.decode()
        assert hashlib.sha256(sent["messages"][1]["content"].encode()).hexdigest() == plan["inference_input_sha256"]
        seen.append(sent)
        return httpx.Response(200, json=reply(runtime.public_khipu, sent))
    monkeypatch.setattr(runtime.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(response), **kw))
    result = asyncio.run(runtime.vertical_intelligence_invoke("finance", payload, SCOPE))
    assert len(seen) == 1
    assert result["provider_verification"]["request_hash_verified"] is True
    assert result["provider_verification"]["authenticity_established"] is False
    assert result["provider_verification"]["output_complete"] is True
    assert result["effectors_enabled"] is False


@pytest.mark.parametrize("overrides", [
    {"public_demo_consent": False}, {"context": "private context"},
    {"max_new_tokens": 384}, {"temperature": .1}, {"task": "filing-research"},
    {"evidence_sha256": DIGESTS[:1]}, {"evidence_sha256": ["a" * 64, "b" * 64]},
])
def test_public_contract_and_evidence_fail_closed_before_network(public_runtime, monkeypatch, overrides):
    runtime = public_runtime
    calls = []
    async def forbidden(*a, **kw):
        calls.append(True)
        raise AssertionError("no dispatch")
    monkeypatch.setattr(runtime, "_invoke_provider", forbidden)
    with pytest.raises(HTTPException) as error:
        asyncio.run(runtime.vertical_intelligence_invoke("finance", request(runtime, **overrides), SCOPE))
    assert error.value.status_code == 503
    assert not calls


@pytest.mark.parametrize("mutation", ["model", "revision", "request", "output", "record", "usage"])
def test_mismatched_unsigned_reply_is_withheld(public_runtime, monkeypatch, mutation):
    runtime = public_runtime
    real_client = httpx.AsyncClient
    def response(req):
        value = copy.deepcopy(reply(runtime.public_khipu, json.loads(req.content)))
        record = value["szl_provenance"]["execution_record"]
        if mutation == "model": value["model"] = "different-model"
        if mutation == "revision": record["model"]["revision"] = "a" * 40
        if mutation == "request": record["canonical_request_sha256"] = "b" * 64
        if mutation == "output": value["choices"][0]["message"]["content"] = "changed"
        if mutation == "record": record["record_sha256"] = "c" * 64
        if mutation == "usage": record["usage"]["completion_tokens"] = 33
        # Even a self-consistent wrong identity/request/usage must be rejected.
        if mutation != "record":
            record["record_sha256"] = runtime.public_khipu.digest({k: v for k, v in record.items() if k != "record_sha256"})
        return httpx.Response(200, json=value)
    monkeypatch.setattr(runtime.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(response), **kw))
    with pytest.raises(HTTPException) as error:
        asyncio.run(runtime.vertical_intelligence_invoke("finance", request(runtime), SCOPE))
    assert error.value.status_code == 502


@pytest.mark.parametrize("reason", ["length", "time_budget"])
def test_bounded_output_is_explicitly_incomplete(public_runtime, reason):
    k = public_runtime.public_khipu
    sent = k.payload(k.SYSTEM, "Public numbers only")
    value = reply(k, sent)
    record = value["szl_provenance"]["execution_record"]
    record["termination"] = {"reason": reason, "time_budget_reached": reason == "time_budget"}
    record["record_sha256"] = k.digest({key: item for key, item in record.items() if key != "record_sha256"})
    value["choices"][0]["finish_reason"] = "length"
    _, verified = k.verify_reply(value, sent)
    assert verified["output_complete"] is False
    assert verified["finish_reason"] == reason


def test_inconsistent_termination_label_is_rejected(public_runtime):
    k = public_runtime.public_khipu
    sent = k.payload(k.SYSTEM, "Public numbers only")
    value = reply(k, sent)
    value["choices"][0]["finish_reason"] = "length"
    with pytest.raises(HTTPException):
        k.verify_reply(value, sent)
