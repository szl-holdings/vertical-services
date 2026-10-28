"""Time admission for Killinchu replay, Terra coverage and Finance authorization.

Every observation timestamp must carry a UTC offset and may be at most
``ALLOWED_FUTURE_SKEW_SECONDS`` ahead of the injected clock. A later timestamp
is rejected (ValueError in-process, HTTP 422 on the route); it is never clamped
to fresh. A future timestamp inside the allowed skew is admitted and reported
explicitly.

New symbols are read from the module inside each test so that, on a base that
lacks them, every test fails on its own instead of failing collection.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from deploy.szl_verticals import frontier_contracts as fc

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def iso(moment):
    return moment.isoformat().replace("+00:00", "Z")


def skew():
    return timedelta(seconds=fc.ALLOWED_FUTURE_SKEW_SECONDS)


def trust_all(entity_id, source_id, events, snapshot):
    """Test-only stand-in for an owner-approved history verifier."""
    return True


def killinchu(event_time, *, now=NOW, **kwargs):
    return fc.replay_identity_lifecycle(
        prior_event_ids=[],
        incoming=[
            fc.IdentityEvent(
                event_id="add-1",
                entity_id="imo-1000001",
                event_time=event_time,
                kind="DESIGNATION_ADDED",
                source_id="ofac-snapshot",
                source_revision="rev-1",
                source_state="OBSERVED",
                payload={"designation_id": "sdn-1"},
            )
        ],
        chain_complete=True,
        now=now,
        **kwargs,
    )


def terra(observed_at, *, now=NOW, freshness_seconds=3600):
    return fc.evaluate_coverage(
        source_id="nyc-pluto",
        jurisdiction="NYC",
        observed_at=observed_at,
        freshness_seconds=freshness_seconds,
        record_count=10,
        expected_scope="NYC PLUTO 2026 Q4",
        now=now,
    )


def finance(observed_at, *, now=NOW, freshness_seconds=3600):
    return fc.authorize_finance_read(
        actor_id="user-1",
        tenant_id="tenant-1",
        scopes=["read:balances"],
        field_scopes=["balance"],
        query="select balance",
        source_revision="finance@1",
        observed_at=observed_at,
        freshness_seconds=freshness_seconds,
        approval_id="approval-1",
        now=now,
    )


CONTRACTS = {"killinchu": killinchu, "terra": terra, "finance": finance}


def test_allowed_future_skew_is_an_explicit_pinned_constant():
    assert fc.ALLOWED_FUTURE_SKEW_SECONDS == 300
    assert isinstance(fc.ALLOWED_FUTURE_SKEW_SECONDS, int)


# -- future boundary --------------------------------------------------------------

@pytest.mark.parametrize("contract", sorted(CONTRACTS))
@pytest.mark.parametrize(
    "label,extra",
    [
        ("exact_boundary", timedelta(0)),
        ("just_inside", timedelta(seconds=-1)),
        ("just_inside_microsecond", timedelta(microseconds=-1)),
    ],
)
def test_future_timestamp_within_allowed_skew_is_admitted(contract, label, extra):
    moment = NOW + skew() + extra
    result = CONTRACTS[contract](moment.isoformat())
    assert result["allowed_future_skew_seconds"] == fc.ALLOWED_FUTURE_SKEW_SECONDS
    assert 0 < result["future_skew_seconds"] <= fc.ALLOWED_FUTURE_SKEW_SECONDS


@pytest.mark.parametrize("contract", sorted(CONTRACTS))
@pytest.mark.parametrize(
    "extra",
    [timedelta(microseconds=1), timedelta(seconds=1), timedelta(days=1), timedelta(days=365 * 100)],
    ids=["one_microsecond_outside", "just_outside", "one_day", "far_future"],
)
def test_future_timestamp_beyond_allowed_skew_is_rejected(contract, extra):
    moment = NOW + skew() + extra
    with pytest.raises(ValueError, match="allowed future clock skew"):
        CONTRACTS[contract](moment.isoformat())


@pytest.mark.parametrize("contract", sorted(CONTRACTS))
def test_offset_timezone_is_normalised_before_the_boundary_check(contract):
    plus_five = timezone(timedelta(hours=5))
    at_boundary = (NOW + skew()).astimezone(plus_five).isoformat()
    beyond = (NOW + skew() + timedelta(seconds=1)).astimezone(plus_five).isoformat()
    assert "+05:00" in at_boundary
    CONTRACTS[contract](at_boundary)
    with pytest.raises(ValueError, match="allowed future clock skew"):
        CONTRACTS[contract](beyond)


@pytest.mark.parametrize("contract", sorted(CONTRACTS))
def test_past_timestamp_reports_zero_future_skew(contract):
    result = CONTRACTS[contract](iso(NOW - timedelta(seconds=60)))
    assert result["future_skew_seconds"] == 0
    assert result["allowed_future_skew_seconds"] == fc.ALLOWED_FUTURE_SKEW_SECONDS


def test_terra_future_within_skew_is_reported_not_silently_clamped():
    result = terra(iso(NOW + timedelta(seconds=120)))
    assert result["freshness_state"] == "FRESH"
    assert result["age_seconds"] == 0
    assert result["future_skew_seconds"] == 120
    assert result["time_admission"] == "FUTURE_WITHIN_ALLOWED_SKEW"


def test_sub_second_future_skew_is_never_reported_as_zero():
    result = terra((NOW + timedelta(milliseconds=1)).isoformat())
    assert result["future_skew_seconds"] == 1
    assert result["time_admission"] == "FUTURE_WITHIN_ALLOWED_SKEW"


def test_past_observation_is_admitted_as_past_or_present():
    assert terra(iso(NOW - timedelta(seconds=1)))["time_admission"] == "PAST_OR_PRESENT"
    assert finance(iso(NOW))["time_admission"] == "PAST_OR_PRESENT"


# -- timezone-naive and invalid -------------------------------------------------------

NAIVE = ["2026-10-27T11:59:00", "2026-10-27 11:59:00", "2026-10-27"]
INVALID = ["not-a-timestamp!", "2026-13-01T00:00:00Z", "2026-10-27T25:00:00Z", "2026-10-27T11:59:00ZZ"]


@pytest.mark.parametrize("contract", sorted(CONTRACTS))
@pytest.mark.parametrize("value", NAIVE)
def test_timezone_naive_timestamp_is_rejected(contract, value):
    with pytest.raises(ValueError, match="UTC offset"):
        CONTRACTS[contract](value)


@pytest.mark.parametrize("contract", sorted(CONTRACTS))
@pytest.mark.parametrize("value", INVALID)
def test_invalid_timestamp_is_rejected(contract, value):
    with pytest.raises(ValueError, match="ISO-8601"):
        CONTRACTS[contract](value)


@pytest.mark.parametrize("contract", sorted(CONTRACTS))
def test_timezone_naive_injected_clock_is_rejected(contract):
    with pytest.raises(ValueError, match="clock"):
        CONTRACTS[contract](iso(NOW - timedelta(seconds=60)), now=NOW.replace(tzinfo=None))


# -- stale boundaries -------------------------------------------------------------------


def test_terra_stale_boundary():
    at_limit = terra(iso(NOW - timedelta(seconds=3600)))
    assert at_limit["freshness_state"] == "FRESH"
    assert at_limit["coverage_state"] == "BOUND"
    beyond = terra(iso(NOW - timedelta(seconds=3601)))
    assert beyond["freshness_state"] == "STALE"
    assert beyond["coverage_state"] == "UNAVAILABLE"
    assert beyond["truth_label"] == "UNAVAILABLE"


def test_finance_stale_boundary():
    at_limit = finance(iso(NOW - timedelta(seconds=3600)))
    assert at_limit["freshness_state"] == "FRESH"
    assert at_limit["decision"] == "ALLOW_READ"
    beyond = finance(iso(NOW - timedelta(seconds=3601)))
    assert beyond["freshness_state"] == "STALE"
    assert beyond["decision"] == "REVIEW_REQUIRED"


def test_killinchu_stale_boundary():
    def add_then_remove(age):
        added = NOW - age - timedelta(seconds=1)
        removed = NOW - age
        return fc.replay_identity_lifecycle(
            prior_event_ids=[],
            incoming=[
                fc.IdentityEvent("add-1", "imo-1000001", iso(added), "DESIGNATION_ADDED",
                                 "ofac-snapshot", "rev-1", "OBSERVED", {"designation_id": "sdn-1"}),
                fc.IdentityEvent("rm-1", "imo-1000001", iso(removed), "DESIGNATION_REMOVED",
                                 "ofac-snapshot", "rev-1", "OBSERVED", {"designation_id": "sdn-1"}),
            ],
            chain_complete=True,
            now=NOW,
            history_verifier=trust_all,
        )

    fresh = add_then_remove(timedelta(days=365) - timedelta(seconds=1))
    assert fresh["screening_state"] == "CLEAR"
    stale = add_then_remove(timedelta(days=365))
    assert stale["screening_state"] == "REVIEW_REQUIRED"
    assert stale["truth_label"] == "REPORTED"


# -- protected semantics are unchanged ------------------------------------------------


def test_finance_measured_label_and_audit_material_are_unchanged():
    result = finance("2026-10-27T11:59:00Z")
    assert result["truth_label"] == "MEASURED"
    assert result["decision"] == "ALLOW_READ"
    # Pinned on base 1907f507 (MEASURED): audit material is not changed by time admission.
    assert result["audit_receipt_sha256"] == (
        "ed644ccc6c35309d54a7dcb9caaa32c666350daca84af7ceb4d5f3ab412143c0"
    )


def test_terra_past_observation_output_is_unchanged_apart_from_additive_fields():
    result = terra("2026-10-27T11:59:00Z")
    legacy = {
        "age_seconds": 60, "conflict_count": 0, "coverage_claim": "SCOPED_EVIDENCE_ONLY",
        "coverage_state": "BOUND", "expected_scope": "NYC PLUTO 2026 Q4",
        "freshness_seconds": 3600, "freshness_state": "FRESH", "jurisdiction": "NYC",
        "observed_at": "2026-10-27T11:59:00+00:00", "record_count": 10,
        "schema": "szl.terra-coverage-contract/v1", "source_id": "nyc-pluto",
        "truth_label": "MEASURED", "unavailable_reason": None,
    }
    assert {key: result[key] for key in legacy} == legacy
    assert set(result) - set(legacy) == {
        "allowed_future_skew_seconds", "future_skew_seconds", "time_admission",
    }


# -- routes with an injected deterministic clock ----------------------------------------


def _client(now=NOW):
    app = FastAPI()
    app.include_router(fc.frontier_contracts)
    app.dependency_overrides[fc.contract_clock] = lambda: now
    return TestClient(app)


def _terra_body(observed_at):
    return {
        "source_id": "nyc-pluto", "jurisdiction": "NYC", "observed_at": observed_at,
        "freshness_seconds": 3600, "record_count": 10, "expected_scope": "NYC PLUTO 2026 Q4",
    }


def _finance_body(observed_at):
    return {
        "actor_id": "user-1", "tenant_id": "tenant-1", "scopes": ["read:balances"],
        "field_scopes": ["balance"], "query": "select balance", "source_revision": "finance@1",
        "observed_at": observed_at, "freshness_seconds": 3600, "approval_id": "approval-1",
    }


def _killinchu_body(event_time):
    return {
        "events": [{
            "event_id": "add-1", "entity_id": "imo-1000001", "event_time": event_time,
            "kind": "DESIGNATION_ADDED", "source_id": "ofac-snapshot", "source_revision": "rev-1",
            "payload": {"designation_id": "sdn-1"},
        }],
        "chain_complete": True,
    }


ROUTES = {
    "killinchu": ("/killinchu/v1/identity/replay", _killinchu_body),
    "terra": ("/terra/v1/coverage/evaluate", _terra_body),
    "finance": ("/finance/v1/adapter/authorize", _finance_body),
}


@pytest.mark.parametrize("contract", sorted(ROUTES))
def test_route_uses_injected_clock_for_the_future_boundary(contract):
    path, body = ROUTES[contract]
    client = _client()
    at_boundary = client.post(path, json=body(iso(NOW + skew())))
    assert at_boundary.status_code == 200, at_boundary.text
    assert at_boundary.json()["future_skew_seconds"] == fc.ALLOWED_FUTURE_SKEW_SECONDS
    beyond = client.post(path, json=body(iso(NOW + skew() + timedelta(seconds=1))))
    assert beyond.status_code == 422
    assert "allowed future clock skew" in beyond.json()["detail"]


@pytest.mark.parametrize("contract", sorted(ROUTES))
def test_route_rejects_naive_timestamp(contract):
    path, body = ROUTES[contract]
    response = _client().post(path, json=body("2026-10-27T11:59:00"))
    assert response.status_code == 422
    assert "UTC offset" in response.json()["detail"]


@pytest.mark.parametrize("contract", sorted(ROUTES))
def test_route_with_system_clock_rejects_far_future(contract):
    path, body = ROUTES[contract]
    app = FastAPI()
    app.include_router(fc.frontier_contracts)
    response = TestClient(app).post(path, json=body("2999-01-01T00:00:00Z"))
    assert response.status_code == 422


def test_terra_route_far_future_is_not_bound():
    app = FastAPI()
    app.include_router(fc.frontier_contracts)
    response = TestClient(app).post(
        "/terra/v1/coverage/evaluate", json=_terra_body("2999-01-01T00:00:00Z")
    )
    assert response.status_code != 200 or response.json()["coverage_state"] != "BOUND"
