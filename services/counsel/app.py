import time
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="PRISM Counsel")
MATTERS = {
    "C-441": {"caption": "In re Hudson Supply", "forum": "SDNY", "issue": "contract interpretation", "status": "OPEN", "authority": "NOT_OBSERVED"},
    "C-442": {"caption": "State v. withheld", "forum": "NY Sup.", "issue": "suppression clock", "status": "HOLD", "authority": "LICENSE_REQUIRED"},
    "C-443": {"caption": "Estate of P.", "forum": "Surrogate", "issue": "fiduciary accounting", "status": "OPEN", "authority": "HUMAN_WORKFLOW"},
}


class Matter(BaseModel):
    caption: str
    forum: str
    issue: str


def triage(matter):
    blocked = matter["authority"] in {"LICENSE_REQUIRED", "UNAVAILABLE"}
    return {
        **matter,
        "next": "BLOCKED" if blocked else "HUMAN_REVIEW",
        "truth": matter["authority"],
        "advice": "No legal conclusion. Public docket text is not authorization to file.",
    }


DASH = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PRISM Counsel</title>
<style>
body{margin:0;background:#f7f1e4;color:#1b2430;font:16px/1.5 "Iowan Old Style",Georgia,serif}
header{padding:32px 40px;background:#1b2430;color:#f7f1e4}
h1{margin:0;font-size:48px;font-weight:400}
main{padding:28px 40px}
.row{display:grid;grid-template-columns:120px 1fr 160px 180px;gap:12px;padding:14px 0;border-bottom:1px solid #d7cbb3}
.k{font:12px ui-sans-serif,system-ui;letter-spacing:.08em;text-transform:uppercase;color:#6b6254}
.block{color:#9b2c2c}.ok{color:#1f4d3a}
</style></head>
<body>
<header>
  <div class="k">Not PACER · fail-closed · no legal advice</div>
  <h1>PRISM Counsel</h1>
</header>
<main id="m"></main>
<script>
async function load(){
  const j = await (await fetch('/v1/docket')).json();
  m.innerHTML = '<div class="row k"><div>ID</div><div>Caption</div><div>Forum</div><div>Next</div></div>' +
    j.matters.map(x=>`<div class="row"><div>${x.id}</div><div>${x.caption}<br><span class="k">${x.issue}</span></div><div>${x.forum}</div><div class="${x.next==='BLOCKED'?'block':'ok'}">${x.next}<br><span class="k">${x.truth}</span></div></div>`).join('');
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
    return {"ok": True, "product": "PRISM Counsel", "matters": len(MATTERS), "legal_advice": False}


@app.post("/v1/matters")
def ingest(matter: Matter):
    item_id = f"C-{441 + len(MATTERS)}"
    MATTERS[item_id] = {**matter.model_dump(), "status": "OPEN", "authority": "NOT_OBSERVED"}
    return {"accepted": True, "id": item_id}


@app.get("/v1/docket")
def docket():
    rows = [{"id": item_id, **triage(matter)} for item_id, matter in MATTERS.items()]
    return {"matters": rows, "generated_at": time.time(), "book": "SAMPLE", "legal_advice": False}
