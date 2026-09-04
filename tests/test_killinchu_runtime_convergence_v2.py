from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
sys.path.insert(0, str(DEPLOY))

os.environ.setdefault("SZL_SOURCE_REVISION", "f" * 40)
os.environ.setdefault(
    "SZL_STATE_PATH",
    "/tmp/szl-vertical-services-killinchu-contract-v2.sqlite3",
)
os.environ.setdefault("SENTRA_SIGNING_KEY", "test-only-killinchu-contract-key")

from szl_verticals.killinchu_runtime_contract import (  # noqa: E402
    CANONICAL_PRODUCT,
    LAMBDA_STATUS,
    LOCKED_FORMULA_IDS,
    PRODUCT_STATE,
    architecture,
    compatibility_headers,
    lobe,
)

APP_PATH = DEPLOY / "app.py"
SPEC = importlib.util.spec_from_file_location("szl_vertical_services_contract_app", APP_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load deployed vertical-services app")
APP_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APP_MODULE)
CLIENT = TestClient(APP_MODULE.app)


def test_one_killinchu_product_preserves_two_engine_lobes() -> None:
    assert CANONICAL_PRODUCT == "killinchu"
    assert PRODUCT_STATE == "SOLE_PUBLIC_CYBER_PHYSICAL_RESILIENCE_AUTHORITY"
    document = architecture()
    assert document["canonical_product"] == "killinchu"
    assert set(document["lobes"]) == {"aegis", "vessels"}
    assert document["lobes"]["aegis"]["engine"] == "sentra"
    assert document["lobes"]["vessels"]["engine"] == "vessels"
    assert all(not row["standalone_product"] for row in document["lobes"].values())


def test_governance_boundary_is_exact_and_non_actuating() -> None:
    assert LOCKED_FORMULA_IDS == (
        "F1",
        "F4",
        "F7",
        "F11",
        "F12",
        "F18",
        "F19",
        "F22",
    )
    assert LAMBDA_STATUS == "CONJECTURE_1_ADVISORY"
    document = architecture()
    assert document["human_authority_required"] is True
    assert document["receipt_required"] is True
    assert document["destructive_or_offensive_autonomy"] is False
    assert document["effectors_enabled"] is False


def test_aliases_resolve_to_lobes_not_new_products() -> None:
    assert lobe("defend")["lobe"] == "aegis"
    assert lobe("sentra")["lobe"] == "aegis"
    assert lobe("immune")["lobe"] == "aegis"
    assert lobe("maritime")["lobe"] == "vessels"
    assert lobe("vessels")["lobe"] == "vessels"
    for alias in ("defend", "sentra", "immune", "maritime", "vessels"):
        assert lobe(alias)["standalone_product"] is False


def test_compatibility_headers_are_bounded_to_declared_prefixes() -> None:
    assert compatibility_headers("/sentra/healthz") == {
        "X-SZL-Canonical-Product": "killinchu",
        "X-SZL-Product-Lobe": "aegis",
        "X-SZL-Standalone-Product": "false",
    }
    assert compatibility_headers("/vessels/v1/fleet/risk") == {
        "X-SZL-Canonical-Product": "killinchu",
        "X-SZL-Product-Lobe": "vessels",
        "X-SZL-Standalone-Product": "false",
    }
    assert compatibility_headers("/api/verticals/immune/readyz")[
        "X-SZL-Product-Lobe"
    ] == "aegis"
    assert compatibility_headers("/terra/healthz") == {}
    assert compatibility_headers("/not-vessels/healthz") == {}


def test_source_native_routes_answer_from_the_combined_process() -> None:
    architecture_response = CLIENT.get("/killinchu/architecture")
    assert architecture_response.status_code == 200
    assert architecture_response.json()["canonical_product"] == "killinchu"

    aegis_response = CLIENT.get("/killinchu/aegis/healthz")
    assert aegis_response.status_code == 200
    assert aegis_response.json()["engine"] == "sentra"
    assert aegis_response.json()["runtime_state"] == (
        "REACHABLE_ONLY_WHEN_THIS_ENDPOINT_ANSWERS"
    )

    vessels_response = CLIENT.get("/killinchu/vessels/healthz")
    assert vessels_response.status_code == 200
    assert vessels_response.json()["engine"] == "vessels"


def test_existing_engine_payloads_gain_identity_headers_only() -> None:
    sentra_response = CLIENT.get("/sentra/healthz")
    assert sentra_response.status_code == 200
    assert sentra_response.headers["X-SZL-Canonical-Product"] == "killinchu"
    assert sentra_response.headers["X-SZL-Product-Lobe"] == "aegis"
    assert sentra_response.headers["X-SZL-Standalone-Product"] == "false"
    assert sentra_response.json()["status"] == "ok"
    assert sentra_response.json()["service"] == "sentra"

    vessels_response = CLIENT.get("/vessels/healthz")
    assert vessels_response.status_code == 200
    assert vessels_response.headers["X-SZL-Canonical-Product"] == "killinchu"
    assert vessels_response.headers["X-SZL-Product-Lobe"] == "vessels"
    assert vessels_response.json()["status"] == "ok"
    assert vessels_response.json()["service"] == "vessels"

    terra_response = CLIENT.get("/terra/healthz")
    assert terra_response.status_code == 200
    assert "X-SZL-Canonical-Product" not in terra_response.headers


def test_contract_module_is_inside_the_existing_container_copy_closure() -> None:
    module = DEPLOY / "szl_verticals" / "killinchu_runtime_contract.py"
    dockerfile = (DEPLOY / "Dockerfile").read_text(encoding="utf-8")
    app_source = APP_PATH.read_text(encoding="utf-8")
    assert module.is_file()
    assert "COPY deploy/szl_verticals/ ./szl_verticals/" in dockerfile
    assert "from szl_verticals.killinchu_runtime_contract import" in app_source
    assert 'app.get("/killinchu/architecture"' in app_source
    assert 'app.get("/killinchu/aegis/healthz"' in app_source
    assert 'app.get("/killinchu/vessels/healthz"' in app_source


def test_temporary_self_merge_controls_are_absent() -> None:
    workflow = ROOT / ".github" / "workflows"
    assert not (workflow / "apply-killinchu-runtime-convergence-v1.yml").exists()
    assert not (workflow / "finalize-killinchu-runtime-convergence-v1.yml").exists()
    assert not (ROOT / "tools" / "apply_killinchu_runtime_convergence_v1.py").exists()
