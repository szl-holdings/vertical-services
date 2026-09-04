# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app  # noqa: E402
import kernel_engine  # noqa: E402
import model_gateway  # noqa: E402
import runtime  # noqa: E402


def test_gateway_route_only_is_explicit_and_non_authorizing() -> None:
    result = model_gateway.propose(
        vertical=app.VERTICALS["a11oy"],
        objective="inspect the evidence",
        requested_action="prepare an operator recommendation",
        evidence=[{"source": "test", "claim": "bounded fact"}],
        config=model_gateway.InferenceConfig(
            mode="route_only",
            base_url=None,
            chat_path="/v1/chat/completions",
            allowed_hosts=frozenset({"localhost"}),
            token=None,
            timeout_seconds=1.0,
            max_tokens=64,
            temperature=0.0,
        ),
    )
    assert result["state"] == "ROUTE_ONLY"
    assert result["model"] == "SZLHOLDINGS/szl-nemo"
    assert result["content"] is None
    assert result["authorization"] == "NONE"
    assert result["execution_performed"] is False
    assert result["tool_calls"] == []
    assert len(result["gateway_receipt_sha256"]) == 64


def test_gateway_rejects_unallowlisted_or_insecure_remote_endpoint() -> None:
    config = model_gateway.InferenceConfig(
        mode="openai_compatible",
        base_url="https://untrusted.example/v1",
        chat_path="/v1/chat/completions",
        allowed_hosts=frozenset({"router.huggingface.co"}),
        token="secret",
        timeout_seconds=1.0,
        max_tokens=64,
        temperature=0.0,
    )
    with pytest.raises(RuntimeError, match="not in SZL_INFERENCE_ALLOWED_HOSTS"):
        config.validated_endpoint()

    insecure = model_gateway.InferenceConfig(
        mode="openai_compatible",
        base_url="http://router.huggingface.co",
        chat_path="/v1/chat/completions",
        allowed_hosts=frozenset({"router.huggingface.co"}),
        token="secret",
        timeout_seconds=1.0,
        max_tokens=64,
        temperature=0.0,
    )
    with pytest.raises(RuntimeError, match="must use HTTPS"):
        insecure.validated_endpoint()


