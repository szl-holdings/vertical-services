# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import json
import re
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_app() -> ModuleType:
    spec = importlib.util.spec_from_file_location("szl_vertical_frontier", ROOT / "app.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve postponed annotations through the defining module.
    # Mirror normal import semantics before executing the module so Python 3.12
    # can find that namespace while decorating Snapshot and related contracts.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


@pytest.fixture(scope="module")
def app() -> ModuleType:
    return load_app()


def test_registry_is_eight_unique_products(app: ModuleType) -> None:
    assert app.REGISTRY["schema"] == "szl.vertical-frontier.v1"
    assert len(app.VERTICALS) == 8
    assert set(app.VERTICALS) == {
        "a11oy",
        "killinchu",
        "lyte",
        "sentra",
        "terra",
        "puriq",
        "prism",
        "anatomy",
    }

    layouts = {row["experience"]["layout"] for row in app.VERTICALS.values()}
    instruments = {row["experience"]["instrument"] for row in app.VERTICALS.values()}
    palettes = {tuple(row["experience"]["palette"]) for row in app.VERTICALS.values()}
    assert len(layouts) == len(app.VERTICALS)
    assert len(instruments) == len(app.VERTICALS)
    assert len(palettes) == len(app.VERTICALS)

    for row in app.VERTICALS.values():
        assert row["models"]
        assert row["kernels"]
        assert row["sources"]
        assert row["unserved_wedge"]
        assert row["prohibited"]
        fashion = row["fashion"]
        assert fashion["job"]
        assert fashion["leader"]
        assert fashion["tweak"]
        assert fashion["official_source"]


def test_authority_contract_is_fail_closed(app: ModuleType) -> None:
    authority = app.REGISTRY["authority"]
    assert authority["model_may_authorize"] is False
    assert authority["kernel_may_authorize"] is False
    assert authority["human_binding_required"] is True
    assert authority["public_effectors_enabled"] is False
    assert authority["lambda_uniqueness"] == "CONJECTURE_1_OPEN"

    build = app.build_info()
    assert build["model_may_authorize"] is False
    assert build["kernel_may_authorize"] is False
    assert build["public_effectors_enabled"] is False
    assert build["vertical_count"] == 8


def test_public_frontend_has_local_assets_and_accessibility_markers(app: ModuleType) -> None:
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "base.css").read_text(encoding="utf-8")
    themes = (ROOT / "static" / "themes.css").read_text(encoding="utf-8")

    assert 'lang="en"' in html
    assert 'href="#content"' in html
    assert 'aria-label="Primary"' in html
    assert 'aria-live="polite"' in html
    assert 'name="viewport"' in html
    assert "prefers-reduced-motion" in css
    assert "forced-colors" in css
    assert "min-height: 2.85rem" in css

    script_sources = re.findall(r"<script[^>]+src=\"([^\"]+)", html)
    style_sources = re.findall(r"<link[^>]+rel=\"stylesheet\"[^>]+href=\"([^\"]+)", html)
    assert script_sources == ["/static/app.js"]
    assert style_sources == ["/static/base.css", "/static/themes.css"]

    for function_name in (
        "renderDecisionRibbon",
        "renderTheaterMap",
        "renderSignalWaterfall",
        "renderExposureGraph",
        "renderParcelStack",
        "renderResearchTerminal",
        "renderCitationRail",
        "renderOrganBody",
    ):
        assert f"function {function_name}" in js

    for selector in (
        ".decision-ribbon",
        ".theater-map",
        ".signal-waterfall",
        ".exposure-field",
        ".parcel-scene",
        ".research-terminal",
        ".citation-scene",
        ".anatomy-scene",
    ):
        assert selector in themes


def test_local_and_historical_snapshots_are_honest(app: ModuleType) -> None:
    a11oy = app.snapshot_a11oy({}).as_dict()
    anatomy = app.snapshot_anatomy({}).as_dict()
    killinchu = app.snapshot_killinchu({}).as_dict()

    assert a11oy["state"] == "LOCAL_VERIFIED"
    assert a11oy["payload"]["vertical_count"] == 8
    assert anatomy["state"] == "LIVE_LOCAL"
    assert anatomy["payload"]["model_may_authorize"] is False
    assert killinchu["state"] == "HISTORICAL_SOURCE_CONTRACT"
    assert killinchu["payload"]["historical_planning_data"] is True
    assert killinchu["payload"]["live_positions_connected"] is False
    assert killinchu["payload"]["public_actuation"] == "SIMULATED"

    for snapshot in (a11oy, anatomy, killinchu):
        assert re.fullmatch(r"[0-9a-f]{64}", snapshot["receipt_sha256"])


def test_official_fetch_rejects_arbitrary_hosts(app: ModuleType) -> None:
    with pytest.raises(ValueError, match="not allowlisted"):
        app.bounded_json("https://example.com/private")
    with pytest.raises(ValueError, match="not allowlisted"):
        app.bounded_json("http://www.cisa.gov/not-https")


