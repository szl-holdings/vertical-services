"""Small deterministic domain formulas used by connector normalization.

These functions transform already-observed public data. They never fetch data,
place trades, infer protected traits, or independently authorize action.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


def clamp01(value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        return 0.0
    return min(1.0, max(0.0, numeric))


def binary_entropy(probability: float) -> float:
    """Return normalized binary Shannon entropy in [0, 1]."""
    p = clamp01(probability)
    if p in {0.0, 1.0}:
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


def probability_edge(probability: float, reference: float = 0.5) -> float:
    """Signed distance from a bounded reference probability."""
    return round(clamp01(probability) - clamp01(reference), 8)


def weighted_distress_load(class_counts: Mapping[str, Any]) -> dict[str, Any]:
    """Compute a transparent HPD-style severity load from A/B/C counts."""
    weights = {"A": 1.0, "B": 2.0, "C": 4.0}
    clean: dict[str, int] = {}
    for class_name, weight in weights.items():
        try:
            count = max(0, int(class_counts.get(class_name, 0)))
        except (TypeError, ValueError):
            count = 0
        clean[class_name] = count
    total = sum(clean.values())
    weighted = sum(clean[name] * weights[name] for name in weights)
    normalized = weighted / (4.0 * total) if total else 0.0
    return {
        "class_counts": clean,
        "record_count": total,
        "weighted_load": round(weighted, 6),
        "normalized_load": round(clamp01(normalized), 6),
        "weights": weights,
        "truth_label": "MODELED",
    }


def delivery_reliability(success_rate: float | None) -> dict[str, Any]:
    """Map an observed success rate to a bounded review band."""
    if success_rate is None:
        return {
            "score": None,
            "band": "UNAVAILABLE",
            "truth_label": "UNAVAILABLE",
        }
    score = clamp01(success_rate)
    if score >= 0.95:
        band = "HEALTHY"
    elif score >= 0.80:
        band = "WATCH"
    else:
        band = "DEGRADED"
    return {
        "score": round(score, 6),
        "band": band,
        "truth_label": "MODELED",
    }
