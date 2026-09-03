"""SZL Holdings vertical-services - six governed engines, one service.

sentra:   policy gates (deny-by-default, HMAC-SHA256 receipts)
lyte:     observability (summaries, drift)
vessels:  maritime risk (dark activity, speed anomaly, loitering)
finance:  portfolio analytics (volatility, drawdown, momentum)
terra:    real estate intel (PSF, cap rate, comps)
counsel:  legal matter command (obligations, hash-chained receipts)

Truth labels: MEASURED | REPORTED | MODELED. No fabricated data.
Source: github.com/szl-holdings/vertical-services
"""
import hashlib, hmac, math, os, secrets, statistics, time
import uuid as uuidlib
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="SZL Vertical Services", version="1.0.0",
              description="Six governed vertical engines. Honest truth labels.")

# ----------------------------- sentra -------------------------------------
sentra = APIRouter(prefix="/sentra", tags=["sentra"])

_SK = os.environ.get("SENTRA_SIGNING_KEY")
SENTRA_KEY_SOURCE = "env" if _SK else "ephemeral-dev"
SENTRA_KEY = (_SK or secrets.token_hex(32)).encode()
VERDICTS: Deque[Dict[str, Any]] = deque(maxlen=500)
RATE: Dict[str, List[float]] = {}

class EvaluateRequest(BaseModel):
    actor: str
    action: str
    resource: str
    risk_score: float = Field(0.0, ge=0.0, le=1.0)
    authenticated: bool = False
    tier: str = "untrusted"
    evidence: List[str] = []

GATES = [
    ("g1_actor_present",   lambda r: bool(r.actor.strip())),
    ("g2_action_present",  lambda r: bool(r.action.strip())),
    ("g3_resource_scoped", lambda r: "/" in r.resource or ":" in r.resource),
    ("g4_authenticated",   lambda r: r.authenticated),
    ("g5_tier_allowed",    lambda r: r.tier in {"operator", "admin", "service"}),
    ("g6_risk_threshold",  lambda r: r.risk_score < 0.75),
    ("g7_evidence_cited",  lambda r: len(r.evidence) >= 1),
    ("g8_not_destructive_unattended",
     lambda r: not (r.action.lower() in {"delete", "purge", "drop"} and r.tier != "admin")),
]

def _rate_ok(actor: str, limit: int = 60, window: float = 60.0) -> bool:
    now = time.time()
    hits = [t for t in RATE.get(actor, []) if now - t < window]
    hits.append(now)
    RATE[actor] = hits
    return len(hits) <= limit

def _sign(payload: str) -> str:
    return hmac.new(SENTRA_KEY, payload.encode(), hashlib.sha256).hexdigest()

@sentra.get("/healthz")
def sentra_health():
    return {"status": "ok", "service": "sentra",
            "signing_key_source": SENTRA_KEY_SOURCE, "gates": len(GATES)}

@sentra.post("/v1/evaluate")
def sentra_evaluate(req: EvaluateRequest):
    traversed = [{"gate": n, "passed": bool(f(req))} for n, f in GATES]
    traversed.append({"gate": "g9_rate_limit", "passed": _rate_ok(req.actor)})
    failed = [g["gate"] for g in traversed if not g["passed"]]
    decision = "ALLOW" if not failed else "DENY"
    ts = time.time()
    body = f"{req.actor}|{req.action}|{req.resource}|{decision}|{ts}"
    receipt = {
        "decision": decision,
        "failed_gates": failed,
        "gates_traversed": traversed,
        "timestamp": ts,
        "truth_label": "MEASURED",
        "signature": _sign(body),
        "signature_alg": "HMAC-SHA256",
        "key_source": SENTRA_KEY_SOURCE,
    }
    VERDICTS.append(receipt)
    return receipt

@sentra.get("/v1/verdicts")
def sentra_verdicts(limit: int = 50):
    items = list(VERDICTS)[-limit:]
    return {"count": len(items), "verdicts": items}

# ----------------------------- lyte ---------------------------------------
lyte = APIRouter(prefix="/lyte", tags=["lyte"])
STREAMS: Dict[str, Deque[Dict]] = defaultdict(lambda: deque(maxlen=2000))

