"""Premium public intelligence rooms for the six canonical verticals.

The pages are rendered by Python, use only source-bound runtime contracts, and
remain useful without JavaScript. Each vertical has a distinct visual motif and
product job while sharing the SZL evidence, accessibility, and restraint layer.
"""
from __future__ import annotations

import html
import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .contract import canonical_vertical
from .intelligence import intelligence_profile
from .profiles import CANONICAL_VERTICALS, VERTICALS

showcase = APIRouter(tags=["vertical-showcase"])


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _cards(items: list[dict[str, Any]], *, kind: str) -> str:
    rows: list[str] = []
    for item in items:
        if kind == "model":
            state = item["state"]
            title = item["alias"]
            eyebrow = item["artifact_class"]
            body = item["role"]
            foot = f'{item["repo_id"]} · {item["revision_evidence"]}'
        else:
            state = item["execution_state"]
            title = item["alias"]
            eyebrow = "SOFTWARE KERNEL"
            body = item["role"]
            foot = item["repo_id"]
        rows.append(
            '<article class="asset">'
            f'<div class="asset-top"><span class="micro">{_esc(eyebrow)}</span>'
            f'<span class="state" data-state="{_esc(state)}">{_esc(state)}</span></div>'
            f'<h3>{_esc(title)}</h3><p>{_esc(body)}</p>'
            f'<div class="asset-foot mono">{_esc(foot)}</div></article>'
        )
    return "".join(rows)


def _task_cards(tasks: dict[str, str]) -> str:
    return "".join(
        '<article class="task">'
        f'<span class="micro">{index:02d} / BOUNDED TASK</span>'
        f'<h3>{_esc(task.replace("-", " "))}</h3>'
        f'<p>Default model route: <code>{_esc(model)}</code>. A plan must pass source, evidence, context, model-binding, and advisory-gate checks before inference.</p>'
        "</article>"
        for index, (task, model) in enumerate(tasks.items(), start=1)
    )


def _list_cards(items: list[dict[str, Any]], label: str) -> str:
    return "".join(
        '<article class="idea">'
        f'<span class="micro">{_esc(label)}</span>'
        f'<p>{_esc(item.get("name") or item.get("pattern"))}</p>'
        + (
            '<small>No proprietary code or data copied.</small>'
            if "pattern" in item
            else f'<small>{_esc(item.get("state", "CONTRACT_READY"))}</small>'
        )
        + "</article>"
        for item in items
    )


def _vertical_nav(current: str) -> str:
    links = []
    for vertical in CANONICAL_VERTICALS:
        product = VERTICALS[vertical]["product"]
        aria = ' aria-current="page"' if vertical == current else ""
        links.append(
            f'<a href="/intelligence/{_esc(vertical)}"{aria}>{_esc(product)}</a>'
        )
    return "".join(links)


def _plan_example(vertical: str, task: str, floor: float) -> str:
    payload = {
        "task": task,
        "objective": "Review the evidence and produce a bounded decision brief.",
        "context": "Operator-supplied, rights-cleared context.",
        "axes": {"evidence": max(floor, 0.9), "freshness": 0.9, "reversibility": 0.95},
        "evidence_sha256": ["0" * 64, "1" * 64],
    }
    body = json.dumps(payload, indent=2)
    return (
        f"curl -sS -X POST https://szlholdings-vertical-services.hf.space/api/verticals/{vertical}/intelligence/plan \\\n"
        '  -H "Content-Type: application/json" \\\n'
        '  -H "X-SZL-Session: replace-with-32-plus-character-random-token" \\\n'
        f"  --data '{body}'"
    )


