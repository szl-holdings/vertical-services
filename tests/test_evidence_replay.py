"""Evidence replay: #47 stdlib mixin contract plus #37's source-bound correction replay
using real SQLite and mounted HTTP routes. Not estate qualification."""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))

from test_hatun_evidence_admission import context, seed, post, PAYLOAD, SCOPE, NOW, TOKEN, fr


class ReplayMixinContract(unittest.TestCase):
    def test_mixin_symbols(self):
        from szl_verticals.replay_store import REPLAY_SCHEMA, ReplayStoreMixin
        self.assertTrue(hasattr(ReplayStoreMixin, "withdraw_payloads"))
        self.assertIn("evidence_withdrawals", REPLAY_SCHEMA)

    def test_store_inherits(self):
        from szl_verticals.replay_store import ReplayStoreMixin
        from szl_verticals.store import ObservationStore
        self.assertTrue(issubclass(ObservationStore, ReplayStoreMixin))

    def test_withdraw_latches_cache(self):
        from szl_verticals.store import ObservationStore
        digest = "ab" * 32
        receipt = {
            "receipt_id": "c" * 64,
            "vertical": "counsel",
            "connector_id": "unit",
            "session_scope": "s1",
            "query_hash": "d" * 64,
            "observed_at": 1.0,
            "expires_at": 9.0e18,
            "source_url": "https://example.test/src",
            "http_status": 200,
            "payload_sha256": digest,
            "truth_label": "REPORTED",
            "state": "OBSERVED",
        }
        fd, path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        old = os.environ.get("SZL_STATE_PATH")
        os.environ["SZL_STATE_PATH"] = path
        try:
            store = ObservationStore()
            store.put(receipt, {"k": "v"})
            self.assertIsNotNone(store.cached(
                vertical="counsel", connector_id="unit",
                session_scope="s1", query_hash="d" * 64,
            ))
            store.withdraw_payloads(
                vertical="counsel", session_scope="s1",
                payload_digests=[digest], now=2.0,
            )
            self.assertIsNone(store.cached(
                vertical="counsel", connector_id="unit",
                session_scope="s1", query_hash="d" * 64,
            ))
            rows = store.resolve_payloads(
                vertical="counsel", session_scope="s1",
                payload_digests=[digest],
            )
            self.assertEqual(len(rows), 1)
            self.assertTrue(bool(rows[0]["withdrawn"]))
        finally:
            if old is None:
                os.environ.pop("SZL_STATE_PATH", None)
            else:
                os.environ["SZL_STATE_PATH"] = old
            try:
                os.remove(path)
            except OSError:
                pass


def status(client, assessment, **kwargs):
    return client.get(f"/api/verticals/puriq/evidence/assessments/{assessment}", **kwargs)


def withdraw(client, digests=None, **kwargs):
    return client.post("/api/verticals/puriq/evidence/withdraw",
                       json={"evidence_sha256": [PAYLOAD] if digests is None else digests}, **kwargs)


def assessment(context):
    return post(context)["receipt"]["basis_sha256"]


def test_withdrawal_explains_affected_review_and_preserves_unrelated(context):
    db, client = context
    seed(db)
    seed(db, digest="a" * 64)
    old = assessment(context)
    unaffected = post(context, evidence_sha256=["a" * 64])["receipt"]["basis_sha256"]
    assert status(client, old).json()["state"] == "CURRENT"
    assert withdraw(client).status_code == 200
    body = status(client, old).json()
    assert body["state"] == "REVALIDATION_REQUIRED"
    assert body["changed_dependencies"] == [{"payload_sha256": PAYLOAD, "reason": "EVIDENCE_WITHDRAWN"}]
    assert status(client, unaffected).json()["state"] == "CURRENT"
    assert body["original_decision"] == "REVIEW" and body["can_execute"] is False
    assert TOKEN not in json.dumps(body) and SCOPE not in json.dumps(body)
    assert "fixture_text" not in json.dumps(body)
    assert post(context)["decision"] == "ABSTAIN"


