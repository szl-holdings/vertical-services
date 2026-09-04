"""Public-product identity contracts for the shared vertical runtime."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))

_STATE = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "boundary-test-key-not-production")
os.environ.setdefault("SZL_SOURCE_REVISION", "7" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_STATE.name) / "boundary.sqlite3"))

from app import CATALOG, app  # noqa: E402
from szl_verticals.profiles import ALIASES, VERTICALS  # noqa: E402

CLIENT = TestClient(app)


def test_aegis_and_sentra_are_killinchu_defend_plane() -> None:
    profile = VERTICALS["sentra"]
    assert profile["product"] == "Killinchu / Defend"
    assert profile["portfolio_name"] == "Aegis"
    assert profile["component_engine"] == "Sentra"
    assert profile["canonical_repository"] == "szl-holdings/szl-defensive-control-plane"
    assert profile["public_space"] == "SZLHOLDINGS/killinchu"
    assert profile["public_route"] == "/defend"
    assert profile["consolidation"]["public_product"] == "KILLINCHU"
    assert profile["consolidation"]["sentra_status"] == "COMPONENT_ENGINE"
    assert profile["consolidation"]["aegis_status"] == "PORTFOLIO_NAME"
    assert profile["consolidation"]["effectors"] == "DISABLED"
    assert profile["consolidation"]["human_approval_required"] is True


def test_shared_catalog_links_command_to_live_killinchu_defend() -> None:
    sentra = CATALOG["sentra"]
    assert sentra["public_home"] == "SZLHOLDINGS/killinchu"
    assert sentra["public_route"] == "https://szlholdings-killinchu.hf.space/defend"
    assert sentra["experience"] == sentra["public_route"]
    assert sentra["component_experience"] == "/experience/aegis"
    assert sentra["component_engine"] == "sentra"
    assert sentra["portfolio_name"] == "Aegis"

    response = CLIENT.get("/api/catalog")
    assert response.status_code == 200
    body = response.json()
    assert body["engines"]["sentra"]["public_home"] == "SZLHOLDINGS/killinchu"
    assert body["aegis_canonical_runtime"] == "killinchu/defend"
    assert body["sentra_component_runtime"] == "killinchu/defend"
    assert body["immune_migration_state"] == "MIGRATION_REQUIRED"


def test_internal_aliases_do_not_create_competing_products() -> None:
    assert ALIASES["aegis"] == "sentra"
    assert ALIASES["immune"] == "sentra"
    assert ALIASES["vessels"] == "killinchu"
    assert "SZLHOLDINGS/sentra" not in (
        ROOT / "deploy" / "szl_verticals" / "profiles.py"
    ).read_text(encoding="utf-8")
    assert '"public_home": "SZLHOLDINGS/sentra"' not in (
        ROOT / "deploy" / "app.py"
    ).read_text(encoding="utf-8")


def test_counsel_uses_active_canonical_source() -> None:
    assert (
        VERTICALS["counsel"]["canonical_repository"]
        == "szl-holdings/a11oy/verticals/counsel"
    )
    assert VERTICALS["counsel"]["public_space"] == "SZLHOLDINGS/counsel"


def test_independent_vertical_identities_are_unambiguous() -> None:
    expected = {
        "terra": ("Terra", "real-estate-intelligence", "SZLHOLDINGS/terra"),
        "counsel": ("PRISM Counsel", "legal-intelligence", "SZLHOLDINGS/counsel"),
        "finance": (
            "PURIQ Finance",
            "financial-and-prediction-market-intelligence",
            "SZLHOLDINGS/finance",
        ),
        "lyte": ("Lyte", "business-observability", "SZLHOLDINGS/lyte"),
    }
    for vertical, (product, domain, public_space) in expected.items():
        profile = VERTICALS[vertical]
        assert profile["product"] == product
        assert profile["domain"] == domain
        assert profile["public_space"] == public_space
