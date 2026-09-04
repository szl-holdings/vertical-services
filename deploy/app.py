"""SZL Vertical Services — six governed engines behind one operational fabric.

The service combines deterministic vertical calculations, canonical formula
bindings, Living Anatomy contracts, session-scoped Second-Brain memory, bounded
official-source connectors, source-bound builds, model and kernel routing,
hash-addressed receipts, and six domain-native command experiences.

Killinchu is the single public cyber-physical resilience and maritime product.
The legacy ``/vessels`` route remains only as a compatibility surface. Sentra is
an independently testable capability plane behind Killinchu ``/defend``; Aegis
is a portfolio label, IMMUNE remains migration-gated, and neither is another
public Space. PURIQ resolves to Finance without duplicate execution authority.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from szl_verticals.core import (
    ENGINES,
    SOURCE_REPOSITORY,
    VERSION,
    build_info as _build_info,
)
from szl_verticals.counsel import counsel
from szl_verticals.finance import finance
from szl_verticals.frontier import frontier
from szl_verticals.intelligence import intelligence
from szl_verticals.killinchu import killinchu
from szl_verticals.killinchu_runtime_contract import (
    architecture as _szl_killinchu_architecture,
    compatibility_headers as _szl_killinchu_headers,
    lobe as _szl_killinchu_lobe,
)
from szl_verticals.lyte import lyte
from szl_verticals.operational import STORE, operational, vertical_readiness
from szl_verticals.sentra import SENTRA_KEY_SOURCE, sentra
from szl_verticals.showcase import showcase
from szl_verticals.terra import terra
from szl_verticals.vessels import vessels

app = FastAPI(
    title="SZL Vertical Services",
    version=VERSION,
    description=(
        "Six governed Python engines with Living Anatomy, formula bindings, "
        "Second-Brain memory, bounded official-source connectors, source-bound "
        "model and kernel routing, Hatun review, and differentiated command rooms."
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


@app.middleware("http")
async def killinchu_product_identity(request: Request, call_next):
    """Label compatibility responses without changing domain payloads."""
    response = await call_next(request)
    for key, value in _szl_killinchu_headers(request.url.path).items():
        response.headers[key] = value
    return response


for router in (
    sentra,
    lyte,
    vessels,
    killinchu,
    finance,
    terra,
    counsel,
    operational,
    frontier,
    intelligence,
    showcase,
):
    app.include_router(router)


CATALOG = {
    "sentra": {
        "purpose": (
            "Killinchu Defend capability: evidence-linked attack paths, "
            "deny-by-default gates, bounded response review, and signed verdicts"
        ),
        "public_home": "SZLHOLDINGS/killinchu",
        "public_route": "https://szlholdings-killinchu.hf.space/defend",
        "product_state": "CAPABILITY_PLANE",
        "experience": "/experience/defend",
        "intelligence": "/intelligence/defend",
        "aliases": ["aegis", "defend"],
    },
    "lyte": {
        "purpose": (
            "business-observability metrics, delivery health, percentiles, "
            "drift, and economic-outcome context"
        ),
        "public_home": "SZLHOLDINGS/lyte",
        "experience": "/experience/lyte",
        "intelligence": "/intelligence/lyte",
        "aliases": ["business-observability"],
    },
    "killinchu": {
        "purpose": "defense policy and maritime track-risk command",
        "public_home": "SZLHOLDINGS/killinchu",
        "experience": "/experience/killinchu",
        "intelligence": "/intelligence/killinchu",
        "status": "CANONICAL",
        "vessels": "CONSOLIDATED",
        "aliases": ["vessels"],
    },
    "finance": {
        "purpose": (
            "PURIQ market-series analytics, SEC evidence, public rates, crypto "
            "spot references, and read-only prediction-market intelligence"
        ),
        "public_home": "SZLHOLDINGS/finance",
        "experience": "/experience/puriq",
        "intelligence": "/intelligence/puriq",
        "aliases": ["puriq", "markets"],
    },
    "terra": {
        "purpose": (
            "property calculations, parcel evidence, and public building-"
            "condition research"
        ),
        "public_home": "SZLHOLDINGS/terra",
        "experience": "/experience/terra",
        "intelligence": "/intelligence/terra",
        "aliases": ["real-estate"],
    },
    "counsel": {
        "purpose": "matters, obligations, public legal authority, and receipt chains",
        "public_home": "SZLHOLDINGS/counsel",
        "experience": "/experience/prism",
        "intelligence": "/intelligence/prism",
        "aliases": ["prism"],
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
            },
            "/api/verticals/aegis": {
                "status": "PORTFOLIO_ALIAS",
                "canonical": "/api/verticals/sentra",
                "public_route": "https://szlholdings-killinchu.hf.space/defend",
            },
            "/api/verticals/defend": {
                "status": "CAPABILITY_ALIAS",
                "canonical": "/api/verticals/sentra",
                "public_route": "https://szlholdings-killinchu.hf.space/defend",
            },
            "/api/verticals/puriq": {
                "status": "PRODUCT_ALIAS",
                "canonical": "/api/verticals/finance",
            },
        },
        "build": build["build"],
        "sentra_signing_key_source": SENTRA_KEY_SOURCE,
        "state": {
            "business_working_sets": "SESSION_ISOLATED_PROCESS_MEMORY",
            "connector_observations": STORE.status(),
        },
        "session_header": "X-SZL-Session",
        "official_source_connectors_wired": True,
        "vertical_intelligence_wired": True,
        "model_provider_invocation_fail_closed": True,
        "caller_supplied_model_endpoints_allowed": False,
        "hatun_can_authorize": False,
        "effectors_enabled": False,
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
        "intelligence_plan_ready": True,
        "inference_requires_operator_model_binding": True,
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
        "product_authority": _szl_killinchu_architecture(),
        "vessels_independent_vertical": False,
        "vessels_canonical_home": "SZLHOLDINGS/killinchu",
        "aegis_canonical_runtime": "killinchu:defend",
        "sentra_independent_public_vertical": False,
        "sentra_public_route": "https://szlholdings-killinchu.hf.space/defend",
        "immune_canonical_runtime": "MIGRATION_REQUIRED",
        "puriq_canonical_runtime": "finance",
        "operational_fabric": {
            "catalog": "/api/verticals",
            "frontier": "/api/verticals/{vertical}/frontier",
            "experience": "/experience/{vertical}",
            "intelligence_room": "/intelligence/{vertical}",
            "intelligence_profile": "/api/verticals/{vertical}/intelligence",
            "intelligence_plan": "/api/verticals/{vertical}/intelligence/plan",
            "intelligence_invoke": "/api/verticals/{vertical}/intelligence/invoke",
            "anatomy": "/api/verticals/{vertical}/anatomy",
            "formulas": "/api/verticals/{vertical}/formulas",
            "connectors": "/api/verticals/{vertical}/connectors",
            "second_brain": "/api/verticals/{vertical}/second-brain",
            "hatun_review": "/api/verticals/{vertical}/hatun/evaluate",
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
        "caller_supplied_model_endpoints_allowed": False,
        "effectors_enabled": False,
        "truth_label": "MEASURED",
        "fashion_rule": "take the job, never proprietary code",
        "fashion": "/api/fashion",
    }


def _fashion_contract_path() -> Path:
    here = Path(__file__).resolve()
    candidates = (
        here.parent / "contracts" / "fashion-lineage.v1.json",
        here.parents[1] / "contracts" / "fashion-lineage.v1.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("fashion-lineage.v1.json missing from image and repo")


_FASHION_PATH = _fashion_contract_path()


@app.get("/api/fashion")
def fashion_lineage() -> dict:
    payload = json.loads(_FASHION_PATH.read_text(encoding="utf-8"))
    payload["served_from"] = "contracts/fashion-lineage.v1.json"
    return payload


def _landing_page() -> str:
    cards = []
    for engine in ENGINES:
        info = CATALOG[engine]
        badge = (
            " · VESSELS CONSOLIDATED HERE"
            if engine == "killinchu"
            else " · CAPABILITY PLANE INSIDE KILLINCHU"
            if engine == "sentra"
            else ""
        )
        aliases = " · ".join(info.get("aliases", []))
        cards.append(
            f"""<article class="card"><div class="eyebrow">{html.escape(engine.upper())}{badge}</div>
            <h2>{html.escape(info['purpose'].split(',')[0].title())}</h2>
            <p>{html.escape(info['purpose'])}</p>
            <small>{html.escape(aliases)}</small>
            <div class="actions"><a href="{html.escape(info['experience'])}">Command</a>
            <a href="{html.escape(info['intelligence'])}">Intelligence</a>
            <a href="/{engine}/healthz">Health</a>
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
.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}.card{{background:linear-gradient(145deg,rgba(255,255,255,.035),transparent),var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px;min-height:280px;display:flex;flex-direction:column}}
.card h2{{font-size:26px;margin:14px 0 8px}}.card p,.card small{{color:var(--muted);margin:0 0 14px}}.actions{{display:flex;gap:14px;flex-wrap:wrap;margin-top:auto}}.actions a{{text-decoration:none;border-bottom:1px solid var(--accent)}}
.boundary{{margin-top:18px;padding:18px;border:1px solid var(--line);border-radius:14px;color:var(--muted)}}footer{{margin-top:36px;color:var(--muted)}}
@media(max-width:900px){{.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:620px){{.grid{{grid-template-columns:1fr}}h1{{font-size:clamp(46px,18vw,72px)}}}}
@media(pointer:coarse){{a{{min-height:48px}}}}@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{scroll-behavior:auto!important;animation:none!important;transition:none!important}}}}
</style></head><body><main class="shell"><div class="top"><div class="brand">SZL / VERTICAL SERVICES V{VERSION}</div><a href="/docs">OpenAPI</a></div>
<h1>Six engines. One second brain. One governed intelligence fabric.</h1><p class="lede">Real vertical calculations, official-source connectors, Living Anatomy, formula bindings, source identity, governed memory, Hatun review, model routing, kernel gates, and receipts—without fabricated feeds or silent authority.</p>
<div class="proof"><span class="pill"><strong>LIVE</strong> Python runtime contract</span><span class="pill">source {html.escape(revision_short)}</span><span class="pill">store {html.escape(store['durability'])}</span><span class="pill">3 model routes</span><span class="pill">6 kernel contracts</span><span class="pill">effectors disabled</span></div>
<section class="grid">{''.join(cards)}</section><section class="boundary"><strong>Operational boundary:</strong> official-source connectors are fixed and bounded. Connector observations are hash-addressed and stored under a hashed session scope. Model invocation remains unavailable until an operator binds a fixed allowlisted endpoint, credential, protocol, and exact declared revision. Hatun can recommend review or abstention only. NOAA AIS is historical official planning data—not represented as a live vessel feed. Trading, legal advice, cyber effectors, person-level prospecting, and unattended consequential actions remain disabled.</section>
<footer class="mono">{SOURCE_REPOSITORY} · VERSION {VERSION} · <a href="/api/build-info">BUILD INFO</a> · <a href="/readyz">READINESS</a> · <a href="/api/intelligence">INTELLIGENCE CATALOG</a></footer></main></body></html>"""


@app.get("/killinchu/architecture", tags=["Killinchu"])
def killinchu_architecture() -> dict:
    """Read the canonical source contract; reachability is not model truth."""
    return _szl_killinchu_architecture()


@app.get("/killinchu/aegis/healthz", tags=["Killinchu"])
def killinchu_aegis_lobe() -> dict:
    return _szl_killinchu_lobe("aegis")


@app.get("/killinchu/vessels/healthz", tags=["Killinchu"])
def killinchu_vessels_lobe() -> dict:
    return _szl_killinchu_lobe("vessels")


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    return HTMLResponse(_landing_page())
