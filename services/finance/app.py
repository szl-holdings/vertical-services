import time,math,statistics,collections
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
app=FastAPI(title="PURIQ Finance");BOOK=collections.defaultdict(list);now=time.time()
for sym,base in {"SZLX":412.,"A11Y":87.5,"PURIQ":26.4,"TRRA":153.2}.items():
 p=base
 for i in range(60,0,-1):p*=1+.004*math.sin(i*.7+base);BOOK[sym].append({"ts":now-i*86400,"px":round(p,4)})
class Observation(BaseModel):symbol:str;price:float;ts:float|None=None
def analytics(s):
 p=[x["px"] for x in BOOK[s]];r=[(b-a)/a for a,b in zip(p,p[1:])];peak=p[0];mdd=0
 for x in p:peak=max(peak,x);mdd=min(mdd,(x-peak)/peak)
 vol=statistics.pstdev(r)*math.sqrt(252) if len(r)>2 else 0;mom=(p[-1]-p[-6])/p[-6] if len(p)>6 else 0
 return {"symbol":s,"last":p[-1],"points":len(p),"ann_vol":round(vol,4),"max_drawdown":round(mdd,4),"momentum_5p":round(mom,4),"signal":"RISK_OFF" if mdd<-.12 else "ACCUMULATE" if mom>.02 else "HOLD","truth":{"price":"REPORTED","derived":"MODELED"}}
DASH='''<!doctype html><html><body style="background:#030405;color:#f5f7fa;font:15px system-ui;max-width:1000px;margin:40px auto"><h1 style="font-size:64px">PURIQ Finance</h1><p>Volatility, drawdown, momentum. POST /v1/observations.</p><pre id=o></pre><script>async function l(){o.textContent=JSON.stringify(await(await fetch('/v1/portfolio/brief')).json(),null,2)}l();setInterval(l,20000)</script></body></html>'''
@app.get("/",response_class=HTMLResponse)
def root():return DASH
@app.get("/healthz")
def healthz():return {"ok":True,"product":"PURIQ Finance","symbols":len(BOOK)}
@app.post("/v1/observations")
def ingest(o:Observation):BOOK[o.symbol].append({"ts":o.ts or time.time(),"px":o.price});return {"accepted":True,"symbol":o.symbol,"points":len(BOOK[o.symbol])}
@app.get("/v1/portfolio/brief")
def brief():return {"positions":[analytics(s) for s in BOOK],"generated_at":time.time()}
@app.get("/v1/series/{symbol}")
def series(symbol:str):return {"symbol":symbol,"points":BOOK.get(symbol,[])[-200:]}
