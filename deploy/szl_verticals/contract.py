"""Shared contract helpers for the SZL vertical operational fabric."""
from __future__ import annotations

import math
import os
from dataclasses import asdict
from typing import Any, Mapping

from fastapi import HTTPException

from .connector_specs import CONNECTORS, ConnectorFetchRequest, ConnectorSpec
from .formulas import FORMULAS
from .profiles import ALIASES, ANATOMY_ORGANS, CANONICAL_VERTICALS, VERTICALS

def canonical_vertical(value: str) -> str:
    normalized = value.strip().lower()
    normalized = ALIASES.get(normalized, normalized)
    if normalized not in VERTICALS:
        raise HTTPException(404, f"unknown vertical: {value}")
    return normalized


def advisory_lambda(axes: Mapping[str, float]) -> dict[str, Any]:
    """Apply the canonical weighted-geometric-mean shape as an advisory score."""
    if not axes:
        raise ValueError("at least one axis is required")
    clean: dict[str, float] = {}
    for name, value in axes.items():
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0.0 or numeric > 1.0:
            raise ValueError(f"axis {name!r} must be finite and within [0,1]")
        clean[name] = numeric
    if any(value == 0.0 for value in clean.values()):
        score = 0.0
    else:
        weight = 1.0 / len(clean)
        score = math.exp(sum(weight * math.log(value) for value in clean.values()))
    return {
        "score": round(score, 6),
        "axes": clean,
        "weights": {name: round(1.0 / len(clean), 6) for name in clean},
        "label": "ADVISORY",
        "lambda_status": "Conjecture 1 (open) — uniqueness unproven",
        "truth_label": "MODELED",
    }


def connector_state(spec: ConnectorSpec) -> dict[str, Any]:
    configured = not spec.auth_env or bool(os.environ.get(spec.auth_env, "").strip())
    if spec.auth_env and not configured:
        state = "AUTH_REQUIRED"
    else:
        state = "READY"
    return {
        **asdict(spec),
        "state": state,
        "configured": configured,
        "credential_present": configured if spec.auth_env else None,
        "credential_value_exposed": False,
    }


def connectors_for(vertical: str) -> list[dict[str, Any]]:
    canonical = canonical_vertical(vertical)
    return [
        connector_state(spec)
        for spec in CONNECTORS.values()
        if spec.vertical == canonical
    ]


def formulas_for(vertical: str) -> list[dict[str, Any]]:
    canonical = canonical_vertical(vertical)
    return [
        {"id": formula_id, **FORMULAS[formula_id]}
        for formula_id in VERTICALS[canonical]["formula_ids"]
    ]


def anatomy_for(vertical: str) -> dict[str, Any]:
    canonical = canonical_vertical(vertical)
    profile = VERTICALS[canonical]
    return {
        "schema": "szl.living-anatomy.vertical/v2",
        "vertical": canonical,
        "product": profile["product"],
        "domain": profile["domain"],
        "mission": profile["mission"],
        "organs": list(ANATOMY_ORGANS),
        "formula_ids": list(profile["formula_ids"]),
        "connector_ids": [
            item["id"] for item in connectors_for(canonical)
        ],
        "canonical_repository": profile["canonical_repository"],
        "public_space": profile["public_space"],
        "consolidation": profile.get("consolidation"),
        "truth_label": "MEASURED",
    }

__all__ = [
    "ALIASES", "ANATOMY_ORGANS", "CANONICAL_VERTICALS", "CONNECTORS",
    "ConnectorFetchRequest", "ConnectorSpec", "FORMULAS", "VERTICALS",
    "advisory_lambda", "anatomy_for", "canonical_vertical",
    "connector_state", "connectors_for", "formulas_for",
]
