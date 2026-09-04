"""Engine tests for the six vertical services (combined deploy app).

Runs against deploy/app.py via FastAPI TestClient. Truth-label and
fail-closed behavior are asserted, not assumed.
"""
import sys
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
sys.path.insert(0, str(DEPLOY))

from fastapi.testclient import TestClient  # noqa: E402

import app as vertical  # noqa: E402

client = TestClient(vertical.app)


def test_root_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert set(body["engines"]) == {"sentra", "lyte", "vessels", "finance", "terra", "counsel"}
    assert body["truth_label"] == "MEASURED"


def test_sentra_allow_path():
    r = client.post("/sentra/v1/evaluate", json={
        "actor": "ops", "action": "deploy", "resource": "prod/api",
        "risk_score": 0.2, "authenticated": True, "tier": "operator",
        "evidence": ["ticket-1"]})
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "ALLOW"
    assert body["failed_gates"] == []
    assert body["truth_label"] == "MEASURED"
    assert len(body["signature"]) == 64  # HMAC-SHA256 hex


def test_sentra_deny_by_default():
    r = client.post("/sentra/v1/evaluate", json={
        "actor": "", "action": "", "resource": "", "risk_score": 0.9,
        "authenticated": False, "tier": "untrusted", "evidence": []})
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "DENY"
    assert len(body["failed_gates"]) >= 6


def test_sentra_verdicts_recorded():
    client.post("/sentra/v1/evaluate", json={
        "actor": "ops2", "action": "read", "resource": "db:table",
        "authenticated": True, "tier": "operator", "evidence": ["e1"]})
    r = client.get("/sentra/v1/verdicts")
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_lyte_summary_and_unknown_stream():
    for i in range(25):
        client.post("/lyte/v1/metrics", json={"stream": "s1", "value": float(i)})
    r = client.get("/lyte/v1/summary", params={"stream": "s1"})
    assert r.status_code == 200
    body = r.json()
    assert body["n"] == 25
    assert body["min"] == 0.0 and body["max"] == 24.0
    assert client.get("/lyte/v1/summary", params={"stream": "nope"}).status_code == 404


def test_vessels_dark_gap_and_speed_anomaly():
    # 1 deg latitude = 60 nm; over 2h that is 30 kn implied > 28 kn threshold
    base = 1_700_000_000.0
    client.post("/vessels/v1/positions", json={
        "imo": "IMO-1", "lat": 40.0, "lon": -70.0, "sog": 5.0, "ts": base})
    client.post("/vessels/v1/positions", json={
        "imo": "IMO-1", "lat": 41.0, "lon": -70.0, "sog": 5.0, "ts": base + 7200})
    r = client.get("/vessels/v1/vessel/risk", params={"imo": "IMO-1"})
    body = r.json()
    assert body["dark_gaps"] == 1  # 2h gap > 1h threshold
    assert body["max_implied_speed_kn"] > 28.0
    assert body["truth_label"] == "MODELED"
    assert any(f.startswith("dark_activity") for f in body["flags"])
    assert client.get("/vessels/v1/vessel/risk", params={"imo": "IMO-X"}).status_code == 404


def test_finance_needs_three_points():
    client.post("/finance/v1/observations", json={"symbol": "TST", "price": 10.0})
    client.post("/finance/v1/observations", json={"symbol": "TST", "price": 10.5})
    r = client.get("/finance/v1/symbol/brief", params={"symbol": "TST"})
    assert r.status_code == 400  # need >= 3
    client.post("/finance/v1/observations", json={"symbol": "TST", "price": 11.0})
    r = client.get("/finance/v1/symbol/brief", params={"symbol": "TST"})
    assert r.status_code == 200
    body = r.json()
    assert body["n"] == 3
    assert body["truth_label"] == "MODELED"
    assert body["signal"] in {"LONG", "SHORT", "FLAT"}


def test_terra_market_analysis():
    client.post("/terra/v1/listings", json={
        "market": "NYC", "price": 1_000_000, "sqft": 1000, "noi_annual": 50000})
    client.post("/terra/v1/listings", json={
        "market": "NYC", "price": 2_000_000, "sqft": 1000})
    r = client.get("/terra/v1/market/analysis", params={"market": "NYC"})
    assert r.status_code == 200
    body = r.json()
    assert body["n"] == 2
    assert body["psf_median"] == 1500.0
    assert body["cap_rate_median"] == 0.05
    assert client.get("/terra/v1/market/analysis", params={"market": "ATL"}).status_code == 404


def test_counsel_chain_and_docket():
    r = client.post("/counsel/v1/matters", json={
        "title": "Contract dispute", "client": "ACME", "exposure_usd": 500000})
    assert r.status_code == 200
    mid = r.json()["id"]
    assert r.json()["receipt"]["truth_label"] == "MEASURED"

    client.post(f"/counsel/v1/matters/{mid}/obligations", json={
        "clause": "5.2", "obligation": "Deliver audit by Q4", "severity": "critical"})
    client.post(f"/counsel/v1/matters/{mid}/obligations", json={
        "clause": "9.1", "obligation": "Renew insurance", "severity": "low"})

    m = client.get(f"/counsel/v1/matters/{mid}").json()
    assert m["obligations_by_severity"][0]["severity"] == "critical"

    d = client.get("/counsel/v1/docket").json()
    assert d["matters"] >= 1
    assert d["docket"][0]["high_severity"] >= 1
    assert d["truth_label"] == "MODELED"
