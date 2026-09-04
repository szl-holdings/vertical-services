"""Prevent internal vertical engines from becoming duplicate public products."""
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
os.environ.setdefault("SENTRA_SIGNING_KEY", "taxonomy-test-key")
os.environ.setdefault("SZL_SOURCE_REVISION", "7" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_STATE.name) / "taxonomy.sqlite3"))

from app import app  # noqa: E402
from szl_verticals.contract import canonical_vertical  # noqa: E402
from szl_verticals.profiles import ALIASES, VERTICALS  # noqa: E402

CLIENT = TestClient(app)


def test_aegis_sentra_and_immune_have_one_public_home() -> None:
    sentra = VERTICALS["sentra"]
    assert sentra["product"] == "Killinchu Defend"
    assert sentra["public_space"] == "SZLHOLDINGS/killinchu"
    assert sentra["consolidation"]["public_product"] == "Killinchu"
    assert sentra["consolidation"]["sentra_status"] == "INTERNAL_ENGINE"
    assert sentra["consolidation"]["aegis_status"] == "PORTFOLIO_NAME"
    assert sentra["consolidation"]["public_tab"] == "/defend"


def test_defensive_aliases_resolve_to_internal_engine_without_new_space() -> None:
    assert ALIASES["aegis"] == "sentra"
    assert ALIASES["immune"] == "sentra"
    assert ALIASES["defend"] == "sentra"
    for alias in ("aegis", "sentra", "immune", "defend"):
        assert canonical_vertical(alias) == "sentra"


def test_runtime_catalog_names_killinchu_as_public_home() -> None:
    catalog = CLIENT.get("/api/catalog")
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["engines"]["sentra"]["public_home"] == "SZLHOLDINGS/killinchu"
    assert body["engines"]["sentra"]["engine_status"] == "INTERNAL_CAPABILITY_PLANE"
    assert body["engines"]["sentra"]["public_tab"].endswith("/defend")
    assert body["aegis_public_home"] == "SZLHOLDINGS/killinchu"
    assert body["sentra_public_home"] == "SZLHOLDINGS/killinchu"


def test_internal_engine_room_is_truthfully_labelled() -> None:
    page = CLIENT.get("/intelligence/sentra")
    assert page.status_code == 200
    profile = CLIENT.get("/api/verticals/sentra/intelligence")
    assert profile.status_code == 200
    body = profile.json()
    assert body["public_product"] == "Killinchu"
    assert body["public_tab"] == "/defend"
    assert body["engine_status"] == "INTERNAL_CAPABILITY_PLANE"
