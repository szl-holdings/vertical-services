"""Domain-native command surfaces and Hatun review envelopes.

This module is intentionally non-executing. It assembles source-bound state from
the existing operational fabric, renders six distinct accessible experiences,
and evaluates evidence for human review. It never places trades, changes
infrastructure, or authorizes consequential action.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import re
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import Field, field_validator

from .contract import (
    advisory_lambda,
    anatomy_for,
    canonical_vertical,
    connectors_for,
    formulas_for,
)
from .core import SessionScope, StrictModel, build_info
from .operational import STORE, vertical_readiness
from .profiles import ALIASES, VERTICALS

frontier = APIRouter(tags=["frontier-command"])

AXIS_ID = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
ACTION_ID = re.compile(r"^[a-z][a-z0-9_.:-]{1,63}$", re.IGNORECASE)


class HatunEvaluateRequest(StrictModel):
    """Bounded evidence review request.

    Evidence references are converted to digests before they enter the response,
    so caller-held URLs, document handles, or internal identifiers are not
    reflected by the public API.
    """

    intent: str = Field(min_length=1, max_length=240)
    requested_action: str = Field(default="review", min_length=2, max_length=64)
    axes: dict[str, float]
    evidence_refs: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("intent")
    @classmethod
    def validate_intent(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("intent must not be blank")
        return value

    @field_validator("requested_action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        value = value.strip()
        if ACTION_ID.fullmatch(value) is None:
            raise ValueError("requested_action must be a bounded action identifier")
        return value

    @field_validator("axes")
    @classmethod
    def validate_axes(cls, value: dict[str, float]) -> dict[str, float]:
        if not 2 <= len(value) <= 16:
            raise ValueError("axes must contain between 2 and 16 measurements")
        clean: dict[str, float] = {}
        for key, item in value.items():
            normalized = key.strip().lower()
            numeric = float(item)
            if AXIS_ID.fullmatch(normalized) is None:
                raise ValueError(f"invalid axis identifier: {key!r}")
            if not math.isfinite(numeric) or numeric < 0.0 or numeric > 1.0:
                raise ValueError(f"axis {normalized!r} must be finite and within [0,1]")
            clean[normalized] = numeric
        return clean

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, value: list[str]) -> list[str]:
        clean: list[str] = []
        for item in value:
            normalized = " ".join(str(item).split())
            if not normalized or len(normalized) > 240:
                raise ValueError("each evidence reference must contain 1-240 characters")
            clean.append(normalized)
        if len(clean) != len(set(clean)):
            raise ValueError("evidence references must be unique")
        return clean


def _evidence_digests(refs: list[str]) -> list[str]:
    return [hashlib.sha256(item.encode("utf-8")).hexdigest() for item in refs]


def frontier_state(vertical: str) -> dict[str, Any]:
    """Return the non-session command contract for one vertical or alias."""
    requested = vertical.strip().lower()
    canonical = canonical_vertical(requested)
    profile = VERTICALS[canonical]
    readiness = vertical_readiness(canonical)
    return {
        "schema": "szl.vertical-frontier/v3",
        "requested_vertical": requested,
        "vertical": canonical,
        "alias_resolved": requested != canonical,
        "product": profile["product"],
        "domain": profile["domain"],
        "mission": profile["mission"],
        "experience": profile["experience"],
        "anatomy": anatomy_for(canonical),
        "formulas": formulas_for(canonical),
        "connectors": connectors_for(canonical),
        "readiness": readiness,
        "source": build_info(),
        "second_brain": {
            "endpoint": f"/api/verticals/{canonical}/second-brain",
            "scope": "HASHED_CALLER_SESSION",
            "hydration": "EXPLICIT_AUTHORIZED_REQUEST_ONLY",
        },
        "hatun": {
            "endpoint": f"/api/verticals/{canonical}/hatun/evaluate",
            "decision_states": ["REVIEW", "ABSTAIN"],
            "can_authorize": False,
            "effectors_enabled": False,
        },
        "aliases": sorted(alias for alias, target in ALIASES.items() if target == canonical),
        "truth_label": "MEASURED",
    }


@frontier.get("/api/verticals/{vertical}/frontier")
def vertical_frontier(vertical: str) -> dict[str, Any]:
    return frontier_state(vertical)


@frontier.post("/api/verticals/{vertical}/hatun/evaluate")
def hatun_evaluate(
    vertical: str,
    request: HatunEvaluateRequest,
    session: SessionScope,
) -> dict[str, Any]:
    """Evaluate evidence for review without authorizing or executing anything."""
    requested = vertical.strip().lower()
    canonical = canonical_vertical(requested)
    readiness = vertical_readiness(canonical, session_scope=session)
    rollup = advisory_lambda(request.axes)
    evidence_sha256 = _evidence_digests(request.evidence_refs)
    observations = STORE.counts(vertical=canonical, session_scope=session)

    blockers: list[str] = []
    if not readiness["ready"]:
        blockers.append("VERTICAL_NOT_READY")
    if not evidence_sha256:
        blockers.append("NO_EVIDENCE_REFERENCES")
    if observations["observations"] == 0:
        blockers.append("NO_SESSION_OBSERVATIONS")
    if rollup["score"] < 0.80:
        blockers.append("LAMBDA_BELOW_REVIEW_FLOOR")

    decision = "REVIEW" if not blockers else "ABSTAIN"
    basis = {
        "schema": "szl.hatun-review-basis/v1",
        "requested_vertical": requested,
        "vertical": canonical,
        "intent": request.intent,
        "requested_action": request.requested_action,
        "axes": rollup["axes"],
        "lambda_score": rollup["score"],
        "lambda_status": rollup["lambda_status"],
        "source_revision": readiness["build"]["revision"],
        "formula_registry_bound": readiness["requirements"]["formula_registry_bound"],
        "vertical_ready": readiness["ready"],
        "session_observation_count": observations["observations"],
        "evidence_ref_sha256": evidence_sha256,
        "decision": decision,
        "blockers": blockers,
        "can_authorize": False,
        "can_execute": False,
        "human_approval_required": True,
    }
    canonical_basis = json.dumps(
        basis,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return {
        **basis,
        "lambda_advisory": rollup,
        "receipt": {
            "schema": "szl.hatun-review-receipt/v1",
            "algorithm": "SHA-256",
            "basis_sha256": hashlib.sha256(canonical_basis.encode("utf-8")).hexdigest(),
            "signature_claimed": False,
            "session_token_recorded": False,
            "raw_evidence_references_recorded": False,
        },
        "effectors_enabled": False,
        "truth_label": "MODELED",
    }


def _experience_html(vertical: str) -> str:
    state = frontier_state(vertical)
    canonical = state["vertical"]
    profile = VERTICALS[canonical]
    experience = profile["experience"]
    build = state["source"]["build"]
    readiness = state["readiness"]
    formulas = state["formulas"]
    connectors = state["connectors"]

    formula_cards = "".join(
        (
            '<article class="datum">'
            f'<span class="datum-id">{html.escape(item["id"])}</span>'
            f'<strong>{html.escape(item["name"])}</strong>'
            f'<small>{html.escape(item["status"])}</small>'
            "</article>"
        )
        for item in formulas
    )
    connector_cards = "".join(
        (
            '<article class="datum">'
            f'<span class="datum-id">{html.escape(item["id"])}</span>'
            f'<strong>{html.escape(item["authority"])}</strong>'
            f'<small>{html.escape(item["state"])} · '
            f'{"REQUIRED" if item["required"] else "OPTIONAL"}</small>'
            "</article>"
        )
        for item in connectors
    )
    alias_note = (
        f'Alias <code>{html.escape(state["requested_vertical"])}</code> resolves to '
        f'<code>{html.escape(canonical)}</code>.'
        if state["alias_resolved"]
        else f'Canonical runtime <code>{html.escape(canonical)}</code>.'
    )
    consolidation = profile.get("consolidation") or {}
    consolidation_rows = "".join(
        f"<li><span>{html.escape(str(key).replace('_', ' '))}</span>"
        f"<strong>{html.escape(str(value))}</strong></li>"
        for key, value in consolidation.items()
        if not isinstance(value, dict)
    )
    revision = build["revision"]
    revision_short = revision[:12] if revision != "UNAVAILABLE" else revision
    ready_label = "READY" if readiness["ready"] else "DEGRADED"
    ready_class = "good" if readiness["ready"] else "warn"

    return f"""<!doctype html>
