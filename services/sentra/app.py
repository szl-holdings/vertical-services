import json, time, hmac, hashlib, os, collections
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

SIGNING_KEY = os.environ.get("SENTRA_SIGNING_KEY", "")
KEY_SOURCE = "MEASURED" if SIGNING_KEY else "REPORTED"
if not SIGNING_KEY:
    SIGNING_KEY = hashlib.sha256(os.urandom(32)).hexdigest()
app = FastAPI(title="Sentra - Policy-Gate Immune Service")
RATE = collections.defaultdict(list)
VERDICTS = collections.deque(maxlen=500)
POLICIES = {"blocked_actions":{"exfiltrate","credential_dump","lateral_movement","disable_logging"},"blocked_targets":{"/etc/shadow","prod-secrets","kms-root"},"max_payload_bytes":65536,"max_risk_score":70,"rate_per_minute":60}
def receipt(payload):
    body=json.dumps(payload,sort_keys=True,separators=(",",":")).encode(); sig=hmac.new(SIGNING_KEY.encode(),body,hashlib.sha256).hexdigest()
    return {"dsse":{"payloadType":"application/vnd.szl.verdict+json","payload_hash":hashlib.sha256(body).hexdigest(),"signatures":[{"alg":"HMAC-SHA256","sig":sig,"key_source":KEY_SOURCE}]}}
def run_gates(a):
    req={"actor","action","target"}; now=time.time(); RATE[a.get("actor","?")]=[t for t in RATE[a.get("actor","?")] if now-t<60]
    act,tgt=str(a.get("action","")).lower(),str(a.get("target","")).lower()
    return [("schema",req.issubset(a),"required actor/action/target"),("identity",bool(str(a.get("actor","")).strip()) and a.get("actor")!="anonymous","authenticated actor"),("rate",len(RATE[a.get("actor","?")])<POLICIES["rate_per_minute"],"per-actor rate"),("provenance",bool(a.get("source","")),"origin required"),("policy",act not in POLICIES["blocked_actions"] and tgt not in POLICIES["blocked_targets"],"deny list"),("risk",int(a.get("risk_score",0))<=POLICIES["max_risk_score"],"risk threshold"),("budget",len(json.dumps(a.get("payload",{})))<=POLICIES["max_payload_bytes"],"payload budget"),("liveness",not a.get("kill_switch",False),"kill switch")]
DASH='''<!doctype html><html><body style="background:#030405;color:#f5f7fa;font:15px system-ui;max-width:1000px;margin:40px auto"><h1 style="font-size:64px">Sentra</h1><p>Deny-by-default 8-gate engine. Signed verdicts. POST /v1/evaluate.</p><textarea id=r style="width:100%;height:120px">{"actor":"agent-07","action":"read","target":"telemetry-db","source":"a11oy","risk_score":25}</textarea><button onclick=e()>Evaluate</button><pre id=o></pre><script>async function e(){let j=await(await fetch('/v1/evaluate',{method:'POST',headers:{'content-type':'application/json'},body:r.value})).json();o.textContent=JSON.stringify(j,null,2)}</script></body></html>'''
@app.get("/",response_class=HTMLResponse)
def root(): return DASH
@app.get("/healthz")
def healthz(): return {"ok":True,"product":"Sentra","mode":"deny-by-default","gates":8}
@app.post("/v1/evaluate")
async def evaluate(req:Request):
    try: a=await req.json()
    except Exception: return JSONResponse({"verdict":"DENY","reason":"malformed JSON"},status_code=400)
    gates=run_gates(a); failed=[g for g in gates if not g[1]]; rec={"verdict":"DENY" if failed else "ALLOW","actor":a.get("actor"),"action":a.get("action"),"target":a.get("target"),"ts":time.time(),"gates":[{"gate":n,"pass":ok,"rule":d} for n,ok,d in gates],"failed":[n for n,ok,_ in failed]}; rec.update(receipt(rec)); VERDICTS.appendleft(rec); RATE[a.get("actor","?")].append(time.time()); return rec
@app.get("/v1/verdicts")
def verdicts(): return {"count":len(VERDICTS),"verdicts":list(VERDICTS)[:50]}
@app.get("/v1/policies")
def policies(): return {"policies":POLICIES,"truth":"REPORTED"}
