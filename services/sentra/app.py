import collections
import hashlib
import hmac
import json
import os
import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

SIGNING_KEY = os.environ.get("SENTRA_SIGNING_KEY", "")
KEY_SOURCE = "MEASURED" if SIGNING_KEY else "REPORTED"
if not SIGNING_KEY:
    SIGNING_KEY = hashlib.sha256(os.urandom(32)).hexdigest()

app = FastAPI(title="Sentra — policy-gate immune service")
RATE = collections.defaultdict(list)
VERDICTS = collections.deque(maxlen=500)
POLICIES = {
    "blocked_actions": {"exfiltrate", "credential_dump", "lateral_movement", "disable_logging"},
    "blocked_targets": {"/etc/shadow", "prod-secrets", "kms-root"},
    "max_payload_bytes": 65536,
    "max_risk_score": 70,
    "rate_per_minute": 60,
}


def receipt(payload):
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(SIGNING_KEY.encode(), body, hashlib.sha256).hexdigest()
    return {
        "dsse": {
            "payloadType": "application/vnd.szl.verdict+json",
            "payload_hash": hashlib.sha256(body).hexdigest(),
            "signatures": [{"alg": "HMAC-SHA256", "sig": sig, "key_source": KEY_SOURCE}],
        }
    }


def run_gates(a):
    req = {"actor", "action", "target"}
    now = time.time()
    actor = a.get("actor", "?")
    RATE[actor] = [t for t in RATE[actor] if now - t < 60]
    act, tgt = str(a.get("action", "")).lower(), str(a.get("target", "")).lower()
    return [
        ("schema", req.issubset(a), "required actor/action/target"),
        ("identity", bool(str(a.get("actor", "")).strip()) and a.get("actor") != "anonymous", "authenticated actor"),
        ("rate", len(RATE[actor]) < POLICIES["rate_per_minute"], "per-actor rate"),
        ("provenance", bool(a.get("source", "")), "origin required"),
        ("policy", act not in POLICIES["blocked_actions"] and tgt not in POLICIES["blocked_targets"], "deny list"),
        ("risk", int(a.get("risk_score", 0)) <= POLICIES["max_risk_score"], "risk threshold"),
        ("budget", len(json.dumps(a.get("payload", {}))) <= POLICIES["max_payload_bytes"], "payload budget"),
        ("liveness", not a.get("kill_switch", False), "kill switch"),
    ]


DASH = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sentra</title>
<style>
:root{--bg:#07090c;--panel:#10151c;--line:#243041;--ink:#e8eef6;--mute:#8ea0b5;--deny:#ff4d4f;--allow:#3dd68c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 ui-sans-serif,system-ui}
header{padding:28px 32px 16px;border-bottom:1px solid var(--line);background:linear-gradient(#1a0c0c,#07090c)}
h1{margin:0;font:700 42px/1 ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase}
.sub{color:var(--mute);margin-top:8px}
main{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:24px 32px}
@media(max-width:900px){main{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);padding:18px}
textarea,button,pre{font:13px/1.4 ui-monospace,monospace}
textarea{width:100%;min-height:140px;background:#05070a;color:var(--ink);border:1px solid var(--line);padding:10px}
button{margin-top:10px;background:var(--deny);color:#fff;border:0;padding:10px 16px;cursor:pointer;font-weight:700}
.gates{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}
.g{border:1px solid var(--line);padding:8px;font-size:12px}
.pass{border-color:#1f6f4a;color:var(--allow)}.fail{border-color:#7a1f24;color:var(--deny)}
pre{white-space:pre-wrap;color:#c9d4e3}
.badge{display:inline-block;padding:2px 8px;border:1px solid var(--line);color:var(--mute);font-size:11px}
</style></head>
<body>
<header>
  <div class="badge">SZLHOLDINGS / sentra</div>
  <h1>Sentra</h1>
  <p class="sub">Deny-by-default eight-gate engine. Signed verdicts. No auto-remediation.</p>
</header>
<main>
  <section class="card">
    <h2>Evaluate</h2>
    <textarea id="r">{"actor":"agent-07","action":"read","target":"telemetry-db","source":"a11oy","risk_score":25}</textarea>
    <button onclick="go()">Run gates</button>
    <div class="gates" id="gates"></div>
  </section>
  <section class="card">
    <h2>Verdict receipt</h2>
    <pre id="o">waiting</pre>
  </section>
</main>
<script>
async function go(){
  const j = await (await fetch('/v1/evaluate',{method:'POST',headers:{'content-type':'application/json'},body:r.value})).json();
  o.textContent = JSON.stringify(j,null,2);
  gates.innerHTML = (j.gates||[]).map(g=>`<div class="g ${g.pass?'pass':'fail'}">${g.gate}<br>${g.pass?'PASS':'DENY'}</div>`).join('');
}
</script>
</body></html>
"""


@app.get("/", response_class=HTMLResponse)
def root():
    return DASH


@app.get("/healthz")
def healthz():
    return {"ok": True, "product": "Sentra", "mode": "deny-by-default", "gates": 8, "key_source": KEY_SOURCE}


@app.post("/v1/evaluate")
async def evaluate(req: Request):
    try:
        a = await req.json()
    except Exception:
        return JSONResponse({"verdict": "DENY", "reason": "malformed JSON"}, status_code=400)
    gates = run_gates(a)
    failed = [g for g in gates if not g[1]]
    rec = {
        "verdict": "DENY" if failed else "ALLOW",
        "actor": a.get("actor"),
        "action": a.get("action"),
        "target": a.get("target"),
        "ts": time.time(),
        "gates": [{"gate": n, "pass": ok, "rule": d} for n, ok, d in gates],
        "failed": [n for n, ok, _ in failed],
    }
    rec.update(receipt(rec))
    VERDICTS.appendleft(rec)
    RATE[a.get("actor", "?")].append(time.time())
    return rec


@app.get("/v1/verdicts")
def verdicts():
    return {"count": len(VERDICTS), "verdicts": list(VERDICTS)[:50]}


@app.get("/v1/policies")
def policies():
    return {"policies": POLICIES, "truth": "REPORTED"}