def test_missing_evidence_and_human_binding_hold(app: ModuleType) -> None:
    receipt = app.evaluate_proposal(
        {
            "vertical": "lyte",
            "objective": "Explain the current workflow failure",
            "requested_action": "prepare an operator recommendation",
            "risk": 0.2,
            "evidence": [],
            "human_approved": False,
        }
    )
    assert receipt["state"] == "HOLD"
    assert "NO_ADMISSIBLE_EVIDENCE" in receipt["blocks"]
    assert "HUMAN_BINDING_ABSENT" in receipt["blocks"]
    assert receipt["authorization"] == "NONE"
    assert receipt["execution_performed"] is False
    assert receipt["route"]["mode"] == "PROPOSAL_ONLY"


def test_prohibited_actions_fail_closed(app: ModuleType) -> None:
    evidence = [
        {
            "source": "operator-test",
            "claim": "A bounded observation exists.",
            "uri": "urn:szl:test",
            "observed_at": "2026-09-04T00:00:00Z",
        }
    ]
    cases = [
        ("killinchu", "engage target from the public interface"),
        ("sentra", "bypass authentication and exploit host"),
        ("puriq", "execute trade and buy shares"),
        ("prism", "file with court without counsel review"),
        ("terra", "deny housing using a protected class"),
    ]
    for vertical, action in cases:
        receipt = app.evaluate_proposal(
            {
                "vertical": vertical,
                "objective": "Evaluate the supplied evidence",
                "requested_action": action,
                "risk": 0.1,
                "evidence": evidence,
                "human_approved": True,
            }
        )
        assert receipt["state"] == "HOLD"
        assert "PROHIBITED_ACTION_CLASS" in receipt["blocks"]
        assert receipt["execution_performed"] is False
        assert receipt["authorization"] == "NONE"


def test_ready_proposal_still_does_not_execute(app: ModuleType) -> None:
    receipt = app.evaluate_proposal(
        {
            "vertical": "a11oy",
            "objective": "Assess whether the evidence supports a bounded recommendation",
            "requested_action": "review and prepare a recommendation",
            "risk": 0.25,
            "evidence": [
                {
                    "source": "source-bound-test",
                    "claim": "The source revision was independently observed.",
                    "uri": "urn:szl:source:revision",
                    "observed_at": "2026-09-04T00:00:00Z",
                }
            ],
            "human_approved": True,
        }
    )
    assert receipt["state"] == "READY_FOR_OPERATOR_BINDING"
    assert receipt["blocks"] == []
    assert receipt["authorization"] == "NONE"
    assert receipt["execution_performed"] is False
    assert receipt["public_effectors_enabled"] is False
    assert re.fullmatch(r"[0-9a-f]{64}", receipt["receipt_sha256"])


def test_receipt_verifier_detects_tampering(app: ModuleType) -> None:
    result = app.evaluate_proposal(
        {
            "vertical": "anatomy",
            "objective": "Inspect the body health state",
            "requested_action": "prepare a non-actuating explanation",
            "risk": 0.1,
            "evidence": [{"source": "health", "claim": "All five organs answered."}],
            "human_approved": True,
        }
    )
    digest = result.pop("receipt_sha256")
    valid = app.verify_receipt({"receipt": result, "receipt_sha256": digest})
    assert valid["valid"] is True
    assert valid["scope"] == "CANONICAL_JSON_INTEGRITY_ONLY"
    assert "truth" in valid["does_not_prove"]

    result["proposal"]["summary"] = "tampered"
    invalid = app.verify_receipt({"receipt": result, "receipt_sha256": digest})
    assert invalid["valid"] is False


def request_json(url: str, *, body: dict | None = None) -> tuple[int, dict, dict[str, str]]:
    encoded = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        url,
        method="POST" if body is not None else "GET",
        data=encoded,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urlopen(request, timeout=4) as response:
        return response.status, json.load(response), dict(response.headers.items())


def test_http_surface_and_security_headers(app: ModuleType) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urlopen(f"{base}/", timeout=4) as response:
            html = response.read().decode("utf-8")
            assert response.status == 200
            assert "SZL Vertical Frontier" in html
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]

        status, registry, headers = request_json(f"{base}/api/v1/verticals")
        assert status == 200
        assert len(registry["verticals"]) == 8
        assert headers["Cache-Control"] == "no-store"

        status, decision, _ = request_json(
            f"{base}/api/v1/decision",
            body={
                "vertical": "a11oy",
                "objective": "Inspect evidence",
                "requested_action": "review",
                "risk": 0.1,
                "evidence": [],
                "human_approved": False,
            },
        )
        assert status == 200
        assert decision["state"] == "HOLD"
        assert decision["execution_performed"] is False

        with pytest.raises(HTTPError) as exc_info:
            urlopen(f"{base}/api/v1/verticals/not-real", timeout=4)
        assert exc_info.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
