import json
from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from deploy.app import app

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "fashion-lineage.v1.json"


class FashionLineageTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

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
        self.assertEqual(body["lanes"][2]["independent_vertical"], False)

    def test_catalog_points_at_fashion(self):
        catalog = self.client.get("/api/catalog").json()
        self.assertEqual(catalog["fashion"], "/api/fashion")
        self.assertEqual(catalog["fashion_rule"], "take the job, never proprietary code")


if __name__ == "__main__":
    unittest.main()