class FakeInferenceHandler(BaseHTTPRequestHandler):
    response_mode = "text"
    last_request: dict | None = None

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        type(self).last_request = payload
        if self.response_mode == "tool":
            message = {
                "role": "assistant",
                "content": "I will call a tool.",
                "tool_calls": [{"id": "unsafe", "type": "function", "function": {"name": "execute", "arguments": "{}"}}],
            }
        else:
            message = {
                "role": "assistant",
                "content": "Observed evidence: [E1]. Bounded recommendation: human review. AUTHORIZATION: NONE.",
            }
        body = json.dumps(
            {
                "id": "chatcmpl-test",
                "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 40, "completion_tokens": 18, "total_tokens": 58},
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_fake_inference(response_mode: str = "text") -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    handler = type(
        f"FakeInferenceHandler_{response_mode}",
        (FakeInferenceHandler,),
        {"response_mode": response_mode, "last_request": None},
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_address[1]}"


def test_gateway_executes_bounded_openai_compatible_proposal() -> None:
    server, thread, base_url = run_fake_inference("text")
    try:
        config = model_gateway.InferenceConfig(
            mode="openai_compatible",
            base_url=base_url,
            chat_path="/v1/chat/completions",
            allowed_hosts=frozenset({"127.0.0.1"}),
            token=None,
            timeout_seconds=2.0,
            max_tokens=128,
            temperature=0.0,
        )
        result = model_gateway.propose(
            vertical=app.VERTICALS["lyte"],
            objective="trace the failed workflow to an outcome",
            requested_action="prepare an operator recommendation",
            evidence=[
                {
                    "source": "github-actions",
                    "claim": "The exact workflow concluded failure.",
                    "sha256": "a" * 64,
                    "observed_at": "2026-09-04T00:00:00Z",
                }
            ],
            config=config,
        )
        assert result["state"] == "INFERENCE_LIVE"
        assert result["endpoint_host"] == "127.0.0.1"
        assert result["model"] == "SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2"
        assert result["content"].endswith("AUTHORIZATION: NONE.")
        assert result["tool_calls"] == []
        assert result["authorization"] == "NONE"
        assert result["execution_performed"] is False
        request = server.RequestHandlerClass.last_request
        assert request is not None
        assert request["model"] == result["model"]
        assert request["tools"] == []
        assert request["stream"] is False
        assert request["temperature"] == 0.0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_gateway_refuses_provider_tool_calls() -> None:
    server, thread, base_url = run_fake_inference("tool")
    try:
        config = model_gateway.InferenceConfig(
            mode="openai_compatible",
            base_url=base_url,
            chat_path="/v1/chat/completions",
            allowed_hosts=frozenset({"127.0.0.1"}),
            token=None,
            timeout_seconds=2.0,
            max_tokens=128,
            temperature=0.0,
        )
        result = model_gateway.propose(
            vertical=app.VERTICALS["sentra"],
            objective="explain the supplied exposure evidence",
            requested_action="prepare a remediation recommendation",
            evidence=[{"source": "cisa-kev", "claim": "Known exploitation is published."}],
            config=config,
        )
        assert result["state"] == "MODEL_TOOL_CALLS_REFUSED"
        assert result["content"] is None
        assert result["tool_calls"] == ["REDACTED_AND_REFUSED"]
        assert result["authorization"] == "NONE"
        assert result["execution_performed"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_kernel_stack_executes_reference_checks_without_claiming_remote_artifact() -> None:
    receipt = app.evaluate_proposal(
        {
            "vertical": "a11oy",
            "objective": "inspect the evidence",
            "requested_action": "prepare a recommendation",
            "risk": 0.2,
            "evidence": [{"source": "test", "claim": "bounded fact"}],
            "human_approved": True,
        }
    )
    result = kernel_engine.evaluate_kernel_stack(
        vertical=app.VERTICALS["a11oy"],
        proposal_receipt=receipt,
        model_result={
            "content": "Bounded recommendation. AUTHORIZATION: NONE.",
            "authorization": "NONE",
            "execution_performed": False,
            "tool_calls": [],
        },
    )
    assert result["state"] == "ADVISORY_CLEAR"
    assert result["authorization"] == "NONE"
    assert result["execution_performed"] is False
    assert result["external_kernel_artifact_loaded"] is False
    assert result["artifact_execution_claim"] == "EMBEDDED_REFERENCE_ONLY"
    assert result["lambda_uniqueness"] == "CONJECTURE_1_OPEN"
    assert result["proven_trust"] is False
    assert len(result["executed_reference_kernels"]) == 5


def test_runtime_receipt_contains_model_route_and_kernel_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SZL_INFERENCE_MODE", "route_only")
    receipt = runtime.evaluate_with_models(
        {
            "vertical": "terra",
            "objective": "build a bounded parcel diligence hypothesis",
            "requested_action": "prepare an operator-reviewed diligence packet",
            "risk": 0.25,
            "evidence": [{"source": "nyc-pluto", "claim": "A parcel record was observed."}],
            "human_approved": True,
        }
    )
    assert receipt["schema"] == "szl.vertical-decision-receipt.v2"
    assert receipt["state"] == "READY_FOR_OPERATOR_BINDING"
    assert receipt["model_proposal"]["state"] == "ROUTE_ONLY"
    assert receipt["kernel_evaluation"]["state"] == "ADVISORY_CLEAR"
    assert receipt["authorization"] == "NONE"
    assert receipt["execution_performed"] is False
    assert receipt["human_operator_binding_still_required"] is True
    assert len(receipt["receipt_sha256"]) == 64


def test_runtime_stops_prohibited_action_before_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SZL_INFERENCE_MODE", "openai_compatible")
    monkeypatch.setenv("SZL_INFERENCE_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("SZL_INFERENCE_ALLOWED_HOSTS", "127.0.0.1")
    receipt = runtime.evaluate_with_models(
        {
            "vertical": "killinchu",
            "objective": "evaluate the supplied observation",
            "requested_action": "engage target",
            "risk": 0.1,
            "evidence": [{"source": "operator", "claim": "A synthetic track exists."}],
            "human_approved": True,
        }
    )
    assert receipt["state"] == "HOLD"
    assert "PROHIBITED_ACTION_CLASS" in receipt["blocks"]
    assert receipt["model_proposal"]["state"] == "POLICY_BLOCKED"
    assert receipt["model_inference_attempted"] is False
    assert receipt["execution_performed"] is False


def post_json(url: str, payload: dict) -> tuple[int, dict]:
    raw = json.dumps(payload).encode("utf-8")
    request = Request(url, data=raw, method="POST", headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=4) as response:
        return response.status, json.load(response)


def test_runtime_http_capabilities_and_v2_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SZL_INFERENCE_MODE", "route_only")
    server = ThreadingHTTPServer(("127.0.0.1", 0), runtime.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urlopen(f"{base_url}/api/v1/runtime-capabilities", timeout=4) as response:
            capabilities = json.load(response)
            assert response.status == 200
        assert capabilities["model_gateway"]["state"] == "ROUTE_ONLY"
        assert capabilities["kernel_engine"]["state"] == "LIVE_EMBEDDED_REFERENCE"
        assert capabilities["decision_contract"]["external_execution_available"] is False

        status, receipt = post_json(
            f"{base_url}/api/v1/decision",
            {
                "vertical": "prism",
                "objective": "map authority to the issue and human review step",
                "requested_action": "prepare a cited draft for licensed review",
                "risk": 0.3,
                "evidence": [{"source": "federal-register", "claim": "A published rule was observed."}],
                "human_approved": True,
            },
        )
        assert status == 200
        assert receipt["schema"] == "szl.vertical-decision-receipt.v2"
        assert receipt["authorization"] == "NONE"
        assert receipt["execution_performed"] is False

        digest = receipt.pop("receipt_sha256")
        status, verification = post_json(
            f"{base_url}/api/v1/verify",
            {"receipt": receipt, "receipt_sha256": digest},
        )
        assert status == 200
        assert verification["valid"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
