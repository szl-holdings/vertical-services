"""SZL Vertical Services — six governed engines behind one operational fabric.

The service combines deterministic vertical calculations, canonical formula
bindings, Living Anatomy contracts, session-scoped Second-Brain memory, bounded
official-source connectors, source-bound builds, and hash-addressed receipts.

Killinchu is the single defense-and-maritime vertical. The legacy ``/vessels``
route remains only as a compatibility surface; its canonical runtime is
``/killinchu`` and its public product is ``SZLHOLDINGS/killinchu``.
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
from szl_verticals.killinchu import killinchu
from szl_verticals.finance import finance
from szl_verticals.terra import terra
from szl_verticals.counsel import counsel
from szl_verticals.operational import STORE, operational, vertical_readiness

app = FastAPI(
    title="SZL Vertical Services",
    version=VERSION,
    description=(
        "Six governed engines with Living Anatomy, formula bindings, "
        "Second-Brain memory, and bounded official-source connectors."
    ),
)


@app.middleware("http")
async def response_hardening(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    if request.url.path != "/":
        response.headers["Cache-Control"] = "no-store"
    return response


for router in (sentra, lyte, vessels, killinchu, finance, terra, counsel, operational):
    app.include_router(router)


CATALOG = {
    "sentra": {
        "purpose": "deny-by-default policy gates, threat evidence, and signed verdicts",
        "public_home": "SZLHOLDINGS/sentra",
    },
    "lyte": {
        "purpose": "business-observability metrics, percentiles, and drift scoring",
        "public_home": "SZLHOLDINGS/lyte",
    },
    "killinchu": {
        "purpose": "defense policy and maritime track-risk command",
        "public_home": "SZLHOLDINGS/killinchu",
        "status": "CANONICAL",
        "vessels": "CONSOLIDATED",
    },
    "finance": {
        "purpose": "market-series analytics and SEC filing evidence",
        "public_home": "SZLHOLDINGS/finance",
    },
    "terra": {
        "purpose": "property calculations and official parcel evidence",
        "public_home": "SZLHOLDINGS/terra",
    },
    "counsel": {
        "purpose": "matters, obligations, public legal authority, and receipt chains",
        "public_home": "SZLHOLDINGS/counsel",
    },
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
        "compatibility_routes": {
            "/vessels": {
                "status": "DEPRECATED_COMPATIBILITY",
                "canonical": "/killinchu",
            }
        },
        "build": build["build"],
        "sentra_signing_key_source": SENTRA_KEY_SOURCE,
        "state": {
            "business_working_sets": "SESSION_ISOLATED_PROCESS_MEMORY",
            "connector_observations": STORE.status(),
        },
        "session_header": "X-SZL-Session",
        "official_source_connectors_wired": True,
        "truth_label": "MEASURED",
        "source": SOURCE_REPOSITORY,
    }


@app.get("/readyz")
def readiness() -> JSONResponse:
    verticals = {engine: vertical_readiness(engine) for engine in ENGINES}
    ready = all(item["ready"] for item in verticals.values())
    payload = {
        "ready": ready,
        "service": "szl-vertical-services",
        "version": VERSION,
        "verticals": {
            engine: {
                "ready": item["ready"],
                "status": item["status"],
                "requirements": item["requirements"],
                "live_data": item["live_data"],
            }
            for engine, item in verticals.items()
        },
        "build": _build_info()["build"],
        "store": STORE.status(),
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
        "vessels_independent_vertical": False,
        "vessels_canonical_home": "SZLHOLDINGS/killinchu",
        "operational_fabric": {
            "catalog": "/api/verticals",
            "anatomy": "/api/verticals/{vertical}/anatomy",
            "formulas": "/api/verticals/{vertical}/formulas",
            "connectors": "/api/verticals/{vertical}/connectors",
            "second_brain": "/api/verticals/{vertical}/second-brain",
            "readiness": "/api/verticals/{vertical}/readyz",
            "fetch": "/api/verticals/{vertical}/connectors/{connector_id}/fetch",
        },
        "state": {
            "business_working_sets": "SESSION_ISOLATED_PROCESS_MEMORY",
            "connector_observations": STORE.status(),
        },
        "session_header": "X-SZL-Session",
        "official_source_connectors_wired": True,
        "live_observations_require_explicit_fetch": True,
        "caller_supplied_urls_allowed": False,
        "effectors_enabled": False,
        "truth_label": "MEASURED",
    }


def _landing_page() -> str:
    cards = []
    for engine in ENGINES:
        info = CATALOG[engine]
        badge = " · VESSELS CONSOLIDATED HERE" if engine == "killinchu" else ""
        cards.append(
            f"""<article class="card"><div class="eyebrow">{html.escape(engine.upper())}{badge}</div>
            <h2>{html.escape(info['purpose'].split(',')[0].title())}</h2>
            <p>{html.escape(info['purpose'])}</p>
            <div class="actions"><a href="/{engine}/healthz">Health</a>
            <a href="/api/verticals/{engine}/anatomy">Anatomy</a>
            <a href="/api/verticals/{engine}/formulas">Math</a></div></article>"""
        )
    revision = _build_info()["build"]["revision"]
    revision_short = revision[:12] if revision != "UNAVAILABLE" else revision
    store = STORE.status()
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
.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}.card{{background:linear-gradient(145deg,rgba(255,255,255,.035),transparent),var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px;min-height:238px;display:flex;flex-direction:column}}
.card h2{{font-size:26px;margin:14px 0 8px}}.card p{{color:var(--muted);margin:0 0 22px}}.actions{{display:flex;gap:14px;flex-wrap:wrap;margin-top:auto}}.actions a{{text-decoration:none;border-bottom:1px solid var(--accent)}}
.boundary{{margin-top:18px;padding:18px;border:1px solid var(--line);border-radius:14px;color:var(--muted)}}footer{{margin-top:36px;color:var(--muted)}}
@media(max-width:900px){{.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:620px){{.grid{{grid-template-columns:1fr}}h1{{font-size:clamp(46px,18vw,72px)}}}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{scroll-behavior:auto!important;animation:none!important;transition:none!important}}}}
</style></head><body><main class="shell"><div class="top"><div class="brand">SZL / VERTICAL SERVICES V2</div><a href="/docs">OpenAPI</a></div>
<h1>Six engines. One second brain.</h1><p class="lede">Real vertical calculations, official-source connectors, Living Anatomy, formula bindings, source identity, governed memory, and receipts—without fabricated feeds or silent authority.</p>
<div class="proof"><span class="pill"><strong>LIVE</strong> runtime contract</span><span class="pill">source {html.escape(revision_short)}</span><span class="pill">store {html.escape(store['durability'])}</span><span class="pill">Vessels → Killinchu</span></div>
<section class="grid">{''.join(cards)}</section><section class="boundary"><strong>Operational boundary:</strong> official-source connectors are fixed and bounded. Connector observations are hash-addressed and stored under a hashed session scope. Existing business working sets remain process-memory. NOAA AIS is historical official planning data—not represented as a live vessel feed. Effectors remain disabled and human approval is required.</section>
<footer class="mono">{SOURCE_REPOSITORY} · VERSION {VERSION} · <a href="/api/build-info">BUILD INFO</a> · <a href="/readyz">READINESS</a> · <a href="/api/verticals">VERTICAL CATALOG</a></footer></main></body></html>"""


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    return HTMLResponse(_landing_page())
