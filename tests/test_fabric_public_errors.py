"""Raw exception text must never reach a vertical fabric response body.

The caller-facing "unknown vertical" lookup and EvaluationError messages stay
public. A KeyError or ValueError raised anywhere else, for example inside an
operator-bound model or kernel adapter, keeps its status code but is logged
server-side and replaced by a fixed detail.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import frontier_app
from frontier_fabric import showcase
from frontier_fabric.engine import VerticalFabric
from frontier_fabric.fastapi_router import create_router

MARKER = "SYNTHETIC_DIAGNOSTIC_MARKER"
NOT_FOUND_DETAIL = "vertical resource not found"
UNPROCESSABLE_DETAIL = "request could not be evaluated"
VERTICAL_ID = "a11oy"
MODEL_ID = "SZLHOLDINGS/szl-nemo"


def _request(vertical_id: str = VERTICAL_ID) -> dict[str, object]:
    return {
        "vertical_id": vertical_id,
        "signal_id": "signal-1",
        "session_id": "public-errors-session",
        "actor_id": "operator-1",
        "payload": {"probe": "public-errors"},
    }


def _fabric_with_failing_model(exc: Exception) -> VerticalFabric:
    def adapter(request, vertical):  # noqa: ANN001
        raise exc

    fabric = VerticalFabric()
    fabric.register_model(MODEL_ID, adapter)
    return fabric


def _client(fabric: VerticalFabric | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(create_router(fabric or VerticalFabric()))
    app.include_router(showcase.create_showcase_router())
    return TestClient(app)


@pytest.mark.parametrize(
    ("exc", "status", "detail"),
    [
        (KeyError(f"provider field {MARKER}"), 404, NOT_FOUND_DETAIL),
        (ValueError(f"provider rejected token {MARKER}"), 422, UNPROCESSABLE_DETAIL),
    ],
    ids=["key-error", "value-error"],
)
def test_router_evaluate_hides_adapter_errors(
    caplog: pytest.LogCaptureFixture,
    exc: Exception,
    status: int,
    detail: str,
) -> None:
    response = _client(_fabric_with_failing_model(exc)).post(
        "/api/vertical-fabric/v1/evaluate", json=_request()
    )
    assert MARKER not in response.text
    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert MARKER in caplog.text


def test_router_capabilities_hides_internal_lookup_errors(caplog: pytest.LogCaptureFixture) -> None:
    class BrokenFabric(VerticalFabric):
        def capabilities(self, vertical_id: str | None = None) -> dict[str, object]:
            raise KeyError(MARKER)

    response = _client(BrokenFabric()).get(f"/api/vertical-fabric/v1/verticals/{VERTICAL_ID}")
    assert MARKER not in response.text
    assert response.status_code == 404
    assert response.json() == {"detail": NOT_FOUND_DETAIL}
    assert MARKER in caplog.text


def test_showcase_router_hides_internal_lookup_errors(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def explode(vertical_id: str) -> str:
        raise KeyError(MARKER)

    monkeypatch.setattr(showcase, "render_vertical_showcase", explode)
    response = _client().get(f"/vertical-frontier/{VERTICAL_ID}")
    assert MARKER not in response.text
    assert response.status_code == 404
    assert response.json() == {"detail": NOT_FOUND_DETAIL}
    assert MARKER in caplog.text


def test_router_caller_messages_remain_public() -> None:
    client = _client()
    unknown = "'unknown vertical: not-a-vertical'"
    for path in (
        "/api/vertical-fabric/v1/verticals/not-a-vertical",
        "/api/vertical-fabric/v1/verticals/not-a-vertical/experience",
        "/vertical-frontier/not-a-vertical",
    ):
        response = client.get(path)
        assert (response.status_code, response.json()) == (404, {"detail": unknown})

    response = client.post("/api/vertical-fabric/v1/evaluate", json=_request("not-a-vertical"))
    assert (response.status_code, response.json()) == (404, {"detail": unknown})

    response = client.post(
        "/api/vertical-fabric/v1/receipts/verify",
        json={"vertical_id": "not-a-vertical", "session_id": "s"},
    )
    assert (response.status_code, response.json()) == (404, {"detail": unknown})

    response = client.post("/api/vertical-fabric/v1/evaluate", json={"vertical_id": VERTICAL_ID})
    assert (response.status_code, response.json()) == (422, {"detail": "missing required field: signal_id"})

    response = client.post(
        "/api/vertical-fabric/v1/evaluate", json={**_request(), "signal_id": " "}
    )
    assert (response.status_code, response.json()) == (
        422,
        {"detail": "signal_id, session_id, and actor_id are required"},
    )


@pytest.mark.parametrize(
    ("exc", "status", "error"),
    [
        (KeyError(f"provider field {MARKER}"), 404, NOT_FOUND_DETAIL),
        (ValueError(f"provider rejected token {MARKER}"), 422, UNPROCESSABLE_DETAIL),
    ],
    ids=["key-error", "value-error"],
)
def test_frontier_app_evaluate_hides_adapter_errors(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    exc: Exception,
    status: int,
    error: str,
) -> None:
    monkeypatch.setattr(frontier_app, "FABRIC", _fabric_with_failing_model(exc))
    observed_status, content_type, body = frontier_app.resolve_post(
        "/api/vertical-fabric/v1/evaluate", json.dumps(_request()).encode("utf-8")
    )
    assert MARKER.encode("utf-8") not in body
    assert content_type.startswith("application/json")
    assert observed_status == status
    assert json.loads(body) == {"ok": False, "error": error}
    assert MARKER in caplog.text


def test_frontier_app_caller_messages_remain_public() -> None:
    status, _, body = frontier_app.resolve_post(
        "/api/vertical-fabric/v1/evaluate",
        json.dumps(_request("not-a-vertical")).encode("utf-8"),
    )
    assert (status, json.loads(body)) == (
        404,
        {"ok": False, "error": "'unknown vertical: not-a-vertical'"},
    )

    status, _, body = frontier_app.resolve_post(
        "/api/vertical-fabric/v1/evaluate",
        json.dumps({"vertical_id": VERTICAL_ID}).encode("utf-8"),
    )
    assert (status, json.loads(body)) == (
        422,
        {"ok": False, "error": "missing required field: signal_id"},
    )
