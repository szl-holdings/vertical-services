"""Inbound HTTP body and JSON bounds for SZL vertical-services.

Limits are enforced before JSON parsing and before any route handler sees
the body. Declared Content-Length is advisory and never trusted as the
only bound: missing, negative, non-integer, and false lengths are
rejected or overridden by the incremental byte budget.

This module is not a production authorization, publisher, or model
identity proof.
"""
from __future__ import annotations

import json
import math
import time
from typing import Any, AsyncIterator, Iterator, Mapping

MAX_BODY_BYTES = 128 * 1024
MAX_READ_SECONDS = 8.0
JSON_OBJECT_REQUIRED = True


class BodyBoundError(ValueError):
    """A request violated an inbound byte, time, or JSON bound."""

    def __init__(self, code: str, status_code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.message = message


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise BodyBoundError(
                "DUPLICATE_JSON_KEY",
                400,
                "duplicate JSON object keys are rejected",
            )
        out[key] = value
    return out


def _reject_constant(_: str) -> None:
    raise BodyBoundError("NONFINITE_JSON", 400, "non-finite JSON numbers are rejected")


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise BodyBoundError("NONFINITE_JSON", 400, "non-finite JSON numbers are rejected")
    return value


def parse_declared_content_length(headers: Mapping[str, str]) -> int | None:
    raw = headers.get("content-length")
    if raw is None:
        raw = headers.get("Content-Length")
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or not text.isdigit():
        raise BodyBoundError("INVALID_CONTENT_LENGTH", 400, "invalid Content-Length")
    length = int(text)
    if length > MAX_BODY_BYTES:
        raise BodyBoundError(
            "BODY_TOO_LARGE",
            413,
            f"request body exceeds the {MAX_BODY_BYTES} byte inbound budget",
        )
    return length


def parse_strict_json(raw: bytes) -> Any:
    if len(raw) > MAX_BODY_BYTES:
        raise BodyBoundError(
            "BODY_TOO_LARGE",
            413,
            f"request body exceeds the {MAX_BODY_BYTES} byte inbound budget",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BodyBoundError("INVALID_UNICODE", 400, "body must be valid UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except BodyBoundError:
        raise
    except json.JSONDecodeError as exc:
        raise BodyBoundError("INVALID_JSON", 400, "body must be valid JSON") from exc
    if JSON_OBJECT_REQUIRED and not isinstance(value, dict):
        raise BodyBoundError("JSON_OBJECT_REQUIRED", 422, "body must be a JSON object")
    return value


def accumulate_sync(
    chunks: Iterator[bytes],
    *,
    declared_length: int | None = None,
    started_at: float | None = None,
    now: Any = time.monotonic,
) -> bytes:
    """Read a body incrementally. Does not trust Content-Length alone."""
    deadline = (started_at if started_at is not None else now()) + MAX_READ_SECONDS
    data = bytearray()
    for chunk in chunks:
        if now() > deadline:
            raise BodyBoundError("READ_DEADLINE", 408, "request body read exceeded the inbound deadline")
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise BodyBoundError("INVALID_CHUNK", 400, "request body chunk must be bytes")
        piece = bytes(chunk)
        if len(data) + len(piece) > MAX_BODY_BYTES:
            raise BodyBoundError(
                "BODY_TOO_LARGE",
                413,
                f"request body exceeds the {MAX_BODY_BYTES} byte inbound budget",
            )
        data.extend(piece)
    if declared_length is not None and len(data) != declared_length:
        raise BodyBoundError(
            "CONTENT_LENGTH_MISMATCH",
            400,
            "Content-Length does not match the received body",
        )
    return bytes(data)


async def accumulate_async(
    chunks: AsyncIterator[bytes],
    *,
    declared_length: int | None = None,
    started_at: float | None = None,
    now: Any = time.monotonic,
) -> bytes:
    deadline = (started_at if started_at is not None else now()) + MAX_READ_SECONDS
    data = bytearray()
    async for chunk in chunks:
        if now() > deadline:
            raise BodyBoundError("READ_DEADLINE", 408, "request body read exceeded the inbound deadline")
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise BodyBoundError("INVALID_CHUNK", 400, "request body chunk must be bytes")
        piece = bytes(chunk)
        if len(data) + len(piece) > MAX_BODY_BYTES:
            raise BodyBoundError(
                "BODY_TOO_LARGE",
                413,
                f"request body exceeds the {MAX_BODY_BYTES} byte inbound budget",
            )
        data.extend(piece)
    if declared_length is not None and len(data) != declared_length:
        raise BodyBoundError(
            "CONTENT_LENGTH_MISMATCH",
            400,
            "Content-Length does not match the received body",
        )
    return bytes(data)


async def read_bounded_body(request: Any) -> bytes:
    """Read one inbound body from a Starlette/FastAPI request."""
    declared = parse_declared_content_length(request.headers)
    return await accumulate_async(request.stream(), declared_length=declared)


def maybe_parse_json(headers: Mapping[str, str], raw: bytes) -> None:
    """Reject invalid JSON before a route handler materializes it."""
    content_type = str(headers.get("content-type") or headers.get("Content-Type") or "")
    if "application/json" not in content_type.lower():
        return
    if not raw:
        return
    parse_strict_json(raw)


def error_payload(exc: BodyBoundError) -> dict[str, Any]:
    return {
        "ok": False,
        "error": exc.message,
        "code": exc.code,
        "production_authorization": False,
        "effectors_enabled": False,
    }
