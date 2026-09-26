"""The post-deploy probe must read readiness while its own observations are live.

Readiness ``live_data`` counts only unexpired observations. The fake runtime
below applies the real connector freshness windows and lets every fetch take
30 simulated seconds, so a probe that reads Lyte's readiness only after every
other source (Lyte's connector is fresh for 120 s) would see it expired.
No network access.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "deploy") not in sys.path:
    sys.path.insert(0, str(ROOT / "deploy"))

from szl_verticals.connector_specs import CONNECTORS  # noqa: E402

# Load the probe by path so this file also runs on its own from any directory,
# not only when the repository root happens to be the working directory.
_SPEC = importlib.util.spec_from_file_location(
    "probe_live_verticals_under_test", ROOT / "tools" / "probe_live_verticals.py")
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)

FETCH_SECONDS = 30.0


def fake_runtime():
    state = {"now": 0.0, "expiry": {}}

    def handler(request: httpx.Request) -> httpx.Response:
        parts = request.url.path.strip("/").split("/")
        if request.method == "POST" and parts[-1] == "fetch":
            vertical, connector = parts[2], parts[4]
            state["now"] += FETCH_SECONDS
            state["expiry"].setdefault(vertical, []).append(
                state["now"] + CONNECTORS[connector].freshness_seconds)
            return httpx.Response(200, json={
                "receipt": {"state": "OBSERVED", "receipt_id": "a" * 64,
                            "payload_sha256": "b" * 64, "source_url": "https://source.test/"},
                "signal": {}, "cache": "MISS",
                "observation": {"trading_enabled": False, "custody_enabled": False,
                                "person_level_prospecting": False},
            })
        if parts[:2] == ["api", "verticals"] and parts[-1] == "readyz":
            live = any(expires > state["now"] for expires in state["expiry"].get(parts[2], ()))
            return httpx.Response(200, json={"ready": True, "status": "READY",
                                             "live_data": {"observed_in_scope": live}})
        if parts[0] == "experience":
            _, title, motif = probe.EXPERIENCES[parts[1]]
            return httpx.Response(200, text=(
                f'<title>{title}</title><meta content="viewport-fit=cover">'
                f'<main data-motif="{motif}"></main>'
                "<style>@media(prefers-reduced-motion:reduce){*{animation:none}}</style>"))
        if parts[:2] == ["api", "verticals"] and parts[-1] == "frontier":
            return httpx.Response(200, json={
                "vertical": probe.EXPERIENCES[parts[2]][0],
                "source": {"build": {"revision": "c" * 40}},
                "hatun": {"can_authorize": False, "effectors_enabled": False},
            })
        if request.url.path == "/readyz":
            return httpx.Response(200, json={"ready": True})
        if request.url.path == "/api/build-info":
            return httpx.Response(200, json={"build": {"state": "OBSERVED"},
                                             "source_binding": {"bindings_agree": True}})
        return httpx.Response(404, json={"detail": "not found"})

    return handler


def test_probes_are_grouped_by_vertical():
    order = [vertical for vertical, _, _ in probe.PROBES]
    assert order == sorted(order, key=order.index)


def test_each_vertical_readiness_is_read_while_its_observations_are_live(monkeypatch, tmp_path):
    handler = fake_runtime()
    monkeypatch.setattr(probe, "httpx", SimpleNamespace(
        Client=lambda **kwargs: httpx.Client(transport=httpx.MockTransport(handler), **kwargs),
        Timeout=httpx.Timeout, HTTPError=httpx.HTTPError))
    output = tmp_path / "probe.json"
    monkeypatch.setattr(sys, "argv", ["probe", "--base-url", "https://runtime.test",
                                      "--output", str(output)])
    # The whole run outlasts Lyte's freshness window, so only prompt reads pass.
    assert len(probe.PROBES) * FETCH_SECONDS > CONNECTORS["github-actions"].freshness_seconds
    exit_code = probe.main()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["failures"] == [] and exit_code == 0
    assert set(report["vertical_readiness"]) == {vertical for vertical, _, _ in probe.PROBES}
    assert all(item["live_data"]["observed_in_scope"] is True
               for item in report["vertical_readiness"].values())
