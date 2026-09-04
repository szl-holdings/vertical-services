#!/usr/bin/env python3
"""Dependency-free public runtime for the SZL Vertical Frontier Fabric.

The runtime serves the ten original front-end concepts and the fail-closed
Python evaluation API. It binds no model, kernel, operator data, or effector by
default. Consequential requests therefore remain HOLD or DENY rather than being
silently simulated as production capability.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import unquote, urlsplit

from frontier_fabric.catalog import get_vertical, public_catalog
from frontier_fabric.engine import EvaluationError, VerticalFabric, request_from_mapping
from frontier_fabric.showcase import render_showcase_index, render_vertical_showcase
from frontier_fabric.types import ClaimState, as_public_dict

MAX_BODY_BYTES = 1_100_000
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "7860"))
SOURCE_REVISION = os.getenv("SZL_GIT_SHA", "REVISION_UNAVAILABLE")
FABRIC = VerticalFabric()


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _html_bytes(document: str) -> bytes:
    return document.encode("utf-8")


def _health() -> dict[str, Any]:
    capabilities = FABRIC.capabilities()
    return {
        "ok": True,
        "schema": "szl.vertical-frontier-health/v1",
        "surface": "SZL Vertical Frontier Fabric",
        "source_revision": SOURCE_REVISION,
        "verticals": len(capabilities["verticals"]),
        "bound_models": len(capabilities["runtime"]["bound_models"]),
        "bound_kernels": len(capabilities["runtime"]["bound_kernels"]),
        "strict_effect_gate": capabilities["runtime"]["strict_effect_gate"],
        "public_effectors_enabled": False,
        "public_data_connectors_executed_by_default": False,
        "lambda_uniqueness": "CONJECTURE_1_OPEN",
        "truth_boundary": (
            "Reachability and rendered concepts do not prove model quality, provider availability, "
            "production authorization, compliance, adoption, or performance."
        ),
    }


def resolve_get(path: str) -> tuple[int, str, bytes]:
    normalized = unquote(path).rstrip("/") or "/"
    if normalized in {"/healthz", "/readyz", "/api/vertical-fabric/v1/healthz"}:
        return 200, "application/json; charset=utf-8", _json_bytes(_health())
    if normalized == "/api/build-info":
        return 200, "application/json; charset=utf-8", _json_bytes(
            {
                "schema": "szl.build-info/v1",
                "surface": "SZL Vertical Frontier Fabric",
                "source_repository": "szl-holdings/vertical-services",
                "source_revision": SOURCE_REVISION,
                "runtime": "stdlib-python",
                "public_effectors_enabled": False,
            }
        )
    if normalized == "/api/vertical-fabric/v1/verticals":
        return 200, "application/json; charset=utf-8", _json_bytes(FABRIC.capabilities())
    prefix = "/api/vertical-fabric/v1/verticals/"
    if normalized.startswith(prefix):
        suffix = normalized[len(prefix) :]
        experience = suffix.endswith("/experience")
        vertical_id = suffix[: -len("/experience")] if experience else suffix
        if "/" in vertical_id or not vertical_id:
            return 404, "application/json; charset=utf-8", _json_bytes(
                {"ok": False, "error": "route not found"}
            )
        try:
            if experience:
                spec = get_vertical(vertical_id)
                payload = {
                    "schema": "szl.vertical-experience/v1",
                    "vertical_id": spec.id,
                    "display_name": spec.display_name,
                    "lane": spec.lane,
                    "operator_outcome": spec.operator_outcome,
                    "unmet_need": spec.unmet_need,
                    "differentiator": spec.differentiator,
                    "theme": as_public_dict(spec.theme),
                    "modules": list(spec.experience_modules),
                    "evidence_contract": list(spec.evidence_contract),
                    "effect_mode": spec.effect_mode.value,
                    "public_actuation": spec.public_actuation.value,
                }
            else:
                payload = FABRIC.capabilities(vertical_id)
        except KeyError:
            return 404, "application/json; charset=utf-8", _json_bytes(
                {"ok": False, "error": "unknown vertical", "vertical_id": vertical_id}
            )
        return 200, "application/json; charset=utf-8", _json_bytes(payload)
    if normalized == "/api/vertical-fabric/v1/catalog":
        return 200, "application/json; charset=utf-8", _json_bytes(public_catalog())
    if normalized in {"/", "/vertical-frontier"}:
        document = render_showcase_index().replace(
            'href="./', 'href="/vertical-frontier/'
        )
        return 200, "text/html; charset=utf-8", _html_bytes(document)
    showcase_prefix = "/vertical-frontier/"
    if normalized.startswith(showcase_prefix):
        vertical_id = normalized[len(showcase_prefix) :]
        if "/" in vertical_id or not vertical_id:
            return 404, "text/html; charset=utf-8", _html_bytes(
                "<!doctype html><title>Not found</title><h1>Not found</h1>"
            )
        try:
            document = render_vertical_showcase(vertical_id)
        except KeyError:
            return 404, "text/html; charset=utf-8", _html_bytes(
                "<!doctype html><title>Unknown vertical</title><h1>Unknown vertical</h1>"
            )
        return 200, "text/html; charset=utf-8", _html_bytes(document)
    return 404, "application/json; charset=utf-8", _json_bytes(
        {"ok": False, "error": "route not found"}
    )


def resolve_post(path: str, body: bytes) -> tuple[int, str, bytes]:
    normalized = unquote(path).rstrip("/") or "/"
    if len(body) > MAX_BODY_BYTES:
        return 413, "application/json; charset=utf-8", _json_bytes(
            {"ok": False, "error": "request body exceeds the public boundary"}
        )
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, "application/json; charset=utf-8", _json_bytes(
            {"ok": False, "error": "body must be valid UTF-8 JSON"}
        )
    if not isinstance(payload, dict):
        return 422, "application/json; charset=utf-8", _json_bytes(
            {"ok": False, "error": "body must be a JSON object"}
        )

    if normalized == "/api/vertical-fabric/v1/evaluate":
        try:
            result = FABRIC.evaluate(request_from_mapping(payload))
        except KeyError as exc:
            return 404, "application/json; charset=utf-8", _json_bytes(
                {"ok": False, "error": str(exc)}
            )
        except (EvaluationError, ValueError) as exc:
            return 422, "application/json; charset=utf-8", _json_bytes(
                {"ok": False, "error": str(exc)}
            )
        return 200, "application/json; charset=utf-8", _json_bytes(as_public_dict(result))

    if normalized == "/api/vertical-fabric/v1/receipts/verify":
        vertical_id = str(payload.get("vertical_id", "")).strip()
        session_id = str(payload.get("session_id", "")).strip()
        if not vertical_id or not session_id:
            return 422, "application/json; charset=utf-8", _json_bytes(
                {"ok": False, "error": "vertical_id and session_id are required"}
            )
        try:
            get_vertical(vertical_id)
        except KeyError:
            return 404, "application/json; charset=utf-8", _json_bytes(
                {"ok": False, "error": "unknown vertical", "vertical_id": vertical_id}
            )
        result = FABRIC.verify_session(vertical_id, session_id)
        return 200, "application/json; charset=utf-8", _json_bytes(result)

    return 404, "application/json; charset=utf-8", _json_bytes(
        {"ok": False, "error": "route not found"}
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "SZLVerticalFrontier/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def _send(self, status: int, content_type: str, body: bytes, *, head: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; "
            "form-action 'none'",
        )
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def do_HEAD(self) -> None:  # noqa: N802
        status, content_type, body = resolve_get(urlsplit(self.path).path)
        self._send(status, content_type, body, head=True)

    def do_GET(self) -> None:  # noqa: N802
        status, content_type, body = resolve_get(urlsplit(self.path).path)
        self._send(status, content_type, body)

    def do_POST(self) -> None:  # noqa: N802
        if self.headers.get_content_type().lower() != "application/json":
            self._send(
                415,
                "application/json; charset=utf-8",
                _json_bytes({"ok": False, "error": "Content-Type must be application/json"}),
            )
            return
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            self._send(
                411,
                "application/json; charset=utf-8",
                _json_bytes({"ok": False, "error": "Content-Length is required"}),
            )
            return
        try:
            length = int(raw_length)
        except ValueError:
            self._send(
                400,
                "application/json; charset=utf-8",
                _json_bytes({"ok": False, "error": "invalid Content-Length"}),
            )
            return
        if length < 0 or length > MAX_BODY_BYTES:
            self._send(
                413,
                "application/json; charset=utf-8",
                _json_bytes({"ok": False, "error": "request body exceeds the public boundary"}),
            )
            return
        body = self.rfile.read(length)
        status, content_type, response = resolve_post(urlsplit(self.path).path, body)
        self._send(status, content_type, response)


def main() -> int:
    if not 1 <= PORT <= 65535:
        raise SystemExit("PORT must be between 1 and 65535")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(
        f"[szl-vertical-frontier] {HOST}:{PORT} · verticals=10 · "
        "models=0 bound · kernels=0 bound · public effectors=false",
        file=sys.stderr,
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
