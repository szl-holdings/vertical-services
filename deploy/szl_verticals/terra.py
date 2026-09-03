"""Terra caller-supplied real-estate analysis engine."""
from __future__ import annotations

import statistics
import time
import uuid as uuidlib
from collections import defaultdict
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field

from .core import STATE_LOCK, SessionScope, StrictModel

# ----------------------------- terra --------------------------------------
terra = APIRouter(prefix="/terra", tags=["terra"])
LISTINGS: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)


class Listing(StrictModel):
    market: str = Field(..., min_length=1, max_length=128)
    price: float = Field(..., gt=0, allow_inf_nan=False)
    sqft: float = Field(..., gt=0, allow_inf_nan=False)
    noi_annual: Optional[float] = Field(None, allow_inf_nan=False)
    address: str = Field("", max_length=256)


@terra.get("/healthz")
def terra_health() -> dict[str, Any]:
    with STATE_LOCK:
        sessions = len(LISTINGS)
        count = sum(len(listings) for listings in LISTINGS.values())
    return {"status": "ok", "service": "terra", "listings": count, "active_sessions": sessions, "state": "SESSION_ISOLATED_PROCESS_MEMORY"}


@terra.post("/v1/listings")
def terra_add(listing: Listing, session: SessionScope) -> dict[str, Any]:
    listing_id = uuidlib.uuid4().hex[:12]
    record = listing.model_dump()
    record.update(
        {
            "id": listing_id,
            "ts": time.time(),
            "price_per_sqft": round(listing.price / listing.sqft, 2),
            "cap_rate": round(listing.noi_annual / listing.price, 4)
            if listing.noi_annual is not None
            else None,
        }
    )
    with STATE_LOCK:
        LISTINGS[session][listing_id] = record
    return {**record, "truth_label": "REPORTED"}


@terra.get("/v1/market/analysis")
def terra_analysis(session: SessionScope, market: str = Query(..., min_length=1, max_length=128)) -> dict[str, Any]:
    with STATE_LOCK:
        rows = [
            dict(record)
            for record in LISTINGS.get(session, {}).values()
            if record["market"].casefold() == market.casefold()
        ]
    if not rows:
        raise HTTPException(404, "no listings in market")
    psf = [record["price_per_sqft"] for record in rows]
    cap_rates = [record["cap_rate"] for record in rows if record["cap_rate"] is not None]
    return {
        "market": market,
        "n": len(rows),
        "psf_median": statistics.median(psf),
        "psf_mean": round(statistics.fmean(psf), 2),
        "psf_stdev": round(statistics.pstdev(psf), 2) if len(psf) > 1 else 0.0,
        "cap_rate_median": statistics.median(cap_rates) if cap_rates else None,
        "comps": sorted(rows, key=lambda record: record["price_per_sqft"])[:10],
        "truth_label": "MODELED",
        "input_provenance": "CALLER_SUPPLIED",
    }
