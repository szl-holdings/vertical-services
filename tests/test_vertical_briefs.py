"""Research intake remains scoped, bounded and outside connector evidence."""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import logging
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))

from szl_verticals import operational
from szl_verticals.connector_specs import CONNECTORS
from szl_verticals.evidence import resolve_evidence
from szl_verticals.store import ObservationStore

TOKEN = "weekly-brief-test-session-0000000001"
OTHER = "weekly-brief-test-session-0000000002"
SCOPE = hashlib.sha256(TOKEN.encode()).hexdigest()

# Harmless synthetic diagnostic. It stands in for raw exception text from the
# storage layer and must never cross the public response boundary.
MARKER = "SYNTHETIC_DIAGNOSTIC_MARKER"
SYNTHETIC_PATH = "/synthetic/private/state.sqlite3"
SYNTHETIC_ERROR = f"OperationalError: {MARKER} at {SYNTHETIC_PATH}"
GENERIC_BRIEF_503 = {"detail": "brief store unavailable"}
PUBLIC_STORE_ERROR = "STORE_UNAVAILABLE"
STATUS_FIELDS = {"writable", "durability", "configured_path", "persistent_claim_explicit", "error"}


def assert_no_diagnostic(text: str) -> None:
    assert MARKER not in text
    assert SYNTHETIC_PATH not in text
    assert "OperationalError" not in text
    assert "Traceback" not in text


def payload():
    return {
        "week_start": "2026-10-12", "title": "Weekly property research",
        "sources": [{"id": "dof", "title": "Official catalog",
                     "url": "https://data.cityofnewyork.us/City-Government/catalog",
                     "published_on": "2026-10-08",
                     "event_on": "2026-10-08",
                     "verified_at": "2026-10-12T10:00:00Z",
                     "verification_method": "Read official dataset metadata"}],
        "developments": [{"source_fact": "A catalog publishes recorded document fields.",
                          "source_ids": ["dof"], "product_inference": "A bounded adapter could join parcel documents.",
                          "confidence": "WELL_SUPPORTED"}],
        "opportunities": [{"title": "Add official records adapter", "proposal": "Bind the catalog.",
                           "source_ids": ["dof"], "acceptance_criteria": ["Retain source dates"],
                           "priority": "HIGH", "feasibility": "HIGH", "status": "PROPOSED"}],
    }


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("SZL_STATE_PATH", str(tmp_path / "state.sqlite3"))
    store = ObservationStore(clock=lambda: 1791800000.0)
    monkeypatch.setattr(operational, "STORE", store)
    app = FastAPI()
    app.include_router(operational.operational)
    with TestClient(app, headers={"X-SZL-Session": TOKEN}) as client:
        yield client, store


def test_api_idempotency_persistence_alias_and_session_isolation(runtime):
    client, store = runtime
    first = client.post("/api/verticals/real-estate/briefs", json=payload())
    assert first.status_code == 200
    result = first.json()
    assert result["vertical"] == "terra" and result["inserted"] is True
    assert result["review_status"] == "REVIEW_REQUIRED"
    assert result["truth_label"] == "CALLER_REPORTED"
    again = client.post("/api/verticals/terra/briefs", json=payload()).json()
    assert again["content_sha256"] == result["content_sha256"]
    assert again["created_at"] == result["created_at"]
    assert again["inserted"] is False
    assert len(ObservationStore().recent_briefs("terra", SCOPE)) == 1
    assert client.get("/api/verticals/lyte/briefs").json()["items"] == []
    assert client.get("/api/verticals/terra/briefs", headers={"X-SZL-Session": OTHER}).json()["items"] == []
    assert TOKEN not in first.text and SCOPE not in first.text
    assert client.get("/api/verticals/not-a-vertical/briefs").status_code == 404


def test_second_brain_lists_briefs_without_connector_evidence(runtime):
    client, store = runtime
    saved = client.post("/api/verticals/terra/briefs", json=payload()).json()
    brain = client.get("/api/verticals/terra/second-brain").json()
    assert brain["weekly_briefs"]["items"][0]["content_sha256"] == saved["content_sha256"]
    assert brain["weekly_briefs"]["counts_as_connector_evidence"] is False
    assert brain["memory"]["observations"] == []
    assert store.counts(vertical="terra", session_scope=SCOPE)["observations"] == 0
    evidence = resolve_evidence(store, vertical="terra", session_scope=SCOPE,
                                digests=[saved["content_sha256"]], connectors=CONNECTORS)
    assert "EVIDENCE_REFERENCE_UNRESOLVED" in evidence.blockers
    assert evidence.state != "COMPLETE"


