# SPDX-License-Identifier: Apache-2.0
"""Contract for holo3d v2: the vertical frontier scene model against the real server payloads.

The client model (the V2-MODEL block of HOLO3D_JS) is executed under node and
fed the actual /api/verticals/{vertical}/frontier payloads produced by the
in-process app, plus synthetic payloads for the failure paths. The tests pin the
honesty rules: labels are never upgraded, absent data is drawn as a labelled
gap, unknown labels never become solid, the layout is digest-seeded and
reproducible, and malformed feeds fail closed.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
H3 = ROOT / "deploy" / "szl_verticals" / "holo3d.py"
APP_PATH = ROOT / "deploy" / "app.py"
DEPLOY_PATH = str(APP_PATH.parent)
if DEPLOY_PATH not in sys.path:
    sys.path.insert(0, DEPLOY_PATH)

_STATE = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "unit-test-key-do-not-use-in-production")
os.environ.setdefault("SZL_SOURCE_REVISION", "2" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_STATE.name) / "holo-v2.sqlite3"))

VERTICALS = ["finance", "terra", "counsel", "lyte", "killinchu", "sentra"]


def load_holo():
    spec = importlib.util.spec_from_file_location("szl_holo3d_v2", H3)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def model_source() -> str:
    js = load_holo().HOLO3D_JS
    start = js.index("/* V2-MODEL-BEGIN")
    end = js.index("/* V2-MODEL-END */")
    return js[start:end]


def run_model(cases: list[dict]) -> list[dict]:
    """Run buildVerticalScene for each case under node; return JSON-safe summaries."""
    node = shutil.which("node")
    if node is None:
        raise unittest.SkipTest("node unavailable for model behaviour checks")
    harness = (
        model_source()
        + "\nvar cases = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));\n"
        + "var out = cases.map(function (c) {\n"
        + "  if (c.fn === 'kindForLabel') { return { kind: kindForLabel(c.arg) }; }\n"
        + "  if (c.fn === 'kindForStatus') { return { kind: kindForStatus(c.arg) }; }\n"
        + "  if (c.fn === 'lambdaCheck') { return lambdaCheck(c.axes, c.weights, c.score); }\n"
        + "  var s = buildVerticalScene(c.payload, c.key, 0);\n"
        + "  if (!s) { return null; }\n"
        + "  return { nodes: s.nodes.map(function (n) { return { label: n.label, kind: n.kind, group: n.group, text: n.text, pos: n.pos, val: n.val }; }),\n"
        + "           lines: s.lines.map(function (l) { return { kind: l.kind }; }),\n"
        + "           chips: s.chips.map(function (x) { return x[0]; }), gaps: s.gaps, frayFrom: s.frayFrom,\n"
        + "           lambda: s.lambda, readout: s.readout };\n"
        + "});\nconsole.log(JSON.stringify(out));\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        js_path = Path(tmp) / "model.js"
        in_path = Path(tmp) / "cases.json"
        js_path.write_text(harness, encoding="utf-8")
        in_path.write_text(json.dumps(cases), encoding="utf-8")
        result = subprocess.run(
            [node, str(js_path), str(in_path)], capture_output=True, text=True, timeout=60, check=False
        )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class Holo3dV2Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("vertical_services_app_holo_v2", APP_PATH)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        cls.module = module
        cls.client = TestClient(module.app)
        cls.payloads = {}
        for vertical in VERTICALS:
            res = cls.client.get(f"/api/verticals/{vertical}/frontier")
            assert res.status_code == 200, (vertical, res.status_code)
            cls.payloads[vertical] = res.json()

    # ---- static surface --------------------------------------------------
    def test_view_buttons_match_the_catalog_and_the_client_whitelist(self) -> None:
        holo = load_holo()
        catalog = set(self.module.CATALOG)
        self.assertEqual(catalog, set(VERTICALS))
        panel = holo.HOLO3D_PANEL_HTML
        for vertical in VERTICALS:
            self.assertEqual(panel.count(f'data-view="{vertical}"'), 1, vertical)
        self.assertEqual(panel.count('data-view="engines"'), 1)
        self.assertIn('var VERTICALS = ["finance", "terra", "counsel", "lyte", "killinchu", "sentra"]', holo.HOLO3D_JS)
        self.assertEqual(panel.count("data-view="), 7)

    def test_frontier_feed_is_same_origin_read_only_and_bounded(self) -> None:
        js = load_holo().HOLO3D_JS
        self.assertIn('"/api/verticals/" + encodeURIComponent(key) + "/frontier"', js)
        self.assertEqual(js.count('credentials: "same-origin"'), 2)
        self.assertEqual(js.count('cache: "no-store"'), 2)
        for forbidden in ('method: "POST"', "X-SZL-Session", "/fetch", "/receipt", "innerHTML", "outerHTML", "insertAdjacentHTML"):
            self.assertNotIn(forbidden, js)
        self.assertIn("failing closed", js)
        self.assertIn("FRONTIER UNREACHABLE", js)
        self.assertTrue(5_000 < len(js) < 45_000)

    def test_text_alternative_and_focus_order_exist(self) -> None:
        holo = load_holo()
        self.assertIn('id="holo-readout"', holo.HOLO3D_PANEL_HTML)
        self.assertIn("<details", holo.HOLO3D_PANEL_HTML)
        self.assertIn('var VIEWS_ID = "holo-views"', holo.HOLO3D_JS)
        self.assertIn('VIEWS_ID + " button"', holo.HOLO3D_JS)
        self.assertIn("min-height:44px", holo.HOLO3D_CSS)
        self.assertNotIn("url(", holo.HOLO3D_CSS)

    # ---- honesty mapping --------------------------------------------------
    def test_labels_are_never_upgraded(self) -> None:
        cases = [{"fn": "kindForLabel", "arg": a} for a in
                 ("MEASURED", "MODELED", "SAMPLE", "ROADMAP", "UNAVAILABLE", "REPORTED", "VERIFIED", "", "measured", None)]
        got = [r["kind"] for r in run_model(cases)]
        # solid=0 wire=1 points=2 outline=3 gap=4 reported-ring=5
        self.assertEqual(got, [0, 1, 2, 3, 4, 5, 3, 3, 3, 3])
        self.assertNotEqual(got[5], 0, "REPORTED must never render as MEASURED/solid")

    def test_statuses_map_only_through_the_declared_table(self) -> None:
        statuses = ["TESTED_IMPLEMENTATION", "TESTED_TRANSFORM", "DETERMINISTIC_IMPLEMENTATION", "MODELED",
                    "MODELED_ADVISORY", "ADVISORY", "ADVISORY_THRESHOLD", "POLICY_PARAMETER",
                    "PROVEN", "MEASURED", "__proto__", "constructor"]
        got = [r["kind"] for r in run_model([{"fn": "kindForStatus", "arg": s} for s in statuses])]
        self.assertEqual(got, [0, 0, 0, 1, 1, 3, 3, 3, 3, 3, 3, 3])

    def test_lambda_recompute_is_a_weighted_geometric_mean(self) -> None:
        ok, bad, zero, invalid = run_model([
            {"fn": "lambdaCheck", "axes": {"a": 1.0, "b": 0.5}, "weights": {"a": 0.5, "b": 0.5}, "score": 0.707107},
            {"fn": "lambdaCheck", "axes": {"a": 1.0, "b": 0.5}, "weights": {"a": 0.5, "b": 0.5}, "score": 0.9},
            {"fn": "lambdaCheck", "axes": {"a": 0.0, "b": 1.0}, "weights": {"a": 0.5, "b": 0.5}, "score": 0.0},
            {"fn": "lambdaCheck", "axes": {"a": 1.5}, "weights": {"a": 1.0}, "score": 1.0},
        ])
        self.assertTrue(ok["agrees"])
        self.assertFalse(bad["agrees"])
        self.assertEqual(zero["local"], 0)
        self.assertIsNone(invalid)

    # ---- real server payloads --------------------------------------------
    def test_every_vertical_renders_its_real_payload_without_inventing_data(self) -> None:
        results = run_model([{"payload": self.payloads[v], "key": v} for v in VERTICALS])
        for vertical, scene in zip(VERTICALS, results):
            payload = self.payloads[vertical]
            self.assertIsNotNone(scene, vertical)
            organs = payload["anatomy"]["organs"]
            formulas = payload["formulas"]
            connectors = payload["connectors"]
            axes = payload["readiness"]["lambda_advisory"]["axes"]
            groups = [n["group"] for n in scene["nodes"]]
            self.assertEqual(groups.count("core"), 1)
            self.assertEqual(groups.count("organ"), len(organs), vertical)
            self.assertEqual(groups.count("formula"), len(formulas), vertical)
            self.assertEqual(groups.count("connector"), len(connectors), vertical)
            self.assertEqual(groups.count("lambda"), len(axes), vertical)
            self.assertEqual(len(scene["readout"]), len(scene["nodes"]))
            # Every formula keeps the exact server status string as text.
            by_label = {n["label"]: n for n in scene["nodes"]}
            for formula in formulas:
                node = by_label[formula["id"][:48]]
                self.assertIn(f"status {formula['status']}", node["text"], (vertical, formula["id"]))
                self.assertNotIn("UNRECOGNISED", node["text"], (vertical, formula["id"]))
            # No reading was fetched: every connector is a labelled gap or non-solid.
            for connector in connectors:
                node = by_label[connector["id"][:48]]
                self.assertNotEqual(node["kind"], 0, "a connector with no reading must never be solid")
                self.assertIn(f"contract state {connector['state']}", node["text"])
            # Lambda is recomputed and agrees with the server value, and is labelled advisory.
            self.assertTrue(scene["lambda"]["agrees"], vertical)
            self.assertTrue(any("MODELED, not an admission" in c for c in scene["chips"]), vertical)
            self.assertTrue(any("ILLUSTRATIVE LAYOUT" in c for c in scene["chips"]))
            self.assertTrue(any("none minted" in c for c in scene["chips"]))
            for chip in scene["chips"]:
                self.assertNotIn("MEASURED reading", chip)
            for node in scene["nodes"]:
                self.assertEqual(len(node["pos"]), 3)
                self.assertTrue(all(isinstance(c, (int, float)) and abs(c) < 3 for c in node["pos"]), node)

    def test_counsel_auth_required_connector_is_a_visible_gap_with_its_reason(self) -> None:
        scene = run_model([{"payload": self.payloads["counsel"], "key": "counsel"}])[0]
        by_label = {n["label"]: n for n in scene["nodes"]}
        gap = by_label["congress-bills"]
        self.assertEqual(gap["kind"], 4)
        self.assertIn("GAP reason: auth_required", gap["text"])
        other = by_label["federal-register"]
        self.assertEqual(other["kind"], 4)
        self.assertIn("no_reading_in_scope", other["text"])
        self.assertEqual(scene["gaps"], 2)

    def test_layout_is_digest_seeded_and_reproducible(self) -> None:
        payload = self.payloads["finance"]
        tampered = copy.deepcopy(payload)
        tampered["source"]["source_revision"] = "f" * 40
        a1, a2, b = run_model([
            {"payload": payload, "key": "finance"},
            {"payload": payload, "key": "finance"},
            {"payload": tampered, "key": "finance"},
        ])
        self.assertEqual([n["pos"] for n in a1["nodes"]], [n["pos"] for n in a2["nodes"]])
        self.assertNotEqual([n["pos"] for n in a1["nodes"]], [n["pos"] for n in b["nodes"]])
        self.assertEqual([n["label"] for n in a1["nodes"]], [n["label"] for n in b["nodes"]])

    # ---- failure paths ----------------------------------------------------
    def test_cord_frays_from_the_first_unmet_requirement_only(self) -> None:
        intact, frayed = run_model([
            {"payload": self.payloads["finance"], "key": "finance"},
            {"payload": self._with_unmet("finance", "formula_registry_bound"), "key": "finance"},
        ])
        self.assertEqual(intact["frayFrom"], -1)
        self.assertEqual([l["kind"] for l in intact["lines"]].count(12), 0)
        self.assertEqual(intact["lines"][0]["kind"], 11)
        organs = self.payloads["finance"]["anatomy"]["organs"]
        idx = next(i for i, o in enumerate(organs) if o["id"] == "formula")
        self.assertEqual(frayed["frayFrom"], idx)
        cord = [l["kind"] for l in frayed["lines"][: len(organs) - 1]]
        self.assertEqual(cord[:idx], [11] * idx)
        self.assertEqual(cord[idx:], [12] * (len(organs) - 1 - idx))
        organ_nodes = [n for n in frayed["nodes"] if n["group"] == "organ"]
        self.assertEqual(organ_nodes[idx]["kind"], 4)
        self.assertIn("requirement formula_registry_bound not met", organ_nodes[idx]["text"])

    def _with_unmet(self, vertical: str, requirement: str) -> dict:
        payload = copy.deepcopy(self.payloads[vertical])
        payload["readiness"]["requirements"][requirement] = False
        return payload

    def test_malformed_or_mismatched_feeds_fail_closed(self) -> None:
        good = self.payloads["lyte"]
        wrong_schema = dict(good, schema="szl.something-else/v1")
        wrong_vertical = dict(good, vertical="finance", requested_vertical="finance")
        results = run_model([
            {"payload": None, "key": "lyte"},
            {"payload": [], "key": "lyte"},
            {"payload": wrong_schema, "key": "lyte"},
            {"payload": wrong_vertical, "key": "lyte"},
            {"payload": {"schema": "szl.vertical-frontier/v3", "vertical": "lyte"}, "key": "lyte"},
        ])
        self.assertIsNone(results[0])
        self.assertIsNone(results[1])
        self.assertIsNone(results[2])
        self.assertIsNone(results[3])
        sparse = results[4]
        self.assertIsNotNone(sparse)
        self.assertTrue(any("READINESS ABSENT" in c for c in sparse["chips"]))
        self.assertEqual([n["group"] for n in sparse["nodes"]], ["core"])

    def test_unknown_statuses_and_control_text_are_neutralised(self) -> None:
        payload = copy.deepcopy(self.payloads["lyte"])
        payload["formulas"][0]["status"] = "VERIFIED_BY_MAGIC"
        payload["formulas"][0]["name"] = "<img src=x onerror=alert(1)>\u0000\u202e" + "x" * 500
        scene = run_model([{"payload": payload, "key": "lyte"}])[0]
        node = next(n for n in scene["nodes"] if n["group"] == "formula")
        self.assertEqual(node["kind"], 3)
        self.assertIn("UNRECOGNISED STATUS", node["text"])
        self.assertLessEqual(len(node["text"]), 220)
        self.assertNotIn("\u0000", node["text"])
        self.assertNotIn("\u202e", node["text"])

    def test_session_scoped_connector_reading_is_not_attributed_or_solid(self) -> None:
        payload = copy.deepcopy(self.payloads["finance"])
        payload["readiness"]["live_data"].update({"observed_in_scope": True, "observations": 2, "connectors_observed": 1})
        scene = run_model([{"payload": payload, "key": "finance"}])[0]
        connectors = [n for n in scene["nodes"] if n["group"] == "connector"]
        self.assertTrue(all(n["kind"] == 3 for n in connectors))
        self.assertTrue(all("reading_not_attributed_per_connector" in n["text"] for n in connectors))
        self.assertTrue(any("1 of 5 connectors" in c for c in scene["chips"]))


if __name__ == "__main__":
    unittest.main()