class Metric(BaseModel):
    stream: str
    value: float
    ts: Optional[float] = None

@lyte.get("/healthz")
def lyte_health():
    return {"status": "ok", "service": "lyte", "streams": len(STREAMS)}

@lyte.post("/v1/metrics")
def lyte_ingest(m: Metric):
    STREAMS[m.stream].append({"value": m.value, "ts": m.ts or time.time()})
    return {"stream": m.stream, "n": len(STREAMS[m.stream]), "truth_label": "MEASURED"}

@lyte.get("/v1/summary")
def lyte_summary(stream: str):
    pts = STREAMS.get(stream)
    if not pts:
        raise HTTPException(404, "unknown stream")
    v = [p["value"] for p in pts]
    v_sorted = sorted(v)
    def pct(p):
        return v_sorted[min(len(v_sorted) - 1, int(p * len(v_sorted)))]
    return {"stream": stream, "n": len(v), "mean": statistics.fmean(v),
            "median": statistics.median(v),
            "stdev": statistics.pstdev(v) if len(v) > 1 else 0.0,
            "min": v_sorted[0], "max": v_sorted[-1],
            "p50": pct(0.50), "p95": pct(0.95), "p99": pct(0.99),
            "truth_label": "MEASURED"}

@lyte.get("/v1/drift")
def lyte_drift(stream: str, split: float = 0.5):
    pts = STREAMS.get(stream)
    if not pts or len(pts) < 20:
        raise HTTPException(400, "need >=20 points")
    v = [p["value"] for p in pts]
    k = max(1, int(len(v) * split))
    a, b = v[:k], v[k:]
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    sa = statistics.pstdev(a) or 1e-9
    z = (mb - ma) / sa
    return {"stream": stream, "baseline_mean": ma, "recent_mean": mb,
            "z_shift": z, "drift_detected": abs(z) > 2.0,
            "truth_label": "MEASURED"}

# ----------------------------- vessels ------------------------------------
vessels = APIRouter(prefix="/vessels", tags=["vessels"])
TRACKS: Dict[str, Deque[Dict]] = defaultdict(lambda: deque(maxlen=1000))
DARK_GAP_S = 3600.0
SPEED_MAX_KN = 28.0

class Position(BaseModel):
    imo: str
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    sog: float = 0.0
    ts: Optional[float] = None

def _haversine_nm(a, b):
    R = 3440.065
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(h))

@vessels.get("/healthz")
def vessels_health():
    return {"status": "ok", "service": "vessels", "tracked": len(TRACKS)}

@vessels.post("/v1/positions")
def vessels_ingest(p: Position):
    TRACKS[p.imo].append({"lat": p.lat, "lon": p.lon, "sog": p.sog,
                          "ts": p.ts or time.time()})
    return {"imo": p.imo, "n": len(TRACKS[p.imo]), "truth_label": "REPORTED"}

def _assess(imo: str):
    t = list(TRACKS[imo])
    flags, dark_gaps, implied = [], 0, []
    for a, b in zip(t, t[1:]):
        dt = b["ts"] - a["ts"]
        if dt > DARK_GAP_S:
            dark_gaps += 1
        if dt > 0:
            implied.append(_haversine_nm((a["lat"], a["lon"]),
                                         (b["lat"], b["lon"])) / (dt / 3600.0))
    if dark_gaps:
        flags.append(f"dark_activity:{dark_gaps}_gaps")
    if implied and max(implied) > SPEED_MAX_KN:
        flags.append(f"speed_anomaly:{max(implied):.1f}kn_implied")
    slow = [p for p in t if p["sog"] < 1.0]
    if len(slow) >= 5:
        flags.append(f"loitering:{len(slow)}_low_sog_fixes")
    score = min(1.0, 0.3 * dark_gaps
                + 0.4 * bool(implied and max(implied) > SPEED_MAX_KN)
                + 0.05 * len(slow))
    return {"imo": imo, "fixes": len(t), "dark_gaps": dark_gaps,
            "max_implied_speed_kn": max(implied) if implied else None,
            "flags": flags, "risk_score": round(score, 3),
            "truth_label": "MODELED"}

@vessels.get("/v1/vessel/risk")
def vessel_risk(imo: str):
    if imo not in TRACKS:
        raise HTTPException(404, "unknown imo")
    return _assess(imo)

