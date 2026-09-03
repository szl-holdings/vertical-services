import collections
import math
import statistics
import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="PURIQ Finance")
BOOK = collections.defaultdict(list)
now = time.time()
for sym, base in {"SZLX": 412.0, "A11Y": 87.5, "PURIQ": 26.4, "TRRA": 153.2}.items():
    price = base
    for i in range(60, 0, -1):
        price *= 1 + 0.004 * math.sin(i * 0.7 + base)
        BOOK[sym].append({"ts": now - i * 86400, "px": round(price, 4)})


class Observation(BaseModel):
    symbol: str
    price: float
    ts: float | None = None


def analytics(symbol):
    prices = [row["px"] for row in BOOK[symbol]]
    rets = [(b - a) / a for a, b in zip(prices, prices[1:])]
    peak = prices[0]
    mdd = 0
    for price in prices:
        peak = max(peak, price)
        mdd = min(mdd, (price - peak) / peak)
    vol = statistics.pstdev(rets) * math.sqrt(252) if len(rets) > 2 else 0
    mom = (prices[-1] - prices[-6]) / prices[-6] if len(prices) > 6 else 0
    return {
        "symbol": symbol,
        "last": prices[-1],
        "points": len(prices),
        "ann_vol": round(vol, 4),
        "max_drawdown": round(mdd, 4),
        "momentum_5p": round(mom, 4),
        "signal": "RISK_OFF" if mdd < -0.12 else "ACCUMULATE" if mom > 0.02 else "HOLD",
        "truth": {"price": "SAMPLE", "derived": "MODELED"},
    }


DASH = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PURIQ Finance</title>
<style>
body{margin:0;background:#04140c;color:#b7f7c8;font:13px/1.4 ui-monospace,Menlo,monospace}
header{padding:20px 24px;border-bottom:1px solid #1c3d2a}
h1{margin:0;font-size:28px;color:#e8ffe9}
table{width:100%;border-collapse:collapse}
th,td{padding:10px 14px;border-bottom:1px solid #1c3d2a;text-align:left}
th{color:#6f9b7c;font-weight:500}
.off{color:#ffb347}.acc{color:#7dffb3}
.badge{color:#6f9b7c}
</style></head>
<body>
<header>
  <div class="badge">SAMPLE book · not an exchange feed</div>
  <h1>PURIQ TAPE</h1>
</header>
<table><thead><tr><th>SYM</th><th>LAST</th><th>VOL</th><th>MDD</th><th>MOM</th><th>SIG</th></tr></thead><tbody id="b"></tbody></table>
<script>
async function load(){
  const j = await (await fetch('/v1/portfolio/brief')).json();
  b.innerHTML = j.positions.map(p=>`<tr><td>${p.symbol}</td><td>${p.last.toFixed(2)}</td><td>${p.ann_vol}</td><td>${p.max_drawdown}</td><td>${p.momentum_5p}</td><td class="${p.signal==='RISK_OFF'?'off':'acc'}">${p.signal}</td></tr>`).join('');
}
load();
</script>
</body></html>
"""


@app.get("/", response_class=HTMLResponse)
def root():
    return DASH


@app.get("/healthz")
def healthz():
    return {"ok": True, "product": "PURIQ Finance", "symbols": len(BOOK), "book": "SAMPLE"}


@app.post("/v1/observations")
def ingest(obs: Observation):
    BOOK[obs.symbol].append({"ts": obs.ts or time.time(), "px": obs.price})
    return {"accepted": True, "symbol": obs.symbol, "points": len(BOOK[obs.symbol])}


@app.get("/v1/portfolio/brief")
def brief():
    return {"positions": [analytics(symbol) for symbol in BOOK], "generated_at": time.time()}


@app.get("/v1/series/{symbol}")
def series(symbol: str):
    return {"symbol": symbol, "points": BOOK.get(symbol, [])[-200:]}
