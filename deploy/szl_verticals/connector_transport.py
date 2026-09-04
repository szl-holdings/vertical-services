"""Bounded HTTP transport for fixed authoritative connectors.

Redirects are denied by default. A connector may opt into one HTTPS redirect to
an exact host tuple when the authority itself publishes via a signed object URL
(for example OFAC SLS). Caller-provided destinations are never accepted.
"""
from __future__ import annotations

from typing import Mapping
from urllib.parse import urljoin

import httpx
from fastapi import HTTPException

from .connector_parameters import _assert_allowed_destination, _assert_allowed_redirect


def _read_bounded(response: httpx.Response, max_bytes: int) -> tuple[int, bytes, str]:
    if response.status_code < 200 or response.status_code >= 300:
        raise HTTPException(502, f"upstream returned HTTP {response.status_code}")
    content_length = response.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(502, "upstream response exceeds connector byte budget")
        except ValueError as exc:
            raise HTTPException(502, "upstream returned an invalid content-length") from exc
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_bytes():
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(502, "upstream response exceeds connector byte budget")
        chunks.append(chunk)
    return (
        response.status_code,
        b"".join(chunks),
        response.headers.get("content-type", ""),
    )


def _bounded_get(
    url: str,
    *,
    query: Mapping[str, str],
    headers: Mapping[str, str],
    max_bytes: int,
    transport: httpx.BaseTransport | None = None,
    allowed_redirect_hosts: tuple[str, ...] = (),
    allowed_redirect_path_prefixes: tuple[str, ...] = (),
) -> tuple[int, bytes, str]:
    _assert_allowed_destination(url)
    timeout = httpx.Timeout(12.0, connect=5.0)
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            transport=transport,
        ) as client:
            with client.stream(
                "GET", url, params=dict(query), headers=dict(headers)
            ) as response:
                if 300 <= response.status_code < 400:
                    if not allowed_redirect_hosts:
                        raise HTTPException(502, "upstream redirect rejected by connector policy")
                    location = response.headers.get("location", "").strip()
                    if not location:
                        raise HTTPException(502, "upstream redirect omitted Location")
                    redirected = urljoin(str(response.request.url), location)
                    _assert_allowed_redirect(
                        redirected,
                        allowed_redirect_hosts,
                        allowed_redirect_path_prefixes,
                    )
                else:
                    return _read_bounded(response, max_bytes)

            # Exactly one redirect is permitted and query parameters are already
            # embedded in the authority-issued Location value.
            with client.stream("GET", redirected, headers=dict(headers)) as response:
                if 300 <= response.status_code < 400:
                    raise HTTPException(502, "second upstream redirect rejected")
                return _read_bounded(response, max_bytes)
    except HTTPException:
        raise
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise HTTPException(502, f"connector transport failed: {type(exc).__name__}") from exc
