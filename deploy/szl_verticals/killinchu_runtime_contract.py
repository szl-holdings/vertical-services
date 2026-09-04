"""Canonical Killinchu product identity for the combined vertical runtime.

Sentra and Vessels remain independently testable engines and compatibility
prefixes. They do not retain separate public-product authority: defensive/cyber
and maritime capability are source-bound lobes of Killinchu.

This module labels identity only. It does not enable an effector, authorize an
action, upgrade data freshness, or turn endpoint reachability into model,
sensor, provider, or operational truth.
"""
from __future__ import annotations

from typing import Any

CANONICAL_PRODUCT = "killinchu"
PRODUCT_STATE = "SOLE_PUBLIC_CYBER_PHYSICAL_RESILIENCE_AUTHORITY"
LOCKED_FORMULA_IDS = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
LAMBDA_STATUS = "CONJECTURE_1_ADVISORY"

LOBES: dict[str, dict[str, Any]] = {
    "aegis": {
        "public_name": "Defend",
        "engine": "sentra",
        "role": "defensive_and_cyber_intelligence",
        "compatibility_prefixes": (
            "/sentra",
            "/api/verticals/sentra",
            "/api/verticals/aegis",
            "/api/verticals/immune",
        ),
    },
    "vessels": {
        "public_name": "Maritime",
        "engine": "vessels",
        "role": "maritime_intelligence",
        "compatibility_prefixes": (
            "/vessels",
            "/api/verticals/vessels",
        ),
    },
}

ALIASES = {
    "aegis": "aegis",
    "defend": "aegis",
    "sentra": "aegis",
    "immune": "aegis",
    "vessels": "vessels",
    "maritime": "vessels",
}


def architecture() -> dict[str, Any]:
    """Return source authority and safety boundaries without a live-state claim."""
    return {
        "schema": "szl.vertical-services.killinchu/v2",
        "canonical_product": CANONICAL_PRODUCT,
        "product_state": PRODUCT_STATE,
        "lobes": {
            name: {
                "public_name": row["public_name"],
                "engine": row["engine"],
                "role": row["role"],
                "compatibility_prefixes": list(row["compatibility_prefixes"]),
                "standalone_product": False,
            }
            for name, row in LOBES.items()
        },
        "locked_formula_ids": list(LOCKED_FORMULA_IDS),
        "lambda_status": LAMBDA_STATUS,
        "human_authority_required": True,
        "receipt_required": True,
        "destructive_or_offensive_autonomy": False,
        "effectors_enabled": False,
        "source_state": "SOFTWARE",
        "runtime_state": "REACHABLE_ONLY_WHEN_THIS_ENDPOINT_ANSWERS",
        "reachability_is_not": [
            "model_quality",
            "sensor_freshness",
            "provider_availability",
            "operational_authorization",
        ],
    }


def lobe(lobe_id: str) -> dict[str, Any]:
    """Resolve a descriptive or compatibility name to one Killinchu lobe."""
    normalized = str(lobe_id or "").strip().lower()
    canonical = ALIASES.get(normalized)
    if canonical is None:
        raise ValueError(f"unknown Killinchu lobe: {lobe_id!r}")
    row = LOBES[canonical]
    return {
        "schema": "szl.vertical-services.killinchu-lobe/v2",
        "canonical_product": CANONICAL_PRODUCT,
        "product_state": PRODUCT_STATE,
        "lobe": canonical,
        "public_name": row["public_name"],
        "engine": row["engine"],
        "role": row["role"],
        "standalone_product": False,
        "source_state": "SOFTWARE",
        "runtime_state": "REACHABLE_ONLY_WHEN_THIS_ENDPOINT_ANSWERS",
        "effectors_enabled": False,
        "human_authority_required": True,
    }


def compatibility_headers(path: str) -> dict[str, str]:
    """Label legacy prefixes without redirecting or changing domain payloads."""
    normalized = "/" + str(path or "").strip().lstrip("/").lower()
    for lobe_id, row in LOBES.items():
        for prefix in row["compatibility_prefixes"]:
            if normalized == prefix or normalized.startswith(prefix + "/"):
                return {
                    "X-SZL-Canonical-Product": CANONICAL_PRODUCT,
                    "X-SZL-Product-Lobe": lobe_id,
                    "X-SZL-Standalone-Product": "false",
                }
    return {}
