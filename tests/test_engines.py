"""Engine tests for the canonical vertical runtime.

These tests exercise the combined deployment app and preserve the legacy
``/vessels`` compatibility route while asserting that Killinchu is the only
canonical defense-and-maritime vertical.
"""
import os
import sys
import tempfile
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
sys.path.insert(0, str(DEPLOY))

_STATE = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "pytest-key-not-used-in-production")
os.environ.setdefault("SZL_SOURCE_REVISION", "2" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_STATE.name) / "state.sqlite3"))

from fastapi.testclient import TestClient  # noqa: E402

import app as vertical  # noqa: E402

client = TestClient(
    vertical.app,
    headers={"X-SZL-Session": "pytest-session-token-0123456789012345"},
)


def test_root_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["engines"]) == {
        "sentra",
        "lyte",
        "killinchu",
        "finance",
        "terra",
        "counsel",
    }
    assert "vessels" not in body["engines"]
    assert body["compatibility_routes"]["/vessels"]["canonical"] == "/killinchu"
    assert body["truth_label"] == "MEASURED"


def test_sentra_allow_path():
    response = client.post(
        "/sentra/v1/evaluate",
        json={
            "actor": "ops",
            "action": "deploy",
            "resource": "prod/api",
            "risk_score": 0.2,
            "authenticated": True,
            "tier": "operator",
            "evidence": ["ticket-1"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "ALLOW"
    assert body["failed_gates"] == []
    assert body["truth_label"] == "MEASURED"
    assert len(body["signature"]) == 64


def test_sentra_deny_by_default():
    response = client.post(
        "/sentra/v1/evaluate",
        json={
            "actor": "anonymous",
            "action": "delete",
            "resource": "prod:ledger",
            "risk_score": 0.9,
            "authenticated": False,
            "tier": "untrusted",
            "evidence": [],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "DENY"
    assert len(body["failed_gates"]) >= 4


def test_sentra_verdicts_recorded():
    client.post(
        "/sentra/v1/evaluate",
        json={
            "actor": "ops2",
            "action": "read",
            "resource": "db:table",
            "authenticated": True,
            "tier": "operator",
            "evidence": ["e1"],
        },
    )
    response = client.get("/sentra/v1/verdicts")
    assert response.status_code == 200
    assert response.json()["count"] >= 1


def test_lyte_summary_and_unknown_stream():
    for index in range(25):
        client.post("/lyte/v1/metrics", json={"stream": "s1", "value": float(index)})
    response = client.get("/lyte/v1/summary", params={"stream": "s1"})
    assert response.status_code == 200
    body = response.json()
    assert body["n"] == 25
    assert body["min"] == 0.0 and body["max"] == 24.0
    assert client.get("/lyte/v1/summary", params={"stream": "nope"}).status_code == 404


def test_killinchu_maritime_dark_gap_and_speed_anomaly():
    base = 1_700_000_000.0
    client.post(
        "/killinchu/v1/maritime/positions",
        json={"imo": "IMO-1", "lat": 40.0, "lon": -70.0, "sog": 5.0, "ts": base},
    )
    client.post(
        "/killinchu/v1/maritime/positions",
        json={"imo": "IMO-1", "lat": 41.0, "lon": -70.0, "sog": 5.0, "ts": base + 7200},
    )
    response = client.get(
        "/killinchu/v1/maritime/vessel/risk",
        params={"imo": "IMO-1"},
    )
    body = response.json()
    assert body["dark_gaps"] == 1
    assert body["max_implied_speed_kn"] > 28.0
    assert body["truth_label"] == "MODELED"
    assert body["vertical"] == "killinchu"
    assert any(flag.startswith("dark_activity") for flag in body["flags"])
    assert client.get(
        "/killinchu/v1/maritime/vessel/risk",
        params={"imo": "IMO-X"},
    ).status_code == 404

    legacy = client.get("/vessels/healthz").json()
    assert legacy["consolidated"] is True
    assert legacy["public_surface"] == "SZLHOLDINGS/killinchu"


def test_finance_needs_three_points():
    client.post("/finance/v1/observations", json={"symbol": "TST", "price": 10.0})
    client.post("/finance/v1/observations", json={"symbol": "TST", "price": 10.5})
    response = client.get("/finance/v1/symbol/brief", params={"symbol": "TST"})
    assert response.status_code == 400
    client.post("/finance/v1/observations", json={"symbol": "TST", "price": 11.0})
    response = client.get("/finance/v1/symbol/brief", params={"symbol": "TST"})
    assert response.status_code == 200
    body = response.json()
    assert body["n"] == 3
    assert body["truth_label"] == "MODELED"
    assert body["signal"] in {"LONG", "SHORT", "FLAT"}


def test_terra_market_analysis():
    client.post(
        "/terra/v1/listings",
        json={
            "market": "NYC",
            "price": 1_000_000,
            "sqft": 1000,
            "noi_annual": 50000,
        },
    )
    client.post(
        "/terra/v1/listings",
        json={"market": "NYC", "price": 2_000_000, "sqft": 1000},
    )
    response = client.get("/terra/v1/market/analysis", params={"market": "NYC"})
    assert response.status_code == 200
    body = response.json()
    assert body["n"] == 2
    assert body["psf_median"] == 1500.0
    assert body["cap_rate_median"] == 0.05
    assert client.get("/terra/v1/market/analysis", params={"market": "ATL"}).status_code == 404


def test_counsel_chain_and_docket():
    response = client.post(
        "/counsel/v1/matters",
        json={
            "title": "Contract dispute",
            "client": "ACME",
            "exposure_usd": 500000,
        },
    )
    assert response.status_code == 200
    matter_id = response.json()["id"]
    assert response.json()["receipt"]["truth_label"] == "MEASURED"

    client.post(
        f"/counsel/v1/matters/{matter_id}/obligations",
        json={
            "clause": "5.2",
            "obligation": "Deliver audit by Q4",
            "severity": "critical",
        },
    )
    client.post(
        f"/counsel/v1/matters/{matter_id}/obligations",
        json={
            "clause": "9.1",
            "obligation": "Renew insurance",
            "severity": "low",
        },
    )

    matter = client.get(f"/counsel/v1/matters/{matter_id}").json()
    assert matter["obligations_by_severity"][0]["severity"] == "critical"

    docket = client.get("/counsel/v1/docket").json()
    assert docket["matters"] >= 1
    assert docket["docket"][0]["high_severity"] >= 1
    assert docket["truth_label"] == "MODELED"


def test_operational_contract_for_every_vertical():
    for engine in vertical.ENGINES:
        anatomy = client.get(f"/api/verticals/{engine}/anatomy").json()
        formulas = client.get(f"/api/verticals/{engine}/formulas").json()
        connectors = client.get(f"/api/verticals/{engine}/connectors").json()
        assert len(anatomy["organs"]) == 9
        assert formulas["count"] > 0
        assert connectors["count"] > 0
        assert connectors["caller_supplied_urls_allowed"] is False
