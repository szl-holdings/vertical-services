"""HTTP surface and readiness assembly for the SZL vertical fabric."""
from __future__ import annotations

from typing import Any
import sqlite3

from fastapi import APIRouter, HTTPException, Query

from .contract import (
    ALIASES,
    VERTICALS,
    ConnectorFetchRequest,
    advisory_lambda,
    anatomy_for,
    canonical_vertical,
    connectors_for,
    formulas_for,
    telemetry_contract_for,
)
from .core import RedactedValidationRoute, SessionScope, build_info
from .briefs import WeeklyBriefRequest
from .official_connectors import fetch_connector
from .published_briefs import ArchiveUnavailable, published_brief_summary, published_briefs
from .store import STORE
from .lyte import (
    TelemetryEvent,
    lyte_telemetry_ingest,
    telemetry_projection,
    telemetry_search_projection,
)

operational = APIRouter(prefix="/api/verticals", tags=["operational-fabric"], route_class=RedactedValidationRoute)

def vertical_readiness(vertical: str, session_scope: str | None = None) -> dict[str, Any]:
    canonical = canonical_vertical(vertical)
    profile = VERTICALS[canonical]
    build = build_info()
    store = STORE.status()
    connectors = connectors_for(canonical)
    required = [item for item in connectors if item["required"]]
    connector_contract_ready = bool(required) and all(item["state"] == "READY" for item in required)
    signing_ready = True
    if canonical in {"sentra", "killinchu"}:
        from .sentra import SENTRA_KEY_SOURCE

        signing_ready = SENTRA_KEY_SOURCE == "env"
    counts = STORE.counts(vertical=canonical, session_scope=session_scope)
    axes = {
        "source_binding": 1.0 if build["build"]["state"] == "OBSERVED" else 0.25,
        "observation_store": 1.0 if store["writable"] else 0.0,
        "connector_contract": 1.0 if connector_contract_ready else 0.0,
        "formula_binding": 1.0 if profile["formula_ids"] else 0.0,
        "live_observation": 1.0 if counts["observations"] else 0.5,
    }
    lambda_score = advisory_lambda(axes)
    production_ready = (
        build["build"]["state"] == "OBSERVED"
        and store["writable"]
        and connector_contract_ready
        and signing_ready
    )
    return {
        "schema": "szl.vertical-readiness/v2",
        "vertical": canonical,
        "product": profile["product"],
        "ready": production_ready,
        "status": "READY" if production_ready else "DEGRADED",
        "requirements": {
            "source_bound": build["build"]["state"] == "OBSERVED",
            "observation_store_writable": store["writable"],
            "required_connector_contracts_ready": connector_contract_ready,
            "persistent_signing_key": signing_ready,
            "formula_registry_bound": bool(profile["formula_ids"]),
        },
        "live_data": {
            "wired": connector_contract_ready,
            "observed_in_scope": counts["observations"] > 0,
            **counts,
        },
        "build": build["build"],
        "store": store,
        "connectors": connectors,
        "lambda_advisory": lambda_score,
        "canonical_repository": profile["canonical_repository"],
        "public_space": profile["public_space"],
        "consolidation": profile.get("consolidation"),
        "truth_label": "MEASURED",
    }


@operational.get("")
def vertical_catalog() -> dict[str, Any]:
    return {
        "schema": "szl.vertical-catalog/v2",
        "verticals": {
            vertical: {
                **profile,
                "connectors": [item["id"] for item in connectors_for(vertical)],
            }
            for vertical, profile in VERTICALS.items()
        },
        "aliases": ALIASES,
        "vessels_independent_vertical": False,
        "truth_label": "MEASURED",
    }