@vessels.get("/v1/fleet/risk")
def fleet_risk():
    rows = [_assess(i) for i in TRACKS]
    rows.sort(key=lambda r: r["risk_score"], reverse=True)
    return {"vessels": len(rows), "assessments": rows}

# ----------------------------- finance ------------------------------------
finance = APIRouter(prefix="/finance", tags=["finance"])
SERIES: Dict[str, Deque[Dict]] = defaultdict(lambda: deque(maxlen=5000))

class Observation(BaseModel):
    symbol: str
    price: float
    ts: Optional[float] = None

@finance.get("/healthz")
def finance_health():
    return {"status": "ok", "service": "finance", "symbols": len(SERIES)}

@finance.post("/v1/observations")
def finance_ingest(o: Observation):
    SERIES[o.symbol.upper()].append({"price": o.price, "ts": o.ts or time.time()})
    return {"symbol": o.symbol.upper(), "n": len(SERIES[o.symbol.upper()]),
            "truth_label": "MEASURED"}

def _finance_metrics(sym: str):
    p = [x["price"] for x in SERIES[sym]]
    if len(p) < 3:
        raise HTTPException(400, "need >=3 observations")
    rets = [math.log(b / a) for a, b in zip(p, p[1:]) if a > 0]
    vol = statistics.pstdev(rets) * math.sqrt(252) if len(rets) > 1 else 0.0
    peak, mdd = p[0], 0.0
    for x in p:
        peak = max(peak, x)
        mdd = min(mdd, (x / peak) - 1.0)
    look = min(20, len(p) - 1)
    mom = (p[-1] / p[-1 - look]) - 1.0
    signal = "LONG" if mom > 0.02 and vol < 0.60 else "SHORT" if mom < -0.02 else "FLAT"
    return {"symbol": sym, "n": len(p), "last": p[-1],
            "annualized_vol": round(vol, 4),
            "max_drawdown": round(mdd, 4),
            "momentum": round(mom, 4),
            "signal": signal, "truth_label": "MODELED"}

@finance.get("/v1/symbol/brief")
def finance_brief(symbol: str):
    sym = symbol.upper()
    if sym not in SERIES:
        raise HTTPException(404, "unknown symbol")
    return _finance_metrics(sym)

@finance.get("/v1/portfolio/brief")
def portfolio_brief():
    out = []
    for s in SERIES:
        try:
            out.append(_finance_metrics(s))
        except HTTPException:
            continue
    return {"positions": len(out), "briefs": out}

# ----------------------------- terra --------------------------------------
terra = APIRouter(prefix="/terra", tags=["terra"])
LISTINGS: Dict[str, Dict] = {}

class Listing(BaseModel):
    market: str
    price: float = Field(..., gt=0)
    sqft: float = Field(..., gt=0)
    noi_annual: Optional[float] = None
    address: str = ""

@terra.get("/healthz")
def terra_health():
    return {"status": "ok", "service": "terra", "listings": len(LISTINGS)}

@terra.post("/v1/listings")
def terra_add(l: Listing):
    lid = uuidlib.uuid4().hex[:12]
    rec = l.model_dump()
    rec.update({"id": lid, "ts": time.time(),
                "price_per_sqft": round(l.price / l.sqft, 2),
                "cap_rate": round(l.noi_annual / l.price, 4) if l.noi_annual else None})
    LISTINGS[lid] = rec
    return {**rec, "truth_label": "REPORTED"}

@terra.get("/v1/market/analysis")
def terra_analysis(market: str):
    rows = [r for r in LISTINGS.values()
            if r["market"].lower() == market.lower()]
    if not rows:
        raise HTTPException(404, "no listings in market")
    psf = [r["price_per_sqft"] for r in rows]
    caps = [r["cap_rate"] for r in rows if r["cap_rate"] is not None]
    return {"market": market, "n": len(rows),
            "psf_median": statistics.median(psf),
            "psf_mean": round(statistics.fmean(psf), 2),
            "psf_stdev": round(statistics.pstdev(psf), 2) if len(psf) > 1 else 0.0,
            "cap_rate_median": statistics.median(caps) if caps else None,
            "comps": sorted(rows, key=lambda r: r["price_per_sqft"])[:10],
            "truth_label": "MODELED"}

