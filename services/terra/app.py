import statistics
import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Terra — real-estate intelligence")
LISTINGS = {
    "T-101": {"addr": "12 Academy St, Poughkeepsie NY", "sqft": 1850, "price": 389000, "rent": 2650, "type": "multi"},
    "T-102": {"addr": "88 Market St, Poughkeepsie NY", "sqft": 1240, "price": 274000, "rent": 1950, "type": "condo"},
    "T-103": {"addr": "241 Hooker Ave, Poughkeepsie NY", "sqft": 2200, "price": 435000, "rent": 2900, "type": "single"},
    "T-104": {"addr": "5 Grand Ave, Poughkeepsie NY", "sqft": 3100, "price": 615000, "rent": 3800, "type": "multi"},
}


class Listing(BaseModel):
    addr: str
    sqft: float
    price: float
    rent: float | None = None
    type: str = "single"


def analyze(listing):
    out = {
        "addr": listing["addr"],
        "type": listing["type"],
        "sqft": listing["sqft"],
        "price": listing["price"],
        "price_per_sqft": round(listing["price"] / listing["sqft"], 2),
    }
    if listing.get("rent"):
        out["cap_rate"] = round(listing["rent"] * 12 * 0.62 / listing["price"], 4)
        out["rent_yield_gross"] = round(listing["rent"] * 12 / listing["price"], 4)
    return out


DASH = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Terra</title>
<style>
body{margin:0;background:#f4efe6;color:#2b241c;font:16px/1.5 Georgia,serif}
header{padding:36px 40px 20px;background:#2b241c;color:#f4efe6}
h1{margin:0;font-size:56px;font-weight:400}
.sub{opacity:.8}
main{padding:28px 40px;display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.card{background:#fffaf3;border:1px solid #d9cbb8;padding:16px}
.k{color:#7a6a56;font-size:12px;text-transform:uppercase;letter-spacing:.08em}
.p{font:700 28px/1 ui-sans-serif,system-ui}
.badge{font:12px ui-sans-serif,system-ui;border:1px solid #c9b79a;padding:2px 8px}
</style></head>
<body>
<header>
  <div class="badge">SAMPLE book · not MLS</div>
  <h1>Terra</h1>
  <p class="sub">Price per square foot, cap rate, comps. Hudson Valley sample desk.</p>
</header>
<main id="grid"></main>
<script>
async function load(){
  const j = await (await fetch('/v1/market/analysis')).json();
  grid.innerHTML = `<div class="card"><div class="k">Median $/ft²</div><div class="p">${j.market.median_ppsf}</div><div class="k">avg cap ${j.market.avg_cap_rate ?? 'n/a'} · ${j.market.truth.inputs}</div></div>` +
    j.listings.map(r=>`<div class="card"><div class="k">${r.type}</div><div>${r.addr}</div><div class="p">$${r.price.toLocaleString()}</div><div class="k">${r.price_per_sqft}/ft² · ${r.vs_median_pct}% vs median</div></div>`).join('');
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
    return {"ok": True, "product": "Terra", "listings": len(LISTINGS), "book": "SAMPLE"}


@app.post("/v1/listings")
def ingest(listing: Listing):
    item_id = f"T-{101 + len(LISTINGS)}"
    LISTINGS[item_id] = listing.model_dump()
    return {"accepted": True, "id": item_id}


@app.get("/v1/market/analysis")
def analysis():
    rows = [analyze(item) for item in LISTINGS.values()]
    prices = [row["price_per_sqft"] for row in rows]
    med = statistics.median(prices)
    for row in rows:
        row["vs_median_pct"] = round((row["price_per_sqft"] - med) / med * 100, 1)
    caps = [row["cap_rate"] for row in rows if "cap_rate" in row]
    return {
        "listings": rows,
        "market": {
            "median_ppsf": round(med, 2),
            "ppsf_stdev": round(statistics.pstdev(prices), 2),
            "avg_cap_rate": round(statistics.fmean(caps), 4) if caps else None,
            "count": len(rows),
            "truth": {"inputs": "SAMPLE", "cap_rate": "MODELED", "opex_allowance": 0.38},
        },
        "generated_at": time.time(),
    }
