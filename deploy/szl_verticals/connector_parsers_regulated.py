"""Finance, real-estate, and public-law source normalizers."""
from __future__ import annotations

from typing import Any, Mapping

from fastapi import HTTPException

from .connector_parameters import _bounded_int, _safe_text


def _limit(parameters: Mapping[str, Any], default: int = 10, high: int = 100) -> int:
    return _bounded_int(parameters, "limit", default, 1, high)

def _zip_columns(columns: Mapping[str, Any], limit: int) -> list[dict[str, Any]]:
    keys = [key for key, value in columns.items() if isinstance(value, list)]
    length = min(min([len(columns[key]) for key in keys] or [0]), limit)
    return [{key: columns[key][index] for key in keys} for index in range(length)]


def _parse_sec_submissions(payload: Any, parameters: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(502, "SEC submissions payload schema is not recognized")
    recent = payload.get("filings", {}).get("recent", {})
    return {
        "cik": payload.get("cik"),
        "name": payload.get("name"),
        "tickers": payload.get("tickers", []),
        "exchanges": payload.get("exchanges", []),
        "sic": payload.get("sic"),
        "sic_description": payload.get("sicDescription"),
        "fiscal_year_end": payload.get("fiscalYearEnd"),
        "recent_filings": _zip_columns(recent, _limit(parameters, 20, 100)),
    }


def _parse_sec_companyfacts(payload: Any, parameters: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("facts"), dict):
        raise HTTPException(502, "SEC company-facts payload schema is not recognized")
    concept_query = _safe_text(parameters, "concept", max_length=128).casefold()
    concepts: list[dict[str, Any]] = []
    for taxonomy, values in payload["facts"].items():
        if not isinstance(values, dict):
            continue
        for name, fact in values.items():
            if concept_query and concept_query not in name.casefold():
                continue
            units = fact.get("units", {}) if isinstance(fact, dict) else {}
            latest: list[dict[str, Any]] = []
            for unit, observations in units.items():
                if not isinstance(observations, list):
                    continue
                ordered = sorted(
                    observations,
                    key=lambda item: str(item.get("filed", "")),
                    reverse=True,
                )
                latest.extend(
                    {
                        "unit": unit,
                        "value": item.get("val"),
                        "period_end": item.get("end"),
                        "filed": item.get("filed"),
                        "form": item.get("form"),
                        "accession": item.get("accn"),
                    }
                    for item in ordered[:3]
                )
            concepts.append(
                {
                    "taxonomy": taxonomy,
                    "concept": name,
                    "label": fact.get("label") if isinstance(fact, dict) else None,
                    "description": fact.get("description") if isinstance(fact, dict) else None,
                    "latest": latest[:6],
                }
            )
            if len(concepts) >= _limit(parameters, 20, 100):
                break
        if len(concepts) >= _limit(parameters, 20, 100):
            break
    return {
        "cik": payload.get("cik"),
        "entity_name": payload.get("entityName"),
        "concept_filter": concept_query or None,
        "concepts": concepts,
        "concept_count_returned": len(concepts),
    }


def _parse_pluto(payload: Any, _: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, list):
        raise HTTPException(502, "NYC PLUTO payload schema is not recognized")
    return {"records": payload, "returned": len(payload), "dataset": "PLUTO 64uk-42ks"}


def _parse_federal_register(payload: Any, _: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise HTTPException(502, "Federal Register payload schema is not recognized")
    rows = []
    for item in payload["results"][:20]:
        rows.append(
            {
                key: item.get(key)
                for key in (
                    "document_number",
                    "title",
                    "type",
                    "publication_date",
                    "effective_on",
                    "html_url",
                    "pdf_url",
                    "abstract",
                    "agencies",
                )
            }
        )
    return {
        "count": payload.get("count"),
        "total_pages": payload.get("total_pages"),
        "results": rows,
    }


def _parse_congress(payload: Any, _: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(502, "Congress.gov payload schema is not recognized")
    bills = payload.get("bills", [])
    if not isinstance(bills, list):
        bills = []
    return {
        "pagination": payload.get("pagination"),
        "bills": [
            {
                key: item.get(key)
                for key in ("congress", "type", "number", "title", "originChamber", "updateDate", "url")
            }
            for item in bills[:20]
        ],
    }
