"""Dispatch provider normalization and derive vertical signals."""
from __future__ import annotations

import json
from typing import Any, Mapping

from fastapi import HTTPException

from .connector_parsers_frontier import (
    _parse_coinbase,
    _parse_dob_violations,
    _parse_hpd_violations,
    _parse_polymarket,
    _parse_treasury_rates,
)
from .connector_parsers_maritime import _parse_noaa
from .connector_parsers_regulated import (
    _parse_congress,
    _parse_federal_register,
    _parse_pluto,
    _parse_sec_companyfacts,
    _parse_sec_submissions,
)
from .connector_parsers_security import _parse_cisa, _parse_github, _parse_nvd
from .connector_specs import ConnectorSpec
from .domain_math import delivery_reliability

JSON_PARSERS = {
    "cisa-kev": _parse_cisa,
    "nvd-cve": _parse_nvd,
    "github-actions": _parse_github,
    "sec-submissions": _parse_sec_submissions,
    "sec-companyfacts": _parse_sec_companyfacts,
    "polymarket-markets": _parse_polymarket,
    "coinbase-spot": _parse_coinbase,
    "treasury-average-rates": _parse_treasury_rates,
    "nyc-pluto": _parse_pluto,
    "nyc-hpd-violations": _parse_hpd_violations,
    "nyc-dob-violations": _parse_dob_violations,
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
    parser = JSON_PARSERS.get(spec.id)
    if parser is None:
        raise HTTPException(500, f"connector parser is not implemented: {spec.id}")
    return parser(decoded, parameters)


def _signal(vertical: str, connector_id: str, summary: Mapping[str, Any]) -> dict[str, Any]:
    if connector_id == "cisa-kev":
        count = int(summary.get("matched") or 0)
        return {
            "kind": "known-exploited-vulnerability-load",
            "value": count,
            "severity": "HIGH" if count else "INFO",
            "next_route": "/experience/aegis",
        }
    if connector_id == "nvd-cve":
        count = int(summary.get("total_results") or 0)
        return {
            "kind": "cve-enrichment-results",
            "value": count,
            "severity": "INFO",
            "next_route": "/experience/sentra",
        }
    if connector_id == "github-actions":
        rate = summary.get("success_rate")
        reliability = delivery_reliability(rate)
        return {
            "kind": "delivery-health",
            "value": rate,
            "severity": "HIGH" if rate is not None and float(rate) < 0.8 else "INFO",
            "reliability": reliability,
            "next_route": "/experience/lyte",
        }
    if connector_id == "noaa-ais-2025":
        return {
            "kind": "official-ais-corpus-availability",
            "value": summary.get("status"),
            "severity": "INFO",
            "live_feed": False,
            "next_route": "/experience/killinchu",
        }
    if connector_id == "sec-submissions":
        count = len(summary.get("recent_filings", []))
        return {
            "kind": "recent-company-filings",
            "value": count,
            "severity": "INFO",
            "next_route": "/experience/puriq",
        }
    if connector_id == "sec-companyfacts":
        count = int(summary.get("concept_count_returned") or 0)
        return {
            "kind": "xbrl-fact-coverage",
            "value": count,
            "severity": "INFO",
            "next_route": "/experience/puriq",
        }
    if connector_id == "polymarket-markets":
        count = int(summary.get("returned") or 0)
        return {
            "kind": "prediction-market-coverage",
            "value": count,
            "volume_24h_total": summary.get("volume_24h_total"),
            "severity": "INFO" if count else "MEDIUM",
            "trading_enabled": False,
            "next_route": "/experience/puriq",
        }
    if connector_id == "coinbase-spot":
        return {
            "kind": "crypto-spot-reference",
            "value": summary.get("amount"),
            "unit": summary.get("currency"),
            "severity": "INFO",
            "trading_enabled": False,
            "next_route": "/experience/puriq",
        }
    if connector_id == "treasury-average-rates":
        return {
            "kind": "treasury-rate-surface",
            "value": summary.get("returned"),
            "latest_record_date": summary.get("latest_record_date"),
            "severity": "INFO",
            "next_route": "/experience/puriq",
        }
    if connector_id == "nyc-pluto":
        count = int(summary.get("returned") or 0)
        return {
            "kind": "parcel-record-coverage",
            "value": count,
            "severity": "INFO" if count else "MEDIUM",
            "next_route": "/experience/terra",
        }
    if connector_id == "nyc-hpd-violations":
        load = (
            summary.get("distress_load", {}).get("normalized_load")
            if isinstance(summary.get("distress_load"), dict)
            else None
        )
        return {
            "kind": "housing-code-distress-load",
            "value": load,
            "severity": "HIGH" if load is not None and float(load) >= 0.5 else "INFO",
            "person_level_prospecting": False,
            "next_route": "/experience/terra",
        }
    if connector_id == "nyc-dob-violations":
        count = int(summary.get("open_without_disposition") or 0)
        return {
            "kind": "building-violation-load",
            "value": count,
            "severity": "MEDIUM" if count else "INFO",
            "person_level_prospecting": False,
            "next_route": "/experience/terra",
        }
    if connector_id in {"federal-register", "congress-bills"}:
        count = len(summary.get("results", summary.get("bills", [])))
        return {
            "kind": "public-legal-authority",
            "value": count,
            "severity": "INFO",
            "next_route": "/experience/prism",
        }
    return {
        "kind": "observation",
        "value": None,
        "severity": "INFO",
        "vertical": vertical,
    }
