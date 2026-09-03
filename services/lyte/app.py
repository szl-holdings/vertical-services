import collections
import statistics
import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Lyte — business observability")
METRICS = collections.defaultdict(lambda: collections.deque(maxlen=2000))
seed = time.time()
for name, base in (("latency_ms", 120), ("error_rate", 0.012), ("queue_depth", 18)):
    for i in range(40):
        METRICS[name].append((seed - (40 - i) * 15, base * (1 + 0.04 * ((i % 7) - 3))))


class Metric(BaseModel):
    name: str
    value: float
    ts: float | None = None


def stats(values):
    if not values:
        return None
    summary = {
        "count": len(values),
        "mean": round(statistics.fmean(values), 4),
        "min": min(values),
        "max": max(values),
        "stdev": round(statistics.pstdev(values), 4) if len(values) > 1 else 0,
        "last": values[-1],
    }
    if len(values) >= 20:
        baseline, recent = values[:-10], values[-10:]
        z = (statistics.fmean(recent) - statistics.fmean(baseline)) / (statistics.pstdev(baseline) or 1e-9)
        summary.update(drift_z=round(z, 3), drift="DRIFT" if abs(z) > 2 else "STABLE")
    return summary


DASH = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lyte</title>
<style>
body{margin:0;background:#0e1116;color:#d7dde8;font:14px/1.45 ui-sans-serif,system-ui}
header{padding:24px 28px;border-bottom:1px solid #242b36}
h1{margin:0;font-size:36px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;padding:22px}
.card{background:#161b22;border:1px solid #242b36;padding:16px}
.k{color:#8b97a8;font-size:12px;text-transform:uppercase}
.v{font:700 30px/1 ui-monospace,monospace;margin:8px 0}
.drift{color:#f5c542}.ok{color:#6ee7b7}
</style></head>
<body>
<header>
  <div class="k">Process-memory streams · SAMPLE seed until POST /v1/metrics</div>
  <h1>Lyte</h1>
</header>
<div class="grid" id="g"></div>
<script>
async function load(){
  const j = await (await fetch('/v1/summary')).json();
  g.innerHTML = Object.entries(j.streams).map(([n,s])=>{
    if(!s) return '';
    const cls = s.drift==='DRIFT'?'drift':'ok';
    return `<div class="card"><div class="k">${n}</div><div class="v">${s.last.toFixed(3)}</div><div class="${cls}">${s.drift||'WARMING'} z=${s.drift_z??'n/a'}</div></div>`;
  }).join('');
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
    return {"ok": True, "product": "Lyte", "streams": len(METRICS)}


@app.post("/v1/metrics")
def ingest(metric: Metric):
    METRICS[metric.name].append((metric.ts or time.time(), metric.value))
    return {"accepted": True, "stream": metric.name, "depth": len(METRICS[metric.name])}


@app.get("/v1/summary")
def summary():
    return {
        "truth": "SAMPLE",
        "streams": {name: stats([value for _, value in points]) for name, points in METRICS.items()},
        "generated_at": time.time(),
    }


@app.get("/v1/drift")
def drift():
    alerts = []
    for name, points in METRICS.items():
        summary_row = stats([value for _, value in points]) or {}
        if summary_row.get("drift") == "DRIFT":
            alerts.append({"stream": name, "drift_z": summary_row["drift_z"]})
    return {"truth": "SAMPLE", "alerts": alerts, "threshold_z": 2.0}


@app.get("/v1/stream/{name}")
def stream(name: str, limit: int = 100):
    return {"stream": name, "points": [{"ts": ts, "value": value} for ts, value in list(METRICS.get(name, []))[-limit:]]}
