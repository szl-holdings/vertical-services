"""Fail-closed RFC 8259 request boundary on the public Python-only frontier."""

from __future__ import annotations

import json

import pytest

import frontier_app


@pytest.mark.parametrize(
    "raw",
    [
        b'{"vertical_id":"lyte","score":NaN}',
        b'{"vertical_id":"lyte","score":Infinity}',
        b'{"vertical_id":"lyte","score":-Infinity}',
        b'{"vertical_id":"lyte","payload":{"confidence":NaN}}',
        b'{"vertical_id":"lyte","payload":[{"risk":Infinity}]}',
        b'{"vertical_id":"lyte","score":1e999}',
        b'{"vertical_id":"lyte","score":-1e999}',
    ],
)
def test_nonfinite_request_never_reaches_evaluation(
    monkeypatch: pytest.MonkeyPatch, raw: bytes
) -> None:
    def _unexpected_evaluation(*args: object, **kwargs: object) -> None:
        raise AssertionError("malformed numeric evidence reached the fabric")

    monkeypatch.setattr(frontier_app.FABRIC, "evaluate", _unexpected_evaluation)
    status, content_type, body = frontier_app.resolve_post(
        "/api/vertical-fabric/v1/evaluate", raw
    )
    assert status == 400
    assert content_type.startswith("application/json")
    assert json.loads(body)["ok"] is False


def test_valid_finite_number_parses_before_route_selection() -> None:
    status, _, body = frontier_app.resolve_post(
        "/api/does-not-exist",
        b'{"nested":{"values":[0.125,1e-5,-1.5e2]}}',
    )
    assert status == 404
    assert json.loads(body)["error"] == "route not found"


def test_duplicate_keys_still_refused() -> None:
    status, _, body = frontier_app.resolve_post(
        "/api/vertical-fabric/v1/evaluate",
        b'{"vertical_id":"sentra","vertical_id":"lyte"}',
    )
    assert status == 400
    assert json.loads(body)["ok"] is False
