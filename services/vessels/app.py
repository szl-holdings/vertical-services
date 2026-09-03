import time
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
app=FastAPI(title="Vessels - Maritime Intelligence"); now=time.time()
FLEET={"SZL-001":{"name":"Khipu Runner","type":"cargo","flag":"PA","lat":40.7,"lon":-74.0,"sog":14.2,"last":now-900},"SZL-002":{"name":"Ayllu Star","type":"tanker","flag":"MH","lat":41.1,"lon":-72.8,"sog":11.0,"last":now-7200},"SZL-003":{"name":"Puriq Dawn","type":"cargo","flag":"LR","lat":40.4,"lon":-73.9,"sog":.4,"last":now-300}}
MAX={"cargo":22,"tanker":18,"fishing":14}; COR={"lat":(38,42.5),"lon":(-76,-70)}
class Position(BaseModel):vessel_id:str;lat:float;lon:float;sog:float;ts:float|None=None
def risk(v):
    age=(time.time()-v["last"])/3600; f=[];s=0
    if age>2:s+=40;f.append("DARK_ACTIVITY")
    if v["sog"]>MAX.get(v["type"],20):s+=25;f.append("SPEED_ANOMALY")
    if not(COR["lat"][0]<=v["lat"]<=COR["lat"][1] and COR["lon"][0]<=v["lon"]<=COR["lon"][1]):s+=20;f.append("OFF_CORRIDOR")
    if v["sog"]<1 and v["type"]!="fishing":s+=10;f.append("LOITERING")
    return {"score":min(s,100),"level":"HIGH" if s>=50 else "MEDIUM" if s>=20 else "LOW","flags":f,"dark_hours":round(age,2)}
DASH='''<!doctype html><html><body style="background:#030405;color:#f5f7fa;font:15px system-ui;max-width:1000px;margin:40px auto"><h1 style="font-size:64px">Vessels</h1><p>Fleet risk: dark activity, speed, corridor, loitering. POST /v1/positions.</p><pre id=o></pre><script>async function l(){o.textContent=JSON.stringify(await(await fetch('/v1/fleet/risk')).json(),null,2)}l();setInterval(l,20000)</script></body></html>'''
@app.get("/",response_class=HTMLResponse)
def root():return DASH
@app.get("/healthz")
def healthz():return {"ok":True,"product":"Vessels","tracked":len(FLEET)}
@app.post("/v1/positions")
def ingest(p:Position):v=FLEET.setdefault(p.vessel_id,{"name":p.vessel_id,"type":"cargo","flag":"??"});v.update(lat=p.lat,lon=p.lon,sog=p.sog,last=p.ts or time.time());return {"accepted":True,"vessel":p.vessel_id}
@app.get("/v1/fleet/risk")
def fleet():
    out=[{"id":i,**{k:v[k] for k in("name","type","flag","lat","lon","sog")},"risk":risk(v),"truth":"MEASURED" if (time.time()-v["last"])/3600<2 else "REPORTED"} for i,v in FLEET.items()];out.sort(key=lambda x:-x["risk"]["score"]);return {"fleet":out,"generated_at":time.time()}
