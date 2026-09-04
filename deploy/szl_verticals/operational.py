"""HTTP surface and readiness assembly for the SZL vertical fabric."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from .contract import (
    ALIASES,
    VERTICALS,
    ConnectorFetchRequest,
    advisory_lambda,
    anatomy_for,
    canonical_vertical,
    connectors_for,
    formulas_for,
)
from .core import SessionScope, build_info
from .official_connectors import fetch_connector
from .store import STORE

operational = APIRouter(prefix="/api/verticals", tags=["operational-fabric"])

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
        "readiness": readiness,
        "effectors_enabled": False,
        "human_approval_required": True,
        "truth_label": "MEASURED",
    }


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
    "operational",
    "vertical_readiness",
]
