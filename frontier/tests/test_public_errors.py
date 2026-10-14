# SPDX-License-Identifier: Apache-2.0
"""Raw exception text must never reach a public frontier response body.

Caller-input validation messages stay public; anything else that fails inside
a request (official-source transport, provider decoding, kernel code) is
replaced by a fixed message and logged server-side.
"""
from __future__ import annotations

import json
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app  # noqa: E402
import kernel_engine  # noqa: E402
import runtime  # noqa: E402

MARKER = "SYNTHETIC_DIAGNOSTIC_MARKER"
PUBLIC_MESSAGES = {
    "INVALID_REQUEST": "request could not be processed",
    "CONFIGURATION_REQUIRED": "required service configuration is unavailable",
    "INTERNAL_ERROR": "request could not be completed",
}


@contextmanager
def serve(handler: type[BaseHTTPRequestHandler]) -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def fetch(url: str, *, body: Any = None, raw: bytes | None = None) -> tuple[int, str]:
    data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
    request = Request(
        url,
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urlopen(request, timeout=4) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


class FakeUpstreamResponse:
    def __init__(self, content_type: str, body: bytes) -> None:
        self.headers = {"Content-Type": content_type}
        self._body = body

    def read(self, _limit: int) -> bytes:
        return self._body

    def __enter__(self) -> FakeUpstreamResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class FakeOpener:
    def __init__(self, response: FakeUpstreamResponse) -> None:
        self.response = response

    def open(self, _request: Request, timeout: float) -> FakeUpstreamResponse:
        return self.response


def assert_redacted(status: int, body: str, *, expected_status: int, expected_code: str) -> dict[str, Any]:
    assert MARKER not in body
    assert status == expected_status
    document = json.loads(body)
    assert set(document) == {"ok", "error", "message"}
    assert document["ok"] is False
    assert document["error"] == expected_code
    assert document["message"] == PUBLIC_MESSAGES[expected_code]
    return document


@pytest.mark.parametrize(
    ("content_type", "raw", "logged"),
    [
        (f"text/html; profile={MARKER}", b"<html>upstream error page</html>", MARKER),
        ("application/json", f"{{\"broken\": {MARKER}".encode("utf-8"), "JSONDecodeError"),
        ("application/json", b"\xff" + MARKER.encode("utf-8"), "UnicodeDecodeError"),
    ],
    ids=["content-type-reflection", "upstream-json-decode", "upstream-utf8-decode"],
)
def test_official_source_diagnostics_stay_out_of_snapshot_errors(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    content_type: str,
    raw: bytes,
    logged: str,
) -> None:
    monkeypatch.setattr(app, "OPENER", FakeOpener(FakeUpstreamResponse(content_type, raw)))
    with serve(app.Handler) as base:
        status, body = fetch(f"{base}/api/v1/verticals/sentra/snapshot")
    assert_redacted(status, body, expected_status=400, expected_code="INVALID_REQUEST")
    assert logged in caplog.text


@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_code"),
    [
        (ValueError(f"cannot read /srv/frontier/{MARKER}.db"), 400, "INVALID_REQUEST"),
        (json.JSONDecodeError(MARKER, "{}", 0), 400, "INVALID_REQUEST"),
        (RuntimeError(f"provider said: {MARKER}"), 503, "CONFIGURATION_REQUIRED"),
        (OSError(MARKER), 500, "INTERNAL_ERROR"),
    ],
    ids=["value-error", "json-decode-error", "runtime-error", "os-error"],
)
def test_injected_internal_errors_keep_status_and_hide_text(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    exc: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    def explode(_: Any) -> Any:
        raise exc

    monkeypatch.setitem(app.SNAPSHOTTERS, "sentra", explode)
    with serve(app.Handler) as base:
        status, body = fetch(f"{base}/api/v1/verticals/sentra/snapshot")
    assert_redacted(status, body, expected_status=expected_status, expected_code=expected_code)
    assert MARKER in caplog.text


@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_code"),
    [
        (ValueError(MARKER), 400, "INVALID_REQUEST"),
        (RuntimeError(MARKER), 503, "CONFIGURATION_REQUIRED"),
    ],
    ids=["value-error", "runtime-error"],
)
def test_runtime_kernel_errors_keep_status_and_hide_text(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    exc: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    def explode(**_: Any) -> Any:
        raise exc

    monkeypatch.setattr(kernel_engine, "evaluate_kernel_stack", explode)
    with serve(runtime.Handler) as base:
        status, body = fetch(
            f"{base}/api/v1/kernel/evaluate",
            body={"vertical": "a11oy", "receipt": {}},
        )
    assert_redacted(status, body, expected_status=expected_status, expected_code=expected_code)
    assert MARKER in caplog.text


def test_caller_validation_messages_remain_public(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with serve(runtime.Handler) as base:
        status, body = fetch(f"{base}/api/v1/verticals/puriq/snapshot?cik=not-a-cik")
        assert (status, json.loads(body)["message"]) == (400, "cik must contain one to ten digits")

        status, body = fetch(f"{base}/api/v1/verticals/terra/snapshot?limit=many")
        assert (status, json.loads(body)["message"]) == (400, "limit must be an integer")

        status, body = fetch(f"{base}/api/v1/decision", body={"vertical": "nope", "objective": "x"})
        assert (status, json.loads(body)["message"]) == (400, "unknown vertical")

        status, body = fetch(f"{base}/api/v1/kernel/evaluate", body={"vertical": "a11oy", "receipt": []})
        assert (status, json.loads(body)["message"]) == (400, "receipt must be a JSON object")

        status, body = fetch(f"{base}/api/v1/verify", raw=b"{not json")
        assert (status, json.loads(body)["message"]) == (400, "request body must be valid UTF-8 JSON")

        status, body = fetch(f"{base}/api/v1/verify", raw=b"\xff\xfe")
        assert (status, json.loads(body)["message"]) == (400, "request body must be valid UTF-8 JSON")

        status, body = fetch(f"{base}/api/v1/verticals/puriq/snapshot?cik=320193")
        document = json.loads(body)
        assert (status, document["error"]) == (503, "CONFIGURATION_REQUIRED")
        assert document["message"] == "SEC_USER_AGENT must identify the operator and include a contact email"
