"""
PURIQ Finance Engine v2 — FastAPI surface.

Advisory-only, paper-only. Every computation carries the five-state honesty
contract (MEASURED / BLOCKED / INVALID / FAILED / PROMOTED) and appends a
hash-chained UNSIGNED_HONEST receipt. Nothing here is financial advice.

Frontend: static/console.html (signal console) + static/panels.html
(verification desk) — served at / and /panels respectively.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import (
    SCHEMA_VERSION,
    STATE_BLOCKED,
    TRUTH_LABELS,
    EngineBlocked,
    beta,
    max_drawdown,
    portfolio_report,
    sharpe,
    signal_suite,
    volatility,
)
from feed import get_closes
from receipts import ReceiptChain

DEFAULT_ORIGIN = os.environ.get("SZL_FINANCE_ORIGIN", "stooq").strip() or "stooq"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="PURIQ Finance Engine v2 — SZL Holdings",
    version="2.0.0",
    description="Provenance-first financial signal and portfolio analytics. "
                "Advisory-only. Paper-only. Not financial advice.",
)

CHAIN = ReceiptChain()


class PortfolioBody(BaseModel):
    holdings: dict[str, list[float]] = Field(min_length=1)


def _blocked(where: str, exc: EngineBlocked):
    payload = {
        "schema": SCHEMA_VERSION,
        "state": STATE_BLOCKED,
        "reason": str(exc),
        **TRUTH_LABELS,
    }
    receipt = CHAIN.append("blocked", {"route": where, "reason": str(exc)})
    payload["receipt_sha256"] = receipt["receipt_sha256"]
    return JSONResponse(payload, status_code=503)


@app.get("/")
def console():
    return FileResponse(STATIC_DIR / "console.html")


@app.get("/panels")
def panels():
    return FileResponse(STATIC_DIR / "panels.html")


@app.get("/healthz")
def healthz():
    return {"ok": True, "engine": "puriq-finance", "schema": SCHEMA_VERSION,
            "default_origin": DEFAULT_ORIGIN, **TRUTH_LABELS}


@app.get("/api/finance/v2/signals/{symbol}")
def signals(symbol: str, origin: str = Query(DEFAULT_ORIGIN, pattern="^(stooq|fixture)$")):
    try:
        closes, lane = get_closes(symbol, origin)
        result = signal_suite(closes, symbol, lane)
    except EngineBlocked as exc:
        return _blocked(f"/signals/{symbol}", exc)
    receipt = CHAIN.append("signal", {
        "symbol": result["symbol"], "verdict": result["verdict"],
        "data_origin": lane, "input_digest": result["input_digest"],
    })
    result["receipt_sha256"] = receipt["receipt_sha256"]
    return result


@app.get("/api/finance/v2/quote/{symbol}")
def quote(symbol: str,
          origin: str = Query(DEFAULT_ORIGIN, pattern="^(stooq|fixture)$"),
          benchmark: "str | None" = Query(default=None)):
    try:
        closes, lane = get_closes(symbol, origin)
        stats = {
            "last": closes[-1],
            "bars": len(closes),
            "volatility": volatility(closes),
            "sharpe": sharpe(closes),
            "max_drawdown": max_drawdown(closes),
        }
        # beta only exists against a measured benchmark; no benchmark -> omitted, not faked
        if benchmark:
            bench_closes, bench_lane = get_closes(benchmark, origin)
            stats["beta_vs"] = benchmark.upper()
            stats["beta_lane"] = bench_lane
            stats["beta"] = beta(closes, bench_closes)
    except EngineBlocked as exc:
        return _blocked(f"/quote/{symbol}", exc)
    payload = {"schema": SCHEMA_VERSION, "state": "MEASURED",
               "symbol": symbol.upper(), "data_origin": lane,
               "stats": stats, **TRUTH_LABELS}
    receipt = CHAIN.append("quote", {"symbol": payload["symbol"], "data_origin": lane})
    payload["receipt_sha256"] = receipt["receipt_sha256"]
    return payload


@app.post("/api/finance/v2/portfolio")
def portfolio(body: PortfolioBody):
    try:
        report = portfolio_report(body.holdings)
    except EngineBlocked as exc:
        return _blocked("/portfolio", exc)
    receipt = CHAIN.append("portfolio", {
        "constituents": report["constituents"], "report_digest": report["report_digest"],
    })
    report["receipt_sha256"] = receipt["receipt_sha256"]
    return report


@app.get("/api/finance/v2/receipts")
def receipts():
    return {"schema": "szl.finance-receipts/v1", "signing": "UNSIGNED_HONEST",
            "length": len(CHAIN.entries()), "entries": CHAIN.entries()}


@app.get("/api/finance/v2/receipts/verify")
def verify_receipts():
    return {"schema": "szl.finance-receipts/verify/v1",
            **ReceiptChain.verify(CHAIN.entries())}
