"""PURIQ market and Terra condition-source normalizers."""
from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any, Mapping

from fastapi import HTTPException

from .connector_parameters import _bounded_int
from .domain_math import binary_entropy, probability_edge, weighted_distress_load


def _limit(parameters: Mapping[str, Any], default: int, high: int) -> int:
    return _bounded_int(parameters, "limit", default, 1, high)


def _number(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        return decoded if isinstance(decoded, list) else []
    return []


def _parse_polymarket(payload: Any, parameters: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, list):
        raise HTTPException(502, "Polymarket Gamma payload schema is not recognized")
    markets: list[dict[str, Any]] = []
    volume_total = 0.0
    liquidity_total = 0.0
    for item in payload[: _limit(parameters, 20, 100)]:
        if not isinstance(item, dict):
            continue
        outcomes = [str(value)[:80] for value in _json_list(item.get("outcomes"))]
        prices_raw = _json_list(item.get("outcomePrices"))
        prices = [_number(value) for value in prices_raw]
        probabilities = [
            min(1.0, max(0.0, value))
            for value in prices
            if value is not None
        ]
        pairs = [
            {"outcome": outcome, "probability": probability}
            for outcome, probability in zip(outcomes, probabilities)
        ]
        yes_probability: float | None = None
        for pair in pairs:
            if pair["outcome"].strip().casefold() == "yes":
                yes_probability = pair["probability"]
                break
        if yes_probability is None and len(probabilities) == 2:
            yes_probability = probabilities[0]

        volume = _number(
            item.get("volume24hr")
            or item.get("volume24Hr")
            or item.get("volume")
        )
        liquidity = _number(item.get("liquidityNum") or item.get("liquidity"))
        best_bid = _number(item.get("bestBid"))
        best_ask = _number(item.get("bestAsk"))
        spread = (
            max(0.0, best_ask - best_bid)
            if best_bid is not None and best_ask is not None
            else None
        )
        volume_total += volume or 0.0
        liquidity_total += liquidity or 0.0
        markets.append(
            {
                "id": item.get("id"),
                "condition_id": item.get("conditionId"),
                "slug": item.get("slug"),
                "question": item.get("question"),
                "active": bool(item.get("active")),
                "closed": bool(item.get("closed")),
                "end_date": item.get("endDate") or item.get("end_date_iso"),
                "outcomes": pairs,
                "yes_probability": yes_probability,
                "binary_entropy": (
                    round(binary_entropy(yes_probability), 8)
                    if yes_probability is not None
                    else None
                ),
                "probability_edge_from_50": (
                    probability_edge(yes_probability)
                    if yes_probability is not None
                    else None
                ),
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": round(spread, 8) if spread is not None else None,
                "volume_24h": volume,
                "liquidity": liquidity,
                "market_url": (
                    f"https://polymarket.com/event/{item.get('slug')}"
                    if item.get("slug")
                    else None
                ),
            }
        )
    return {
        "markets": markets,
        "returned": len(markets),
        "volume_24h_total": round(volume_total, 6),
        "liquidity_total": round(liquidity_total, 6),
        "mode": "PUBLIC_READ_ONLY",
        "trading_enabled": False,
        "custody_enabled": False,
        "probability_is_market_price": True,
        "investment_advice": False,
    }


def _parse_coinbase(payload: Any, _: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise HTTPException(502, "Coinbase spot payload schema is not recognized")
    data = payload["data"]
    amount = _number(data.get("amount"))
    if amount is None:
        raise HTTPException(502, "Coinbase spot amount is unavailable")
    return {
        "base": data.get("base"),
        "currency": data.get("currency"),
        "amount": amount,
        "mode": "PUBLIC_SPOT_REFERENCE",
        "trading_enabled": False,
        "custody_enabled": False,
    }


def _parse_treasury_rates(payload: Any, parameters: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise HTTPException(502, "Treasury FiscalData payload schema is not recognized")
    rows: list[dict[str, Any]] = []
    for item in payload["data"][: _limit(parameters, 20, 100)]:
        if not isinstance(item, dict):
            continue
        rate = _number(item.get("avg_interest_rate_amt"))
        rows.append(
            {
                "record_date": item.get("record_date"),
                "security_type": item.get("security_type_desc"),
                "security_description": item.get("security_desc"),
                "average_interest_rate_pct": rate,
                "source_line_number": item.get("src_line_nbr"),
            }
        )
    observed_rates = [
        item["average_interest_rate_pct"]
        for item in rows
        if item["average_interest_rate_pct"] is not None
    ]
    return {
        "rates": rows,
        "returned": len(rows),
        "latest_record_date": rows[0]["record_date"] if rows else None,
        "rate_min_pct": min(observed_rates) if observed_rates else None,
        "rate_max_pct": max(observed_rates) if observed_rates else None,
        "mode": "OFFICIAL_PUBLIC_REFERENCE",
    }


def _parse_hpd_violations(payload: Any, _: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, list):
        raise HTTPException(502, "NYC HPD violation payload schema is not recognized")
    counts: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        violation_class = str(item.get("class") or "UNAVAILABLE").upper()
        if violation_class in {"A", "B", "C"}:
            counts[violation_class] += 1
        records.append(
            {
                "violation_id": item.get("violationid"),
                "building_id": item.get("buildingid"),
                "bbl": item.get("bbl"),
                "borough": item.get("boro") or item.get("boroid"),
                "block": item.get("block"),
                "lot": item.get("lot"),
                "house_number": item.get("housenumber"),
                "street_name": item.get("streetname"),
                "class": violation_class,
                "inspection_date": item.get("inspectiondate"),
                "current_status": item.get("currentstatus"),
                "current_status_date": item.get("currentstatusdate"),
                "rent_impairing": item.get("rentimpairing"),
                "latitude": _number(item.get("latitude")),
                "longitude": _number(item.get("longitude")),
            }
        )
    load = weighted_distress_load(counts)
    return {
        "records": records,
        "returned": len(records),
        "distress_load": load,
        "dataset": "HPD Housing Maintenance Code Violations wvxf-dwi5",
        "person_level_prospecting": False,
    }


def _parse_dob_violations(payload: Any, _: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, list):
        raise HTTPException(502, "NYC DOB violation payload schema is not recognized")
    records: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        records.append(
            {
                "violation_id": item.get("isn_dob_bis_viol"),
                "bin": item.get("bin"),
                "bbl": item.get("bbl"),
                "boro": item.get("boro"),
                "block": item.get("block"),
                "lot": item.get("lot"),
                "house_number": item.get("house_number"),
                "street": item.get("street"),
                "violation_type": item.get("violation_type"),
                "violation_category": item.get("violation_category"),
                "issue_date": item.get("issue_date"),
                "disposition_date": item.get("disposition_date"),
                "description": item.get("description"),
            }
        )
    open_count = sum(1 for item in records if not item["disposition_date"])
    return {
        "records": records,
        "returned": len(records),
        "open_without_disposition": open_count,
        "dataset": "DOB Violations 3h2n-5cm9",
        "person_level_prospecting": False,
    }