@operational.get("/search")
def vertical_search(
    q: str = Query(..., min_length=1, max_length=128),
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    """Search the governed public catalog without requiring a session token."""
    # Import lazily because intelligence uses the operational readiness helper.
    from .intelligence import KERNEL_ASSETS, MODEL_ASSETS

    needle = q.casefold().strip()
    items: list[dict[str, Any]] = []
    for canonical, profile in VERTICALS.items():
        haystack = " ".join(
            str(profile.get(field, ""))
            for field in ("product", "domain", "mission", "canonical_repository", "public_space")
        ) + f" {canonical}"
        if needle in haystack.casefold():
            items.append({
                "canonical_id": f"vertical:{canonical}",
                "id": canonical,
                "kind": "vertical",
                "name": profile["product"],
                "provider": "szl-vertical-services",
                "state": "CONFIGURED",
                "truth_label": "MEASURED",
                "source_url": f"/api/verticals/{canonical}/anatomy",
                "href": f"/api/verticals/{canonical}/anatomy",
                "telemetry_route": (
                    f"/api/verticals/{canonical}/telemetry" if canonical == "lyte" else None
                ),
            })
        for connector in connectors_for(canonical):
            connector_haystack = " ".join(
                str(connector.get(field, ""))
                for field in ("id", "provider", "authority", "description", "source_url", "authority_url", "state")
            )
            if needle not in connector_haystack.casefold():
                continue
            connector_id = connector["id"]
            items.append({
                "canonical_id": f"connector:{connector_id}",
                "id": connector_id,
                "kind": "connector",
                "name": connector.get("description", connector_id),
                "provider": connector.get("provider") or connector.get("authority", "UNSPECIFIED"),
                "state": connector.get("state", "UNAVAILABLE"),
                "truth_label": "MEASURED",
                "source_url": f"/api/verticals/{canonical}/connectors",
                "href": f"/api/verticals/{canonical}/connectors",
                "vertical": canonical,
            })
        if len(items) >= limit:
            break
    if len(items) < limit:
        for alias, asset in MODEL_ASSETS.items():
            haystack = " ".join(str(asset.get(field, "")) for field in (
                "repo_id", "artifact_class", "runtime", "role", "license", "qualification_truth_label",
            )) + f" {alias}"
            if needle not in haystack.casefold():
                continue
            items.append({
                "canonical_id": f"model:{alias}",
                "id": alias,
                "kind": "model",
                "name": asset.get("repo_id", alias),
                "provider": "huggingface",
                "state": asset.get("qualification_truth_label", asset.get("runtime", "UNAVAILABLE")),
                "truth_label": "MEASURED",
                "source_url": f"/api/verticals/lyte/intelligence",
                "href": f"/api/verticals/lyte/intelligence",
                "rights": asset.get("license", "UNSPECIFIED"),
            })
            if len(items) >= limit:
                break
    if len(items) < limit:
        for alias, asset in KERNEL_ASSETS.items():
            haystack = " ".join(str(asset.get(field, "")) for field in ("repo_id", "role", "execution_state")) + f" {alias}"
            if needle not in haystack.casefold():
                continue
            items.append({
                "canonical_id": f"kernel:{alias}",
                "id": alias,
                "kind": "kernel",
                "name": asset.get("repo_id", alias),
                "provider": "szl-kernels",
                "state": asset.get("execution_state", "UNAVAILABLE"),
                "truth_label": "MEASURED",
                "source_url": "/api/intelligence",
                "href": "/api/intelligence",
            })
            if len(items) >= limit:
                break
    items = items[:limit]
    return {
        "schema": "szl.operational-search/v1",
        "query": q,
        "count": len(items),
        "limit": limit,
        "items": items,
        "live_binding": "CATALOG_METADATA",
        "object_kinds": ["vertical", "connector", "model", "kernel"],
        "receipt_backed": False,
        "telemetry_included": False,
        "telemetry_requires_session": True,
        "dataset_inventory_state": "PUBLIC_INVENTORY_CONNECTOR_AVAILABLE",
        "dataset_inventory_route": "/api/verticals/lyte/connectors/hf-datasets/fetch",
        "dataset_inventory_requires_session": True,
        "truth_label": "MEASURED",
    }


@operational.get("/{vertical}/anatomy")
def vertical_anatomy(vertical: str) -> dict[str, Any]:
    return anatomy_for(vertical)


@operational.get("/{vertical}/formulas")
def vertical_formulas(vertical: str) -> dict[str, Any]:
    canonical = canonical_vertical(vertical)
    formulas = formulas_for(canonical)
    return {
        "schema": "szl.formula-binding.vertical/v2",
        "vertical": canonical,
        "count": len(formulas),
        "formulas": formulas,
        "canonical_formula_repository": "szl-holdings/szl-formulas",
        "lean_proof_repository": "szl-holdings/lutar-lean",
        "lambda_status": "Conjecture 1 (open) — advisory only",
        "truth_label": "MEASURED",
    }


@operational.get("/{vertical}/connectors")
def vertical_connectors(vertical: str) -> dict[str, Any]:
    canonical = canonical_vertical(vertical)
    connectors = connectors_for(canonical)
    return {
        "schema": "szl.connector-catalog.vertical/v2",
        "vertical": canonical,
        "count": len(connectors),
        "connectors": connectors,
        "caller_supplied_urls_allowed": False,
        "redirects_allowed": False,
        "secrets_exposed": False,
        "truth_label": "MEASURED",
    }


@operational.get("/{vertical}/readyz")
def vertical_ready(vertical: str) -> dict[str, Any]:
    return vertical_readiness(vertical)


@operational.get("/{vertical}/second-brain")
def vertical_second_brain(
    vertical: str,
    session: SessionScope,
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    canonical = canonical_vertical(vertical)
    recent = STORE.recent(vertical=canonical, session_scope=session, limit=limit)
    readiness = vertical_readiness(canonical, session_scope=session)
    return {
        "schema": "szl.second-brain.vertical/v2",
        "vertical": canonical,
        "product": VERTICALS[canonical]["product"],
        "anatomy": anatomy_for(canonical),
        "formula_binding": formulas_for(canonical),
        "connector_state": connectors_for(canonical),
        "memory": {
            "scope": "HASHED_CALLER_SESSION",
            "store": STORE.status(),
            "count": len(recent),
            "observations": recent,
        },
        "telemetry": (
            telemetry_projection(session, limit=min(limit, 100))
            if canonical == "lyte"
            else telemetry_contract_for(canonical)
        ),
        "weekly_briefs": {
            "scope": "HASHED_CALLER_SESSION",
            "truth_label": "CALLER_REPORTED",
            "review_status": "REVIEW_REQUIRED",
            "counts_as_connector_evidence": False,
            "items": [
                {key: item[key] for key in ("vertical", "content_sha256", "created_at", "truth_label", "review_status")}
                | {"title": item["brief"]["title"], "week_start": item["brief"]["week_start"],
                   "coverage_state": item["brief"].get("coverage_state", "DEVELOPMENTS")}
                for item in _briefs_for(canonical, session, min(limit, 25))
            ],
        },
        "published_briefs": published_brief_summary(canonical, min(limit, 25)),
        "readiness": readiness,
        "effectors_enabled": False,
        "human_approval_required": True,
        "truth_label": "MEASURED",
    }


@operational.get("/{vertical}/telemetry")
def vertical_telemetry(
    vertical: str,
    session: SessionScope,
    limit: int = Query(50, ge=1, le=200),
    receipt_id: str | None = Query(None, min_length=64, max_length=64),
    trace_id: str | None = Query(None, min_length=1, max_length=128),
    span_id: str | None = Query(None, min_length=1, max_length=128),
    dataset_id: str | None = Query(None, min_length=1, max_length=256),
    model_id: str | None = Query(None, min_length=1, max_length=256),
    provider: str | None = Query(None, min_length=1, max_length=128),
    cohort: str | None = Query(None, min_length=1, max_length=256),
    outcome: str | None = Query(None, min_length=1, max_length=128),
    deployment_revision: str | None = Query(None, min_length=1, max_length=256),
    source_state: str | None = Query(None, min_length=1, max_length=32),
) -> dict[str, Any]:
    canonical = canonical_vertical(vertical)
    if canonical != "lyte":
        raise HTTPException(404, "telemetry projection is assigned to lyte")
    projection = telemetry_projection(
        session,
        limit=limit,
        receipt_id=receipt_id,
        filters={
            "trace_id": trace_id, "span_id": span_id, "dataset_id": dataset_id,
            "model_id": model_id, "provider": provider, "cohort": cohort,
            "outcome": outcome, "deployment_revision": deployment_revision,
            "source_state": source_state,
        },
    )
    if receipt_id is not None and not projection["items"]:
        raise HTTPException(404, "telemetry receipt not found")
    return projection


@operational.post("/{vertical}/telemetry")
def vertical_telemetry_ingest(
    vertical: str,
    event: TelemetryEvent,
    session: SessionScope,
) -> dict[str, Any]:
    canonical = canonical_vertical(vertical)
    if canonical != "lyte":
        raise HTTPException(404, "telemetry projection is assigned to lyte")
    return lyte_telemetry_ingest(event, session)


@operational.get("/{vertical}/telemetry/search")
def vertical_telemetry_search(
    vertical: str,
    session: SessionScope,
    q: str | None = Query(None, min_length=1, max_length=256),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    canonical = canonical_vertical(vertical)
    if canonical != "lyte":
        raise HTTPException(404, "telemetry projection is assigned to lyte")
    return telemetry_search_projection(session, q=q, limit=limit)


def _briefs_for(vertical: str, session: str, limit: int) -> list[dict[str, Any]]:
    try:
        return STORE.recent_briefs(vertical, session, limit)
    except (OSError, sqlite3.Error, RuntimeError):
        raise HTTPException(503, "brief store unavailable") from None


@operational.get("/{vertical}/published-briefs")
def vertical_published_briefs(vertical: str, limit: int = Query(10, ge=1, le=25)) -> dict[str, Any]:
    try:
        return published_briefs(vertical, limit)
    except ArchiveUnavailable:
        raise HTTPException(503, "published brief archive unavailable") from None


@operational.get("/{vertical}/briefs")
def vertical_briefs(vertical: str, session: SessionScope, limit: int = Query(10, ge=1, le=25)) -> dict[str, Any]:
    canonical = canonical_vertical(vertical)
    return {
        "schema": "szl.weekly-brief-list/v1", "vertical": canonical,
        "items": _briefs_for(canonical, session, limit), "store": STORE.status(),
        "truth_label": "CALLER_REPORTED", "review_status": "REVIEW_REQUIRED",
        "counts_as_connector_evidence": False,
    }


@operational.post("/{vertical}/briefs")
def create_vertical_brief(vertical: str, request: WeeklyBriefRequest, session: SessionScope) -> dict[str, Any]:
    canonical = canonical_vertical(vertical)
    try:
        return STORE.put_brief(canonical, session, request)
    except ValueError:
        raise HTTPException(413, "brief exceeds size or scope capacity") from None
    except (OSError, sqlite3.Error, RuntimeError):
        raise HTTPException(503, "brief store unavailable") from None


@operational.post("/{vertical}/connectors/{connector_id}/fetch")
def connector_fetch_endpoint(
    vertical: str,
    connector_id: str,
    request: ConnectorFetchRequest,
    session: SessionScope,
) -> dict[str, Any]:
    return fetch_connector(
        vertical=vertical,
        connector_id=connector_id,
        request=request,
        session_scope=session,
    )


__all__ = [
    "ConnectorFetchRequest",
    "STORE",
    "advisory_lambda",
    "anatomy_for",
    "fetch_connector",
    "formulas_for",
    "telemetry_contract_for",
    "vertical_telemetry",
    "vertical_telemetry_search",
    "operational",
    "vertical_readiness",
]
