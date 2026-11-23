# SPDX-License-Identifier: Apache-2.0
"""SZL Holdings live estate hologram - stdlib HTTP, fail-closed.

Serves the holo3d estate constellation client (index.html) and /api/estate,
which pulls the SZLHOLDINGS model and space inventory from the Hugging Face
Hub at request time. Pull failures become honest UNAVAILABLE blobs; the
client fails closed and never fabricates nodes. Node positions are
procedural (Fibonacci sphere); this is not a measured topology.
"""
from __future__ import annotations

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HF = "https://huggingface.co/api"
HTML = Path(__file__).with_name("index.html")
SCHEMA = "szl.estate-holo/v1"


def pull(url, timeout=10):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "szl-estate-holo/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode())
    except Exception as exc:
        return {"_unavailable": str(exc), "url": url, "honesty": "UNAVAILABLE"}


def estate():
    models = pull(HF + "/models?author=SZLHOLDINGS&limit=100")
    spaces = pull(HF + "/spaces?author=SZLHOLDINGS&limit=100")

    def ids(blob):
        if isinstance(blob, list):
            return [x.get("id") for x in blob if isinstance(x, dict) and x.get("id")]
        return blob

    return {"schema": SCHEMA, "models": ids(models), "spaces": ids(spaces)}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = HTML.read_bytes() if HTML.exists() else b"<h1>estate-holo</h1>"
            self._send(200, body, "text/html; charset=utf-8")
            return
        if path == "/api/estate":
            self._send(200, json.dumps(estate()).encode(), "application/json")
            return
        if path == "/healthz":
            self._send(200, json.dumps({"ok": True, "schema": SCHEMA, "status": "PROCESS_ALIVE", "honesty": "process liveness only; estate pull freshness is per-request and fails closed"}).encode(), "application/json")
            return
        self._send(404, b'{"error":"not found"}', "application/json")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7860"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
