"""Receipt-backed Lyte telemetry projection contracts."""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
sys.path.insert(0, str(DEPLOY))

_STATE = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "telemetry-projection-test-key")
os.environ.setdefault("SZL_SOURCE_REVISION", "a" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_STATE.name) / "state.sqlite3"))

from fastapi.testclient import TestClient  # noqa: E402

from szl_verticals.lyte import TELEMETRY_SCHEMA  # noqa: E402
from szl_verticals import lyte as telemetry  # noqa: E402
from szl_verticals.core import session_scope  # noqa: E402
import app as vertical  # noqa: E402


SESSION = "telemetry-projection-session-0123456789"
OTHER_SESSION = "telemetry-projection-other-0123456789"
client = TestClient(vertical.app, headers={"X-SZL-Session": SESSION})


@pytest.fixture(autouse=True)
def telemetry_clock(monkeypatch):
    clock = {"now": datetime(2026, 11, 16, 12, 0, 1, tzinfo=timezone.utc)}

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock["now"].astimezone(tz) if tz else clock["now"].replace(tzinfo=None)

    monkeypatch.setattr(telemetry, "datetime", Clock)
    telemetry.TELEMETRY.clear()
    yield clock
    telemetry.TELEMETRY.clear()


def event_payload(**overrides):
    payload = {
        "trace_id": "trace-live-search-001",
        "span_id": "span-001",
        "source_revision": "github:szl-holdings/lyte@abc123",
        "dataset_id": "SZLHOLDINGS/telemetry-dataset",
        "model_id": "SZLHOLDINGS/lyte-model",
        "provider": "opentelemetry",
        "observed_at": "2026-11-16T12:00:00Z",
        "freshness_seconds": 600,
        "sampling_rate": 0.25,
        "rights": "CC-BY-4.0",
        "license": "CC-BY-4.0",
        "outcome": "success",
        "latency_ms": 42.5,
        "deployment_revision": "deploy-abc123",
        "cohort": "canary",
        "action": "live-search",
        "approval_id": "human-review-7",
        "approval_required": True,
        "source_state": "OBSERVED",
    }
    payload.update(overrides)
    return payload


def test_ingest_is_receipted_and_readable_from_both_projections():
    response = client.post("/lyte/v1/telemetry", json=event_payload())
    assert response.status_code == 200, response.text
    item = response.json()
    duplicate = client.post("/lyte/v1/telemetry", json=event_payload()).json()
    assert duplicate["receipt_id"] == item["receipt_id"]
    health = client.get("/lyte/healthz").json()
    assert health["telemetry_events"] >= 1
    assert health["active_sessions"] >= 1
    assert item["schema"] == TELEMETRY_SCHEMA
    assert item["trace_id"] == "trace-live-search-001"
    assert item["span_id"] == "span-001"
    assert item["source_revision"] == "github:szl-holdings/lyte@abc123"
    assert item["dataset_id"] == "SZLHOLDINGS/telemetry-dataset"
    assert item["model_id"] == "SZLHOLDINGS/lyte-model"
    assert item["provider"] == "opentelemetry"
    assert item["freshness_seconds"] == 600
    assert item["sampling_rate"] == 0.25
    assert item["rights"] == "CC-BY-4.0"
    assert item["license"] == "CC-BY-4.0"
    assert item["outcome"] == "success"
    assert item["latency_ms"] == 42.5
    assert item["deployment_revision"] == "deploy-abc123"
    assert item["cohort"] == "canary"
    assert item["action"] == "live-search"
    assert item["approval_id"] == "human-review-7"
    assert item["truth_label"] == "REPORTED"
    assert item["source_provenance"] == "CALLER_REPORTED_NOT_AUTHENTICATED"
    assert item["counts_as_connector_evidence"] is False
    assert item["receipt"]["receipt_id"] == item["receipt_id"]
    assert item["receipt"]["receipt_algorithm"] == "SHA-256"
    assert item["receipt"]["signature_claimed"] is False
    assert item["receipt_url"] == f"/lyte/v1/telemetry?receipt_id={item['receipt_id']}"

    by_receipt = client.get("/lyte/v1/telemetry", params={"receipt_id": item["receipt_id"]})
    assert by_receipt.status_code == 200
    assert by_receipt.json()["items"] == [item]
    assert client.get("/lyte/v1/telemetry", params={"receipt_id": "f" * 64}).status_code == 404

    operational = client.get("/api/verticals/lyte/telemetry", params={"trace_id": item["trace_id"]})
    assert operational.status_code == 200
    assert operational.json()["items"] == [item]

    alias = client.post("/api/verticals/lyte/telemetry", json=event_payload(trace_id="trace-alias"))
    assert alias.status_code == 200
    assert alias.json()["trace_id"] == "trace-alias"

    brain = client.get("/api/verticals/lyte/second-brain")
    assert brain.status_code == 200
    assert item in brain.json()["telemetry"]["items"]

    anatomy = client.get("/api/verticals/lyte/anatomy")
    assert anatomy.status_code == 200
    contract = anatomy.json()["telemetry"]
    assert contract["enabled"] is True
    assert "trace_id" in contract["fields"]
    assert contract["receipt_backed"] is True
    assert contract["raw_payload_retained"] is False


def test_search_is_bounded_and_session_scoped():
    client.post("/lyte/v1/telemetry", json=event_payload(trace_id="trace-canary", outcome="failure"))
    client.post("/lyte/v1/telemetry", json=event_payload(trace_id="trace-production", outcome="success"))

    result = client.get("/lyte/v1/telemetry/search", params={"q": "canary"})
    assert result.status_code == 200
    assert result.json()["count"] >= 1
    assert all(item["cohort"] == "canary" for item in result.json()["items"])

    operational = client.get("/api/verticals/lyte/telemetry/search", params={"q": "failure"})
    assert operational.status_code == 200
    assert all(item["outcome"] == "failure" for item in operational.json()["items"])

    other = TestClient(vertical.app, headers={"X-SZL-Session": OTHER_SESSION})
    assert other.get("/lyte/v1/telemetry").json()["items"] == []


