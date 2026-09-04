#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""SZL Vertical Frontier runtime with governed model and kernel execution.

This server extends the public reference service in ``app.py``. Every decision
first passes the deterministic evidence/action/human-binding gates, then may be
sent to an operator-configured OpenAI-compatible endpoint as a proposal-only
analysis. The returned text is checked by the embedded SZL kernel reference
stack and bound into a new deterministic receipt.

No public route grants authorization or executes an external effect.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import app as base  # noqa: E402
import kernel_engine  # noqa: E402
import model_gateway  # noqa: E402


def policy_blocked_model_result(
    *,
    vertical: Mapping[str, Any],
    base_receipt: Mapping[str, Any],
    reason: str,
) -> dict[str, Any]:
    route = base_receipt.get("route") if isinstance(base_receipt, Mapping) else None
    models = route.get("models") if isinstance(route, Mapping) else None
    first = models[0] if isinstance(models, list) and models and isinstance(models[0], Mapping) else {}
    body = {
        "schema": "szl.model-proposal.v1",
        "state": "POLICY_BLOCKED",
        "vertical": vertical.get("slug"),
        "model": first.get("id"),
        "model_role": first.get("role"),
        "request_sha256": None,
        "content": None,
        "content_sha256": None,
        "tool_calls": [],
        "authorization": "NONE",
        "execution_performed": False,
        "proposal_only": True,
        "reason": reason,
    }
    return {**body, "gateway_receipt_sha256": model_gateway.sha256(body)}


def evaluate_with_models(payload: dict[str, Any]) -> dict[str, Any]:
    """Create the full proposal → model route → kernel → receipt object."""
    base_receipt = base.evaluate_proposal(payload)
    slug = base_receipt["vertical"]
    vertical = base.VERTICALS[slug]
    base_digest = base_receipt.pop("receipt_sha256")
    blocks = set(base_receipt.get("blocks", []))
    evidence = base_receipt.get("evidence", [])
    prohibited = "PROHIBITED_ACTION_CLASS" in blocks
    no_evidence = "NO_ADMISSIBLE_EVIDENCE" in blocks

    if prohibited:
        model_result = policy_blocked_model_result(
            vertical=vertical,
            base_receipt=base_receipt,
            reason="The requested action matched a prohibited class. No model call was made.",
        )
    elif no_evidence:
        model_result = policy_blocked_model_result(
            vertical=vertical,
            base_receipt=base_receipt,
            reason="No admissible evidence was supplied. No model call was made.",
        )
    else:
        model_result = model_gateway.propose(
            vertical=vertical,
            objective=str(payload.get("objective", "")),
            requested_action=str(payload.get("requested_action", "review")),
            evidence=evidence,
            preferred_role=str(payload.get("preferred_model_role", "")) or None,
        )

    kernel_result = kernel_engine.evaluate_kernel_stack(
        vertical=vertical,
        proposal_receipt=base_receipt,
        model_result=model_result,
    )

    final_blocks = sorted(set(base_receipt.get("blocks", [])) | set(kernel_result.get("blocks", [])))
    final_state = "HOLD" if final_blocks else "READY_FOR_OPERATOR_BINDING"
    body = {
        **base_receipt,
        "schema": "szl.vertical-decision-receipt.v2",
        "state": final_state,
        "blocks": final_blocks,
        "base_receipt_sha256": base_digest,
        "model_proposal": model_result,
        "kernel_evaluation": kernel_result,
        "model_inference_attempted": model_result.get("state") == "INFERENCE_LIVE",
        "model_inference_state": model_result.get("state"),
        "kernel_state": kernel_result.get("state"),
        "authorization": "NONE",
        "execution_performed": False,
        "public_effectors_enabled": False,
        "human_operator_binding_still_required": True,
        "lambda_uniqueness": "CONJECTURE_1_OPEN",
        "proven_trust": False,
    }
    return {**body, "receipt_sha256": base.sha256(body)}


def runtime_capabilities() -> dict[str, Any]:
    return {
        "schema": "szl.vertical-runtime-capabilities.v1",
        "surface": "SZL Vertical Frontier",
        "build": base.build_info(),
        "model_gateway": model_gateway.capabilities(),
        "kernel_engine": {
            "state": "LIVE_EMBEDDED_REFERENCE",
            "external_artifact_loaded": False,
            "artifact_execution_claim": "EMBEDDED_REFERENCE_ONLY",
            "supported_bindings": list(kernel_engine.DEFAULT_KERNEL_IDS),
        },
        "decision_contract": {
            "model_may_authorize": False,
            "kernel_may_authorize": False,
            "human_binding_required": True,
            "public_effectors_enabled": False,
            "external_execution_available": False,
        },
    }


