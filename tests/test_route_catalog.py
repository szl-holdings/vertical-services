"""`/api/catalog` must name exactly the operational routes the app mounts.

`operational_fabric` is hand-maintained. #48 mounted the evidence withdraw and
assessment routes without listing them, so this ties the catalog to the routes
FastAPI actually serves: a new `/api/verticals` route cannot ship uncatalogued,
and a catalogued path cannot outlive its route.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "deploy" / "app.py"
DEPLOY_PATH = str(APP_PATH.parent)
if DEPLOY_PATH not in sys.path:
    sys.path.insert(0, DEPLOY_PATH)

_TEST_STATE_DIR = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "unit-test-key-do-not-use-in-production")
os.environ.setdefault("SZL_SOURCE_REVISION", "1" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_TEST_STATE_DIR.name) / "vertical-services.sqlite3"))

# The operational fabric is every per-vertical API route plus the two HTML surfaces.
OPERATIONAL_PREFIXES = ("/api/verticals", "/experience/", "/intelligence/")


def load_app():
    spec = importlib.util.spec_from_file_location("vertical_services_app_catalog", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_operational_fabric_names_every_mounted_operational_route():
    module = load_app()
    mounted = {
        route.path
        for route in module.app.routes
        if isinstance(route, APIRoute) and route.path.startswith(OPERATIONAL_PREFIXES)
    }
    response = TestClient(module.app).get("/api/catalog")
    assert response.status_code == 200
    fabric = response.json()["operational_fabric"]
    listed = set(fabric.values())

    assert len(listed) == len(fabric), "two catalog keys name the same route"
    assert "/api/verticals/{vertical}/evidence/withdraw" in mounted
    assert sorted(mounted - listed) == [], "mounted but missing from operational_fabric"
    assert sorted(listed - mounted) == [], "listed in operational_fabric but not mounted"
