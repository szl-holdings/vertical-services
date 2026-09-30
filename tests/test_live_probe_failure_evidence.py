"""Exercise the actual probe against HTTP and transport failures without a network."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import httpx


def load_probe():
    path = Path(__file__).parents[1] / "tools/probe_live_verticals.py"
    spec = importlib.util.spec_from_file_location("live_probe_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def setup_main(monkeypatch, tmp_path, handler, *, base="https://fixed.example"):
    probe = load_probe()
    client_type = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(probe.httpx, "Client", lambda **kwargs: client_type(transport=transport, **kwargs))
    monkeypatch.setattr(probe.secrets, "token_urlsafe", lambda _: "PRIVATE_SESSION_FIXTURE")
    sleeps = []
    monkeypatch.setattr(probe.time, "sleep", sleeps.append)
    output = tmp_path / "retained/probe.json"
    monkeypatch.setattr(sys, "argv", ["probe", "--base-url", base, "--output", str(output)])
    return probe, output, sleeps


def test_exhausted_http_failure_retains_nonzero_receipt_and_bounded_hash(monkeypatch, tmp_path):
    requests = []
    sensitive_body = b"PRIVATE_RESPONSE_FIXTURE" + b"x" * 5000

    def handler(request):
        requests.append(request)
        return httpx.Response(503, content=sensitive_body)

    probe, output, sleeps = setup_main(monkeypatch, tmp_path, handler)
    assert probe.main() == 1
    text = output.read_text()
    report = json.loads(text)
    assert report["status"] == "FAIL" and report["complete"] is False
    assert report["probes"] == [] and report["stopped_before_remaining_requests"] is True
    failure = report["request_failure"]
    assert failure["state"] == "UNAVAILABLE"
    assert failure["url"] == "https://fixed.example/api/verticals/sentra/connectors/cisa-kev/fetch"
    assert len(requests) == 3 and sleeps == [1, 2]
    assert [a["http_status"] for a in failure["attempts"]] == [503] * 3
    for attempt in failure["attempts"]:
        assert attempt["body_prefix_bytes"] == 4096
        assert attempt["body_prefix_truncated"] is True
        assert attempt["body_prefix_sha256"] == hashlib.sha256(sensitive_body[:4096]).hexdigest()
    assert "PRIVATE_SESSION_FIXTURE" not in text and "PRIVATE_RESPONSE_FIXTURE" not in text


def test_transport_failure_redacts_exception_and_url_credentials(monkeypatch, tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        raise httpx.ConnectTimeout("PRIVATE_TRANSPORT_FIXTURE", request=request)

    probe, output, sleeps = setup_main(monkeypatch, tmp_path, handler, base="https://private-user:PRIVATE_PASSWORD_FIXTURE@fixed.example")
    assert probe.main() == 1
    text = output.read_text()
    report = json.loads(text)
    assert report["base_url"] == "https://fixed.example"
    failure = report["request_failure"]
    assert failure["url"].startswith("https://fixed.example/")
    assert all(a["error_type"] == "ConnectTimeout" and a["http_status"] is None for a in failure["attempts"])
    assert len(requests) == 3 and sleeps == [1, 2]
    for secret in ("PRIVATE_PASSWORD_FIXTURE", "private-user", "PRIVATE_TRANSPORT_FIXTURE", "PRIVATE_SESSION_FIXTURE"):
        assert secret not in text


def observation():
    return {"receipt": {"state": "OBSERVED", "receipt_id": "a" * 64, "payload_sha256": "b" * 64}, "observation": {"trading_enabled": False, "custody_enabled": False, "person_level_prospecting": False}}


def test_later_failure_preserves_already_observed_connector(monkeypatch, tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        if "/cisa-kev/" in request.url.path:
            return httpx.Response(200, json=observation())
        return httpx.Response(502, content=b"unavailable")

    probe, output, sleeps = setup_main(monkeypatch, tmp_path, handler)
    assert probe.main() == 1
    report = json.loads(output.read_text())
    assert len(report["probes"]) == 1
    assert report["probes"][0]["state"] == "OBSERVED"
    assert report["request_failure"]["url"].endswith("/lyte/connectors/github-actions/fetch")
    assert len(requests) == 4 and sleeps == [1, 2]


def test_client_error_still_returns_without_retry(monkeypatch):
    probe = load_probe()
    requests = []
    sleeps = []
    monkeypatch.setattr(probe.time, "sleep", sleeps.append)
    def handler(request):
        requests.append(request)
        return httpx.Response(403, content=b"denied")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert probe.request_with_retry(client, "GET", "https://fixed.example/readyz").status_code == 403
    assert len(requests) == 1 and sleeps == []


def test_later_readiness_failure_retains_earlier_readiness(monkeypatch, tmp_path):
    def handler(request):
        if request.url.path.endswith("/fetch"):
            return httpx.Response(200, json=observation())
        if request.url.path == "/api/verticals/sentra/readyz":
            return httpx.Response(200, json={"ready": True, "live_data": {"observed_in_scope": True}})
        return httpx.Response(503, content=b"unavailable")
    probe, output, sleeps = setup_main(monkeypatch, tmp_path, handler)
    assert probe.main() == 1
    report = json.loads(output.read_text())
    assert len(report["probes"]) == 11
    assert report["vertical_readiness"] == {"sentra": {"http_status": 200, "ready": True, "status": None, "live_data": {"observed_in_scope": True}, "build": None, "lambda_advisory": None}}
    assert report["request_failure"]["url"].endswith("/api/verticals/lyte/readyz")
    assert report["complete"] is False and sleeps == [1, 2]
    assert report["experiences"] == [] and "root_readiness" not in report


def test_recovered_request_still_returns_original_success(monkeypatch):
    probe = load_probe()
    requests = []
    sleeps = []
    monkeypatch.setattr(probe.time, "sleep", sleeps.append)
    def handler(request):
        requests.append(request)
        return httpx.Response(502 if len(requests) == 1 else 200, json={"ready": True})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert probe.request_with_retry(client, "GET", "https://fixed.example/readyz").json() == {"ready": True}
    assert len(requests) == 2 and sleeps == [1]


def successful_handler():
    probe_for_contract = load_probe()
    def handler(request):
        path = request.url.path
        if path.endswith("/fetch"):
            return httpx.Response(200, json=observation())
        if path.endswith("/readyz"):
            return httpx.Response(200, json={"ready": True, "live_data": {"observed_in_scope": True}})
        if path == "/api/build-info":
            return httpx.Response(200, json={"build": {"state": "OBSERVED"}, "source_binding": {"bindings_agree": True}})
        if path.startswith("/experience/"):
            alias = path.rsplit("/", 1)[-1]
            _, title, motif = probe_for_contract.EXPERIENCES[alias]
            return httpx.Response(200, text=f'{title} data-motif="{motif}" viewport-fit=cover @media(prefers-reduced-motion:reduce)')
        alias = path.split("/")[-2]
        canonical = probe_for_contract.EXPERIENCES[alias][0]
        return httpx.Response(200, json={"vertical": canonical, "hatun": {"can_authorize": False, "effectors_enabled": False}})
    return handler


def test_build_failure_retains_successful_root_readiness(monkeypatch, tmp_path):
    successful = successful_handler()
    def handler(request):
        if request.url.path == "/api/build-info":
            return httpx.Response(503, content=b"unavailable")
        return successful(request)
    probe, output, sleeps = setup_main(monkeypatch, tmp_path, handler)
    assert probe.main() == 1
    report = json.loads(output.read_text())
    assert report["root_readiness"]["http_status"] == 200
    assert report["root_readiness"]["body"]["ready"] is True
    assert len(report["vertical_readiness"]) == 6 and len(report["experiences"]) == 6
    assert report["request_failure"]["url"].endswith("/api/build-info")
    assert "build_info" not in report and report["complete"] is False
    assert sleeps == [1, 2]


def test_complete_success_remains_pass(monkeypatch, tmp_path):
    probe, output, sleeps = setup_main(monkeypatch, tmp_path, successful_handler())
    assert probe.main() == 0
    report = json.loads(output.read_text())
    assert report["status"] == "PASS" and report["complete"] is True
    assert len(report["probes"]) == 11 and len(report["experiences"]) == 6
    assert "request_failure" not in report and sleeps == []