def test_withdrawal_persists_after_restart_and_refetch(context, monkeypatch):
    db, client = context
    receipt = seed(db)
    old = assessment(context)
    assert withdraw(client).json() == withdraw(client).json()
    restarted = type(db)()
    monkeypatch.setattr(fr, "STORE", restarted)
    restarted.put(receipt, {"fixture_text": "refetched same bytes"})
    assert status(client, old).json()["state"] == "REVALIDATION_REQUIRED"
    assert post(context)["decision"] == "ABSTAIN"
    assert restarted.cached(vertical="finance", connector_id=receipt["connector_id"],
                            session_scope=SCOPE, query_hash=receipt["query_hash"]) is None


def test_new_corrected_payload_requires_new_normal_review(context):
    seed(context[0])
    old = assessment(context)
    withdraw(context[1])
    seed(context[0], digest="b" * 64, summary={"corrected": True})
    new = post(context, evidence_sha256=["b" * 64])
    assert new["decision"] == "REVIEW"
    assert new["receipt"]["basis_sha256"] != old
    assert status(context[1], old).json()["state"] == "REVALIDATION_REQUIRED"
    assert status(context[1], new["receipt"]["basis_sha256"]).json()["state"] == "CURRENT"


def test_change_then_restore_without_status_read_is_still_invalid(context):
    db, client = context
    receipt = seed(db)
    old = assessment(context)
    db.put(receipt, {"changed": True})
    db.put(receipt, {"fixture_text": "not a legal authority"})
    assert status(client, old).json()["state"] == "REVALIDATION_REQUIRED"


def test_unchanged_reobservation_preserves_current_assessment(context):
    receipt = seed(context[0])
    old = assessment(context)
    context[0].put(receipt, {"fixture_text": "not a legal authority"})
    assert status(context[1], old).json()["state"] == "CURRENT"


def test_withdrawn_latest_cache_does_not_resurrect_older_query_result(context, monkeypatch):
    db = context[0]
    seed(db, digest="a" * 64, observed=NOW - 10)
    receipt = seed(db)
    module = importlib.import_module("szl_verticals.store")
    monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: NOW))
    query = dict(vertical="finance", connector_id=receipt["connector_id"],
                 session_scope=SCOPE, query_hash=receipt["query_hash"])
    assert db.cached(**query)["payload_sha256"] == PAYLOAD
    assert withdraw(context[1]).status_code == 200
    assert db.cached(**query) is None


@pytest.mark.parametrize("change,reason", [
    ("summary", "EVIDENCE_SUMMARY_CHANGED"), ("new-record", "EVIDENCE_RECORD_CHANGED"),
    ("corrupt-url", "EVIDENCE_RECORD_INVALID"), ("duplicate-json", "EVIDENCE_RECORD_INVALID"),
])
def test_changed_evidence_is_detected_and_never_silently_requalified(context, change, reason):
    db, client = context
    receipt = seed(db)
    old = assessment(context)
    if change == "summary":
        db.put(receipt, {"changed": True})
    elif change == "new-record":
        seed(db, observed=NOW)
    else:
        with sqlite3.connect(db.path) as connection:
            if change == "corrupt-url":
                connection.execute("UPDATE connector_observations SET source_url='https://other.test/'")
            else:
                connection.execute('UPDATE connector_observations SET summary_json=?', ('{"x":1,"x":2}',))
    result = status(client, old).json()
    assert result["state"] == "REVALIDATION_REQUIRED"
    assert result["changed_dependencies"][0]["reason"] == reason
    db.put(receipt, {"fixture_text": "not a legal authority"})
    assert status(client, old).json()["state"] == "REVALIDATION_REQUIRED"