@pytest.mark.parametrize("mutation", [
    lambda b: b.update(truth_label="MEASURED"),
    lambda b: b.update(review_status="VERIFIED"),
    lambda b: b.update(week_start="2026-10-13"),
    lambda b: b["sources"][0].update(verified_at="2026-10-01T00:00:00Z"),
    lambda b: b["sources"][0].update(verified_at="2999-01-01T00:00:00Z"),
    lambda b: b["sources"][0].update(verified_at="2026-10-12T10:00:00"),
    lambda b: b["sources"][0].update(data_period_start="2026-10-08"),
    lambda b: b["sources"][0].update(data_period_start="2026-10-08", data_period_end="2026-10-01"),
    lambda b: b.update(week_start="2999-01-07"),
    lambda b: b["sources"][0].update(url="https://user:secret@example.com/file"),
    lambda b: b["sources"][0].update(url="https://example.com/file?api_key=secret"),
    lambda b: b["sources"][0].update(url="http://example.com/file"),
    lambda b: b["developments"][0].update(source_ids=["missing"]),
    lambda b: b["opportunities"][0].update(status="DEPLOYED_VERIFIED"),
    lambda b: b.update(sources=b["sources"] * 13),
    lambda b: b.update(title="x" * 241),
])
def test_invalid_or_promoted_claims_rejected(runtime, mutation):
    client, _ = runtime
    value = payload()
    mutation(value)
    assert client.post("/api/verticals/terra/briefs", json=value).status_code == 422


def test_payload_bytes_and_scope_capacity_are_bounded(runtime, monkeypatch):
    client, store = runtime
    value = payload()
    value["developments"] = [copy.deepcopy(value["developments"][0]) for _ in range(16)]
    for development in value["developments"]:
        development.update(source_fact="x" * 2400, product_inference="y" * 2400)
    assert client.post("/api/verticals/terra/briefs", json=value).status_code == 413
    monkeypatch.setattr("szl_verticals.briefs.MAX_BRIEFS_PER_SCOPE", 1)
    assert client.post("/api/verticals/terra/briefs", json=payload()).status_code == 200
    changed = payload()
    changed["title"] = "Another brief"
    assert client.post("/api/verticals/terra/briefs", json=changed).status_code == 413
    assert client.post("/api/verticals/terra/briefs", json=payload()).json()["inserted"] is False
    assert client.get("/api/verticals/terra/briefs?limit=26").status_code == 422


def test_no_network_or_evidence_promotion_from_source_claim(runtime, monkeypatch):
    client, _ = runtime
    def forbidden(*args, **kwargs):
        raise AssertionError("brief intake must not fetch a source URL")
    monkeypatch.setattr("szl_verticals.official_connectors._bounded_get", forbidden)
    saved = client.post("/api/verticals/terra/briefs", json=payload()).json()
    assert saved["verification_claims"] == "CALLER_REPORTED_NOT_INDEPENDENTLY_VERIFIED"
    assert saved["counts_as_connector_evidence"] is False
    assert saved["effectors_enabled"] is False


def test_store_failure_is_explicit(runtime):
    client, store = runtime
    store.error = SYNTHETIC_ERROR
    responses = (
        client.post("/api/verticals/terra/briefs", json=payload()),
        client.get("/api/verticals/terra/briefs"),
        client.get("/api/verticals/terra/second-brain"),
    )
    for response in responses:
        assert response.status_code == 503
        assert response.json() == GENERIC_BRIEF_503
        assert_no_diagnostic(response.text)


def test_public_status_never_returns_internal_store_diagnostic(runtime):
    _, store = runtime
    store.error = SYNTHETIC_ERROR
    status = store.status()
    assert set(status) == STATUS_FIELDS
    assert status["writable"] is False
    assert status["durability"] == "UNAVAILABLE"
    assert status["error"] == PUBLIC_STORE_ERROR
    assert_no_diagnostic(json.dumps(status))
    with pytest.raises(RuntimeError) as error:
        store.put({}, {})
    assert_no_diagnostic(str(error.value))