<html lang="en" data-vertical="{html.escape(canonical)}" data-motif="{html.escape(experience['motif'])}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="dark">
<title>{html.escape(experience['title'])} · SZL Holdings</title>
<style>
:root{{
  color-scheme:dark;
  --bg:{experience['background']};
  --panel:{experience['panel']};
  --ink:#f4f7fb;
  --muted:#9ba8b7;
  --line:color-mix(in srgb,{experience['accent']} 23%,transparent);
  --accent:{experience['accent']};
  --accent2:{experience['accent_secondary']};
  --good:#6ee7b7;
  --warn:#f4c873;
}}
*{{box-sizing:border-box;min-inline-size:0}}
html{{overflow-x:clip;background:var(--bg);scroll-padding-top:80px}}
body{{margin:0;min-height:100vh;overflow-x:clip;color:var(--ink);font:15px/1.55 Inter,ui-sans-serif,system-ui,sans-serif;background:
radial-gradient(circle at 78% 8%,color-mix(in srgb,var(--accent) 15%,transparent),transparent 34rem),
radial-gradient(circle at 12% 62%,color-mix(in srgb,var(--accent2) 10%,transparent),transparent 28rem),
var(--bg)}}
a{{color:inherit;min-height:44px;display:inline-flex;align-items:center}}
a:focus-visible,button:focus-visible{{outline:3px solid var(--accent);outline-offset:3px}}
.skip{{position:fixed;left:12px;top:-80px;z-index:9;background:#fff;color:#000;padding:10px 14px}}
.skip:focus{{top:12px}}
.field{{position:fixed;inset:0;pointer-events:none;opacity:.42;overflow:hidden}}
.field::before,.field::after{{content:"";position:absolute;border:1px solid var(--line);filter:drop-shadow(0 0 18px color-mix(in srgb,var(--accent) 16%,transparent));animation:drift 16s ease-in-out infinite alternate}}
[data-motif="probability-orbit"] .field::before{{width:42vmin;height:42vmin;border-radius:50%;right:8vw;top:12vh;box-shadow:0 0 0 4vmin transparent,0 0 0 calc(4vmin + 1px) var(--line),0 0 0 11vmin transparent,0 0 0 calc(11vmin + 1px) var(--line)}}
[data-motif="parcel-grid"] .field::before{{width:54vmin;height:54vmin;right:5vw;top:11vh;transform:rotate(17deg);background:linear-gradient(90deg,var(--line) 1px,transparent 1px),linear-gradient(var(--line) 1px,transparent 1px);background-size:12% 12%}}
[data-motif="service-lattice"] .field::before{{width:50vmin;height:50vmin;border-radius:34% 66% 54% 46%;right:6vw;top:12vh;box-shadow:inset 0 0 0 9vmin transparent,inset 0 0 0 calc(9vmin + 1px) var(--line)}}
[data-motif="threat-shield"] .field::before{{width:42vmin;height:48vmin;right:8vw;top:10vh;clip-path:polygon(50% 0,94% 18%,84% 72%,50% 100%,16% 72%,6% 18%);background:linear-gradient(145deg,color-mix(in srgb,var(--accent) 10%,transparent),transparent)}}
[data-motif="voyage-radar"] .field::before{{width:52vmin;height:52vmin;border-radius:50%;right:5vw;top:10vh;background:conic-gradient(from 20deg,color-mix(in srgb,var(--accent) 20%,transparent),transparent 22%,transparent 100%)}}
[data-motif="authority-chain"] .field::before{{width:52vmin;height:32vmin;right:4vw;top:18vh;border-radius:999px;box-shadow:-16vmin 12vmin 0 -1px transparent,-16vmin 12vmin 0 0 var(--line),16vmin 12vmin 0 -1px transparent,16vmin 12vmin 0 0 var(--line)}}
.field::after{{width:18vmin;height:18vmin;border-radius:50%;left:8vw;bottom:10vh;animation-delay:-7s}}
@keyframes drift{{to{{transform:translate3d(0,18px,0) rotate(4deg)}}}}
.shell{{position:relative;width:min(1220px,100%);margin:auto;padding:clamp(20px,5vw,68px)}}
.top{{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}}
.brand,.eyebrow,.datum-id,.mono{{font:700 11px/1.4 ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:.12em;text-transform:uppercase}}
.brand,.eyebrow,.datum-id{{color:var(--accent)}}
.nav{{display:flex;gap:12px;flex-wrap:wrap}}
.nav a{{text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:0 14px;background:color-mix(in srgb,var(--panel) 74%,transparent)}}
.hero{{padding:clamp(54px,9vw,112px) 0 46px;display:grid;grid-template-columns:minmax(0,1.25fr) minmax(270px,.75fr);gap:clamp(30px,6vw,82px);align-items:end}}
h1{{font-size:clamp(54px,9vw,118px);line-height:.84;letter-spacing:-.06em;margin:16px 0 24px;max-width:9ch}}
.lede{{font-size:clamp(17px,2vw,23px);max-width:68ch;color:var(--muted)}}
.proof{{display:flex;gap:8px;flex-wrap:wrap;margin-top:28px}}
.pill{{border:1px solid var(--line);border-radius:999px;padding:8px 12px;background:color-mix(in srgb,var(--panel) 72%,transparent)}}
.pill.{ready_class}{{color:var(--{ready_class});border-color:color-mix(in srgb,var(--{ready_class}) 40%,transparent)}}
.instrument{{min-height:330px;border:1px solid var(--line);border-radius:30px;padding:22px;background:linear-gradient(145deg,color-mix(in srgb,var(--accent) 8%,transparent),transparent 45%),color-mix(in srgb,var(--panel) 88%,transparent);box-shadow:0 30px 90px rgb(0 0 0/.34);display:flex;flex-direction:column;justify-content:space-between}}
.instrument strong{{font-size:clamp(32px,4vw,60px);line-height:.95;letter-spacing:-.04em}}
.instrument ul{{list-style:none;padding:0;margin:22px 0 0;display:grid;gap:10px}}
.instrument li{{display:flex;justify-content:space-between;gap:18px;border-top:1px solid var(--line);padding-top:10px;color:var(--muted)}}
.instrument li strong{{font:700 12px/1.4 ui-monospace,monospace;color:var(--ink);letter-spacing:0;text-align:right}}
.section{{padding:26px 0}}
.section-head{{display:flex;justify-content:space-between;gap:18px;align-items:end;flex-wrap:wrap;margin-bottom:18px}}
.section h2{{font-size:clamp(30px,5vw,60px);line-height:.95;letter-spacing:-.045em;margin:0}}
.section p{{color:var(--muted);max-width:70ch}}
.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}}
.datum{{border:1px solid var(--line);border-radius:16px;padding:18px;min-height:150px;background:color-mix(in srgb,var(--panel) 82%,transparent);display:flex;flex-direction:column;gap:12px}}
.datum strong{{font-size:18px}}.datum small{{margin-top:auto;color:var(--muted)}}
.boundary{{margin-top:28px;padding:20px;border:1px solid var(--line);border-radius:16px;background:color-mix(in srgb,var(--panel) 76%,transparent);color:var(--muted)}}
footer{{display:flex;gap:18px;justify-content:space-between;flex-wrap:wrap;margin-top:42px;padding-top:22px;border-top:1px solid var(--line);color:var(--muted)}}
code{{overflow-wrap:anywhere;color:var(--accent2)}}
@media(max-width:900px){{.hero{{grid-template-columns:1fr}}.instrument{{min-height:260px}}.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media(max-width:620px){{.shell{{padding-inline:18px}}h1{{font-size:clamp(52px,18vw,78px)}}.grid{{grid-template-columns:1fr}}.nav{{width:100%}}.nav a{{flex:1;justify-content:center}}}}
@media(pointer:coarse){{a,button{{min-height:48px}}}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{animation:none!important;transition:none!important;scroll-behavior:auto!important}}}}
@media(forced-colors:active){{*{{forced-color-adjust:auto}}.field{{display:none}}}}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to command surface</a><div class="field" aria-hidden="true"></div>
<main id="main" class="shell">
<header class="top"><div class="brand">SZL / {html.escape(experience['kicker'])}</div>
<nav class="nav" aria-label="Command links"><a href="/">Estate</a><a href="/docs">API</a><a href="/api/verticals/{html.escape(canonical)}/frontier">Contract</a></nav></header>
<section class="hero"><div><div class="eyebrow">{html.escape(profile['domain'])} · {html.escape(experience['archetype'])}</div>
<h1>{html.escape(experience['title'])}</h1><p class="lede">{html.escape(profile['mission'])}</p>
<div class="proof"><span class="pill {ready_class}">{ready_label}</span><span class="pill">SOURCE {html.escape(revision_short)}</span><span class="pill">Λ ADVISORY ONLY</span><span class="pill">SECOND BRAIN SESSION-SCOPED</span></div></div>
<aside class="instrument" aria-label="Current contract"><div class="mono">SIGNATURE VIEW</div><strong>{html.escape(experience['signature_view'])}</strong>
<ul><li><span>Runtime</span><strong>{html.escape(canonical)}</strong></li><li><span>Alias</span><strong>{html.escape(alias_note)}</strong></li>
<li><span>Connectors</span><strong>{len(connectors)} BOUNDED</strong></li><li><span>Formulas</span><strong>{len(formulas)} BOUND</strong></li>
{consolidation_rows}</ul></aside></section>
<section class="section"><div class="section-head"><div><div class="eyebrow">LIVING ANATOMY / FORMULA ORGAN</div><h2>Math with boundaries.</h2></div>
<p>Each formula is named, source-associated, and status-labelled. Formula output can constrain review; it cannot independently authorize action.</p></div><div class="grid">{formula_cards}</div></section>
<section class="section"><div class="section-head"><div><div class="eyebrow">SENSE / CONNECTOR ORGAN</div><h2>Fixed sources, no invented feeds.</h2></div>
<p>All network destinations are allowlisted, response sizes are bounded, redirects are rejected, and observations receive hash-addressed receipts.</p></div><div class="grid">{connector_cards}</div></section>
<section class="boundary"><strong>Operational boundary.</strong> Live observations require an explicit connector request and a caller-held <code>X-SZL-Session</code>. Hatun returns only <code>REVIEW</code> or <code>ABSTAIN</code>; effectors remain disabled. This interface does not place trades, provide legal advice, or execute security actions.</section>
<footer class="mono"><span>{html.escape(state['product'])} · {html.escape(canonical)}</span><span>{html.escape(experience['benchmark'])}</span><span><a href="/api/build-info">BUILD INFO</a></span></footer>
</main></body></html>"""


@frontier.get("/experience/{vertical}", response_class=HTMLResponse)
def vertical_experience(vertical: str) -> HTMLResponse:
    return HTMLResponse(_experience_html(vertical))