def test_unavailable_source_is_explicit_and_non_lyte_is_not_claimed():
    response = client.post(
        "/lyte/v1/telemetry",
        json=event_payload(source_state="UNAVAILABLE", source_revision="UNAVAILABLE"),
    )
    assert response.status_code == 200
    assert response.json()["truth_label"] == "UNAVAILABLE"

    blocked = client.post(
        "/lyte/v1/telemetry",
        json=event_payload(source_state="OBSERVED", source_revision="UNAVAILABLE"),
    )
    assert blocked.status_code == 422

    unsupported = client.get("/api/verticals/terra/telemetry")
    assert unsupported.status_code == 404
    unsupported_search = client.get("/api/verticals/terra/telemetry/search")
    assert unsupported_search.status_code == 404


def test_unknown_fields_and_oversized_payload_are_rejected():
    unknown = event_payload(untrusted_payload="do not retain")
    assert client.post("/lyte/v1/telemetry", json=unknown).status_code == 422

    too_long = event_payload(trace_id="x" * 129)
    assert client.post("/lyte/v1/telemetry", json=too_long).status_code == 422

    blank = event_payload(source_revision="   ")
    assert client.post("/lyte/v1/telemetry", json=blank).status_code == 422


@pytest.mark.parametrize("route", ["/lyte/v1/telemetry", "/api/verticals/lyte/telemetry"])
def test_unencodable_metadata_is_rejected_without_echo_or_receipt(route):
    encoded = json.dumps(event_payload(provider=chr(0xD800)))
    response = client.post(route, content=encoded, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json() == {"detail": "invalid request"}
    assert client.get("/lyte/v1/telemetry").json()["items"] == []


def test_public_search_returns_canonical_catalog_objects_without_session():
    public = TestClient(vertical.app)
    response = public.get("/api/verticals/search", params={"q": "telemetry", "limit": 20})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema"] == "szl.operational-search/v1"
    assert body["telemetry_requires_session"] is True
    assert any(item["canonical_id"] == "vertical:lyte" for item in body["items"])
    assert all(item["href"].startswith("/api/") for item in body["items"])


def test_freshness_expires_at_read_time_without_changing_the_receipt(telemetry_clock):
    posted = client.post("/lyte/v1/telemetry", json=event_payload(freshness_seconds=2)).json()
    assert posted["freshness_state"] == "FRESH"
    assert posted["effective_state"] == "OBSERVED"

    telemetry_clock["now"] += timedelta(seconds=60)
    response = client.get("/lyte/v1/telemetry", params={"receipt_id": posted["receipt_id"]})
    assert response.status_code == 200
    current = response.json()["items"][0]
    assert current["freshness_state"] == "STALE"
    assert current["freshness"]["state"] == "STALE"
    assert current["effective_state"] == "STALE"
    assert current["age_seconds"] == 61
    assert current["source_state"] == "OBSERVED"
    assert current["receipt"] == posted["receipt"]
    assert current["truth_label"] == "REPORTED"


@pytest.mark.parametrize("field,value", [("latency_ms", 999), ("source_state", "UNAVAILABLE"), ("trace_id", "tampered")])
def test_projection_rejects_a_displayed_observation_that_disagrees_with_its_receipt(field, value):
    posted = client.post("/lyte/v1/telemetry", json=event_payload()).json()
    telemetry.TELEMETRY[session_scope(SESSION)][-1][field] = value
    assert client.get("/lyte/v1/telemetry", params={"receipt_id": posted["receipt_id"]}).status_code == 404
    assert client.get("/lyte/v1/telemetry").json()["items"] == []


def test_projection_rejects_altered_receipt_basis_and_wrong_session():
    posted = client.post("/lyte/v1/telemetry", json=event_payload()).json()
    stored = telemetry.TELEMETRY[session_scope(SESSION)][-1]
    telemetry.TELEMETRY[session_scope(OTHER_SESSION)].append(stored)
    other = TestClient(vertical.app, headers={"X-SZL-Session": OTHER_SESSION})
    assert other.get("/lyte/v1/telemetry").json()["items"] == []
    stored["_receipt_basis"]["latency_ms"] = 999
    assert client.get("/lyte/v1/telemetry", params={"receipt_id": posted["receipt_id"]}).status_code == 404


@pytest.mark.parametrize("timestamp", ["9999-12-31T23:59:59Z", "0001-01-01T00:00:00+01:00", "2026-11-16T12:00:07Z"])
def test_future_or_overflowing_timestamp_returns_validation_error(timestamp):
    response = client.post("/lyte/v1/telemetry", json=event_payload(observed_at=timestamp))
    assert response.status_code == 422
    assert client.get("/lyte/v1/telemetry").json()["items"] == []


def test_search_filters_the_full_retained_history_before_limiting_results():
    scope = session_scope(SESSION)
    for index in range(201):
        telemetry.lyte_telemetry_ingest(
            telemetry.TelemetryEvent(**event_payload(trace_id="oldest-search-hit" if index == 0 else f"trace-{index}")),
            scope,
        )
    for route in ("/lyte/v1/telemetry/search", "/api/verticals/lyte/telemetry/search"):
        response = client.get(route, params={"q": "oldest-search-hit", "limit": 1})
        assert response.status_code == 200
        result = response.json()
        assert result["count"] == 1
        assert result["items"][0]["trace_id"] == "oldest-search-hit"
        assert result["limit"] == 1
