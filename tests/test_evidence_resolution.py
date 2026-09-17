"""Network-free evidence admission regressions using a real temporary SQLite ledger."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


E = load_module("_szl_evidence_contract", ROOT / "deploy/szl_verticals/evidence.py")
# Store construction is delayed into each test's isolated temporary directory.
_STORE_MODULE = None
CLOCK = 10_000.0
SCOPE = "a" * 64
OTHER_SCOPE = "b" * 64
DIGESTS = [hashlib.sha256(f"payload-{n}".encode()).hexdigest() for n in range(3)]
SPEC = SimpleNamespace(vertical="finance", freshness_seconds=60)
CONNECTORS = {"fixture-official": SPEC}


@pytest.fixture
def ledger(monkeypatch, tmp_path):
    global _STORE_MODULE
    monkeypatch.setenv("SZL_STATE_PATH", str(tmp_path / "observations.sqlite3"))
    if _STORE_MODULE is None:
        _STORE_MODULE = load_module("_szl_store_contract", ROOT / "deploy/szl_verticals/store.py")
    store = _STORE_MODULE.ObservationStore()
    assert store.error is None
    return store


def row(digest=DIGESTS[0], **overrides):
    basis = {
        "schema": "szl.connector-observation/v2", "vertical": "finance",
        "connector_id": "fixture-official", "session_scope": SCOPE,
        "query_hash": "c" * 64, "source_url": "https://example.test/official?private=not-exported",
        "http_status": 200, "payload_sha256": digest,
        "observed_at": CLOCK - 10.0, "expires_at": CLOCK + 50.0,
        "state": "OBSERVED", "truth_label": "REPORTED",
    }
    basis.update(overrides)
    return {**basis, "receipt_id": E.sha256(E.canonical_json(basis))}


def put(ledger, digest=DIGESTS[0], summary=None, **overrides):
    receipt = row(digest, **overrides)
    ledger.put(receipt, {"finding": "source observation"} if summary is None else summary)
    return receipt


def resolve(ledger, digests=None, **kwargs):
    return E.resolve_evidence(ledger, vertical="finance", session_scope=SCOPE,
                              digests=DIGESTS[:2] if digests is None else digests,
                              connectors=CONNECTORS, now=CLOCK, **kwargs)


def test_unknown_hashes_cannot_satisfy_admission(ledger):
    snapshot = resolve(ledger)
    assert snapshot.state == "PARTIAL"
    assert snapshot.metadata()["resolved_count"] == 0
    assert snapshot.fresh_at(CLOCK) is False
    assert snapshot.metadata()["unresolved_digests"] == sorted(DIGESTS[:2])


def test_two_distinct_scoped_fresh_observations_resolve(ledger):
    for digest in DIGESTS[:2]:
        put(ledger, digest)
    snapshot = resolve(ledger)
    assert snapshot.state == "COMPLETE"
    assert snapshot.metadata()["resolved_count"] == 2
    assert snapshot.fresh_at(CLOCK)
    assert snapshot.matches_scope("finance", SCOPE, DIGESTS[:2])
    assert not snapshot.matches_scope("counsel", SCOPE, DIGESTS[:2])
    assert not snapshot.matches_scope("finance", OTHER_SCOPE, DIGESTS[:2])
    assert not snapshot.matches_scope("finance", SCOPE, DIGESTS[:1])
    assert snapshot.metadata()["payload_bytes_reverified"] is False
    assert snapshot.metadata()["source_signature_verified"] is False
    assert snapshot.metadata()["independent_authorities"] == "NOT_ESTABLISHED"
    assert "source observation" not in json.dumps(snapshot.metadata())
    assert "private=not-exported" not in snapshot.records_json
    assert SCOPE not in json.dumps(snapshot.metadata())


def test_repeated_payload_and_reordered_request_are_deterministic(ledger):
    put(ledger)
    put(ledger, observed_at=CLOCK-5.0, expires_at=CLOCK+55.0)
    single = resolve(ledger, [DIGESTS[0]])
    repeated = resolve(ledger, [DIGESTS[0], DIGESTS[0]])
    assert single.metadata()["resolved_count"] == 1
    assert repeated.snapshot_sha256 == single.snapshot_sha256
    put(ledger, DIGESTS[1])
    assert resolve(ledger, DIGESTS[:2]).snapshot_sha256 == resolve(ledger, DIGESTS[1::-1]).snapshot_sha256


@pytest.mark.parametrize("overrides", [
    {"session_scope": OTHER_SCOPE}, {"vertical": "counsel"},
    {"observed_at": CLOCK-80.0, "expires_at": CLOCK-20.0},
    {"expires_at": CLOCK},
    {"observed_at": CLOCK+1.0, "expires_at": CLOCK+61.0},
    {"expires_at": CLOCK+500.0}, {"state": "FAILED"},
    {"truth_label": "MODELED"}, {"http_status": 503},
    {"connector_id": "unconfigured"}, {"source_url": "http://example.test"},
    {"source_url": "https://name:password@example.test"},
    {"source_url": "https://example.test/#fragment"},
])
def test_unqualified_rows_are_indistinguishable_from_missing(ledger, overrides):
    put(ledger, **overrides)
    result = resolve(ledger, [DIGESTS[0]])
    assert result.state == "PARTIAL"
    assert result.metadata()["resolved_count"] == 0
    assert result.blockers == ("EVIDENCE_REFERENCE_UNRESOLVED",)
    assert result.records_json == "[]"


def test_latest_invalid_does_not_fall_back_to_older_good_record(ledger):
    put(ledger)
    put(ledger, observed_at=CLOCK+1.0, expires_at=CLOCK+61.0)
    assert resolve(ledger, [DIGESTS[0]]).metadata()["resolved_count"] == 0


def test_tampered_receipt_identity_is_rejected(ledger):
    receipt = put(ledger)
    with sqlite3.connect(ledger.path) as connection:
        connection.execute("UPDATE connector_observations SET source_url=? WHERE receipt_id=?",
                           ("https://example.test/altered", receipt["receipt_id"]))
    assert resolve(ledger, [DIGESTS[0]]).state == "PARTIAL"


@pytest.mark.parametrize("serialized", ['{"a":1,"a":2}', '{"n":NaN}', '[1,2]', 'not json', '{"n":1e999}'])
def test_malformed_summary_fails_closed(ledger, serialized):
    put(ledger)
    with sqlite3.connect(ledger.path) as connection:
        connection.execute("UPDATE connector_observations SET summary_json=?", (serialized,))
    assert resolve(ledger, [DIGESTS[0]]).state == "PARTIAL"


def test_snapshot_binds_summary_bytes_and_cannot_alias_mutable_rows(ledger):
    receipt = put(ledger, summary={"finding": "first"})
    first = resolve(ledger, [DIGESTS[0]])
    ledger.put(receipt, {"finding": "second"})
    second = resolve(ledger, [DIGESTS[0]])
    assert first.snapshot_sha256 != second.snapshot_sha256
    assert '"first"' in first.records_json
    assert '"second"' in second.records_json
    assert not first.fresh_at(CLOCK+50.0)
    assert not first.fresh_at(CLOCK-20.0)
    with pytest.raises(FrozenInstanceError):
        first.state = "FORCED_PASS"


def test_store_failure_is_not_observed_empty(ledger):
    assert resolve(ledger, []).state == "EMPTY"
    ledger.error = "sensitive local path /credentials/hidden"
    result = resolve(ledger, [])
    assert result.state == "UNAVAILABLE"
    assert result.metadata()["resolved_count"] is None
    assert "/credentials" not in json.dumps(result.metadata())


def test_broken_database_is_sanitized_and_never_empty_success(ledger):
    with sqlite3.connect(ledger.path) as connection:
        connection.execute("DROP TABLE connector_observations")
    result = resolve(ledger, [])
    assert result.state == "UNAVAILABLE"
    assert result.metadata()["resolved_count"] is None


def test_total_and_single_summary_byte_limits(ledger):
    put(ledger, summary={"unicode": "界" * 1000})
    result = resolve(ledger, [DIGESTS[0]], budget_bytes=1000)
    assert result.state == "PARTIAL"
    assert len(result.records_json.encode()) <= 1000
    put(ledger, summary={"text": "x" * 550})
    result = resolve(ledger, [DIGESTS[0]], budget_bytes=1000)
    assert "EVIDENCE_CONTEXT_BUDGET_EXCEEDED" in result.blockers
    assert not result.fresh_at(CLOCK)


@pytest.mark.parametrize("digests", [["fake"], ["A"*64], ["a"*64+"\n"], ["a"*64]*65, "a"*64])
def test_invalid_lookup_inputs_rejected(ledger, digests):
    with pytest.raises(ValueError):
        resolve(ledger, digests)


@pytest.mark.parametrize("clock", [float("nan"), float("inf"), -1.0, True, 10**10000],
                         ids=["nan", "infinity", "negative", "boolean", "oversized-integer"])
def test_invalid_assessment_time_rejected(ledger, clock):
    with pytest.raises(ValueError):
        E.resolve_evidence(ledger, vertical="finance", session_scope=SCOPE,
                           digests=[], connectors=CONNECTORS, now=clock)
