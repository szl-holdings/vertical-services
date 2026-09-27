"""Inbound HTTP body and JSON bounds for SZL vertical-services.

Limits are enforced before JSON parsing and before any route handler sees
the body. Declared Content-Length is advisory and never trusted as the
only bound: missing, negative, non-integer, and false lengths are
rejected or overridden by the incremental byte budget.

The strict JSON checks (duplicate keys, non-finite numbers, nesting depth)
run on every body that FastAPI will decode as JSON: a missing or empty
Content-Type, ``application/json``, and any ``application/*+json`` type.
That coverage is keyed to the route parser's rule, so no body reaches a
route as JSON without passing the strict parser. Bodies whose Content-Type
merely mentions ``application/json`` (for example ``application/json-seq``)
are also checked, as they were before, so invalid JSON sent with them keeps
the fixed-body 400 instead of the framework's input-echoing 422.

This module is not a production authorization, publisher, or model
identity proof.
"""
from __future__ import annotations

import email.message
import json
import math
import re
import time
from itertools import accumulate
from typing import Any, AsyncIterator, Iterator, Mapping

MAX_BODY_BYTES = 128 * 1024
MAX_READ_SECONDS = 8.0
JSON_OBJECT_REQUIRED = True
# Deepest container nesting ({ or [) accepted in an inbound JSON body. The
# byte budget alone does not bound nesting: 128 KiB of "[" is enough to
# exhaust the interpreter stack in json.loads.
MAX_JSON_DEPTH = 64

_NON_BRACKETS = re.compile(r"[^\[\]{}]+")
_BRACKET_STEP = {"[": 1, "{": 1, "]": -1, "}": -1}


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


def json_nesting_depth(text: str) -> int:
    """Return the deepest container nesting of a JSON text, without recursion.

    Linear time, and the loops run in C. Escaped backslashes and then escaped
    quotes are deleted, so every remaining double quote opens or closes a
    string; keeping only the text between strings drops brackets that sit
    inside strings, and the result is the maximum running bracket balance.

    For valid JSON the result is exact. For invalid JSON it can be wrong, but
    json.loads stops at the first invalid token and recurses only through
    the prefix it parsed, where the running balance is exact, so the result
    is never below the depth json.loads reaches.
    """
    unescaped = text.replace("\\\\", "").replace('\\"', "")
    between_strings = "".join(unescaped.split('"')[0::2])
    brackets = _NON_BRACKETS.sub("", between_strings)
    return max(accumulate(map(_BRACKET_STEP.__getitem__, brackets)), default=0)


def _too_deep() -> BodyBoundError:
    return BodyBoundError(
        "JSON_TOO_DEEP",
        400,
        f"JSON nesting exceeds the {MAX_JSON_DEPTH} level inbound bound",
    )


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
    if json_nesting_depth(text) > MAX_JSON_DEPTH:
        raise _too_deep()
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
    except RecursionError as exc:
        # Unreachable while MAX_JSON_DEPTH is far below the interpreter's
        # recursion limit; kept so a raised bound or a deeper call stack
        # still yields a client error instead of a 500.
        raise _too_deep() from exc
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


def body_is_parsed_as_json(headers: Mapping[str, str]) -> bool:
    """Return True when FastAPI's route parser will decode the body as JSON.

    This mirrors fastapi.routing.get_request_handler: an absent or empty
    Content-Type is decoded as JSON, and otherwise the header is parsed with
    email.message and decoded when the media type is application/json or
    application/<subtype>+json. Parameters and letter case do not matter.
    tests/test_http_bounds.py pins this rule to the installed FastAPI.
    """
    content_type = headers.get("content-type")
    if content_type is None:
        content_type = headers.get("Content-Type")
    if not content_type:
        return True
    message = email.message.Message()
    message["content-type"] = str(content_type)
    if message.get_content_maintype() != "application":
        return False
    subtype = message.get_content_subtype()
    return subtype == "json" or subtype.endswith("+json")


def _names_application_json(headers: Mapping[str, str]) -> bool:
    """The earlier gate: any Content-Type mentioning application/json.

    Kept alongside body_is_parsed_as_json so types such as
    application/json-seq keep their fixed-body 400 for invalid JSON instead
    of falling through to the framework's default 422, which reflects input.
    """
    content_type = headers.get("content-type") or headers.get("Content-Type") or ""
    return "application/json" in str(content_type).lower()


def maybe_parse_json(headers: Mapping[str, str], raw: bytes) -> None:
    """Reject invalid JSON before a route handler materializes it."""
    if not raw:
        return
    if not (body_is_parsed_as_json(headers) or _names_application_json(headers)):
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
