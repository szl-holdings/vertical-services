import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "deploy" / "app.py"
CONTRACT = ROOT / "contracts" / "fashion-lineage.v1.json"
DEPLOY_PATH = str(APP_PATH.parent)
if DEPLOY_PATH not in sys.path:
    sys.path.insert(0, DEPLOY_PATH)

_TEST_STATE_DIR = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "unit-test-key-do-not-use-in-production")
os.environ.setdefault("SZL_SOURCE_REVISION", "1" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_TEST_STATE_DIR.name) / "vertical-services.sqlite3"))


def load_app():
    spec = importlib.util.spec_from_file_location("vertical_services_app_fashion", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FashionLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_app()
        cls.client = TestClient(cls.module.app)

    def test_contract_has_nine_lanes_and_https_sources(self):
        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "szl.fashion-lineage/v1")
        self.assertEqual(len(payload["lanes"]), 9)
        for lane in payload["lanes"]:
            self.assertTrue(lane["job"])
            self.assertTrue(lane["tweak"])
            self.assertTrue(lane["szl_software"])
            self.assertTrue(all(url.startswith("https://") for url in lane["sources"]))

    def test_api_fashion_serves_the_contract(self):
        response = self.client.get("/api/fashion")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["schema"], "szl.fashion-lineage/v1")
        self.assertEqual(body["served_from"], "contracts/fashion-lineage.v1.json")
        vessels = next(lane for lane in body["lanes"] if lane["id"] == "vessels")
        self.assertFalse(vessels["independent_vertical"])

    def test_catalog_points_at_fashion(self):
        catalog = self.client.get("/api/catalog").json()
        self.assertEqual(catalog["fashion"], "/api/fashion")
        self.assertEqual(catalog["fashion_rule"], "take the job, never proprietary code")


if __name__ == "__main__":
    unittest.main()
