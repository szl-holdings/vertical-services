# SPDX-License-Identifier: Apache-2.0
"""Contract for the holo3d front-door mount (3D engine constellation)."""
from __future__ import annotations

import py_compile
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H3 = ROOT / "deploy" / "szl_verticals" / "holo3d.py"
APP = ROOT / "deploy" / "app.py"


def load_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("szl_holo3d", H3)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Holo3dContract(unittest.TestCase):
    def test_constants_are_bounded(self) -> None:
        m = load_module()
        self.assertTrue(2_000 < len(m.HOLO3D_CSS) < 20_000)
        self.assertTrue(5_000 < len(m.HOLO3D_JS) < 45_000)
        self.assertTrue(500 < len(m.HOLO3D_PANEL_HTML) < 6_000)

    def test_panel_has_dialog_semantics(self) -> None:
        panel = load_module().HOLO3D_PANEL_HTML
        self.assertEqual(panel.count('role="dialog"'), 1)
        self.assertEqual(panel.count('aria-modal="true"'), 1)
        self.assertEqual(panel.count('aria-haspopup="dialog"'), 1)
        self.assertIn('id="holo-canvas" tabindex="0"', panel)
        self.assertIn("ILLUSTRATIVE LAYOUT", panel)

    def test_app_wires_the_mount_exactly_once(self) -> None:
        src = APP.read_text(encoding="utf-8")
        self.assertEqual(src.count("holo3d import HOLO3D_CSS, HOLO3D_JS, HOLO3D_PANEL_HTML"), 1)
        self.assertEqual(src.count("{HOLO3D_CSS}"), 1)
        self.assertEqual(src.count("{HOLO3D_JS}"), 1)
        self.assertEqual(src.count("{HOLO3D_PANEL_HTML}"), 1)
        self.assertEqual(src.count("<script>{HOLO3D_JS}</script>"), 1)
        self.assertEqual(src.count("{NATIVE_INTERFACE_CSS}"), 1)

    def test_client_is_same_origin_fails_closed_and_honest(self) -> None:
        js = load_module().HOLO3D_JS
        self.assertIn('var FEED = "/api/catalog"', js)
        self.assertIn('credentials: "same-origin"', js)
        self.assertIn('cache: "no-store"', js)
        self.assertIn("failing closed", js)
        self.assertIn("ILLUSTRATIVE LAYOUT", js)
        self.assertIn("prefers-reduced-motion", js)
        self.assertIn("ResizeObserver", js)
        self.assertIn('e.key === "Escape"', js)
        self.assertIn("Object.keys(raw)", js)
        for forbidden in (
            "localStorage",
            "sessionStorage",
            "indexedDB",
            "WebSocket",
            "EventSource",
            "sendBeacon",
            "document.cookie",
            "eval(",
            "new Function",
            "http://",
            "https://",
        ):
            self.assertNotIn(forbidden, js)

    def test_collect_nodes_handles_live_catalog_shapes(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node unavailable for behavior check")
        js = load_module().HOLO3D_JS
        start = js.index("function collectNodes")
        end = js.index("function fetchFeed")
        source = js[start:end]
        harness = (
            source
            + chr(10)
            + 'var r1 = collectNodes({engines: {sentra: {aliases: ["alpha", "beta"]}}});'
            + chr(10)
            + 'var r2 = collectNodes({engines: [{name: "x", models: ["m1"]}, {name: "y", aliases: ["a1"]}]});'
            + chr(10)
            + "var r3 = collectNodes({});"
            + chr(10)
            + "var r4 = collectNodes(null);"
            + chr(10)
            + 'console.log(r1.join(","));'
            + chr(10)
            + 'console.log(r2.join(","));'
            + chr(10)
            + 'console.log(r3.join(","));'
            + chr(10)
            + 'console.log(r4.join("@"));'
            + chr(10)
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(harness)
            name = handle.name
        try:
            result = subprocess.run(
                [node, name], capture_output=True, text=True, timeout=30, check=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            Path(name).unlink(missing_ok=True)
        parts = result.stdout.split(chr(10))
        self.assertEqual(parts[0], "sentra,alpha,beta")
        self.assertEqual(parts[1], "x,m1,y,a1")
        self.assertEqual(parts[2], "")
        self.assertEqual(parts[3], "")

    def test_css_is_cosmetic_only_and_accessible(self) -> None:
        css = load_module().HOLO3D_CSS
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("forced-colors", css)
        self.assertIn("min-height:44px", css)
        self.assertNotIn("@import", css)
        self.assertNotIn("url(", css)

    def test_python_modules_compile(self) -> None:
        py_compile.compile(str(H3), doraise=True)
        py_compile.compile(str(APP), doraise=True)

    def test_client_is_valid_javascript(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node unavailable for syntax check")
        js = load_module().HOLO3D_JS
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
            handle.write(js)
            name = handle.name
        try:
            result = subprocess.run(
                [node, "--check", name], capture_output=True, text=True, timeout=30, check=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            Path(name).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
