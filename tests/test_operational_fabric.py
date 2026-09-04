"""Contract tests for the shared vertical operational fabric."""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))

_STATE = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "test-key-only")
os.environ.setdefault("SZL_SOURCE_REVISION", "3" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_STATE.name) / "observations.sqlite3"))

from szl_verticals.operational import (  # noqa: E402
    ConnectorFetchRequest,
    STORE,
    advisory_lambda,
    anatomy_for,
    fetch_connector,
    formulas_for,
    vertical_readiness,
)

SESSION = hashlib.sha256(b"vertical-fabric-contract").hexdigest()


def response(payload, content_type="application/json"):
    content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return httpx.Response(200, headers={"content-type": content_type}, content=content)


def test_every_vertical_has_nine_organs_and_math():
    expected = {"sentra", "lyte", "killinchu", "finance", "terra", "counsel"}
    for vertical in expected:
        anatomy = anatomy_for(vertical)
        assert len(anatomy["organs"]) == 9
        assert formulas_for(vertical)
    assert anatomy_for("vessels")["vertical"] == "killinchu"
    assert anatomy_for("vessels")["consolidation"]["vessels_status"] == "CONSOLIDATED"
    score = advisory_lambda({"source": 1.0, "freshness": 0.81, "coverage": 0.64})
    assert 0.0 <= score["score"] <= 1.0
    assert score["label"] == "ADVISORY"
    assert "Conjecture 1" in score["lambda_status"]


def test_cisa_is_normalized_receipted_and_cached():
    calls = {"count": 0}
    payload = {
        "catalogVersion": "2026.09.03",
        "dateReleased": "2026-09-03T10:00:00Z",
        "vulnerabilities": [{
            "cveID": "CVE-2026-12345",
            "vendorProject": "Example",
            "product": "Widget",
            "vulnerabilityName": "Example flaw",
            "dateAdded": "2026-09-03",
            "dueDate": "2026-09-24",
            "requiredAction": "Apply mitigations",
        }],
    }

    def handler(request):
        calls["count"] += 1
        assert request.url.host == "www.cisa.gov"
        return response(payload)

    req = ConnectorFetchRequest(
        parameters={"cve": "CVE-2026-12345", "limit": 5},
        force_refresh=True,
    )
    first = fetch_connector(
        vertical="sentra", connector_id="cisa-kev", request=req,
        session_scope=SESSION, transport=httpx.MockTransport(handler),
    )
    assert first["observation"]["matched"] == 1
    assert first["receipt"]["signature_claimed"] is False
    assert len(first["receipt"]["payload_sha256"]) == 64
    cached = fetch_connector(
        vertical="sentra", connector_id="cisa-kev",
        request=ConnectorFetchRequest(parameters=req.parameters),
        session_scope=SESSION,
    )
    assert cached["cache"]["hit"] is True
    assert calls["count"] == 1


def test_lyte_github_telemetry_generates_delivery_signal():
    payload = {"total_count": 2, "workflow_runs": [
        {"id": 1, "name": "CI", "status": "completed", "conclusion": "success"},
        {"id": 2, "name": "Deploy", "status": "completed", "conclusion": "failure"},
    ]}
    result = fetch_connector(
        vertical="lyte", connector_id="github-actions",
        request=ConnectorFetchRequest(
            parameters={"repository": "vertical-services", "limit": 10},
            force_refresh=True,
        ),
        session_scope=SESSION,
        transport=httpx.MockTransport(lambda request: response(payload)),
    )
    assert result["observation"]["success_rate"] == 0.5
    assert result["signal"]["kind"] == "delivery-health"
    assert result["signal"]["severity"] == "HIGH"


def test_noaa_is_historical_killinchu_authority_not_live_feed():
    xml = b"""<root><catalog-item-id>77594</catalog-item-id><title>Nationwide AIS 2025</title>
    <status>Complete</status><publication-date>2026-08-27</publication-date>
    <url>https://example.noaa.gov/download</url></root>"""
    result = fetch_connector(
        vertical="killinchu", connector_id="noaa-ais-2025",
        request=ConnectorFetchRequest(force_refresh=True),
        session_scope=SESSION,
        transport=httpx.MockTransport(lambda request: response(xml, "application/xml")),
    )
    assert result["observation"]["data_mode"] == "HISTORICAL_OFFICIAL_AIS"
    assert result["observation"]["live_ais_claimed"] is False
    assert result["signal"]["live_feed"] is False


def test_sec_pluto_and_federal_register_normalize():
    cases = [
        (
            "finance", "sec-submissions", {"cik": "320193", "limit": 2},
            {"cik": "0000320193", "name": "Issuer", "filings": {"recent": {
                "accessionNumber": ["1"], "filingDate": ["2026-08-01"],
                "form": ["10-Q"], "primaryDocument": ["q.htm"]}}},
            lambda result: result["observation"]["recent_filings"][0]["form"] == "10-Q",
        ),
        (
            "terra", "nyc-pluto", {"borough": "MN", "limit": 2},
            [{"bbl": "1000010001", "address": "1 Test Street"}],
            lambda result: result["observation"]["returned"] == 1,
        ),
        (
            "counsel", "federal-register", {"term": "artificial intelligence"},
            {"count": 1, "total_pages": 1, "results": [{
                "document_number": "2026-1", "title": "AI rule", "type": "Rule"}]},
            lambda result: result["signal"]["kind"] == "public-legal-authority",
        ),
    ]
    for vertical, connector, parameters, payload, assertion in cases:
        result = fetch_connector(
            vertical=vertical, connector_id=connector,
            request=ConnectorFetchRequest(parameters=parameters, force_refresh=True),
            session_scope=SESSION,
            transport=httpx.MockTransport(lambda request, body=payload: response(body)),
        )
        assert assertion(result)
        assert result["receipt"]["state"] == "OBSERVED"


def test_network_authority_is_fixed_and_optional_auth_fails_closed(monkeypatch):
    with pytest.raises(HTTPException) as error:
        fetch_connector(
            vertical="terra", connector_id="nyc-pluto",
            request=ConnectorFetchRequest(parameters={"url": "https://evil.invalid"}),
            session_scope=SESSION,
        )
    assert error.value.status_code == 422
    monkeypatch.delenv("CONGRESS_API_KEY", raising=False)
    with pytest.raises(HTTPException) as error:
        fetch_connector(
            vertical="counsel", connector_id="congress-bills",
            request=ConnectorFetchRequest(parameters={"congress": "119"}),
            session_scope=SESSION,
        )
    assert error.value.status_code == 503


def test_readiness_distinguishes_wiring_from_observation():
    state = vertical_readiness("sentra", SESSION)
    assert state["requirements"]["required_connector_contracts_ready"] is True
    assert state["live_data"]["wired"] is True
    assert STORE.status()["writable"] is True
