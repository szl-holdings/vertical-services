from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import frontier_app
from frontier_fabric.catalog import VERTICALS


def _decode(body: bytes):
    return json.loads(body.decode("utf-8"))


def _post_payload(payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    status, content_type, body = frontier_app.resolve_post(
        "/api/vertical-fabric/v1/evaluate",
        json.dumps(payload).encode("utf-8"),
    )
    assert content_type.startswith("application/json")
    return status, _decode(body)


def test_health_and_build_info_are_truthful() -> None:
    status, content_type, body = frontier_app.resolve_get("/healthz")
    payload = _decode(body)
    assert status == 200
    assert content_type.startswith("application/json")
    assert payload["ok"] is True
    assert payload["verticals"] == 10
    assert payload["bound_models"] == 0
    assert payload["bound_kernels"] == 0
    assert payload["public_effectors_enabled"] is False
    assert payload["lambda_uniqueness"] == "CONJECTURE_1_OPEN"

    status, _, body = frontier_app.resolve_get("/api/build-info")
    build = _decode(body)
    assert status == 200
    assert build["source_repository"] == "szl-holdings/vertical-services"
    assert build["source_revision"] == frontier_app.SOURCE_REVISION
    assert build["public_effectors_enabled"] is False


def test_index_and_every_vertical_frontend_are_served() -> None:
    status, content_type, body = frontier_app.resolve_get("/")
    document = body.decode("utf-8")
    assert status == 200
    assert content_type.startswith("text/html")
    for vertical in VERTICALS:
        assert f'href="/vertical-frontier/{vertical.id}"' in document
        status, page_type, page = frontier_app.resolve_get(
            f"/vertical-frontier/{vertical.id}"
        )
        assert status == 200
        assert page_type.startswith("text/html")
        text = page.decode("utf-8")
        assert f'data-vertical="{vertical.id}"' in text
        assert vertical.operator_outcome in text


def test_catalog_and_experience_routes_are_machine_readable() -> None:
    status, _, body = frontier_app.resolve_get(
        "/api/vertical-fabric/v1/catalog"
    )
    catalog = _decode(body)
    assert status == 200
    assert len(catalog["verticals"]) == 10
    assert catalog["truth_boundary"]["public_effectors_enabled"] is False

    status, _, body = frontier_app.resolve_get(
        "/api/vertical-fabric/v1/verticals/lyte/experience"
    )
    experience = _decode(body)
    assert status == 200
    assert experience["vertical_id"] == "lyte"
    assert experience["effect_mode"] == "HUMAN_BOUND"
    assert "causal trace river" in experience["theme"]["signature_modules"]


def test_unbound_runtime_keeps_advisory_evaluation_on_hold() -> None:
    status, result = _post_payload(
        {
            "vertical_id": "lyte",
            "signal_id": "deploy-1",
            "session_id": "frontier-app-session-1",
            "actor_id": "operator-1",
            "payload": {"service": "checkout"},
        }
    )
    assert status == 200
    assert result["decision"] == "HOLD"
    assert result["state"] == "UNAVAILABLE"
    assert result["proposal"]["model_id"] is None
    assert result["receipt"]["authorization_proof"] is False


def test_killinchu_non_simulated_effect_is_denied() -> None:
    status, result = _post_payload(
        {
            "vertical_id": "killinchu",
            "signal_id": "synthetic-track-1",
            "session_id": "frontier-app-session-2",
            "actor_id": "operator-2",
            "payload": {"track": "synthetic"},
            "proposal": {
                "summary": "Reviewed synthetic-track proposal.",
                "model_id": "SZLHOLDINGS/szl-nemo",
                "model_revision": "a" * 40,
                "confidence": 0.7,
                "state": "ADVISORY",
            },
            "requested_effect": "launch weapon at target",
            "human_bind": {
                "approver_id": "operator-2",
                "approved_at": "2026-09-04T00:00:00Z",
                "scope": "synthetic public demo",
                "decision": "ALLOW",
                "policy_revision": "policy-v1",
            },
        }
    )
    assert status == 200
    assert result["decision"] == "DENY"
    assert result["state"] == "BLOCKED"
    assert "violates policy" in result["reason"]


def test_receipt_verification_uses_the_same_session_scope() -> None:
    session_id = "frontier-app-session-verify"
    status, result = _post_payload(
        {
            "vertical_id": "sentra",
            "signal_id": "exposure-1",
            "session_id": session_id,
            "actor_id": "analyst-1",
            "payload": {"asset": "public-test"},
        }
    )
    assert status == 200
    assert result["receipt"]["sequence"] == 0

    status, _, body = frontier_app.resolve_post(
        "/api/vertical-fabric/v1/receipts/verify",
        json.dumps({"vertical_id": "sentra", "session_id": session_id}).encode(
            "utf-8"
        ),
    )
    verified = _decode(body)
    assert status == 200
    assert verified["ok"] is True
    assert verified["entries"] == 1


def test_unknown_and_malformed_requests_fail_closed() -> None:
    status, _, _ = frontier_app.resolve_get("/vertical-frontier/unknown")
    assert status == 404
    status, _, _ = frontier_app.resolve_get(
        "/api/vertical-fabric/v1/verticals/unknown"
    )
    assert status == 404

    status, _, body = frontier_app.resolve_post(
        "/api/vertical-fabric/v1/evaluate", b"not-json"
    )
    assert status == 400
    assert _decode(body)["ok"] is False

    status, _, body = frontier_app.resolve_post(
        "/api/vertical-fabric/v1/evaluate", b"x" * (frontier_app.MAX_BODY_BYTES + 1)
    )
    assert status == 413
    assert _decode(body)["ok"] is False


def test_http_handler_emits_security_headers() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), frontier_app.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_address[1]}/healthz",
            headers={"Accept": "application/json"},
        )
        with urlopen(request, timeout=3) as response:
            assert response.status == 200
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["Referrer-Policy"] == "no-referrer"
            assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
            assert response.headers["Permissions-Policy"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