# ----------------------------- counsel ------------------------------------
counsel = APIRouter(prefix="/counsel", tags=["counsel"])
MATTERS: Dict[str, Dict[str, Any]] = {}
RECEIPT_CHAIN: Deque[Dict[str, Any]] = deque(maxlen=500)
_PREV_HASH = "GENESIS"

def _chain(step: str, payload: str) -> Dict[str, Any]:
    global _PREV_HASH
    h = hashlib.sha256(f"{_PREV_HASH}|{step}|{payload}".encode()).hexdigest()
    receipt = {"step": step, "hash": h, "prev": _PREV_HASH,
               "ts": time.time(), "truth_label": "MEASURED"}
    _PREV_HASH = h
    RECEIPT_CHAIN.append(receipt)
    return receipt

class MatterIn(BaseModel):
    title: str
    client: str
    domain: str = "general"
    counterparty: str = ""
    exposure_usd: float = Field(0.0, ge=0)
    deadline_ts: Optional[float] = None

class ObligationIn(BaseModel):
    clause: str
    obligation: str
    party: str = "client"
    due_days: int = Field(30, ge=0)
    severity: str = Field("medium")

@counsel.get("/healthz")
def counsel_health():
    return {"status": "ok", "service": "counsel", "matters": len(MATTERS),
            "receipt_chain": len(RECEIPT_CHAIN)}

@counsel.post("/v1/matters")
def counsel_open(m: MatterIn):
    mid = hashlib.sha256(f"{m.title}|{m.client}|{time.time_ns()}".encode()).hexdigest()[:12]
    rec = m.model_dump()
    rec.update({"id": mid, "ts": time.time(), "status": "open", "obligations": []})
    MATTERS[mid] = rec
    receipt = _chain("matter.open", f"{mid}|{m.title}")
    return {**rec, "receipt": receipt}

@counsel.post("/v1/matters/{mid}/obligations")
def counsel_obligation(mid: str, o: ObligationIn):
    if mid not in MATTERS:
        raise HTTPException(404, "unknown matter")
    ob = o.model_dump()
    ob["id"] = f"ob-{len(MATTERS[mid]['obligations']) + 1:03d}"
    ob["truth_label"] = "REPORTED"
    MATTERS[mid]["obligations"].append(ob)
    receipt = _chain("obligation.map", f"{mid}|{ob['id']}|{o.obligation}")
    return {"matter_id": mid, "obligation": ob, "receipt": receipt}

@counsel.get("/v1/matters/{mid}")
def counsel_get(mid: str):
    if mid not in MATTERS:
        raise HTTPException(404, "unknown matter")
    m = MATTERS[mid]
    sev = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    ranked = sorted(m["obligations"], key=lambda o: sev.get(o["severity"], 9))
    return {**m, "obligations_by_severity": ranked, "truth_label": "REPORTED"}

@counsel.get("/v1/docket")
def counsel_docket():
    rows = []
    for mid, m in MATTERS.items():
        crit = sum(1 for o in m["obligations"] if o["severity"] in ("critical", "high"))
        rows.append({"id": mid, "title": m["title"], "client": m["client"],
                     "domain": m["domain"], "open_obligations": len(m["obligations"]),
                     "high_severity": crit, "exposure_usd": m["exposure_usd"],
                     "status": m["status"]})
    rows.sort(key=lambda r: (-r["high_severity"], -r["exposure_usd"]))
    return {"matters": len(rows), "docket": rows, "truth_label": "MODELED"}

# ----------------------------- mount + root -------------------------------
app.include_router(sentra)
app.include_router(lyte)
app.include_router(vessels)
app.include_router(finance)
app.include_router(terra)
app.include_router(counsel)

@app.get("/healthz")
def root_health():
    return {"status": "ok", "service": "szl-vertical-services",
            "version": "1.0.0",
            "engines": ["sentra", "lyte", "vessels", "finance", "terra", "counsel"],
            "routes": {e: f"/{e}/healthz" for e in
                       ["sentra", "lyte", "vessels", "finance", "terra", "counsel"]},
            "truth_label": "MEASURED",
            "source": "github.com/szl-holdings/vertical-services"}
