"""Bounded, no-redirect HTTP transport for official connectors."""
from __future__ import annotations

from typing import Mapping

import httpx
from fastapi import HTTPException

from .connector_parameters import _assert_allowed_destination

def _bounded_get(
    url: str,
    *,
    query: Mapping[str, str],
    headers: Mapping[str, str],
    max_bytes: int,
    transport: httpx.BaseTransport | None = None,
) -> tuple[int, bytes, str]:
    _assert_allowed_destination(url)
    timeout = httpx.Timeout(12.0, connect=5.0)
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            transport=transport,
        ) as client:
            with client.stream("GET", url, params=dict(query), headers=dict(headers)) as response:
                if 300 <= response.status_code < 400:
                    raise HTTPException(502, "upstream redirect rejected by connector policy")
                if response.status_code < 200 or response.status_code >= 300:
                    raise HTTPException(502, f"upstream returned HTTP {response.status_code}")
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    raise HTTPException(502, "upstream response exceeds connector byte budget")
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise HTTPException(502, "upstream response exceeds connector byte budget")
                    chunks.append(chunk)
                return response.status_code, b"".join(chunks), response.headers.get("content-type", "")
    except HTTPException:
        raise
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise HTTPException(502, f"connector transport failed: {type(exc).__name__}") from exc
