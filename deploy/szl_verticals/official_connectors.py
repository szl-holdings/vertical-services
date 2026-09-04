"""Receipt, cache, and fetch orchestration for official connectors."""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Mapping

import httpx
from fastapi import HTTPException

from .connector_parameters import _redacted_url
from .connector_request_builder import _request_definition
from .connector_transport import _bounded_get
from .connector_specs import CONNECTORS, ConnectorFetchRequest, ConnectorSpec
from .contract import canonical_vertical, connector_state
from .connector_parsers import _normalize, _signal
from .store import STORE

def _query_hash(parameters: Mapping[str, Any]) -> str:
    canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _receipt(
    *,
    spec: ConnectorSpec,
    session_scope: str,
    query_hash: str,
    source_url: str,
    http_status: int,
    payload_sha256: str,
    observed_at: float,
    state: str,
) -> dict[str, Any]:
    body = {
        "schema": "szl.connector-observation/v2",
        "vertical": spec.vertical,
        "connector_id": spec.id,
        "session_scope": session_scope,
        "query_hash": query_hash,
        "source_url": source_url,
        "http_status": http_status,
        "payload_sha256": payload_sha256,
        "observed_at": observed_at,
        "expires_at": observed_at + spec.freshness_seconds,
        "state": state,
        "truth_label": "REPORTED" if state == "OBSERVED" else "UNAVAILABLE",
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {
        **body,
        "receipt_id": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "receipt_algorithm": "SHA-256",
        "signature_claimed": False,
    }


def fetch_connector(
    *,
    vertical: str,
    connector_id: str,
    request: ConnectorFetchRequest,
    session_scope: str,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    canonical = canonical_vertical(vertical)
    spec = CONNECTORS.get(connector_id)
    if spec is None or spec.vertical != canonical:
        raise HTTPException(404, "connector is not assigned to this vertical")
    if spec.auth_env and not os.environ.get(spec.auth_env, "").strip():
        raise HTTPException(503, f"{spec.auth_env} is not configured")
    parameters = request.parameters
    url, query, headers = _request_definition(spec, parameters)
    safe_url = _redacted_url(url, query)
    qhash = _query_hash(parameters)

    if not request.force_refresh:
        cached = STORE.cached(
            vertical=canonical,
            connector_id=connector_id,
            session_scope=session_scope,
            query_hash=qhash,
        )
        if cached:
            return {
                "vertical": canonical,
                "connector": connector_state(spec),
                "observation": cached["summary"],
                "signal": _signal(canonical, connector_id, cached["summary"]),
                "receipt": {
                    key: cached[key]
                    for key in (
                        "receipt_id",
                        "connector_id",
                        "observed_at",
                        "source_url",
                        "http_status",
                        "payload_sha256",
                        "truth_label",
                        "state",
                    )
                },
                "cache": {"hit": True, "fresh": True},
            }

    status, raw, content_type = _bounded_get(
        url,
        query=query,
        headers=headers,
        max_bytes=spec.max_bytes,
        transport=transport,
    )
    observed_at = time.time()
    digest = hashlib.sha256(raw).hexdigest()
    summary = _normalize(spec, raw, content_type, parameters)
    receipt = _receipt(
        spec=spec,
        session_scope=session_scope,
        query_hash=qhash,
        source_url=safe_url,
        http_status=status,
        payload_sha256=digest,
        observed_at=observed_at,
        state="OBSERVED",
    )
    try:
        STORE.put(receipt, summary)
    except RuntimeError as exc:
        raise HTTPException(503, f"observation store unavailable: {exc}") from exc
    return {
        "vertical": canonical,
        "connector": connector_state(spec),
        "observation": summary,
        "signal": _signal(canonical, connector_id, summary),
        "receipt": {key: value for key, value in receipt.items() if key != "session_scope"},
        "cache": {"hit": False, "fresh": True},
    }