class Handler(base.Handler):
    server_version = "SZLVerticalFrontierRuntime/1.0"

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if path == "/api/v1/runtime-capabilities":
                self._send_json(HTTPStatus.OK, runtime_capabilities())
                return
            if path == "/api/v1/model/capabilities":
                self._send_json(HTTPStatus.OK, model_gateway.capabilities())
                return
            if path == "/api/v1/kernel/self-test":
                self._send_json(HTTPStatus.OK, kernel_engine.self_test())
                return
            super().do_GET()
        except Exception as exc:
            status, code, message = base.sanitize_error(exc)
            self._send_json(status, {"ok": False, "error": code, "message": message})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if path == "/api/v1/decision":
                payload = self._read_json()
                self._send_json(HTTPStatus.OK, evaluate_with_models(payload))
                return
            if path == "/api/v1/inference":
                payload = self._read_json()
                receipt = evaluate_with_models(payload)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "schema": "szl.vertical-inference-response.v1",
                        "vertical": receipt["vertical"],
                        "state": receipt["state"],
                        "blocks": receipt["blocks"],
                        "model_proposal": receipt["model_proposal"],
                        "kernel_evaluation": receipt["kernel_evaluation"],
                        "authorization": "NONE",
                        "execution_performed": False,
                        "decision_receipt_sha256": receipt["receipt_sha256"],
                    },
                )
                return
            if path == "/api/v1/kernel/evaluate":
                payload = self._read_json()
                slug = str(payload.get("vertical", "")).strip().lower()
                receipt = payload.get("receipt")
                model_result = payload.get("model_proposal")
                if slug not in base.VERTICALS:
                    raise ValueError("unknown vertical")
                if not isinstance(receipt, dict):
                    raise ValueError("receipt must be a JSON object")
                result = kernel_engine.evaluate_kernel_stack(
                    vertical=base.VERTICALS[slug],
                    proposal_receipt=receipt,
                    model_result=model_result if isinstance(model_result, dict) else None,
                )
                self._send_json(HTTPStatus.OK, result)
                return
            super().do_POST()
        except Exception as exc:
            status, code, message = base.sanitize_error(exc)
            self._send_json(status, {"ok": False, "error": code, "message": message})


def self_test() -> dict[str, Any]:
    base_result = base.evaluate_proposal(
        {
            "vertical": "a11oy",
            "objective": "inspect an evidence-bound proposal",
            "requested_action": "prepare an operator recommendation",
            "risk": 0.2,
            "evidence": [{"source": "self-test", "claim": "a source-bound observation exists"}],
            "human_approved": True,
        }
    )
    result = evaluate_with_models(
        {
            "vertical": "a11oy",
            "objective": "inspect an evidence-bound proposal",
            "requested_action": "prepare an operator recommendation",
            "risk": 0.2,
            "evidence": [{"source": "self-test", "claim": "a source-bound observation exists"}],
            "human_approved": True,
        }
    )
    assert base_result["authorization"] == "NONE"
    assert result["authorization"] == "NONE"
    assert result["execution_performed"] is False
    assert result["public_effectors_enabled"] is False
    assert result["model_proposal"]["state"] in {"ROUTE_ONLY", "INFERENCE_LIVE"}
    assert result["kernel_evaluation"]["external_kernel_artifact_loaded"] is False
    assert len(result["receipt_sha256"]) == 64

    blocked = evaluate_with_models(
        {
            "vertical": "killinchu",
            "objective": "evaluate evidence",
            "requested_action": "engage target",
            "risk": 0.1,
            "evidence": [{"source": "self-test", "claim": "observation"}],
            "human_approved": True,
        }
    )
    assert blocked["state"] == "HOLD"
    assert blocked["model_proposal"]["state"] == "POLICY_BLOCKED"
    assert blocked["model_inference_attempted"] is False
    return {
        "ok": True,
        "base_receipt_sha256": base_result["receipt_sha256"],
        "runtime_receipt_sha256": result["receipt_sha256"],
        "capabilities": runtime_capabilities(),
    }


def serve(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(
        f"SZL Vertical Frontier runtime on http://{host}:{port} · "
        f"model mode {model_gateway.InferenceConfig.from_env().mode} · "
        "kernels embedded-reference · humans bind"
    )
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "7860")))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
        return 0
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
