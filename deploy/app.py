"""SZL Vertical Services — six governed engines behind one FastAPI service.

This runtime performs real, deterministic calculations over caller-supplied data.
It does not claim that process-memory state is durable or that external market,
AIS, MLS, court, or security feeds are connected. Truth labels remain explicit:
MEASURED, REPORTED, and MODELED.
"""
from __future__ import annotations

import html

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from szl_verticals.core import (
    ENGINES,
    SOURCE_REPOSITORY,
    VERSION,
    build_info as _build_info,
)
from szl_verticals.sentra import SENTRA_KEY_SOURCE, sentra
from szl_verticals.lyte import lyte
from szl_verticals.vessels import vessels
from szl_verticals.finance import finance
from szl_verticals.terra import terra
from szl_verticals.counsel import counsel

app = FastAPI(
    title="SZL Vertical Services",
    version=VERSION,
    description=(
        "Six governed engines. Real calculations over caller-supplied inputs; "
        "no fabricated feeds and no durability overclaim."
    ),
)


@app.middleware("http")
async def response_hardening(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path != "/":
        response.headers["Cache-Control"] = "no-store"
    return response


for router in (sentra, lyte, vessels, finance, terra, counsel):
    app.include_router(router)


CATALOG = {
    "sentra": {"purpose": "deny-by-default policy gates and signed verdicts", "public_home": "SZLHOLDINGS/sentra"},
    "lyte": {"purpose": "metric summaries and drift scoring", "public_home": "SZLHOLDINGS/lyte"},
    "vessels": {
        "purpose": "caller-supplied maritime track risk calculations",
        "public_home": "SZLHOLDINGS/killinchu",
        "status": "CONSOLIDATED",
    },
    "finance": {"purpose": "volatility, drawdown, momentum, and signal calculations", "public_home": "SZLHOLDINGS/finance"},
    "terra": {"purpose": "price-per-square-foot, cap-rate, and comp calculations", "public_home": "SZLHOLDINGS/terra"},
    "counsel": {"purpose": "matter, obligation, docket, and receipt-chain operations", "public_home": "SZLHOLDINGS/counsel"},
}


@app.get("/healthz")
def root_health() -> dict:
    build = _build_info()
    return {
        "ok": True,
        "status": "ok",
        "service": "szl-vertical-services",
        "version": VERSION,
        "engines": list(ENGINES),
        "routes": {engine: f"/{engine}/healthz" for engine in ENGINES},
        "build": build["build"],
        "sentra_signing_key_source": SENTRA_KEY_SOURCE,
        "state": "SESSION_ISOLATED_PROCESS_MEMORY",
        "session_header": "X-SZL-Session",
        "input_mode": "CALLER_SUPPLIED",
        "truth_label": "MEASURED",
        "source": SOURCE_REPOSITORY,
    }


@app.get("/readyz")
def readiness() -> JSONResponse:
    build = _build_info()
    ready = build["build"]["state"] == "OBSERVED" and SENTRA_KEY_SOURCE == "env"
    payload = {
        "ready": ready,
        "build": build["build"],
        "source_binding": build["source_binding"],
        "sentra_signing_key_source": SENTRA_KEY_SOURCE,
        "requirements": {
            "source_bound": build["build"]["state"] == "OBSERVED",
            "persistent_signing_key": SENTRA_KEY_SOURCE == "env",
        },
        "truth_label": "MEASURED",
    }
    return JSONResponse(payload, status_code=200 if ready else 503)


@app.get("/api/build-info")
def build_info() -> dict:
    return _build_info()


@app.get("/.well-known/szl-source.json")
def source_document() -> dict:
    return _build_info()


@app.get("/api/catalog")
def catalog() -> dict:
    return {
        "service": "szl-vertical-services",
        "version": VERSION,
        "engines": CATALOG,
        "state": "SESSION_ISOLATED_PROCESS_MEMORY",
        "session_header": "X-SZL-Session",
        "input_mode": "CALLER_SUPPLIED",
        "external_feeds_claimed": False,
        "truth_label": "MEASURED",
    }


def _landing_page() -> str:
    cards = []
    for engine in ENGINES:
        info = CATALOG[engine]
        badge = " · CONSOLIDATED INTO KILLINCHU" if engine == "vessels" else ""
        cards.append(
            f"""<article class="card"><div class="eyebrow">{html.escape(engine.upper())}{badge}</div>
            <h2>{html.escape(engine.title())}</h2><p>{html.escape(info['purpose'])}</p>
            <div class="actions"><a href="/{engine}/healthz">Health</a><a href="/docs#/{engine}">API</a></div></article>"""
        )
    revision = _build_info()["build"]["revision"]
    revision_short = revision[:12] if revision != "UNAVAILABLE" else revision
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>SZL Vertical Services</title><style>
:root{{color-scheme:dark;--bg:#05070a;--panel:#0d1219;--line:#263241;--ink:#f4f7fb;--muted:#98a6b8;--accent:#7dd3fc;--good:#6ee7b7}}
*{{box-sizing:border-box;min-inline-size:0}}html{{overflow-x:clip}}body{{margin:0;background:radial-gradient(circle at 80% 0,#10273a 0,transparent 30%),var(--bg);color:var(--ink);font:15px/1.55 system-ui,sans-serif}}
a{{color:inherit;min-height:44px;display:inline-flex;align-items:center}}a:focus-visible{{outline:3px solid var(--accent);outline-offset:3px}}
.shell{{width:min(1180px,100%);margin:auto;padding:clamp(22px,5vw,64px)}}.top{{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;align-items:center}}
.brand,.eyebrow,.mono{{font:700 11px/1.4 ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase}}.brand,.eyebrow{{color:var(--accent)}}
h1{{font-size:clamp(48px,9vw,104px);line-height:.88;letter-spacing:-.055em;margin:40px 0 24px;max-width:10ch}}.lede{{font-size:clamp(17px,2vw,22px);max-width:72ch;color:var(--muted)}}
.proof{{display:flex;gap:8px;flex-wrap:wrap;margin:28px 0 42px}}.pill{{border:1px solid var(--line);border-radius:999px;padding:8px 12px;color:var(--muted)}}.pill strong{{color:var(--good)}}
.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}.card{{background:linear-gradient(145deg,rgba(255,255,255,.035),transparent),var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px;min-height:220px;display:flex;flex-direction:column}}
.card h2{{font-size:28px;margin:14px 0 8px}}.card p{{color:var(--muted);margin:0 0 22px}}.actions{{display:flex;gap:14px;margin-top:auto}}.actions a{{text-decoration:none;border-bottom:1px solid var(--accent)}}
.boundary{{margin-top:18px;padding:18px;border:1px solid var(--line);border-radius:14px;color:var(--muted)}}footer{{margin-top:36px;color:var(--muted)}}
@media(max-width:900px){{.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:620px){{.grid{{grid-template-columns:1fr}}h1{{font-size:clamp(46px,18vw,72px)}}}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{scroll-behavior:auto!important;animation:none!important;transition:none!important}}}}
</style></head><body><main class="shell"><div class="top"><div class="brand">SZL / VERTICAL SERVICES</div><a href="/docs">OpenAPI</a></div>
<h1>Six engines. One governed runtime.</h1><p class="lede">Executable vertical calculations with explicit provenance, signed decisions, source-bound builds, and fail-closed readiness. No fabricated feeds.</p>
<div class="proof"><span class="pill"><strong>LIVE</strong> runtime</span><span class="pill">source {html.escape(revision_short)}</span><span class="pill">truth labels preserved</span><span class="pill">caller-supplied inputs</span></div>
<section class="grid">{''.join(cards)}</section><section class="boundary"><strong>Operational boundary:</strong> calculations and API contracts are live. State is isolated by a caller-held X-SZL-Session token and remains process-memory unless a future persistent store is explicitly connected. External AIS, market, MLS, PACER, and security feeds are not claimed by this service.</section>
<footer class="mono">{SOURCE_REPOSITORY} · VERSION {VERSION} · <a href="/api/build-info">BUILD INFO</a> · <a href="/readyz">READINESS</a></footer></main></body></html>"""


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    return HTMLResponse(_landing_page())