def test_expiry_and_clock_rollback_cannot_revive_old_assessment(context, monkeypatch):
    receipt = seed(context[0])
    old = assessment(context)
    monkeypatch.setattr(fr, "time", SimpleNamespace(time=lambda: receipt["expires_at"]))
    assert status(context[1], old).json()["state"] == "REVALIDATION_REQUIRED"
    monkeypatch.setattr(fr, "time", SimpleNamespace(time=lambda: NOW))
    assert status(context[1], old).json()["state"] == "REVALIDATION_REQUIRED"


def test_clock_regression_is_terminal_even_when_evidence_still_fresh(context, monkeypatch):
    seed(context[0], observed=NOW - 10)
    old = assessment(context)
    monkeypatch.setattr(fr, "time", SimpleNamespace(time=lambda: NOW - 1))
    result = status(context[1], old).json()
    assert result["state"] == "REVALIDATION_REQUIRED"
    assert {"payload_sha256": None, "reason": "ASSESSMENT_CLOCK_REGRESSED"} in result["changed_dependencies"]


def test_current_connector_policy_is_revalidated(context, monkeypatch):
    seed(context[0])
    old = assessment(context)
    monkeypatch.setattr(fr, "CONNECTORS", {})
    result = status(context[1], old).json()
    assert result["state"] == "REVALIDATION_REQUIRED"
    assert result["changed_dependencies"] == [
        {"payload_sha256": None, "reason": "EVIDENCE_ADMISSION_CHANGED"}]


def test_foreign_and_missing_are_indistinguishable_and_no_cross_scope_withdrawal(context):
    seed(context[0])
    old = assessment(context)
    foreign = {"X-SZL-Session": "other-session-token-01234567890123456789"}
    assert status(context[1], old, headers=foreign).status_code == 404
    assert status(context[1], old, headers=foreign).json() == status(context[1], "a" * 64, headers=foreign).json()
    assert withdraw(context[1], headers=foreign).status_code == 404
    assert status(context[1], old).json()["state"] == "CURRENT"
    # Canonical vertical is also part of every lookup.
    assert context[1].get(f"/api/verticals/counsel/evidence/assessments/{old}").status_code == 404


def test_mixed_missing_withdrawal_is_atomic(context):
    seed(context[0])
    old = assessment(context)
    assert withdraw(context[1], [PAYLOAD, "a" * 64]).status_code == 404
    assert status(context[1], old).json()["state"] == "CURRENT"


def test_database_failure_is_redacted_and_does_not_relabel_unknown_as_current(context):
    seed(context[0])
    old = assessment(context)
    context[0].error = "PRIVATE_DATABASE_ERROR"
    result = status(context[1], old)
    assert result.status_code == 503
    assert "PRIVATE_DATABASE_ERROR" not in result.text
    context[0].error = None
    assert status(context[1], old).json()["state"] == "CURRENT"


def test_scope_capacity_fails_closed_without_erasing_history(context, monkeypatch):
    seed(context[0])
    old = assessment(context)
    module = importlib.import_module("szl_verticals.replay_store")
    monkeypatch.setattr(module, "MAX_ASSESSMENTS_PER_SCOPE", 1)
    # Existing immutable assessment can still be read and registered idempotently.
    assert assessment(context) == old
    seed(context[0], digest="b" * 64)
    result = context[1].post("/api/verticals/puriq/hatun/evaluate", json={
        "intent": "review corrected fixture", "requested_action": "market.review",
        "axes": {"evidence": .99, "freshness": .99}, "evidence_sha256": ["b" * 64]})
    assert result.status_code == 503
    assert status(context[1], old).json()["state"] == "CURRENT"


@pytest.mark.parametrize("digests", [[], ["not-a-digest"], ["a" * 64] * 65, ["\ud800"]])
def test_invalid_withdrawals_rejected_without_echo(context, digests):
    # JSON text handles invalid Unicode without a client-side encoding exception.
    result = context[1].post("/api/verticals/puriq/evidence/withdraw",
        content=json.dumps({"evidence_sha256": digests}), headers={"Content-Type": "application/json"})
    assert result.status_code == 422 and result.json() == {"detail": "invalid request"}

