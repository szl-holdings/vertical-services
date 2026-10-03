"""Bound untrusted model replies before decoding or returning generated text."""
from __future__ import annotations

import json
import math
import re
from typing import Any

import httpx
from fastapi import HTTPException

from .http_bounds import body_is_parsed_as_json, json_nesting_depth

MAX_PROVIDER_BYTES = 2_000_000
MAX_PROVIDER_JSON_DEPTH = 64
READ_CHUNK_BYTES = 64 * 1024
_LENGTH = re.compile(r"^[0-9]{1,20}$")


def _too_large() -> HTTPException:
    return HTTPException(502, "model provider response exceeded the bounded size")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("non-finite JSON number")


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("non-finite JSON number")
    return value


async def read_provider_json(response: httpx.Response) -> dict[str, Any] | list[Any]:
    """Stream at most the byte budget, then reject ambiguous or deep JSON.

    The caller requests identity encoding. Refusing other encodings before a
    read prevents a decompressor from materializing an unbounded expansion.
    Content-Length is advisory; every received chunk is counted independently.
    Error messages never reflect provider data.
    """
    if 300 <= response.status_code < 400:
        raise HTTPException(502, "model provider redirect refused")
    if not 200 <= response.status_code < 300:
        raise HTTPException(502, f"model provider returned HTTP {response.status_code}")
    if not body_is_parsed_as_json(response.headers):
        raise HTTPException(502, "model provider response was not JSON")
    encoding = response.headers.get("content-encoding", "identity").strip().lower()
    if encoding not in {"", "identity"}:
        raise HTTPException(502, "model provider response encoding refused")
    declared = response.headers.get("content-length")
    if declared is not None:
        if _LENGTH.fullmatch(declared) is None:
            raise HTTPException(502, "model provider returned invalid Content-Length")
        declared = int(declared)
        if declared > MAX_PROVIDER_BYTES:
            raise _too_large()

    body = bytearray()
    async for chunk in response.aiter_bytes(chunk_size=READ_CHUNK_BYTES):
        if len(body) + len(chunk) > MAX_PROVIDER_BYTES:
            raise _too_large()
        body.extend(chunk)
    if declared is not None and len(body) != declared:
        raise HTTPException(502, "model provider Content-Length mismatch")
    try:
        text = body.decode("utf-8")
        if json_nesting_depth(text) > MAX_PROVIDER_JSON_DEPTH:
            raise ValueError("JSON depth exceeded")
        value = json.loads(text, object_pairs_hook=_unique_object,
                           parse_constant=_reject_constant, parse_float=_finite_float)
        if not isinstance(value, (dict, list)):
            raise ValueError("JSON object or array required")
        return value
    except (ValueError, RecursionError):
        raise HTTPException(502, "model provider returned invalid bounded JSON") from None
