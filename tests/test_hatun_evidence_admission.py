"""Hatun route regressions using the real scoped SQLite resolver; no live feeds."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))
os.environ.setdefault("SENTRA_SIGNING_KEY", "hatun-fixture-not-production")
os.environ.setdefault("SZL_SOURCE_REVISION", "4" * 40)

from app import app  # noqa: E402
from szl_verticals.evidence import canonical_json, sha256  # noqa: E402
from szl_verticals.store import ObservationStore  # noqa: E402

fr = importlib.import_module("szl_verticals.frontier")
TOKEN = "hatun-evidence-fixture-01234567890123456789"
SCOPE = hashlib.sha256(TOKEN.encode()).hexdigest()
NOW = 10_000.0
PAYLOAD = "d" * 64
URL = "/api/verticals/puriq/hatun/evaluate"


def request_body(**changes):
    return {"intent": "review public fixture evidence", "requested_action": "market.review",
            "axes": {"evidence": 0.96, "freshness": 0.95},
            "evidence_sha256": [PAYLOAD], **changes}


@pytest.fixture
def context(monkeypatch, tmp_path):
    monkeypatch.setenv("SZL_STATE_PATH", str(tmp_path / "ledger.sqlite3"))
    db = ObservationStore()
    if db.error:
        raise RuntimeError("test SQLite ledger initialization failed")
    monkeypatch.setattr(fr, "STORE", db)
    monkeypatch.setattr(fr, "time", SimpleNamespace(time=lambda: NOW))
    # Ancillary readiness is independently tested by the existing native suite.
    # Never stub the actual resolver, ledger, request validators, or route.
    monkeypatch.setattr(fr, "vertical_readiness", lambda *a, **kw: {
        "ready": True, "build": {"revision": "4" * 40},
        "requirements": {"formula_registry_bound": True},
    })
    with TestClient(app, headers={"X-SZL-Session": TOKEN}) as client:
        yield db, client


def seed(db, *, digest=PAYLOAD, scope=SCOPE, observed=NOW - 1.0,
         summary=None, **changes):
    spec = fr.CONNECTORS["polymarket-markets"]
    receipt = {
        "schema": "szl.connector-observation/v2", "vertical": "finance",
        "connector_id": spec.id, "session_scope": scope, "query_hash": "e" * 64,
        "source_url": "https://gamma-api.polymarket.com/markets?private=fixture-only",
        "http_status": 200, "payload_sha256": digest,
        "observed_at": observed, "expires_at": observed + spec.freshness_seconds,
        "state": "OBSERVED", "truth_label": "REPORTED", **changes,
    }
    receipt["receipt_id"] = sha256(canonical_json(receipt))
    db.put(receipt, {"fixture_text": "not a legal authority"} if summary is None else summary)
    return receipt


def post(context, **changes):
    result = context[1].post(URL, json=request_body(**changes))
    assert result.status_code == 200, result.text
    return result.json()


def test_fresh_requested_evidence_qualifies_review_not_authority(context):
    seed(context[0])
    body = post(context)
    assert body["decision"] == "REVIEW"
    assert body["vertical"] == "finance"
    assert body["schema"] == "szl.hatun-review-basis/v2"
    assert body["session_observation_count"] == 1
    assert body["evidence_resolution"]["state"] == "COMPLETE"
    assert body["evidence_sha256"] == [PAYLOAD]
    assert body["evidence_ref_sha256"] == []
    assert body["evidence_fresh_at_review"] is True
    assert body["can_authorize"] is False and body["can_execute"] is False
    assert body["effectors_enabled"] is False and body["human_approval_required"] is True
    assert body["evidence_resolution"]["semantic_validity"] == "NOT_VERIFIED"
    assert body["evidence_resolution"]["independent_authorities"] == "NOT_ESTABLISHED"
    assert body["receipt"]["signature_claimed"] is False
    assert "fixture_text" not in json.dumps(body)
    assert "private=fixture-only" not in json.dumps(body)
    assert TOKEN not in json.dumps(body) and SCOPE not in json.dumps(body)
    basis = {k: v for k, v in body.items()
             if k not in {"lambda_advisory", "receipt", "effectors_enabled", "truth_label"}}
    assert body["receipt"]["basis_sha256"] == sha256(canonical_json(basis))
    basis["evidence_resolution"]["resolved_count"] = 2
    assert body["receipt"]["basis_sha256"] != sha256(canonical_json(basis))


def test_fabricated_hash_does_not_borrow_other_observations(context):
    seed(context[0], digest="c" * 64)
    body = post(context)
    assert body["decision"] == "ABSTAIN"
    assert body["session_observation_count"] == 0
    assert "EVIDENCE_REFERENCE_UNRESOLVED" in body["blockers"]


def test_partial_selection_does_not_review_valid_subset(context):
    seed(context[0])
    body = post(context, evidence_sha256=[PAYLOAD, "a" * 64])
    assert body["decision"] == "ABSTAIN"
    assert body["evidence_resolution"]["state"] == "PARTIAL"
    assert body["session_observation_count"] == 1


@pytest.mark.parametrize("change", [{"scope": "other-session"}, {"vertical": "counsel"}])
def test_wrong_scope_is_indistinguishable_from_missing(context, change):
    missing = post(context)
    seed(context[0], **change)
    assert post(context) == missing


@pytest.mark.parametrize("changes", [
    {"observed": 1.0, "expires_at": 2.0},
    {"observed": NOW + 1.0},
    {"expires_at": NOW},
    {"state": "STALE_LAST_GOOD"},
    {"truth_label": "MODELED"},
    {"http_status": 503},
    {"connector_id": "not-a-connector"},
    {"source_url": "http://gamma-api.polymarket.com/markets"},
])
def test_unqualified_records_never_review(context, changes):
    seed(context[0], **changes)
    body = post(context)
    assert body["decision"] == "ABSTAIN"
    assert body["session_observation_count"] == 0


def test_receipt_corruption_fails_closed(context):
    seed(context[0])
    with sqlite3.connect(context[0].path) as c:
        c.execute("UPDATE connector_observations SET receipt_id=?", ("a" * 64,))
    assert post(context)["decision"] == "ABSTAIN"


def test_new_invalid_record_cannot_fall_back_to_valid_history(context):
    seed(context[0], observed=NOW - 2.0)
    seed(context[0], observed=NOW - 1.0, state="UNAVAILABLE")
    assert post(context)["decision"] == "ABSTAIN"


def test_same_payload_reobserved_counts_once(context):
    seed(context[0], observed=NOW - 2.0)
    latest = seed(context[0], observed=NOW - 1.0)
    body = post(context)
    assert body["decision"] == "REVIEW"
    assert body["session_observation_count"] == 1
    assert body["evidence_resolution"]["records"][0]["receipt_id"] == latest["receipt_id"]


def test_legacy_handles_never_qualify_or_leak(context):
    seed(context[0])
    for digests in ([], [PAYLOAD]):
        body = post(context, evidence_sha256=digests,
                    evidence_refs=["https://private.invalid/matter/fixture"])
        assert body["decision"] == "ABSTAIN"
        assert "LEGACY_REFERENCES_UNRESOLVED" in body["blockers"]
        assert "private.invalid" not in json.dumps(body)
        assert body["legacy_references_qualify"] is False


def test_unavailable_store_is_not_zero(context, monkeypatch):
    monkeypatch.setattr(context[0], "error", "private-db-path-for-test")
    body = post(context)
    assert body["decision"] == "ABSTAIN"
    assert body["session_observation_count"] is None
    assert body["evidence_resolution"]["state"] == "UNAVAILABLE"
    assert "NO_SESSION_OBSERVATIONS" not in body["blockers"]
    assert "private-db-path-for-test" not in json.dumps(body)


def test_store_error_after_initialization_is_unavailable(context, monkeypatch):
    def broken():
        raise sqlite3.OperationalError("private database filename")
    monkeypatch.setattr(context[0], "_connect", broken)
    body = post(context)
    assert body["evidence_resolution"]["state"] == "UNAVAILABLE"
    assert body["session_observation_count"] is None


def test_readiness_failure_does_not_leak_database_errors(context, monkeypatch):
    seed(context[0])
    def broken(*a, **kw):
        raise sqlite3.OperationalError("private database filename")
    monkeypatch.setattr(fr, "vertical_readiness", broken)
    body = post(context)
    assert body["decision"] == "ABSTAIN"
    assert "READINESS_UNAVAILABLE" in body["blockers"]
    assert "private database filename" not in json.dumps(body)


def test_empty_scope_remains_observed_empty(context):
    body = post(context, evidence_sha256=[])
    assert body["decision"] == "ABSTAIN"
    assert body["evidence_resolution"]["state"] == "EMPTY"
    assert body["session_observation_count"] == 0


def test_expiry_between_resolution_and_review_blocks(context, monkeypatch):
    receipt = seed(context[0])
    clock = iter([NOW, receipt["expires_at"]])
    monkeypatch.setattr(fr, "time", SimpleNamespace(time=lambda: next(clock)))
    body = post(context)
    assert body["decision"] == "ABSTAIN"
    assert body["evidence_resolution"]["state"] == "COMPLETE"
    assert body["evidence_fresh_at_review"] is False


def test_regressing_clock_blocks_even_fresh_snapshot(context, monkeypatch):
    seed(context[0], observed=NOW - 2.0)
    clock = iter([NOW, NOW - 1.0])
    monkeypatch.setattr(fr, "time", SimpleNamespace(time=lambda: next(clock)))
    body = post(context)
    assert body["decision"] == "ABSTAIN"
    assert "ASSESSMENT_CLOCK_REGRESSED" in body["blockers"]


def test_evidence_byte_budget_is_not_silently_truncated(context):
    seed(context[0], summary={"text": "x" * 128_001})
    assert post(context)["decision"] == "ABSTAIN"


@pytest.mark.parametrize("changes", [
    {"evidence_sha256": ["A" * 64]},
    {"evidence_sha256": ["a" * 63]},
    {"evidence_sha256": [" " + PAYLOAD]},
    {"evidence_sha256": [PAYLOAD, PAYLOAD]},
    {"evidence_sha256": [format(i, "064x") for i in range(33)]},
    {"axes": {"Evidence": 0.9, " evidence ": 0.95}},
    {"axes": {"evidence": -0.1, "freshness": 0.95}},
])
def test_invalid_inputs_remain_validation_errors(context, changes):
    result = context[1].post(URL, json=request_body(**changes))
    assert result.status_code == 422


@pytest.mark.parametrize("changes", [{"intent": "bad\ud800"}, {"evidence_refs": ["bad\ud800"]}])
def test_invalid_unicode_is_redacted_http_error(context, changes):
    raw = json.dumps(request_body(**changes), ensure_ascii=True)
    result = context[1].post(URL, content=raw, headers={"content-type": "application/json"})
    assert result.status_code == 422
    assert result.json() == {"detail": "invalid request"}


def test_low_caller_score_still_blocks_review(context):
    seed(context[0])
    body = post(context, axes={"evidence": 0.2, "freshness": 0.2})
    assert body["decision"] == "ABSTAIN"
    assert "LAMBDA_BELOW_REVIEW_FLOOR" in body["blockers"]


def test_actual_session_dependency_is_required(context):
    with TestClient(app) as client:
        assert client.post(URL, json=request_body()).status_code == 422
        assert client.post(URL, json=request_body(),
                           headers={"X-SZL-Session": "too-short"}).status_code == 400
