"""Fixed-source inventory, bounded metadata, and receipt admission regressions."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))
os.environ.setdefault("SENTRA_SIGNING_KEY", "dataset-fixture-not-production")
os.environ.setdefault("SZL_SOURCE_REVISION", "4" * 40)

from app import app  # noqa: E402
from szl_verticals.connector_parameters import _assert_allowed_destination  # noqa: E402
from szl_verticals.connector_parsers_datasets import _parse_hf_datasets  # noqa: E402
from szl_verticals.connector_specs import CONNECTORS, HF_DATASET_API_URL  # noqa: E402
from szl_verticals.core import session_scope  # noqa: E402
from szl_verticals.store import ObservationStore  # noqa: E402

official = importlib.import_module("szl_verticals.official_connectors")
operational = importlib.import_module("szl_verticals.operational")
frontier = importlib.import_module("szl_verticals.frontier")
TOKEN = "dataset-inventory-test-session-0123456789"
OTHER_TOKEN = "dataset-inventory-other-session-0123456789"
FETCH_URL = "/api/verticals/lyte/connectors/hf-datasets/fetch"


def dataset(**changes):
    return {
        "id": "SZLHOLDINGS/fixture-inventory",
        "sha": "a" * 40,
        "tags": ["license:apache-2.0", "task_categories:text-generation"],
        "private": False,
        "gated": "manual",
        "lastModified": "2026-11-16T12:00:00Z",
        "description": "Metadata only: this source text must not be retained.",
        **changes,
    }


@pytest.fixture
def context(monkeypatch, tmp_path):
    monkeypatch.setenv("SZL_STATE_PATH", str(tmp_path / "observations.sqlite3"))
    monkeypatch.setenv("SZL_SOURCE_REVISION", "4" * 40)
    # A configured inference credential must not change the public catalog scope.
    monkeypatch.setenv("HF_TOKEN", "fixture-token-never-sent")
    db = ObservationStore()
    assert db.error is None
    monkeypatch.setattr(official, "STORE", db)
    monkeypatch.setattr(operational, "STORE", db)
    monkeypatch.setattr(frontier, "STORE", db)
    state = {"payload": [dataset()], "requests": [], "status": 200, "headers": {}}

    def handler(request):
        state["requests"].append(request)
        assert request.method == "GET"
        assert request.url.scheme == "https"
        assert request.url.host == "huggingface.co"
        assert request.url.path == "/api/datasets"
        assert dict(request.url.params) == {"author": "SZLHOLDINGS", "limit": "500", "full": "true"}
        assert "authorization" not in request.headers
        encoded = json.dumps(state["payload"], ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()
        return httpx.Response(
            state["status"], content=encoded,
            headers={"content-type": "application/json", **state["headers"]},
        )

    transport = httpx.MockTransport(handler)
    bounded_get = official._bounded_get

    def local_get(url, **kwargs):
        kwargs["transport"] = transport
        return bounded_get(url, **kwargs)

    monkeypatch.setattr(official, "_bounded_get", local_get)
    with TestClient(app, headers={"X-SZL-Session": TOKEN}) as client:
        yield db, client, state


def fetch(context, **body):
    return context[1].post(FETCH_URL, json={"force_refresh": True, **body})


def test_fixed_public_inventory_is_receipted_cached_and_keeps_unknowns(context):
    db, client, state = context
    state["payload"] = [dataset(), {"id": "SZLHOLDINGS/unknown-fields"}, dataset()]
    response = fetch(context)
    assert response.status_code == 200, response.text
    result = response.json()
    observed = result["observation"]
    assert observed["coverage"] == "PUBLIC_CATALOG_PAGE"
    assert (observed["returned_count"], observed["unique_count"], observed["duplicate_count"]) == (3, 2, 1)
    assert observed["completeness"] == "UNKNOWN"
    assert observed["private_estate_covered"] is False
    assert observed["training_admission"] == "NOT_ADMITTED"
    assert observed["quality_evidence"] == "UNAVAILABLE"
    known, unknown = observed["items"]
    assert known["revision"] == "a" * 40
    assert known["source_url"] == "https://huggingface.co/datasets/SZLHOLDINGS/fixture-inventory"
    assert known["license_tags"] == ["apache-2.0"]
    assert known["gated"] == "manual" and known["private"] is False
    assert known["last_modified"] == "2026-11-16T12:00:00.000Z"
    assert all(unknown[field] is None for field in ("revision", "license_tags", "gated", "private", "last_modified"))
    assert "description" not in json.dumps(observed)
    receipt = result["receipt"]
    raw = json.dumps(state["payload"], ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    assert receipt["payload_sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["truth_label"] == "REPORTED"
    assert receipt["signature_claimed"] is False
    assert "session_scope" not in receipt
    assert result["signal"]["kind"] == "public-dataset-inventory"
    assert result["signal"]["training_admission"] == "NOT_ADMITTED"
    cached = client.post(FETCH_URL, json={}).json()
    assert cached["cache"]["hit"] is True
    assert cached["receipt"]["receipt_id"] == receipt["receipt_id"]
    assert len(state["requests"]) == 1
    reopened = ObservationStore()
    assert reopened.recent(vertical="lyte", session_scope=session_scope(TOKEN))[0]["summary"] == observed
    assert db.status()["writable"] is True


def test_inventory_uses_existing_second_brain_and_hatun_scope_without_training_authority(context):
    _, client, _ = context
    result = fetch(context).json()
    digest = result["receipt"]["payload_sha256"]
    memory = client.get("/api/verticals/lyte/second-brain").json()["memory"]
    assert memory["count"] == 1
    assert memory["observations"][0]["connector_id"] == "hf-datasets"
    assert memory["observations"][0]["summary"]["training_admission"] == "NOT_ADMITTED"
    review_request = {
        "intent": "review the public dataset catalog metadata",
        "requested_action": "dataset.inventory.review",
        "axes": {"evidence": 0.95, "freshness": 0.95},
        "evidence_sha256": [digest],
    }
    reviewed = client.post("/api/verticals/lyte/hatun/evaluate", json=review_request)
    assert reviewed.status_code == 200, reviewed.text
    review = reviewed.json()
    assert review["decision"] == "REVIEW"
    assert review["evidence_resolution"]["state"] == "COMPLETE"
    assert review["session_observation_count"] == 1
    assert review["evidence_resolution"]["semantic_validity"] == "NOT_VERIFIED"
    assert review["can_authorize"] is False and review["can_execute"] is False
    with TestClient(app, headers={"X-SZL-Session": OTHER_TOKEN}) as other:
        assert other.get("/api/verticals/lyte/second-brain").json()["memory"]["count"] == 0
        denied = other.post("/api/verticals/lyte/hatun/evaluate", json=review_request).json()
        assert denied["decision"] == "ABSTAIN"
        assert denied["evidence_resolution"]["resolved_count"] == 0
    withdrawn = client.post("/api/verticals/lyte/evidence/withdraw", json={"evidence_sha256": [digest]})
    assert withdrawn.status_code == 200
    assert client.post("/api/verticals/lyte/hatun/evaluate", json=review_request).json()["decision"] == "ABSTAIN"


@pytest.mark.parametrize("parameters", [
    {"url": "https://example.invalid"}, {"owner": "someone-else"}, {"author": "someone-else"},
    {"limit": 1}, {"full": False}, {"query": "private"}, {"token": "no"},
])
def test_caller_cannot_change_source_or_scope(context, parameters):
    result = fetch(context, parameters=parameters)
    assert result.status_code == 422
    assert context[2]["requests"] == []


@pytest.mark.parametrize("url", [
    "http://huggingface.co/api/datasets", "https://huggingface.co/api/models",
    "https://huggingface.co/api/datasets/other", "https://huggingface.co.evil.invalid/api/datasets",
    "https://user:pass@huggingface.co/api/datasets", "https://huggingface.co:8443/api/datasets",
    "https://huggingface.co/api/datasets?author=other", "https://huggingface.co/api/datasets#fragment",
])
def test_hub_allowlist_is_one_fixed_destination(url):
    _assert_allowed_destination(HF_DATASET_API_URL)
    with pytest.raises(HTTPException):
        _assert_allowed_destination(url)


@pytest.mark.parametrize("payload", [
    {"datasets": []}, [None], [{"id": "OTHER/dataset"}], [{"id": "SZLHOLDINGS/../escape"}],
    [dataset(sha="main")], [dataset(private="false")], [dataset(gated=1)],
    [dataset(tags="license:mit")], [dataset(tags=[None])], [dataset(tags=["license:"])],
    [dataset(tags=["license:" + chr(0xD800)])], [dataset(gated=chr(0xD800))],
    [dataset(lastModified="not-a-time")], [dataset(lastModified="0001-01-01T00:00:00+01:00")],
    [dataset(), dataset(sha="b" * 40)], [dataset()] * 501,
])
def test_malformed_catalog_is_rejected_without_ledger_evidence(context, payload):
    context[2]["payload"] = payload
    response = fetch(context)
    assert response.status_code == 502, response.text
    assert context[0].recent(vertical="lyte", session_scope=session_scope(TOKEN)) == []


def test_empty_page_and_cap_are_explicit_without_completeness_claims():
    empty = _parse_hf_datasets([], {})
    assert empty["unique_count"] == 0 and empty["completeness"] == "UNKNOWN"
    capped = _parse_hf_datasets([dataset()] * 500, {})
    assert capped["at_limit"] is True
    assert capped["completeness"] == "AT_LIMIT"
    assert capped["returned_count"] == 500 and capped["duplicate_count"] == 499
    assert "next_page" not in capped and "has_more" not in capped


def test_unknown_gating_state_is_preserved_without_access_claim():
    result = _parse_hf_datasets([dataset(gated="provider-new-state")], {})
    assert result["items"][0]["gated"] == "provider-new-state"
    assert result["training_admission"] == "NOT_ADMITTED"


def test_normalized_summary_cannot_exceed_existing_evidence_budget(context):
    context[2]["payload"] = [
        dataset(id=f"SZLHOLDINGS/budget-{i}", tags=[f"license:license-{n}-" + "x" * 110 for n in range(16)])
        for i in range(80)
    ]
    result = fetch(context)
    assert result.status_code == 502
    assert "evidence summary budget" in result.json()["detail"]
    assert context[0].recent(vertical="lyte", session_scope=session_scope(TOKEN)) == []


@pytest.mark.parametrize("status,headers", [
    (302, {"location": "https://example.invalid"}),
    (200, {"content-length": "4000001"}),
])
def test_existing_no_redirect_and_byte_budget_transport_is_preserved(context, status, headers):
    context[2]["status"] = status
    context[2]["headers"] = headers
    response = fetch(context)
    assert response.status_code == 502
    assert len(context[2]["requests"]) == 1
    assert context[0].recent(vertical="lyte", session_scope=session_scope(TOKEN)) == []


def test_inventory_connector_is_optional_and_does_not_redefine_lyte_readiness():
    assert CONNECTORS["hf-datasets"].required is False
    assert CONNECTORS["hf-datasets"].auth_env is None
    assert [spec.id for spec in CONNECTORS.values() if spec.vertical == "lyte" and spec.required] == ["github-actions"]
