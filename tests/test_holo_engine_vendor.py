# SPDX-License-Identifier: Apache-2.0
"""Contract for the vendored three.js r170 WebGPU engine used by holo3d.

The engine is the one external file the holo front door may load. It must be the
exact pinned bytes, be served same-origin, be re-verified in the browser, and
never weaken the honesty rules of the v1/v2 contracts.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = str(ROOT / "deploy")
if DEPLOY not in sys.path:
    sys.path.insert(0, DEPLOY)

_STATE = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "unit-test-key-do-not-use-in-production")
os.environ.setdefault("SZL_SOURCE_REVISION", "2" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_STATE.name) / "holo-engine.sqlite3"))

# Pinned in szl-holdings/a11oy static/3d/vendor/VENDOR_MANIFEST.md (three@0.170.0, MIT).
PINNED_BYTES = 822115
PINNED_SHA256 = "9d01bb1bae1badb5071d341f76c3569f6118bad126effd425a06611a9d993035"


def load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HoloEngineVendor(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = load("szl_holo_engine", "deploy/szl_verticals/holo_engine.py")
        cls.holo = load("szl_holo3d_engine_test", "deploy/szl_verticals/holo3d.py")
        import app as app_module  # noqa: PLC0415

        cls.client = TestClient(app_module.app)

    def test_vendored_file_matches_the_pin_byte_for_byte(self) -> None:
        data = self.engine.ENGINE_PATH.read_bytes()
        self.assertEqual(len(data), PINNED_BYTES)
        self.assertEqual(hashlib.sha256(data).hexdigest(), PINNED_SHA256)
        self.assertEqual(self.engine.ENGINE_BYTES, PINNED_BYTES)
        self.assertEqual(self.engine.ENGINE_SHA256, PINNED_SHA256)
        self.assertIsNotNone(self.engine.load_pinned_engine())

    def test_upstream_license_and_version_are_embedded_and_self_contained(self) -> None:
        text = self.engine.ENGINE_PATH.read_bytes().decode("utf-8")
        self.assertIn("SPDX-License-Identifier: MIT", text[:400])
        self.assertIn('const e="170"', text[:400])
        # One import-free module: it cannot pull a second, unpinned file.
        self.assertIsNone(re.search(r"\bimport\s*\(", text))
        self.assertIsNone(re.search(r"\bfrom\s*[\"']", text))

    def test_a_tampered_or_missing_copy_is_never_served(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "engine.js"
            bad.write_bytes(self.engine.ENGINE_PATH.read_bytes() + b"\n")
            self.assertIsNone(self.engine.load_pinned_engine(bad))
            bad.write_bytes(b"x" * PINNED_BYTES)
            self.assertIsNone(self.engine.load_pinned_engine(bad))
            self.assertIsNone(self.engine.load_pinned_engine(Path(tmp) / "missing.js"))

    def test_route_serves_the_exact_bytes_same_origin_with_immutable_cache(self) -> None:
        res = self.client.get(self.engine.ENGINE_ROUTE)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(hashlib.sha256(res.content).hexdigest(), PINNED_SHA256)
        self.assertEqual(len(res.content), PINNED_BYTES)
        self.assertTrue(res.headers["content-type"].startswith("text/javascript"))
        self.assertIn("immutable", res.headers["cache-control"])
        self.assertEqual(res.headers["etag"], f'"sha256-{PINNED_SHA256}"')
        self.assertEqual(res.headers["x-content-type-options"], "nosniff")
        self.assertEqual(res.headers["cross-origin-resource-policy"], "same-site")
        # Everything else stays uncacheable, exactly as before.
        self.assertEqual(self.client.get("/api/build-info").headers["cache-control"], "no-store")

    def test_server_withholds_the_route_when_the_pin_fails(self) -> None:
        import app as app_module  # noqa: PLC0415

        saved = app_module._HOLO_ENGINE
        app_module._HOLO_ENGINE = None
        try:
            self.assertEqual(self.client.get(self.engine.ENGINE_ROUTE).status_code, 404)
        finally:
            app_module._HOLO_ENGINE = saved

    def test_client_pins_match_the_server_pins_and_verify_before_import(self) -> None:
        js = self.holo.HOLO3D_JS
        self.assertIn(f'url: "{self.engine.ENGINE_ROUTE}"', js)
        self.assertIn(f"bytes: {PINNED_BYTES}", js)
        self.assertIn(f'sha: "{PINNED_SHA256}"', js)
        self.assertEqual(js.count("import("), 1)
        digest = js.index('digest("SHA-256"')
        self.assertLess(js.index("buf.byteLength !== ENGINE.bytes"), digest)
        self.assertLess(digest, js.index("import(URL.createObjectURL"))
        self.assertIn("hex(d) !== ENGINE.sha", js)
        # The engine is fetched anonymously and the only imported specifier is the verified blob.
        self.assertIn('credentials: "omit"', js)
        self.assertNotIn("importScripts", js)

    def test_the_only_allowed_external_asset_is_that_one_pinned_file(self) -> None:
        holo = self.holo
        everything = holo.HOLO3D_JS + holo.HOLO3D_CSS + holo.HOLO3D_PANEL_HTML
        for forbidden in ("http://", "https://", "<script", "src=", "url(", "@import", "<link", "<iframe"):
            self.assertNotIn(forbidden, everything)
        routes = re.findall(r'"(/[A-Za-z0-9_./-]*\.(?:js|mjs|css|wasm|json|png|svg|woff2?))"', holo.HOLO3D_JS)
        self.assertEqual(routes, [self.engine.ENGINE_ROUTE])

    def test_raw_webgl_fallback_and_honest_engine_labels_remain(self) -> None:
        js = self.holo.HOLO3D_JS
        self.assertIn("function initGL()", js)
        self.assertIn('st.mode = "raw"', js)
        self.assertIn("ENGINE raw WebGL fallback", js)
        self.assertIn("sha256 verified in this browser", js)
        self.assertIn("engine integrity check failed or unavailable", js)
        # The three.js path must never replace the honesty vocabulary or the text alternative.
        for token in ("ILLUSTRATIVE LAYOUT", "failing closed", "READING AGE"):
            self.assertIn(token, js)
        self.assertIn('id="holo-readout"', self.holo.HOLO3D_PANEL_HTML)

    def test_gaps_are_drawn_as_the_dashed_ring_with_x_the_key_promises(self) -> None:
        js = self.holo.HOLO3D_JS
        self.assertIn("DASHED RING WITH X = gap", js)
        self.assertIn("nd.kind === K.GAP", js)
        self.assertIn("gaps.push(", js)

    def test_engine_glue_is_valid_javascript_and_bounded(self) -> None:
        import shutil
        import subprocess

        node = shutil.which("node")
        if node is None:
            self.skipTest("node unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "holo.js"
            path.write_text(self.holo.HOLO3D_JS, encoding="utf-8")
            done = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, timeout=30)
            self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(5_000 < len(self.holo.HOLO3D_JS) < 45_000)


if __name__ == "__main__":
    unittest.main()