def _page(vertical: str) -> str:
    canonical = canonical_vertical(vertical)
    product = VERTICALS[canonical]
    experience = product["experience"]
    intel = intelligence_profile(canonical)
    models = intel["models"]
    bound_models = sum(item["state"] == "BOUND" for item in models)
    tasks = intel["tasks"]
    first_task = next(iter(tasks))
    plan = _plan_example(canonical, first_task, intel["policy"]["lambda_floor"])

    return f"""<!doctype html>
<html lang="en" data-vertical="{_esc(canonical)}" data-motif="{_esc(experience['motif'])}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="dark">
<title>{_esc(product['product'])} Intelligence · SZL Holdings</title>
<meta name="description" content="{_esc(intel['primary_job'])}">
<style>
:root{{color-scheme:dark;--bg:{experience['background']};--panel:{experience['panel']};--ink:#f5f7fb;--muted:#9da8b6;--faint:#687486;--accent:{experience['accent']};--accent2:{experience['accent_secondary']};--line:color-mix(in srgb,var(--accent) 22%,transparent);--good:#6ee7b7;--hold:#f4c873;--bad:#ff7886;--max:1240px}}
*{{box-sizing:border-box;min-inline-size:0}}html{{overflow-x:clip;background:var(--bg);scroll-behavior:smooth}}body{{margin:0;overflow-x:clip;color:var(--ink);font:15px/1.58 Inter,"Segoe UI",system-ui,sans-serif;background:radial-gradient(circle at 82% 5%,color-mix(in srgb,var(--accent) 16%,transparent),transparent 33rem),radial-gradient(circle at 8% 55%,color-mix(in srgb,var(--accent2) 9%,transparent),transparent 28rem),var(--bg)}}
a{{color:inherit}}:where(a,button,summary,[tabindex]):focus-visible{{outline:3px solid var(--accent);outline-offset:3px}}:where(h1,h2,h3){{letter-spacing:-.045em;text-wrap:balance}}:where(p,li){{text-wrap:pretty}}code,.mono,.micro{{font-family:"SFMono-Regular","Cascadia Code",ui-monospace,monospace}}
.skip{{position:fixed;z-index:99;left:12px;top:-80px;padding:10px 14px;background:#fff;color:#000}}.skip:focus{{top:12px}}
.rail{{position:sticky;top:0;z-index:50;border-bottom:1px solid var(--line);background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(20px) saturate(120%)}}
.rail-inner{{width:min(var(--max),calc(100% - 28px));margin:auto;display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:18px;min-height:64px}}.identity{{display:flex;align-items:center;gap:10px;text-decoration:none;min-height:48px}}.mark{{width:28px;height:28px;border:1px solid var(--line);border-radius:9px;background:conic-gradient(from 20deg,var(--accent),transparent 28%,var(--accent2),transparent 68%,var(--accent));box-shadow:0 0 24px color-mix(in srgb,var(--accent) 22%,transparent)}}.identity strong{{font-size:14px}}.family{{display:flex;justify-content:flex-end;gap:5px;overflow-x:auto;scroll-snap-type:x proximity;padding:7px 0;scrollbar-width:thin}}.family a{{flex:0 0 auto;min-height:44px;display:inline-flex;align-items:center;padding:7px 11px;border:1px solid transparent;border-radius:9px;color:var(--muted);font:700 10px/1.2 ui-monospace,monospace;letter-spacing:.08em;text-decoration:none;text-transform:uppercase;scroll-snap-align:start}}.family a:hover,.family a[aria-current="page"]{{border-color:var(--line);color:var(--ink);background:color-mix(in srgb,var(--panel) 82%,transparent)}}
.shell{{position:relative;width:min(var(--max),100%);margin:auto;padding-inline:clamp(18px,5vw,70px)}}.hero{{min-height:min(830px,88vh);display:grid;grid-template-columns:minmax(0,1.14fr) minmax(310px,.86fr);gap:clamp(36px,7vw,100px);align-items:center;padding-block:clamp(72px,10vw,150px);border-bottom:1px solid var(--line)}}.eyebrow,.micro{{color:var(--accent);font-size:10px;font-weight:750;line-height:1.4;letter-spacing:.16em;text-transform:uppercase}}h1{{max-width:10ch;margin:16px 0 0;font-size:clamp(56px,8.8vw,124px);font-weight:520;line-height:.84;letter-spacing:-.075em}}.lede{{max-width:64ch;margin:26px 0 0;color:var(--muted);font-size:clamp(17px,1.7vw,22px)}}.actions{{display:flex;flex-wrap:wrap;gap:10px;margin-top:30px}}.button{{min-height:48px;display:inline-flex;align-items:center;justify-content:center;padding:10px 16px;border:1px solid var(--line);border-radius:10px;background:color-mix(in srgb,var(--panel) 82%,transparent);font:700 11px/1.2 ui-monospace,monospace;letter-spacing:.07em;text-decoration:none;text-transform:uppercase}}.button.primary{{border-color:color-mix(in srgb,var(--accent) 52%,transparent);background:linear-gradient(135deg,color-mix(in srgb,var(--accent) 18%,transparent),color-mix(in srgb,var(--accent2) 8%,transparent))}}
.instrument{{position:relative;min-height:440px;overflow:hidden;border:1px solid var(--line);border-radius:26px;background:linear-gradient(145deg,color-mix(in srgb,var(--accent) 9%,transparent),transparent 44%),color-mix(in srgb,var(--panel) 90%,transparent);box-shadow:0 35px 110px rgb(0 0 0/.38)}}.instrument::before{{position:absolute;inset:0;opacity:.58;content:""}}
[data-motif="threat-shield"] .instrument::before{{inset:13% 25%;clip-path:polygon(50% 0,96% 18%,84% 74%,50% 100%,16% 74%,4% 18%);border:1px solid var(--accent);background:linear-gradient(145deg,color-mix(in srgb,var(--accent) 14%,transparent),transparent)}}
[data-motif="service-lattice"] .instrument::before{{background:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);background-size:42px 42px;mask-image:radial-gradient(circle,#000,transparent 76%)}}
[data-motif="voyage-radar"] .instrument::before{{inset:13%;border:1px solid var(--accent);border-radius:50%;background:repeating-radial-gradient(circle,transparent 0 44px,var(--line) 45px 46px),conic-gradient(from 20deg,color-mix(in srgb,var(--accent) 30%,transparent),transparent 21%)}}
[data-motif="probability-orbit"] .instrument::before{{inset:17%;border:1px solid var(--accent);border-radius:50%;box-shadow:0 0 0 42px transparent,0 0 0 43px var(--line),0 0 0 90px transparent,0 0 0 91px var(--line)}}
[data-motif="parcel-grid"] .instrument::before{{inset:10%;transform:rotate(12deg);background:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);background-size:20% 20%;border:1px solid var(--accent)}}
[data-motif="authority-chain"] .instrument::before{{inset:22% 10%;border:1px solid var(--accent);border-radius:999px;box-shadow:-85px 90px 0 -1px transparent,-85px 90px 0 0 var(--line),85px 90px 0 -1px transparent,85px 90px 0 0 var(--line)}}
.instrument-copy{{position:absolute;inset:auto 18px 18px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:1px solid var(--line);border-radius:14px;background:color-mix(in srgb,var(--bg) 86%,transparent);backdrop-filter:blur(18px)}}.reading{{padding:14px;border-right:1px solid var(--line)}}.reading:last-child{{border-right:0}}.reading small{{display:block;color:var(--faint);font:700 9px/1.2 ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase}}.reading strong{{display:block;margin-top:7px;font:700 13px/1.35 ui-monospace,monospace;overflow-wrap:anywhere}}
.band{{border-bottom:1px solid var(--line);background:color-mix(in srgb,var(--panel) 52%,transparent)}}.stats{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))}}.stat{{padding:22px;border-right:1px solid var(--line)}}.stat:last-child{{border-right:0}}.stat strong{{display:block;font-size:clamp(28px,4vw,46px);letter-spacing:-.05em}}.stat small{{display:block;margin-top:6px;color:var(--faint);font:700 9px/1.3 ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase}}
section{{padding-block:clamp(62px,8vw,112px);border-bottom:1px solid var(--line)}}.section-head{{display:grid;grid-template-columns:minmax(0,1fr) minmax(280px,.72fr);gap:30px;align-items:end;margin-bottom:30px}}.section-head h2{{max-width:13ch;margin:12px 0 0;font-size:clamp(38px,6vw,76px);font-weight:520;line-height:.92}}.section-head p{{margin:0;color:var(--muted);font-size:17px}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}}.asset,.task,.idea{{position:relative;display:flex;flex-direction:column;min-height:190px;padding:20px;border:1px solid var(--line);border-radius:17px;background:linear-gradient(145deg,color-mix(in srgb,var(--accent) 6%,transparent),transparent 45%),color-mix(in srgb,var(--panel) 82%,transparent)}}.asset:hover,.task:hover,.idea:hover{{border-color:color-mix(in srgb,var(--accent) 50%,transparent)}}.asset-top{{display:flex;justify-content:space-between;gap:12px;align-items:start}}.asset h3,.task h3{{margin:15px 0 0;font-size:24px}}.asset p,.task p,.idea p{{color:var(--muted)}}.asset-foot,.idea small{{margin-top:auto;padding-top:14px;color:var(--faint);font-size:10px;overflow-wrap:anywhere}}.state{{border:1px solid currentColor;border-radius:999px;padding:5px 8px;color:var(--hold);font:700 8px/1.15 ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase}}.state[data-state="BOUND"],.state[data-state="LOCAL_CONTRACT_BOUND"]{{color:var(--good)}}.state[data-state="INVALID"],.state[data-state="BLOCKED"]{{color:var(--bad)}}
.split{{display:grid;grid-template-columns:1fr 1fr;gap:13px}}.thesis{{min-height:300px;padding:clamp(24px,4vw,44px);border:1px solid var(--line);border-radius:22px;background:color-mix(in srgb,var(--panel) 78%,transparent)}}.thesis h3{{margin:12px 0;font-size:clamp(30px,4vw,54px);line-height:.96}}.thesis p{{color:var(--muted);font-size:17px}}
pre{{margin:0;max-height:500px;overflow:auto;padding:22px;border:1px solid var(--line);border-radius:18px;background:#020306;color:#d9e3ec;font:12px/1.6 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere}}.boundary{{margin-top:20px;padding:20px;border:1px solid var(--line);border-radius:16px;color:var(--muted);background:color-mix(in srgb,var(--panel) 74%,transparent)}}footer{{display:flex;justify-content:space-between;gap:18px;flex-wrap:wrap;padding-block:30px;color:var(--faint);font:700 10px/1.4 ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase}}
@media(max-width:920px){{.hero,.section-head{{grid-template-columns:1fr}}.hero{{min-height:0}}.instrument{{min-height:360px}}.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.stats{{grid-template-columns:repeat(2,minmax(0,1fr))}}.stat:nth-child(2){{border-right:0}}.stat:nth-child(-n+2){{border-bottom:1px solid var(--line)}}}}
@media(max-width:620px){{.rail-inner{{grid-template-columns:1fr;gap:0}}.family{{justify-content:flex-start}}h1{{font-size:clamp(54px,18vw,82px)}}.grid,.split{{grid-template-columns:1fr}}.instrument-copy{{grid-template-columns:1fr}}.reading{{border-right:0;border-bottom:1px solid var(--line)}}.reading:last-child{{border-bottom:0}}}}
@media(pointer:coarse){{a,button{{min-height:48px}}}}@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{animation:none!important;transition:none!important;scroll-behavior:auto!important}}}}@media(forced-colors:active){{.instrument::before{{display:none}}}}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to intelligence room</a>
<header class="rail"><div class="rail-inner"><a class="identity" href="/"><span class="mark" aria-hidden="true"></span><strong>SZL / {_esc(product['product'])}</strong></a><nav class="family" aria-label="Vertical intelligence rooms">{_vertical_nav(canonical)}</nav></div></header>
<main id="main">
<div class="shell"><section class="hero"><div><p class="eyebrow">{_esc(product['domain'])} · GOVERNED INTELLIGENCE</p><h1>{_esc(experience['title'])}</h1><p class="lede">{_esc(intel['primary_job'])}</p><div class="actions"><a class="button primary" href="/experience/{_esc(canonical)}">Open command surface</a><a class="button" href="/api/verticals/{_esc(canonical)}/intelligence">Inspect contract</a><a class="button" href="/api/verticals/{_esc(canonical)}/second-brain">Second Brain API</a></div></div><aside class="instrument" aria-label="Vertical intelligence instrument"><div class="instrument-copy"><div class="reading"><small>Model bindings</small><strong>{bound_models}/{len(models)} BOUND</strong></div><div class="reading"><small>Kernel contracts</small><strong>{len(intel['kernels'])} ACTIVE</strong></div><div class="reading"><small>Authority</small><strong>HUMAN BIND</strong></div></div></aside></section></div>
<div class="band"><div class="shell stats"><div class="stat"><strong>{len(tasks)}</strong><small>bounded model tasks</small></div><div class="stat"><strong>{len(models)}</strong><small>approved model assets</small></div><div class="stat"><strong>{len(intel['kernels'])}</strong><small>kernel contracts</small></div><div class="stat"><strong>{intel['policy']['lambda_floor']:.2f}</strong><small>advisory inference floor</small></div></div></div>
<div class="shell"><section><div class="section-head"><div><p class="eyebrow">PRODUCT WEDGE</p><h2>The job others leave fragmented.</h2></div><p>{_esc(intel['unserved_job'])}</p></div><div class="split"><article class="thesis"><span class="micro">PRIMARY JOB</span><h3>{_esc(intel['primary_job'])}</h3><p>One bounded workflow, one source identity, one session scope, and one review receipt.</p></article><article class="thesis"><span class="micro">SIGNATURE VIEW</span><h3>{_esc(experience['signature_view'])}</h3><p>{_esc(experience['benchmark'])}. This view combines product clarity with evidence-native operating controls.</p></article></div></section>
<section><div class="section-head"><div><p class="eyebrow">MODEL ROUTING</p><h2>Use the right model, not every model.</h2></div><p>Models remain unavailable until an operator binds a fixed HTTPS endpoint, allowlisted host, credential, protocol, and exact declared revision. The public interface cannot supply an endpoint.</p></div><div class="grid">{_cards(models, kind='model')}</div></section>
<section><div class="section-head"><div><p class="eyebrow">KERNEL FABRIC</p><h2>Evidence before language.</h2></div><p>The model never owns authority. Invariants, context limits, advisory Lambda, blocking rules, receipt attention, and deterministic hashes constrain the request and preserve reviewability.</p></div><div class="grid">{_cards(intel['kernels'], kind='kernel')}</div></section>
<section><div class="section-head"><div><p class="eyebrow">TASK PLANE</p><h2>Four jobs. Explicit routes.</h2></div><p>Each task maps to a reviewed default model. A preferred model is accepted only when it belongs to the vertical's approved set.</p></div><div class="grid">{_task_cards(tasks)}</div></section>
<section><div class="section-head"><div><p class="eyebrow">FRONTIER DELTA</p><h2>Build what is still missing.</h2></div><p>These are contract-ready product directions, not unsupported claims of production capability.</p></div><div class="grid">{_list_cards(intel['novel_capabilities'], 'CONTRACT-READY EDGE')}</div></section>
<section><div class="section-head"><div><p class="eyebrow">PATTERN SYNTHESIS</p><h2>Learn broadly. Copy nothing proprietary.</h2></div><p>Public product patterns inform interaction design and workflow shape. Proprietary source, private data, logos, and trade dress are excluded.</p></div><div class="grid">{_list_cards(intel['reference_patterns'], 'PUBLIC PATTERN')}</div></section>
<section><div class="section-head"><div><p class="eyebrow">PYTHON CONTRACT</p><h2>Plan before inference.</h2></div><p>The planning endpoint can run without provider mutation. It returns ABSTAIN until source, evidence, model binding, context, and advisory-score gates are satisfied.</p></div><pre aria-label="Example plan request">{_esc(plan)}</pre><div class="boundary"><strong>Operational boundary.</strong> Public or properly licensed data only. Raw context is not returned or persisted by the intelligence fabric. Finance cannot trade or hold custody. Counsel does not provide or file legal advice. Sentra cannot execute remediation. Killinchu public effects remain simulated. Terra excludes person-level prospecting. Every model output requires human review.</div></section>
<footer><span>{_esc(product['product'])} · {_esc(canonical)}</span><span>CONTROL BEFORE ACTION · EVIDENCE AFTER</span><span><a href="https://a-11-oy.com">A11OY</a> · <a href="https://a11oy.net">PROOF</a></span></footer></div>
</main>
</body>
</html>"""


@showcase.get("/intelligence/{vertical}", response_class=HTMLResponse)
def vertical_intelligence_room(vertical: str) -> HTMLResponse:
    return HTMLResponse(_page(vertical))


__all__ = ["showcase", "vertical_intelligence_room"]
