import time,statistics,collections
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
app=FastAPI(title="Lyte - Business Observability"); METRICS=collections.defaultdict(lambda:collections.deque(maxlen=2000))
class Metric(BaseModel): name:str; value:float; ts:float|None=None
def stats(v):
    if not v:return None
    s={"count":len(v),"mean":round(statistics.fmean(v),4),"min":min(v),"max":max(v),"stdev":round(statistics.pstdev(v),4) if len(v)>1 else 0,"last":v[-1]}
    if len(v)>=20:
        b,r=v[:-10],v[-10:]; z=(statistics.fmean(r)-statistics.fmean(b))/(statistics.pstdev(b) or 1e-9); s.update(drift_z=round(z,3),drift="DRIFT" if abs(z)>2 else "STABLE")
    return s
DASH='''<!doctype html><html><body style="background:#030405;color:#f5f7fa;font:15px system-ui;max-width:1000px;margin:40px auto"><h1 style="font-size:64px">Lyte</h1><p>Real-time metrics, baselines and drift detection. POST /v1/metrics.</p><pre id=o></pre><script>async function l(){o.textContent=JSON.stringify(await(await fetch('/v1/summary')).json(),null,2)}l();setInterval(l,20000)</script></body></html>'''
@app.get("/",response_class=HTMLResponse)
def root():return DASH
@app.get("/healthz")
def healthz():return {"ok":True,"product":"Lyte","streams":len(METRICS)}
@app.post("/v1/metrics")
def ingest(m:Metric):METRICS[m.name].append((m.ts or time.time(),m.value));return {"accepted":True,"stream":m.name,"depth":len(METRICS[m.name])}
@app.get("/v1/summary")
def summary():return {"truth":"MEASURED","streams":{n:stats([v for _,v in p]) for n,p in METRICS.items()},"generated_at":time.time()}
@app.get("/v1/drift")
def drift():return {"truth":"MEASURED","alerts":[{"stream":n,"drift_z":stats([v for _,v in p])["drift_z"]} for n,p in METRICS.items() if (stats([v for _,v in p]) or {}).get("drift")=="DRIFT"],"threshold_z":2.0}
@app.get("/v1/stream/{name}")
def stream(name:str,limit:int=100):return {"stream":name,"points":[{"ts":t,"value":v} for t,v in list(METRICS.get(name,[]))[-limit:]]}
