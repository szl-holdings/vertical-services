"""
SZL Finance Engine v2 — market data plane.

Two lanes, honestly labeled:
  - stooq:   live public daily OHLCV via stooq.com CSV (no key required)
  - fixture: deterministic local series for offline verification

Fail-closed: any fetch/parse problem -> EngineBlocked; the app surfaces
BLOCKED with the reason. Fixture data is always labeled data_origin="fixture"
and never presented as market data.
"""

from __future__ import annotations

import csv
import hashlib
import io
import random
import urllib.request

from engine import EngineBlocked

USER_AGENT = "SZLHOLDINGS-FinanceEngine/2.0"
STOOQ_BASE = "https://stooq.com/q/d/l/"
# Stooq symbols are ticker[.market] (e.g. aapl.us, ^spx). A symbol is rebuilt character by
# character from this constant table, so the query string is composed of allowlisted
# constants only — anything else is BLOCKED before a request exists (CodeQL py/partial-ssrf).
_SYMBOL_CHARS = {c: c for c in "abcdefghijklmnopqrstuvwxyz0123456789.^-_"}
_SYMBOL_MAX = 24


def stooq_symbol(symbol: str) -> str:
    """Return the sanitized ``s=`` value for Stooq or raise EngineBlocked."""
    raw = symbol.lower().strip()
    if not raw:
        raise EngineBlocked("stooq: empty symbol")
    if len(raw) > _SYMBOL_MAX:
        raise EngineBlocked("stooq: symbol too long")
    try:
        sym = "".join(_SYMBOL_CHARS[c] for c in raw)
    except KeyError as exc:
        raise EngineBlocked("stooq: symbol contains characters outside [a-z0-9.^-_]") from exc
    if "." not in sym:
        sym = sym + ".us"
    return sym


def fetch_stooq_daily(symbol: str, timeout: float = 10.0) -> list[float]:
    sym = stooq_symbol(symbol)
    url = f"{STOOQ_BASE}?s={sym}&i=d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise EngineBlocked(f"stooq: fetch failed: {type(exc).__name__}") from exc
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or "Close" not in rows[0]:
        raise EngineBlocked(f"stooq: no data for {sym}")
    closes = []
    for r in rows:
        v = (r.get("Close") or "").strip()
        if not v or v.upper() == "N/D":
            continue
        try:
            closes.append(float(v))
        except ValueError:
            continue
    if len(closes) < 2:
        raise EngineBlocked(f"stooq: insufficient bars for {sym}")
    return closes


def fixture_series(symbol: str, n: int = 260) -> list[float]:
    """Deterministic geometric walk seeded by the symbol hash. Honest fixture lane."""
    seed = int(hashlib.sha256(symbol.upper().encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    out = [100.0]
    for _ in range(n - 1):
        out.append(round(out[-1] * (1 + 0.0004 + rng.gauss(0, 0.015)), 4))
    return out


def get_closes(symbol: str, origin: str = "stooq") -> tuple[list[float], str]:
    if origin == "fixture":
        return fixture_series(symbol), "fixture"
    if origin == "stooq":
        return fetch_stooq_daily(symbol), "stooq"
    raise EngineBlocked(f"origin: unknown lane {origin!r}")
