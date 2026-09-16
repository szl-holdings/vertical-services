"""Bounded HTTP adapter for PRISM's non-authorizing text-integrity review."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError

from .claim_integrity import ClaimReviewRequest, review_claims
from .core import SessionScope, build_info
from .counsel_review_ui import REVIEW_CSP, REVIEW_HTML

counsel_review = APIRouter(tags=["counsel-text-integrity"])
MAX_REQUEST_BYTES = 512_000


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate JSON key")
        output[key] = value
    return output


def _reject_constant(value: str) -> None:
    raise ValueError("non-finite JSON constant")


@counsel_review.post("/v1/claim-integrity")
async def claim_integrity_review(request: Request, session: SessionScope) -> JSONResponse:
    """Read a bounded body; validation errors never echo confidential passages.

    The inherited session boundary is not presented as production identity or
    privilege protection. This handler makes no network calls or persistent writes.
    """
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(415, "JSON_REQUIRED")
    body = bytearray()
    try:
        async with asyncio.timeout(5.0):
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_REQUEST_BYTES:
                    raise HTTPException(413, "REVIEW_BODY_TOO_LARGE")
                body.extend(chunk)
    except TimeoutError as exc:
        raise HTTPException(408, "REVIEW_BODY_TIMEOUT") from exc
    try:
        payload = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
        review = ClaimReviewRequest.model_validate(payload)
    except (UnicodeError, ValueError, ValidationError, RecursionError) as exc:
        raise HTTPException(422, "INVALID_REVIEW_REQUEST") from exc
    result = review_claims(review, source_revision=build_info()["source_revision"])
    return JSONResponse(result, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@counsel_review.get("/review", response_class=HTMLResponse)
def claim_integrity_workbench() -> HTMLResponse:
    return HTMLResponse(REVIEW_HTML, headers={
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": REVIEW_CSP,
    })
