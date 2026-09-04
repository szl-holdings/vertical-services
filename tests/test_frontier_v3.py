"""Frontier-v3 contract tests for aliases, experiences, sources, and Hatun."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))

_STATE = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "frontier-test-key")
os.environ.setdefault("SZL_SOURCE_REVISION", "4" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_STATE.name) / "frontier.sqlite3"))

from app import app  # noqa: E402
from szl_verticals.domain_math import (  # noqa: E402
    binary_entropy,
    probability_edge,
    weighted_distress_load,
)
from szl_verticals.operational import (  # noqa: E402
    ConnectorFetchRequest,
    STORE,
    fetch_connector,
)

SESSION_TOKEN = "frontier-session-token-01234567890123456789"
SESSION_SCOPE = hashlib.sha256(SESSION_TOKEN.encode()).hexdigest()
CLIENT = TestClient(app, headers={"X-SZL-Session": SESSION_TOKEN})


def response(payload: object) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "application/json"},
        content=json.dumps(payload).encode(),
    )


def test_aliases_resolve_without_duplicate_runtime_authority():
    expected = {
        "aegis": ("sentra", "Aegis Immune Cell"),
        "immune": ("sentra", "Aegis Immune Cell"),
        "puriq": ("finance", "PURIQ Market Chamber"),
        "markets": ("finance", "PURIQ Market Chamber"),
        "real-estate": ("terra", "Terra Parcel Loom"),
        "business-observability": ("lyte", "Lyte Signal Lattice"),
        "prism": ("counsel", "PRISM Authority Chain"),
        "vessels": ("killinchu", "Killinchu Voyage Radar"),
    }
    for alias, (canonical, title) in expected.items():
        result = CLIENT.get(f"/api/verticals/{alias}/frontier")
        assert result.status_code == 200
        body = result.json()
        assert body["vertical"] == canonical
        assert body["alias_resolved"] is True
        assert body["experience"]["title"] == title
        assert body["hatun"]["can_authorize"] is False


def test_each_canonical_experience_is_unique_mobile_and_accessible():
    expected = {
        "sentra": ("Aegis Immune Cell", "threat-shield"),
        "lyte": ("Lyte Signal Lattice", "service-lattice"),
        "killinchu": ("Killinchu Voyage Radar", "voyage-radar"),
        "finance": ("PURIQ Market Chamber", "probability-orbit"),
        "terra": ("Terra Parcel Loom", "parcel-grid"),
        "counsel": ("PRISM Authority Chain", "authority-chain"),
    }
    pages = {}
    for vertical, (title, motif) in expected.items():
        result = CLIENT.get(f"/experience/{vertical}")
        assert result.status_code == 200
        assert title in result.text
        assert f'data-motif="{motif}"' in result.text
        assert "viewport-fit=cover" in result.text
        assert "@media(prefers-reduced-motion:reduce)" in result.text
        assert "@media(forced-colors:active)" in result.text
        assert "X-SZL-Session" in result.text
        pages[vertical] = result.text
    assert len({hashlib.sha256(page.encode()).hexdigest() for page in pages.values()}) == 6


def test_puriq_public_market_connectors_are_bounded_and_non_executing():
    polymarket_payload = [
        {
            "id": "m1",
            "conditionId": "c1",
            "slug": "will-example-happen",
            "question": "Will the example happen?",
            "active": True,
            "closed": False,
            "endDate": "2026-12-31T00:00:00Z",
            "outcomes": '["Yes","No"]',
            "outcomePrices": '["0.63","0.37"]',
            "bestBid": 0.62,
            "bestAsk": 0.64,
            "volume24hr": 12500,
            "liquidityNum": 9000,
        }
    ]
    result = fetch_connector(
        vertical="puriq",
        connector_id="polymarket-markets",
        request=ConnectorFetchRequest(parameters={"limit": 5}, force_refresh=True),
        session_scope=SESSION_SCOPE,
        transport=httpx.MockTransport(lambda request: response(polymarket_payload)),
    )
    market = result["observation"]["markets"][0]
    assert market["yes_probability"] == 0.63
    assert market["binary_entropy"] > 0
    assert market["probability_edge_from_50"] == 0.13
    assert market["spread"] == 0.02
    assert result["observation"]["trading_enabled"] is False
    assert result["observation"]["custody_enabled"] is False
    assert result["signal"]["trading_enabled"] is False
    assert result["receipt"]["state"] == "OBSERVED"

    coinbase = fetch_connector(
        vertical="finance",
        connector_id="coinbase-spot",
        request=ConnectorFetchRequest(
            parameters={"base": "BTC", "currency": "USD"},
            force_refresh=True,
        ),
        session_scope=SESSION_SCOPE,
        transport=httpx.MockTransport(
            lambda request: response(
                {"data": {"base": "BTC", "currency": "USD", "amount": "61234.50"}}
            )
        ),
    )
    assert coinbase["observation"]["amount"] == 61234.5
    assert coinbase["observation"]["trading_enabled"] is False

    treasury = fetch_connector(
        vertical="finance",
        connector_id="treasury-average-rates",
        request=ConnectorFetchRequest(parameters={"limit": 2}, force_refresh=True),
        session_scope=SESSION_SCOPE,
        transport=httpx.MockTransport(
            lambda request: response(
                {
                    "data": [
                        {
                            "record_date": "2026-08-31",
                            "security_type_desc": "Marketable",
                            "security_desc": "Treasury Notes",
                            "avg_interest_rate_amt": "4.125",
                            "src_line_nbr": "1",
                        }
                    ]
                }
            )
        ),
    )
    assert treasury["observation"]["rate_max_pct"] == 4.125
    assert treasury["signal"]["kind"] == "treasury-rate-surface"


def test_terra_condition_sources_emit_property_not_person_signals():
    hpd = fetch_connector(
        vertical="real-estate",
        connector_id="nyc-hpd-violations",
        request=ConnectorFetchRequest(parameters={"limit": 3}, force_refresh=True),
        session_scope=SESSION_SCOPE,
        transport=httpx.MockTransport(
            lambda request: response(
                [
                    {"violationid": "1", "class": "A", "bbl": "1000010001"},
                    {"violationid": "2", "class": "B", "bbl": "1000010001"},
                    {"violationid": "3", "class": "C", "bbl": "1000010001"},
                ]
            )
        ),
    )
    load = hpd["observation"]["distress_load"]
    assert load["class_counts"] == {"A": 1, "B": 1, "C": 1}
    assert load["normalized_load"] == round(7 / 12, 6)
    assert hpd["observation"]["person_level_prospecting"] is False
    assert hpd["signal"]["person_level_prospecting"] is False

    dob = fetch_connector(
        vertical="terra",
        connector_id="nyc-dob-violations",
        request=ConnectorFetchRequest(parameters={"limit": 2}, force_refresh=True),
        session_scope=SESSION_SCOPE,
        transport=httpx.MockTransport(
            lambda request: response(
                [
                    {
                        "isn_dob_bis_viol": "9",
                        "violation_type": "V",
                        "disposition_date": None,
                    }
                ]
            )
        ),
    )
    assert dob["observation"]["open_without_disposition"] == 1
    assert dob["observation"]["person_level_prospecting"] is False


def test_domain_math_has_explicit_bounded_semantics():
    assert binary_entropy(0.5) == 1.0
    assert binary_entropy(0.0) == 0.0
    assert probability_edge(0.8) == 0.3
    load = weighted_distress_load({"A": 0, "B": 2, "C": 1})
    assert 0 <= load["normalized_load"] <= 1
    assert load["truth_label"] == "MODELED"


def test_hatun_abstains_without_evidence_and_never_authorizes():
    result = CLIENT.post(
        "/api/verticals/aegis/hatun/evaluate",
        json={
            "intent": "review a cyber response proposal",
            "requested_action": "contain.review",
            "axes": {"evidence": 0.95, "safety": 0.96, "reversibility": 0.92},
            "evidence_refs": [],
        },
    )
    assert result.status_code == 200
    body = result.json()
    assert body["decision"] == "ABSTAIN"
    assert "NO_EVIDENCE_REFERENCES" in body["blockers"]
    assert body["can_authorize"] is False
    assert body["can_execute"] is False
    assert body["receipt"]["session_token_recorded"] is False


def test_hatun_emits_review_only_after_session_evidence_exists():
    now = time.time()
    STORE.put(
        {
            "receipt_id": "f" * 64,
            "vertical": "finance",
            "connector_id": "polymarket-markets",
            "session_scope": SESSION_SCOPE,
            "query_hash": "e" * 64,
            "observed_at": now,
            "expires_at": now + 300,
            "source_url": "https://gamma-api.polymarket.com/markets?limit=1",
            "http_status": 200,
            "payload_sha256": "d" * 64,
            "truth_label": "REPORTED",
            "state": "OBSERVED",
        },
        {"returned": 1, "mode": "PUBLIC_READ_ONLY"},
    )
    result = CLIENT.post(
        "/api/verticals/puriq/hatun/evaluate",
        json={
            "intent": "review a market evidence brief",
            "requested_action": "market.review",
            "axes": {
                "evidence": 0.95,
                "freshness": 0.90,
                "reversibility": 0.96,
            },
            "evidence_refs": ["receipt:public-market-example"],
        },
    )
    assert result.status_code == 200
    body = result.json()
    assert body["decision"] == "REVIEW"
    assert body["vertical"] == "finance"
    assert body["session_observation_count"] >= 1
    assert len(body["evidence_ref_sha256"][0]) == 64
    assert body["receipt"]["raw_evidence_references_recorded"] is False
    assert body["effectors_enabled"] is False
    assert "Conjecture 1" in body["lambda_status"]
