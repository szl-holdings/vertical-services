import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Vessels — maritime intelligence")
now = time.time()
FLEET = {
    "SZL-001": {"name": "Khipu Runner", "type": "cargo", "flag": "PA", "lat": 40.7, "lon": -74.0, "sog": 14.2, "last": now - 900},
    "SZL-002": {"name": "Ayllu Star", "type": "tanker", "flag": "MH", "lat": 41.1, "lon": -72.8, "sog": 11.0, "last": now - 7200},
    "SZL-003": {"name": "Puriq Dawn", "type": "cargo", "flag": "LR", "lat": 40.4, "lon": -73.9, "sog": 0.4, "last": now - 300},
}
MAX = {"cargo": 22, "tanker": 18, "fishing": 14}
COR = {"lat": (38, 42.5), "lon": (-76, -70)}


class Position(BaseModel):
    vessel_id: str
    lat: float
    lon: float
    sog: float
    ts: float | None = None


def risk(vessel):
    age = (time.time() - vessel["last"]) / 3600
    flags = []
    score = 0
    if age > 2:
        score += 40
        flags.append("DARK_ACTIVITY")
    if vessel["sog"] > MAX.get(vessel["type"], 20):
        score += 25
        flags.append("SPEED_ANOMALY")
    if not (COR["lat"][0] <= vessel["lat"] <= COR["lat"][1] and COR["lon"][0] <= vessel["lon"] <= COR["lon"][1]):
        score += 20
        flags.append("OFF_CORRIDOR")
    if vessel["sog"] < 1 and vessel["type"] != "fishing":
        score += 10
        flags.append("LOITERING")
    return {"score": min(score, 100), "level": "HIGH" if score >= 50 else "MEDIUM" if score >= 20 else "LOW", "flags": flags, "dark_hours": round(age, 2)}


DASH = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vessels</title>
<style>
body{margin:0;background:#03131c;color:#d7e7f2;font:14px/1.45 ui-sans-serif,system-ui}
header{padding:24px 28px;background:#021018;border-bottom:1px solid #1a3a4c}
h1{margin:0;font-size:40px;letter-spacing:.12em;text-transform:uppercase}
.hi{color:#ff6b4a}.med{color:#ffd166}.lo{color:#7bdff2}
table{width:100%;border-collapse:collapse}
td,th{padding:12px 16px;border-bottom:1px solid #163445;text-align:left}
.badge{color:#7aa0b4;font-size:12px}
</style></head>
<body>
<header>
  <div class="badge">SAMPLE AIS book · not a live feed</div>
  <h1>Vessels</h1>
</header>
<table><thead><tr><th>ID</th><th>Name</th><th>SOG</th><th>Pos</th><th>Risk</th><th>Flags</th></tr></thead><tbody id="b"></tbody></table>
<script>
async function load(){
  const j = await (await fetch('/v1/fleet/risk')).json();
  b.innerHTML = j.fleet.map(v=>{
    const cls = v.risk.level==='HIGH'?'hi':v.risk.level==='MEDIUM'?'med':'lo';
    return `<tr><td>${v.id}</td><td>${v.name}</td><td>${v.sog}</td><td>${v.lat.toFixed(2)}, ${v.lon.toFixed(2)}</td><td class="${cls}">${v.risk.level} ${v.risk.score}</td><td>${(v.risk.flags||[]).join(', ')||'—'}</td></tr>`;
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
    return {"ok": True, "product": "Vessels", "tracked": len(FLEET), "book": "SAMPLE"}


@app.post("/v1/positions")
def ingest(pos: Position):
    vessel = FLEET.setdefault(pos.vessel_id, {"name": pos.vessel_id, "type": "cargo", "flag": "??"})
    vessel.update(lat=pos.lat, lon=pos.lon, sog=pos.sog, last=pos.ts or time.time())
    return {"accepted": True, "vessel": pos.vessel_id}


@app.get("/v1/fleet/risk")
def fleet():
    out = []
    for item_id, vessel in FLEET.items():
        out.append({
            "id": item_id,
            **{key: vessel[key] for key in ("name", "type", "flag", "lat", "lon", "sog")},
            "risk": risk(vessel),
            "truth": "MEASURED" if (time.time() - vessel["last"]) / 3600 < 2 else "REPORTED",
        })
    out.sort(key=lambda row: -row["risk"]["score"])
    return {"fleet": out, "generated_at": time.time(), "book": "SAMPLE"}
