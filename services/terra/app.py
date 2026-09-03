import time,statistics
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
app=FastAPI(title="Terra - Real Estate Intelligence")
LISTINGS={"T-101":{"addr":"12 Academy St, Poughkeepsie NY","sqft":1850,"price":389000,"rent":2650,"type":"multi"},"T-102":{"addr":"88 Market St, Poughkeepsie NY","sqft":1240,"price":274000,"rent":1950,"type":"condo"},"T-103":{"addr":"241 Hooker Ave, Poughkeepsie NY","sqft":2200,"price":435000,"rent":2900,"type":"single"},"T-104":{"addr":"5 Grand Ave, Poughkeepsie NY","sqft":3100,"price":615000,"rent":3800,"type":"multi"}}
class Listing(BaseModel):addr:str;sqft:float;price:float;rent:float|None=None;type:str="single"
def analyze(l):
 o={"addr":l["addr"],"type":l["type"],"sqft":l["sqft"],"price":l["price"],"price_per_sqft":round(l["price"]/l["sqft"],2)}
 if l.get("rent"):o["cap_rate"]=round(l["rent"]*12*.62/l["price"],4);o["rent_yield_gross"]=round(l["rent"]*12/l["price"],4)
 return o
DASH='''<!doctype html><html><body style="background:#030405;color:#f5f7fa;font:15px system-ui;max-width:1000px;margin:40px auto"><h1 style="font-size:64px">Terra</h1><p>Price-per-sqft, cap rate, comps. POST /v1/listings.</p><pre id=o></pre><script>async function l(){o.textContent=JSON.stringify(await(await fetch('/v1/market/analysis')).json(),null,2)}l();setInterval(l,20000)</script></body></html>'''
@app.get("/",response_class=HTMLResponse)
def root():return DASH
@app.get("/healthz")
def healthz():return {"ok":True,"product":"Terra","listings":len(LISTINGS)}
@app.post("/v1/listings")
def ingest(l:Listing):i=f"T-{101+len(LISTINGS)}";LISTINGS[i]=l.model_dump();return {"accepted":True,"id":i}
@app.get("/v1/market/analysis")
def analysis():
 rows=[analyze(l) for l in LISTINGS.values()];p=[r["price_per_sqft"] for r in rows];med=statistics.median(p)
 for r in rows:r["vs_median_pct"]=round((r["price_per_sqft"]-med)/med*100,1)
 caps=[r["cap_rate"] for r in rows if "cap_rate" in r];return {"listings":rows,"market":{"median_ppsf":round(med,2),"ppsf_stdev":round(statistics.pstdev(p),2),"avg_cap_rate":round(statistics.fmean(caps),4) if caps else None,"count":len(rows),"truth":{"inputs":"REPORTED","cap_rate":"MODELED","opex_allowance":.38}},"generated_at":time.time()}
