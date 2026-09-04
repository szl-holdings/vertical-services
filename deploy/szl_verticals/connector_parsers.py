"""Dispatch provider normalization and derive vertical signals."""
from __future__ import annotations

import json
from typing import Any, Mapping

from fastapi import HTTPException

from .connector_specs import ConnectorSpec
from .connector_parsers_maritime import _parse_noaa
from .connector_parsers_regulated import (
    _parse_congress, _parse_federal_register, _parse_pluto,
    _parse_sec_companyfacts, _parse_sec_submissions,
)
from .connector_parsers_security import _parse_cisa, _parse_github, _parse_nvd


JSON_PARSERS = {
    "cisa-kev": _parse_cisa,
    "nvd-cve": _parse_nvd,
    "github-actions": _parse_github,
    "sec-submissions": _parse_sec_submissions,
    "sec-companyfacts": _parse_sec_companyfacts,
    "nyc-pluto": _parse_pluto,
    "federal-register": _parse_federal_register,
    "congress-bills": _parse_congress,
}

def _normalize(
    spec: ConnectorSpec,
    raw: bytes,
    content_type: str,
    parameters: Mapping[str, Any],
) -> dict[str, Any]:
    if spec.response_format == "xml":
        return _parse_noaa(raw, parameters)
    try:
        decoded = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(502, f"{spec.id} returned invalid JSON") from exc
    parser = JSON_PARSERS[spec.id]
    return parser(decoded, parameters)


def _signal(vertical: str, connector_id: str, summary: Mapping[str, Any]) -> dict[str, Any]:
    if connector_id == "cisa-kev":
        count = int(summary.get("matched") or 0)
        return {
            "kind": "known-exploited-vulnerability-load",
            "value": count,
            "severity": "HIGH" if count else "INFO",
            "next_route": "/sentra/v1/evaluate",
        }
    if connector_id == "nvd-cve":
        count = int(summary.get("total_results") or 0)
        return {"kind": "cve-enrichment-results", "value": count, "severity": "INFO"}
    if connector_id == "github-actions":
        rate = summary.get("success_rate")
        return {
            "kind": "delivery-health",
            "value": rate,
            "severity": "HIGH" if rate is not None and rate < 0.8 else "INFO",
            "next_route": "/lyte/v1/metrics",
        }
    if connector_id == "noaa-ais-2025":
        return {
            "kind": "official-ais-corpus-availability",
            "value": summary.get("status"),
            "severity": "INFO",
            "live_feed": False,
            "next_route": "/killinchu/v1/maritime/positions",
        }
    if connector_id == "sec-submissions":
        count = len(summary.get("recent_filings", []))
        return {"kind": "recent-company-filings", "value": count, "severity": "INFO"}
    if connector_id == "sec-companyfacts":
        count = int(summary.get("concept_count_returned") or 0)
        return {"kind": "xbrl-fact-coverage", "value": count, "severity": "INFO"}
    if connector_id == "nyc-pluto":
        count = int(summary.get("returned") or 0)
        return {
            "kind": "parcel-record-coverage",
            "value": count,
            "severity": "INFO" if count else "MEDIUM",
            "next_route": "/terra/v1/listings",
        }
    if connector_id in {"federal-register", "congress-bills"}:
        count = len(summary.get("results", summary.get("bills", [])))
        return {
            "kind": "public-legal-authority",
            "value": count,
            "severity": "INFO",
            "next_route": "/counsel/v1/matters",
        }
    return {"kind": "observation", "value": None, "severity": "INFO", "vertical": vertical}