def test_initialization_failure_keeps_diagnostic_server_side(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("SZL_STATE_PATH", str(tmp_path / "state.sqlite3"))

    class FailingStore(ObservationStore):
        def _connect(self):
            raise sqlite3.OperationalError(f"{MARKER} at {SYNTHETIC_PATH}")

    with caplog.at_level(logging.ERROR, logger="szl_verticals.store"):
        store = FailingStore()
    # Existing truthiness guards still see the failure.
    assert store.error
    # Full detail stays internal: a private attribute and the server log.
    assert MARKER in store._error_detail and "OperationalError" in store._error_detail
    assert MARKER in caplog.text
    status = store.status()
    assert set(status) == STATUS_FIELDS
    assert status["writable"] is False and status["error"] == PUBLIC_STORE_ERROR
    assert_no_diagnostic(json.dumps(status))
    assert_no_diagnostic(str(store.error))


def test_readiness_redacts_store_diagnostic_and_stays_degraded(runtime, monkeypatch):
    client, store = runtime
    store.error = SYNTHETIC_ERROR

    nested = client.get("/api/verticals/terra/readyz")
    assert nested.status_code == 200
    body = nested.json()
    assert body["ready"] is False and body["status"] == "DEGRADED"
    assert body["requirements"]["observation_store_writable"] is False
    assert set(body["store"]) == STATUS_FIELDS
    assert body["store"]["writable"] is False
    assert body["store"]["error"] == PUBLIC_STORE_ERROR
    assert_no_diagnostic(nested.text)

    app_module = importlib.import_module("app")
    assert Path(app_module.__file__).resolve() == DEPLOY / "app.py"
    monkeypatch.setattr(app_module, "STORE", store)
    service = TestClient(app_module.app, headers={"X-SZL-Session": TOKEN})
    top = service.get("/readyz")
    assert top.status_code == 503
    top_body = top.json()
    assert top_body["ready"] is False
    assert top_body["store"]["writable"] is False
    assert top_body["store"]["error"] == PUBLIC_STORE_ERROR
    for item in top_body["verticals"].values():
        assert item["status"] == "DEGRADED"
        assert item["requirements"]["observation_store_writable"] is False
    assert_no_diagnostic(top.text)
    for path in ("/healthz", "/api/catalog"):
        response = service.get(path)
        assert response.json()["state"]["connector_observations"]["error"] == PUBLIC_STORE_ERROR
        assert_no_diagnostic(response.text)
    frontier = service.get("/api/verticals/terra/frontier")
    assert frontier.json()["readiness"]["store"]["error"] == PUBLIC_STORE_ERROR
    assert_no_diagnostic(frontier.text)


@pytest.mark.parametrize("failure", [sqlite3.OperationalError, sqlite3.DatabaseError, OSError])
def test_query_time_storage_exception_is_not_echoed(runtime, monkeypatch, failure):
    client, store = runtime

    def broken_connect():
        raise failure(f"{MARKER} at {SYNTHETIC_PATH}")

    monkeypatch.setattr(store, "_connect", broken_connect)
    responses = (
        client.post("/api/verticals/terra/briefs", json=payload()),
        client.get("/api/verticals/terra/briefs"),
    )
    for response in responses:
        assert response.status_code == 503
        assert response.json() == GENERIC_BRIEF_503
        assert failure.__name__ not in response.text
        assert_no_diagnostic(response.text)


def test_healthy_status_and_brief_behaviour_are_unchanged(runtime):
    client, store = runtime
    status = store.status()
    assert set(status) == STATUS_FIELDS
    assert status["writable"] is True
    assert status["error"] is None
    assert status["durability"] != "UNAVAILABLE"
    readiness = client.get("/api/verticals/terra/readyz").json()
    assert readiness["store"] == status
    assert readiness["requirements"]["observation_store_writable"] is True
    # A recovered store serves briefs again, still isolated per session.
    store.error = SYNTHETIC_ERROR
    assert client.get("/api/verticals/terra/briefs").status_code == 503
    store.error = None
    saved = client.post("/api/verticals/terra/briefs", json=payload())
    assert saved.status_code == 200 and saved.json()["inserted"] is True
    listed = client.get("/api/verticals/terra/briefs").json()
    assert listed["store"] == status
    assert [item["content_sha256"] for item in listed["items"]] == [saved.json()["content_sha256"]]
    assert client.get("/api/verticals/terra/briefs", headers={"X-SZL-Session": OTHER}).json()["items"] == []


def test_no_material_change_is_storable_without_invented_findings(runtime):
    client, _ = runtime
    value = {
        "week_start": "2026-10-12", "title": "Weekly review: no material change",
        "coverage_state": "NO_MATERIAL_CHANGE",
        "coverage_note": "Reviewed current public sources; no material development met the inclusion threshold.",
    }
    result = client.post("/api/verticals/lyte/briefs", json=value)
    assert result.status_code == 200
    stored = result.json()["brief"]
    assert stored["coverage_state"] == "NO_MATERIAL_CHANGE"
    assert stored["sources"] == stored["developments"] == stored["opportunities"] == []
    value["sources"] = payload()["sources"]
    with_sources = client.post("/api/verticals/lyte/briefs", json=value)
    assert with_sources.status_code == 200
    assert len(with_sources.json()["brief"]["sources"]) == 1


@pytest.mark.parametrize("change", [
    {"coverage_note": None},
    {"coverage_note": "   "},
    {"developments": payload()["developments"]},
    {"opportunities": payload()["opportunities"]},
])
def test_no_material_change_rejects_missing_note_and_contradictory_findings(runtime, change):
    client, _ = runtime
    value = {
        "week_start": "2026-10-12", "title": "Weekly review",
        "coverage_state": "NO_MATERIAL_CHANGE", "coverage_note": "Nothing material found.",
        "sources": payload()["sources"],
    }
    value.update(change)
    assert client.post("/api/verticals/lyte/briefs", json=value).status_code == 422


@pytest.mark.parametrize("field", ["sources", "developments", "opportunities"])
def test_developments_mode_requires_real_source_findings_and_opportunities(runtime, field):
    client, _ = runtime
    value = payload()
    value[field] = []
    assert client.post("/api/verticals/terra/briefs", json=value).status_code == 422
