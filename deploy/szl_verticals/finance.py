"""PURIQ Finance caller-supplied market-series analytics engine."""
from __future__ import annotations

import math
import statistics
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field

from .core import STATE_LOCK, SessionScope, StrictModel

# ----------------------------- finance ------------------------------------
finance = APIRouter(prefix="/finance", tags=["finance"])
SERIES: Dict[str, Dict[str, Deque[Dict[str, float]]]] = defaultdict(
    lambda: defaultdict(lambda: deque(maxlen=5000))
)


class Observation(StrictModel):
    symbol: str = Field(..., min_length=1, max_length=24, pattern=r"^[A-Za-z0-9._:/-]+$")
    price: float = Field(..., gt=0, allow_inf_nan=False)
    ts: Optional[float] = Field(None, gt=0, allow_inf_nan=False)


@finance.get("/healthz")
def finance_health() -> dict[str, Any]:
    with STATE_LOCK:
        sessions = len(SERIES)
        count = sum(len(series) for series in SERIES.values())
    return {"status": "ok", "service": "finance", "symbols": count, "active_sessions": sessions, "state": "SESSION_ISOLATED_PROCESS_MEMORY"}


@finance.post("/v1/observations")
def finance_ingest(observation: Observation, session: SessionScope) -> dict[str, Any]:
    symbol = observation.symbol.upper()
    with STATE_LOCK:
        SERIES[session][symbol].append({"price": observation.price, "ts": observation.ts or time.time()})
        count = len(SERIES[session][symbol])
    return {"symbol": symbol, "n": count, "truth_label": "MEASURED"}


def _finance_metrics(session: str, symbol: str) -> dict[str, Any]:
    with STATE_LOCK:
        prices = [point["price"] for point in SERIES.get(session, {}).get(symbol, ())]
    if len(prices) < 3:
        raise HTTPException(400, "need >=3 observations")
    returns = [math.log(current / prior) for prior, current in zip(prices, prices[1:])]
    volatility = statistics.pstdev(returns) * math.sqrt(252) if len(returns) > 1 else 0.0
    peak = prices[0]
    max_drawdown = 0.0
    for price in prices:
        peak = max(peak, price)
        max_drawdown = min(max_drawdown, (price / peak) - 1.0)
    lookback = min(20, len(prices) - 1)
    momentum = (prices[-1] / prices[-1 - lookback]) - 1.0
    signal = "LONG" if momentum > 0.02 and volatility < 0.60 else "SHORT" if momentum < -0.02 else "FLAT"
    return {
        "symbol": symbol,
        "n": len(prices),
        "last": prices[-1],
        "annualized_vol": round(volatility, 4),
        "max_drawdown": round(max_drawdown, 4),
        "momentum": round(momentum, 4),
        "signal": signal,
        "truth_label": "MODELED",
        "input_provenance": "CALLER_SUPPLIED",
    }


@finance.get("/v1/symbol/brief")
def finance_brief(session: SessionScope, symbol: str = Query(..., min_length=1, max_length=24)) -> dict[str, Any]:
    normalized = symbol.upper()
    with STATE_LOCK:
        exists = normalized in SERIES.get(session, {})
    if not exists:
        raise HTTPException(404, "unknown symbol")
    return _finance_metrics(session, normalized)


@finance.get("/v1/portfolio/brief")
def portfolio_brief(session: SessionScope) -> dict[str, Any]:
    with STATE_LOCK:
        symbols = list(SERIES.get(session, {}))
    briefs = []
    for symbol in symbols:
        try:
            briefs.append(_finance_metrics(session, symbol))
        except HTTPException:
            continue
    return {"positions": len(briefs), "briefs": briefs, "truth_label": "MODELED"}
