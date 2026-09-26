"""Readiness and health must say what is true now, in the body and the status.

Readiness ``live_data`` counts only current, non-withdrawn observations, and
every health route fails closed in its HTTP status when the running source is
not bound. Real SQLite ledger and mounted routes; no live feeds.
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from test_hatun_evidence_admission import NOW, PAYLOAD, SCOPE, TOKEN, app, context, fr, seed  # noqa: F401

store_module = importlib.import_module("szl_verticals.store")
operational = importlib.import_module("szl_verticals.operational")
OTHER_SCOPE = "f" * 64
TTL = fr.CONNECTORS["polymarket-markets"].freshness_seconds
HEALTH_ROUTES = ("/healthz", "/sentra/healthz", "/lyte/healthz", "/killinchu/healthz",
                 "/vessels/healthz", "/finance/healthz", "/terra/healthz", "/counsel/healthz")
UNBOUND = {
    "MISMATCH": {"state": "MISMATCH", "revision": "UNAVAILABLE", "bindings_agree": False,
                 "evidence_sources": ["container-file", "env"], "invalid_sources": []},
    "INVALID": {"state": "INVALID", "revision": "UNAVAILABLE", "bindings_agree": False,
                "evidence_sources": ["env"], "invalid_sources": ["env"]},
    "UNBOUND": {"state": "UNBOUND", "revision": "UNAVAILABLE", "bindings_agree": True,
                "evidence_sources": [], "invalid_sources": []},
}


@pytest.fixture
def clock(context, monkeypatch):
    """Pin the ledger's read clock and route readiness to the test ledger."""
    db, client = context
    current = {"now": NOW}
    monkeypatch.setattr(store_module, "time", SimpleNamespace(time=lambda: current["now"]))
    monkeypatch.setattr(operational, "STORE", db)
    return db, client, current


def counts(db, scope=SCOPE):
    return db.counts(vertical="finance", session_scope=scope)


def live_data(client):
    response = client.get("/api/verticals/finance/readyz")
    assert response.status_code == 200
    return response.json()["live_data"]


def test_withdrawn_observation_leaves_readiness_live_data(clock):
    db, client, _ = clock
    seed(db)
    assert counts(db) == {"observations": 1, "connectors_observed": 1}
    assert live_data(client)["observed_in_scope"] is True
    withdrawn = client.post("/api/verticals/puriq/evidence/withdraw", json={"evidence_sha256": [PAYLOAD]})
    assert withdrawn.status_code == 200
    assert counts(db) == {"observations": 0, "connectors_observed": 0}
    assert counts(db, scope=None) == {"observations": 0, "connectors_observed": 0}
    assert live_data(client) == {"wired": True, "observed_in_scope": False,
                                 "observations": 0, "connectors_observed": 0}
    # The ledger keeps the history; only the live claim is withdrawn.
    assert [row["withdrawn"] for row in db.recent(vertical="finance", session_scope=SCOPE)] == [True]


def test_withdrawal_is_scoped_to_the_withdrawing_session(clock):
    db, client, _ = clock
    seed(db)
    seed(db, scope=OTHER_SCOPE)
    assert client.post("/api/verticals/puriq/evidence/withdraw",
                       json={"evidence_sha256": [PAYLOAD]}).status_code == 200
    assert counts(db)["observations"] == 0
    assert counts(db, scope=OTHER_SCOPE)["observations"] == 1
    assert counts(db, scope=None)["observations"] == 1
    assert live_data(client)["observed_in_scope"] is True


def test_expired_and_future_observations_are_not_live(clock):
    db, client, current = clock
    seed(db, observed=NOW - 1.0)
    assert counts(db)["observations"] == 1
    current["now"] = NOW - 1.0 + TTL  # expires_at is exclusive, as in cached()
    assert counts(db) == {"observations": 0, "connectors_observed": 0}
    assert live_data(client)["observed_in_scope"] is False
    current["now"] = NOW
    seed(db, digest="a" * 64, observed=NOW + 5.0)
    assert counts(db)["observations"] == 1  # only the first row; the new one is not yet observed
    current["now"] = NOW + 5.0
    assert counts(db)["observations"] == 2


def test_counts_and_cache_agree_on_what_is_live(clock):
    db, client, current = clock
    receipt = seed(db)
    query = dict(vertical="finance", connector_id=receipt["connector_id"],
                 session_scope=SCOPE, query_hash=receipt["query_hash"])
    for now in (NOW, receipt["expires_at"] - 0.001, receipt["expires_at"]):
        current["now"] = now
        assert (db.cached(**query) is not None) == (counts(db)["observations"] == 1), now
    current["now"] = NOW
    client.post("/api/verticals/puriq/evidence/withdraw", json={"evidence_sha256": [PAYLOAD]})
    assert db.cached(**query) is None and counts(db)["observations"] == 0


@pytest.mark.parametrize("state", sorted(UNBOUND))
@pytest.mark.parametrize("path", HEALTH_ROUTES)
def test_unbound_source_fails_every_health_route_in_the_status(path, state):
    client = TestClient(app)
    with patch("szl_verticals.core._revision_observation", return_value=UNBOUND[state]):
        response = client.get(path)
    body = response.json()
    assert response.status_code == 503, (path, state)
    assert body["ok"] is False
    assert body["status"] == "source-unavailable"
    assert body["truth_label"] == "UNAVAILABLE"
    assert body["build"] == {"state": state, "revision": "UNAVAILABLE"}


@pytest.mark.parametrize("path", HEALTH_ROUTES)
def test_bound_source_keeps_every_health_route_ok(path):
    response = TestClient(app).get(path)
    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True and body["status"] == "ok"
    assert body["truth_label"] == "MEASURED"
    assert body["build"]["state"] == "OBSERVED"
    expected = {"/healthz": "szl-vertical-services"}.get(path, path.split("/")[1])
    assert body["service"] == expected
