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


def fetch_stooq_daily(symbol: str, timeout: float = 10.0) -> list[float]:
    sym = symbol.lower().strip()
    if not sym:
        raise EngineBlocked("stooq: empty symbol")
    if "." not in sym:
        sym = sym + ".us"
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
