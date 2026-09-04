import hashlib
import hmac
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
DEPLOY_PATH = str(APP_PATH.parent)
if DEPLOY_PATH not in sys.path:
    sys.path.insert(0, DEPLOY_PATH)

_TEST_STATE_DIR = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "unit-test-key-do-not-use-in-production")
os.environ.setdefault("SZL_SOURCE_REVISION", "1" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_TEST_STATE_DIR.name) / "vertical-services.sqlite3"))


def load_app():
    spec = importlib.util.spec_from_file_location("vertical_services_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class VerticalServicesContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_app()
        cls.client = TestClient(cls.module.app)
        cls.client.headers.update({"X-SZL-Session": "unit-test-session-token-0123456789"})

    def test_root_and_control_plane(self):
        root = self.client.get("/")
        self.assertEqual(root.status_code, 200)
        self.assertIn("Six engines. One second brain.", root.text)
        health = self.client.get("/healthz")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["engines"], list(self.module.ENGINES))
        self.assertFalse(health.json()["compatibility_routes"]["/vessels"]["canonical"] != "/killinchu")
        build = self.client.get("/api/build-info")
        self.assertEqual(build.status_code, 200)
        self.assertFalse(build.json()["receipt_minted"])
        readiness = self.client.get("/readyz")
        self.assertEqual(readiness.status_code, 200)
        self.assertTrue(readiness.json()["ready"])

    def test_every_canonical_engine_health_route(self):
        for engine in self.module.ENGINES:
            with self.subTest(engine=engine):
                response = self.client.get(f"/{engine}/healthz")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["service"], engine)

    def test_stateful_routes_require_and_isolate_session_tokens(self):
        anonymous = TestClient(self.module.app)
        missing = anonymous.post("/lyte/v1/metrics", json={"stream": "private", "value": 1.0})
        self.assertEqual(missing.status_code, 422)
        other = TestClient(
            self.module.app,
            headers={"X-SZL-Session": "other-session-token-01234567890123"},
        )
        hidden = other.get("/lyte/v1/summary?stream=latency")
        self.assertEqual(hidden.status_code, 404)

    def test_sentra_denies_untrusted_and_signs_canonical_receipt(self):
        response = self.client.post(
            "/sentra/v1/evaluate",
            json={
                "actor": "agent-7",
                "action": "delete",
                "resource": "prod:ledger",
                "risk_score": 0.2,
                "authenticated": True,
                "tier": "operator",
                "evidence": ["receipt:test"],
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["decision"], "DENY")
        self.assertIn("g8_not_destructive_unattended", body["failed_gates"])
        signature = body.pop("signature")
        body.pop("receipt_id")
        body.pop("signature_alg")
        body.pop("key_source")
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        expected = hmac.new(
            os.environ["SENTRA_SIGNING_KEY"].encode(),
            canonical.encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(signature, expected)

    def test_lyte_ingest_summary_and_drift(self):
        for index in range(20):
            response = self.client.post(
                "/lyte/v1/metrics",
                json={"stream": "latency", "value": float(index)},
            )
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/lyte/v1/summary?stream=latency").status_code, 200)
        drift = self.client.get("/lyte/v1/drift?stream=latency")
        self.assertEqual(drift.status_code, 200)
        self.assertEqual(drift.json()["truth_label"], "MODELED")

    def test_finance_rejects_non_positive_price_and_calculates(self):
        self.assertEqual(
            self.client.post(
                "/finance/v1/observations",
                json={"symbol": "SZL", "price": 0},
            ).status_code,
            422,
        )
        for price in (100, 103, 99, 106):
            self.assertEqual(
                self.client.post(
                    "/finance/v1/observations",
                    json={"symbol": "SZL", "price": price},
                ).status_code,
                200,
            )
        brief = self.client.get("/finance/v1/symbol/brief?symbol=SZL")
        self.assertEqual(brief.status_code, 200)
        self.assertEqual(brief.json()["truth_label"], "MODELED")

    def test_terra_and_counsel_workflows(self):
        listing = self.client.post(
            "/terra/v1/listings",
            json={
                "market": "Westchester",
                "price": 900000,
                "sqft": 3000,
                "noi_annual": 72000,
            },
        )
        self.assertEqual(listing.status_code, 200)
        analysis = self.client.get("/terra/v1/market/analysis?market=Westchester")
        self.assertEqual(analysis.status_code, 200)
        matter = self.client.post(
            "/counsel/v1/matters",
            json={"title": "Vendor review", "client": "SZL", "exposure_usd": 250000},
        )
        self.assertEqual(matter.status_code, 200)
        matter_id = matter.json()["id"]
        obligation = self.client.post(
            f"/counsel/v1/matters/{matter_id}/obligations",
            json={
                "clause": "8.2",
                "obligation": "Notify within five days",
                "severity": "high",
            },
        )
        self.assertEqual(obligation.status_code, 200)
        docket = self.client.get("/counsel/v1/docket")
        self.assertEqual(docket.status_code, 200)
        self.assertEqual(docket.json()["docket"][0]["high_severity"], 1)

    def test_vessels_is_killinchu_organ_and_not_independent_vertical(self):
        catalog = self.client.get("/api/catalog").json()
        self.assertFalse(catalog["vessels_independent_vertical"])
        self.assertNotIn("vessels", catalog["engines"])
        legacy_health = self.client.get("/vessels/healthz").json()
        self.assertTrue(legacy_health["consolidated"])
        self.assertEqual(legacy_health["public_surface"], "SZLHOLDINGS/killinchu")

        for payload in (
            {"imo": "IMO1234567", "lat": 40.0, "lon": -70.0, "sog": 12.0, "ts": 1000},
            {"imo": "IMO1234567", "lat": 41.0, "lon": -69.0, "sog": 12.0, "ts": 5000},
        ):
            response = self.client.post("/killinchu/v1/maritime/positions", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["vertical"], "killinchu")
        risk = self.client.get("/killinchu/v1/maritime/vessel/risk?imo=IMO1234567")
        self.assertEqual(risk.status_code, 200)
        self.assertEqual(risk.json()["truth_label"], "MODELED")
        self.assertEqual(risk.json()["canonical_surface"], "SZLHOLDINGS/killinchu")

    def test_every_vertical_has_anatomy_formulas_connectors_and_second_brain(self):
        for vertical in self.module.ENGINES:
            with self.subTest(vertical=vertical):
                anatomy = self.client.get(f"/api/verticals/{vertical}/anatomy")
                formulas = self.client.get(f"/api/verticals/{vertical}/formulas")
                connectors = self.client.get(f"/api/verticals/{vertical}/connectors")
                second_brain = self.client.get(f"/api/verticals/{vertical}/second-brain")
                self.assertEqual(anatomy.status_code, 200)
                self.assertEqual(len(anatomy.json()["organs"]), 9)
                self.assertEqual(formulas.status_code, 200)
                self.assertGreater(formulas.json()["count"], 0)
                self.assertEqual(connectors.status_code, 200)
                self.assertGreater(connectors.json()["count"], 0)
                self.assertEqual(second_brain.status_code, 200)
                self.assertEqual(second_brain.json()["vertical"], vertical)
                self.assertFalse(second_brain.json()["effectors_enabled"])

    def test_vessels_alias_resolves_to_killinchu_operational_contract(self):
        anatomy = self.client.get("/api/verticals/vessels/anatomy")
        self.assertEqual(anatomy.status_code, 200)
        self.assertEqual(anatomy.json()["vertical"], "killinchu")
        self.assertEqual(anatomy.json()["consolidation"]["vessels_status"], "CONSOLIDATED")


if __name__ == "__main__":
    unittest.main()
