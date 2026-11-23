# SPDX-License-Identifier: Apache-2.0
# Contract for the holo3d live-estate hologram mount (estate-holo Space).
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"


def holo_parts():
    src = INDEX.read_text(encoding="utf-8")
    i0 = src.index('<style data-holo3d="v1">')
    i1 = src.index("</style>", i0) + len("</style>")
    css = src[i0:i1]
    j0 = src.index('<script data-holo3d="v1">')
    j1 = src.index("</script>", j0) + len("</script>")
    js = src[j0:j1]
    return css, js


class Holo3dContract(unittest.TestCase):

    def test_mount_present_exactly_once(self):
        src = INDEX.read_text(encoding="utf-8")
        self.assertEqual(src.count('data-holo3d="v1"'), 2)
        self.assertEqual(src.count('id="holo-fab"'), 1)
        self.assertEqual(src.count('id="holo-panel"'), 1)
        self.assertEqual(src.count('role="dialog"'), 1)
        self.assertEqual(src.count('aria-modal="true"'), 1)

    def test_feed_same_origin_estate_and_fails_closed(self):
        _, js = holo_parts()
        self.assertIn('var FEED = "/api/estate"', js)
        self.assertIn('credentials: "same-origin"', js)
        self.assertIn('cache: "no-store"', js)
        self.assertIn("failing closed", js)
        self.assertIn("LIVE ESTATE DATA", js)
        self.assertIn("ESTATE UNREACHABLE", js)
        self.assertIn("prefers-reduced-motion", js)
        self.assertIn('"Escape"', js)
        for forbidden in ("localStorage", "sessionStorage", "indexedDB", "WebSocket", "EventSource", "sendBeacon", "document.cookie", "eval(", "new Function", "http://", "https://"):
            self.assertNotIn(forbidden, js)

    def test_collect_nodes_handles_estate_shapes(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node unavailable")
        _, js = holo_parts()
        start = js.index("function collectNodes")
        end = js.index("function fetchFeed")
        source = js[start:end]
        harness = (
            source
            + "var r1 = collectNodes({models: ['SZLHOLDINGS/a', 'SZLHOLDINGS/b'], spaces: ['SZLHOLDINGS/counsel']});"
            + "var r2 = collectNodes({models: {_unavailable: 'x'}, spaces: null});"
            + "var r3 = collectNodes(null);"
            + "var big = []; for (var i = 0; i < 300; i++) { big.push('m' + i); }"
            + "var r4 = collectNodes({models: big, spaces: []});"
            + "var r5 = collectNodes({models: [{id: 'SZLHOLDINGS/x'}, {name: 'SZLHOLDINGS/y'}], spaces: []});"
            + "console.log(r1.join(','));"
            + "console.log(r2.length + ',' + r3.length + ',' + r4.length);"
            + "console.log(r5.join(','));"
        )
        proc = subprocess.run([node, "-e", harness], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
        parts = proc.stdout.strip().splitlines()
        self.assertEqual(parts[0], "SZLHOLDINGS/a,SZLHOLDINGS/b,SZLHOLDINGS/counsel")
        self.assertEqual(parts[1], "0,0,96")
        self.assertEqual(parts[2], "SZLHOLDINGS/x,SZLHOLDINGS/y")

    def test_css_cosmetic_and_accessible(self):
        css, _ = holo_parts()
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("forced-colors", css)
        self.assertIn("44px", css)
        self.assertNotIn("@import", css)
        self.assertNotIn("url(", css)

    def test_client_is_valid_javascript(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node unavailable")
        _, js = holo_parts()
        body = js[js.index(">") + 1: js.rindex("</script>")]
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(body)
            path = fh.name
        proc = subprocess.run([node, "--check", path], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])

    def test_page_declares_honest_disclosure(self):
        src = INDEX.read_text(encoding="utf-8")
        for marker in ("LIVE ESTATE DATA", "procedural", "not a measured topology", "Fails closed", "/api/estate"):
            self.assertIn(marker, src)


if __name__ == "__main__":
    unittest.main()
