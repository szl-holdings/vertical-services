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
from .presentation import NATIVE_ICON_HTML, NATIVE_INTERFACE_CSS, NATIVE_TOKENS_CSS
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


def _public_market_brief(vertical: str) -> str:
    if vertical != "finance":
        return ""
    return '''<section aria-labelledby="public-brief-title"><div class="section-head"><div>
<p class="eyebrow">LIVE PUBLIC MARKET OBSERVATION</p><h2 id="public-brief-title">Two sources. One checked observation.</h2></div>
<p>Fetch a Bitcoin spot reference and official Treasury rate observations, then ask Khipu to restate the spot reference. Only a completed exact match is displayed. This public demo is best effort and the underlying observation requires human review.</p></div>
<div class="boundary"><label><input type="checkbox" id="public-brief-consent"> I agree to send these public market numbers to the Khipu demo. No private context is accepted.</label>
<p>The advisory score uses a disclosed 0.90 preset; it is not a measurement of investment quality. No trading or custody is enabled.</p>
<button type="button" class="button primary" id="public-brief-run">Restate public market observation</button>
<p id="public-brief-status" role="status" aria-live="polite">Ready when you choose to run.</p>
<pre id="public-brief-output" hidden></pre></div></section>
<script>
(() => {
  const button = document.getElementById('public-brief-run');
  const status = document.getElementById('public-brief-status');
  const output = document.getElementById('public-brief-output');
  button.addEventListener('click', async () => {
    if (!document.getElementById('public-brief-consent').checked) {
      status.textContent = 'Confirm the public demo consent before running.'; return;
    }
    button.disabled = true; output.hidden = true;
    const session = Array.from(crypto.getRandomValues(new Uint8Array(32)), b => b.toString(16).padStart(2, '0')).join('');
    const post = async (path, body) => {
      const response = await fetch(path, {method: 'POST', headers: {
        'Content-Type': 'application/json', 'X-SZL-Session': session}, body: JSON.stringify(body), signal: AbortSignal.timeout(90000)});
      const value = await response.json();
      if (!response.ok) throw new Error('Request unavailable (HTTP ' + response.status + '). Review the contract and try again later.');
      return value;
    };
    try {
      status.textContent = 'Fetching public market observations…';
      const spot = await post('/api/verticals/finance/connectors/coinbase-spot/fetch', {parameters: {base: 'BTC', currency: 'USD'}, force_refresh: true});
      const rates = await post('/api/verticals/finance/connectors/treasury-average-rates/fetch', {parameters: {limit: 5}, force_refresh: true});
      const request = {task: 'risk-summary', objective: 'Review the public market observations.', context: '',
        axes: {evidence: 0.90, freshness: 0.90, reversibility: 0.90},
        evidence_sha256: [spot.receipt.payload_sha256, rates.receipt.payload_sha256],
        preferred_model: 'khipu-gguf-public', public_demo_consent: true, max_new_tokens: 32, temperature: 0};
      status.textContent = 'Checking evidence and preparing the brief…';
      const {max_new_tokens, temperature, ...planRequest} = request;
      const plan = await post('/api/verticals/finance/intelligence/plan', planRequest);
      if (plan.decision !== 'READY_FOR_INFERENCE') throw new Error('Brief withheld: ' + plan.blockers.join(', '));
      const result = await post('/api/verticals/finance/intelligence/invoke', request);
      if (result.provider_verification.output_complete !== true || result.provider_verification.observation_match_verified !== true) {
        throw new Error('Observation withheld: the model did not return a completed exact match.');
      }
      output.textContent = result.output; output.hidden = false;
      status.textContent = 'Completed observation received. Its text matches the locally compiled public value. The source and unsigned reply require human review.';
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });
})();
</script>'''


CATALOG_SEARCH_JS = r"""
(() => {
  const form = document.getElementById('catalog-search-form');
  const input = document.getElementById('catalog-query');
  const results = document.getElementById('catalog-results');
  const status = document.getElementById('catalog-status');
  if (!form || !input || !results || !status) return;
  let activeRequest = null;
  let version = 0;
  const cancel = () => {
    version += 1;
    if (activeRequest) activeRequest.abort();
  };
  input.addEventListener('input', () => {
    cancel();
    results.replaceChildren();
    status.textContent = 'Choose Search to inspect matching catalog objects.';
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    cancel();
    const query = input.value.trim();
    results.replaceChildren();
    if (query.length < 2 || query.length > 128) {
      status.textContent = 'Enter between 2 and 128 characters.';
      return;
    }
    const currentVersion = version;
    const controller = new AbortController();
    activeRequest = controller;
    const timeout = setTimeout(() => controller.abort(), 10000);
    status.textContent = 'Searching catalog metadata…';
    try {
      const response = await fetch('/api/verticals/search?q=' + encodeURIComponent(query) + '&limit=12', {
        headers: {'Accept': 'application/json'}, credentials: 'same-origin',
        cache: 'no-store', signal: controller.signal,
      });
      if (!response.ok) throw new Error('Catalog unavailable');
      const body = await response.json();
      if (currentVersion !== version) return;
      if (body.schema !== 'szl.operational-search/v1' || body.live_binding !== 'CATALOG_METADATA' || !Array.isArray(body.items)) {
        throw new Error('Catalog contract unavailable');
      }
      const fragment = document.createDocumentFragment();
      for (const item of body.items.slice(0, 12)) {
        if (!item || typeof item !== 'object') continue;
        const row = document.createElement('li');
        row.className = 'asset';
        const title = document.createElement('strong');
        title.textContent = String(item.name || item.canonical_id || item.id || 'Catalog object');
        const detail = document.createElement('p');
        detail.textContent = [item.kind, item.provider, item.state].filter(Boolean).join(' · ');
        row.append(title, detail);
        if (typeof item.href === 'string' && item.href.startsWith('/api/')) {
          const source = document.createElement('a');
          source.className = 'catalog-source';
          source.href = item.href;
          source.textContent = 'Inspect ' + String(item.canonical_id || item.id || 'catalog contract');
          row.append(source);
        }
        fragment.append(row);
      }
      const count = fragment.childElementCount;
      results.replaceChildren(fragment);
      status.textContent = count
        ? count + ' catalog result' + (count === 1 ? '' : 's') + ' · configuration metadata'
        : 'No catalog matches. Try a vertical, connector, model, or kernel.';
    } catch (_error) {
      if (currentVersion !== version) return;
      results.replaceChildren();
      status.textContent = 'Catalog search is unavailable. Try again or inspect the catalog contract.';
    } finally {
      clearTimeout(timeout);
      if (activeRequest === controller) activeRequest = null;
    }
  });
})();
"""


def _catalog_search() -> str:
    return '''<section aria-labelledby="catalog-title" data-catalog-search>
<div class="section-head"><div><p class="eyebrow">CATALOG METADATA</p><h2 id="catalog-title">Find the configured object.</h2></div>
<p>Search configured verticals, connectors, models, and kernels, then inspect their source contracts. These results describe configuration. Lyte provides session telemetry and can observe the public dataset inventory.</p></div>
<form id="catalog-search-form" class="catalog-search" role="search" action="/api/verticals/search" method="get">
<label for="catalog-query">Search the configured catalog</label>
<div class="catalog-controls"><input id="catalog-query" name="q" type="search" minlength="2" maxlength="128" required placeholder="vertical, connector, model, kernel…" autocomplete="off"><button class="button primary" type="submit">Search</button></div>
<input type="hidden" name="limit" value="12"></form>
<p id="catalog-status" role="status" aria-live="polite">Choose Search to inspect matching catalog objects.</p>
<ul id="catalog-results" class="grid catalog-results" aria-label="Catalog results"></ul>
<p><a href="/api/verticals">Inspect the catalog contract</a></p>
</section><script>''' + CATALOG_SEARCH_JS + '</script>'


DATASET_INVENTORY_JS = r"""
(() => {
  const token = document.getElementById('dataset-session');
  const newSession = document.getElementById('dataset-new-session');
  const observe = document.getElementById('dataset-observe');
  const brain = document.getElementById('dataset-brain');
  const review = document.getElementById('dataset-review');
  const query = document.getElementById('dataset-query');
  const status = document.getElementById('dataset-status');
  const summary = document.getElementById('dataset-summary');
  const results = document.getElementById('dataset-results');
  const proof = document.getElementById('dataset-proof');
  if (!token || !newSession || !observe || !brain || !review || !query || !status || !summary || !results || !proof) return;
  let snapshot = null;
  let receipt = null;
  let version = 0;
  let activeRequest = null;
  const buttons = [observe, brain, review];
  const busy = (value) => buttons.forEach(button => { button.disabled = value || (button === review && !receipt); });
  const reset = () => {
    version += 1;
    if (activeRequest) activeRequest.abort();
    snapshot = null; receipt = null;
    results.replaceChildren(); summary.textContent = ''; proof.textContent = '';
    busy(false);
    status.textContent = 'Session changed. Observe the public inventory or open its Second Brain memory.';
  };
  token.addEventListener('input', reset);
  newSession.addEventListener('click', () => {
    token.value = Array.from(crypto.getRandomValues(new Uint8Array(32)), byte => byte.toString(16).padStart(2, '0')).join('');
    reset();
  });
  const render = () => {
    results.replaceChildren();
    if (!snapshot) return;
    const needle = query.value.trim().toLocaleLowerCase();
    const matches = snapshot.items.filter(item => [item.id, item.revision, ...(item.license_tags || [])]
      .some(value => String(value || '').toLocaleLowerCase().includes(needle)));
    const shown = matches.slice(0, 50);
    const fragment = document.createDocumentFragment();
    for (const item of shown) {
      const row = document.createElement('li'); row.className = 'asset';
      const title = document.createElement('strong'); title.textContent = item.id;
      const revision = document.createElement('p'); revision.className = 'mono';
      revision.textContent = 'Reported revision: ' + (item.revision || 'UNAVAILABLE');
      const rights = document.createElement('p');
      rights.textContent = 'License tags: ' + ((item.license_tags || []).join(', ') || 'UNAVAILABLE') + ' · rights require review';
      row.append(title, revision, rights);
      if (/^SZLHOLDINGS\/[A-Za-z0-9._-]+$/.test(item.id)) {
        const source = document.createElement('a'); source.className = 'catalog-source';
        source.href = 'https://huggingface.co/datasets/' + item.id;
        source.textContent = 'Open dataset source'; row.append(source);
      }
      fragment.append(row);
    }
    results.replaceChildren(fragment);
    summary.textContent = snapshot.items.length + ' dataset records in one public catalog observation. ' +
      matches.length + ' search matches; showing ' + shown.length + '. Full and private estate coverage is unknown. Training is not admitted.';
  };
  query.addEventListener('input', render);
  const admit = (value, sourceReceipt) => {
    if (!value || value.schema !== 'szl.public-dataset-inventory/v1' || value.owner !== 'SZLHOLDINGS' ||
        !Array.isArray(value.items) || value.items.length > 500 || !sourceReceipt ||
        !/^[a-f0-9]{64}$/.test(sourceReceipt.payload_sha256 || '')) throw new Error('Inventory contract unavailable');
    for (const item of value.items) {
      if (!item || typeof item.id !== 'string' || !/^SZLHOLDINGS\/[A-Za-z0-9._-]+$/.test(item.id) ||
          (item.license_tags !== null && (!Array.isArray(item.license_tags) || item.license_tags.some(tag => typeof tag !== 'string')))) {
        throw new Error('Inventory contract unavailable');
      }
    }
    snapshot = value; receipt = sourceReceipt;
    proof.textContent = 'Source payload digest: ' + receipt.payload_sha256 + '\n' +
      'Receipt: ' + (receipt.receipt_id || 'UNAVAILABLE') + '\n' +
      'One source observation; dataset records are not independent sources. Revision and license metadata do not verify contents or training rights.';
    render();
  };
  const run = async (kind) => {
    const session = token.value.trim();
    if (!/^[A-Za-z0-9._~-]{32,128}$/.test(session)) {
      status.textContent = 'Create a session or enter your existing 32–128 character session token.'; return;
    }
    const currentVersion = ++version;
    if (activeRequest) activeRequest.abort();
    const controller = new AbortController(); activeRequest = controller;
    const timeout = setTimeout(() => controller.abort(), 30000);
    busy(true);
    const request = async (path, body) => {
      const response = await fetch(path, {method: body === undefined ? 'GET' : 'POST',
        headers: {'Accept': 'application/json', 'Content-Type': 'application/json', 'X-SZL-Session': session},
        credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
        ...(body === undefined ? {} : {body: JSON.stringify(body)})});
      if (!response.ok) throw new Error('Request unavailable');
      return response.json();
    };
    try {
      if (kind === 'observe') {
        status.textContent = 'Observing the public dataset catalog and storing its metadata receipt…';
        const value = await request('/api/verticals/lyte/connectors/hf-datasets/fetch', {parameters: {}, force_refresh: true});
        if (currentVersion !== version) return;
        admit(value.observation, value.receipt);
        status.textContent = 'Public catalog metadata observed. Open Second Brain to verify the same stored source observation.';
      } else if (kind === 'brain') {
        status.textContent = 'Reading this session’s Second Brain memory…';
        const value = await request('/api/verticals/lyte/second-brain?limit=100');
        if (currentVersion !== version) return;
        const records = value.memory && Array.isArray(value.memory.observations) ? value.memory.observations : [];
        const record = records.find(item => item.connector_id === 'hf-datasets' && item.withdrawn !== true &&
          (!receipt || item.payload_sha256 === receipt.payload_sha256));
        if (!record) throw new Error('Stored inventory unavailable');
        admit(record.summary, record);
        status.textContent = 'Second Brain contains this source observation in the same session. Stored history may be stale; Hatun checks freshness during review.';
      } else if (kind === 'review' && receipt) {
        status.textContent = 'Requesting a bounded Hatun review of this metadata observation…';
        const value = await request('/api/verticals/lyte/hatun/evaluate', {
          intent: 'Inspect public dataset inventory metadata and remaining evidence gaps.',
          requested_action: 'review-dataset-metadata',
          axes: {source_presence: 1, content_quality: 0, training_rights: 0},
          evidence_sha256: [receipt.payload_sha256],
        });
        if (currentVersion !== version) return;
        if (!['REVIEW', 'ABSTAIN'].includes(value.decision) || value.can_authorize !== false || value.can_execute !== false) {
          throw new Error('Review contract unavailable');
        }
        status.textContent = 'Hatun: ' + value.decision + '. ' +
          (Array.isArray(value.blockers) ? value.blockers.join(', ') : '') + '. No action or training authorized.';
        proof.textContent += '\nHatun review digest: ' + (value.receipt && value.receipt.basis_sha256 || 'UNAVAILABLE');
      }
    } catch (_error) {
      if (currentVersion !== version) return;
      status.textContent = 'Inventory operation unavailable. No new successful observation or review is claimed. Check the session and try again.';
    } finally {
      clearTimeout(timeout);
      if (currentVersion === version) busy(false);
      if (activeRequest === controller) activeRequest = null;
    }
  };
  observe.addEventListener('click', () => run('observe'));
  brain.addEventListener('click', () => run('brain'));
  review.addEventListener('click', () => run('review'));
  busy(false);
})();
"""


def _dataset_inventory(vertical: str) -> str:
    if vertical != "lyte":
        return ""
    return '''<section aria-labelledby="dataset-title" data-dataset-inventory>
<div class="section-head"><div><p class="eyebrow">PUBLIC DATASET INVENTORY</p><h2 id="dataset-title">Observe. Remember. Review.</h2></div>
<p>Observe SZLHOLDINGS public dataset metadata from Hugging Face, retain the source receipt in this session’s Second Brain, and request Hatun review. Living Anatomy describes the connector. Dataset contents and training are separate steps.</p></div>
<div class="boundary"><label for="dataset-session">Session token</label>
<div class="catalog-controls"><input id="dataset-session" type="password" minlength="32" maxlength="128" autocomplete="off" spellcheck="false" aria-describedby="dataset-session-note"><button id="dataset-new-session" type="button" class="button">New page session</button></div>
<p id="dataset-session-note">Use an existing session token to reopen memory, or create a token held only in this page. The token is sent only to this application and is not saved in browser storage.</p>
<div class="actions"><button id="dataset-observe" type="button" class="button primary">Observe public inventory</button><button id="dataset-brain" type="button" class="button">Open Second Brain</button><button id="dataset-review" type="button" class="button" disabled>Request Hatun review</button><a class="button" href="/api/verticals/lyte/anatomy">Living Anatomy contract</a></div>
<p id="dataset-status" role="status" aria-live="polite">No inventory observed in this page.</p>
<p>Unknown content quality and training rights enter the Hatun review as zero advisory axes. Metadata alone cannot authorize training.</p></div>
<div class="catalog-search"><label for="dataset-query">Search this session’s inventory</label><div class="catalog-controls"><input id="dataset-query" type="search" maxlength="128" placeholder="dataset, revision, license tag…" autocomplete="off"></div></div>
<p id="dataset-summary" role="status" aria-live="polite"></p>
<ul id="dataset-results" class="grid catalog-results" aria-label="Observed dataset metadata"></ul>
<details><summary>Inspect observation and review receipts</summary><pre id="dataset-proof"></pre></details>
</section><script>''' + DATASET_INVENTORY_JS + '</script>'


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
<html lang="en" data-native-view="intelligence" data-vertical="{_esc(canonical)}" data-motif="{_esc(experience['motif'])}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="dark">
<title>{_esc(product['product'])} Intelligence · SZL Holdings</title>
<meta name="description" content="{_esc(intel['primary_job'])}">
<style>
{NATIVE_TOKENS_CSS}
:root{{color-scheme:dark;--bg:{experience['background']};--panel:{experience['panel']};--ink:#f5f7fb;--muted:#9da8b6;--faint:#687486;--accent:{experience['accent']};--accent2:{experience['accent_secondary']};--line:color-mix(in srgb,var(--accent) 22%,transparent);--good:#6ee7b7;--hold:#f4c873;--bad:#ff7886;--max:1240px}}
*{{box-sizing:border-box;min-inline-size:0}}html{{overflow-x:clip;background:var(--bg);scroll-behavior:smooth}}body{{margin:0;overflow-x:clip;color:var(--ink);font:15px/1.58 Inter,"Segoe UI",system-ui,sans-serif;background:radial-gradient(circle at 82% 5%,color-mix(in srgb,var(--accent) 16%,transparent),transparent 33rem),radial-gradient(circle at 8% 55%,color-mix(in srgb,var(--accent2) 9%,transparent),transparent 28rem),var(--bg)}}
a{{color:inherit}}:where(a,button,summary,[tabindex]):focus-visible{{outline:3px solid var(--accent);outline-offset:3px}}:where(h1,h2,h3){{letter-spacing:-.045em;text-wrap:balance}}:where(p,li){{text-wrap:pretty}}code,.mono,.micro{{font-family:"SFMono-Regular","Cascadia Code",ui-monospace,monospace}}
.skip{{position:fixed;z-index:99;left:12px;top:-80px;padding:10px 14px;background:#fff;color:#000}}.skip:focus{{top:12px}}
.rail{{position:sticky;top:0;z-index:50;border-bottom:1px solid var(--line);background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(20px) saturate(120%)}}
.rail-inner{{width:min(var(--max),calc(100% - 28px));margin:auto;display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:18px;min-height:64px}}.identity{{display:flex;align-items:center;gap:10px;text-decoration:none;min-height:48px}}.identity strong{{font-size:14px}}.family{{display:flex;justify-content:flex-end;gap:5px;overflow-x:auto;scroll-snap-type:x proximity;padding:7px 0;scrollbar-width:thin}}.family a{{flex:0 0 auto;min-height:44px;display:inline-flex;align-items:center;padding:7px 11px;border:1px solid transparent;border-radius:9px;color:var(--muted);font:700 10px/1.2 ui-monospace,monospace;letter-spacing:.08em;text-decoration:none;text-transform:uppercase;scroll-snap-align:start}}.family a:hover,.family a[aria-current="page"]{{border-color:var(--line);color:var(--ink);background:color-mix(in srgb,var(--panel) 82%,transparent)}}
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
.catalog-search label{{display:block;margin-bottom:10px;font-weight:650}}.catalog-controls{{display:flex;flex-wrap:wrap;gap:12px}}.catalog-controls input{{flex:1 1 260px;min-height:48px;padding:12px 15px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink);font:inherit}}.catalog-controls input:focus-visible{{outline:3px solid var(--accent);outline-offset:3px}}.catalog-controls button,[data-dataset-inventory] button{{color:var(--ink);cursor:pointer}}.catalog-results{{padding:0;list-style:none}}.catalog-results .asset{{min-height:150px}}.catalog-source{{display:flex;align-items:center;min-height:44px;margin-top:auto;overflow-wrap:anywhere}}
@media(max-width:920px){{.hero,.section-head{{grid-template-columns:1fr}}.hero{{min-height:0}}.instrument{{min-height:360px}}.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.stats{{grid-template-columns:repeat(2,minmax(0,1fr))}}.stat:nth-child(2){{border-right:0}}.stat:nth-child(-n+2){{border-bottom:1px solid var(--line)}}}}
@media(max-width:620px){{.rail-inner{{grid-template-columns:1fr;gap:0}}.family{{justify-content:flex-start}}h1{{font-size:clamp(54px,18vw,82px)}}.grid,.split{{grid-template-columns:1fr}}.instrument-copy{{grid-template-columns:1fr}}.reading{{border-right:0;border-bottom:1px solid var(--line)}}.reading:last-child{{border-bottom:0}}}}
/* Size against the available content width, including browser and CSS zoom. */
.shell{{container-type:inline-size}}:where(h1,h2,h3,p,li,span,small,strong,a){{overflow-wrap:anywhere}}
h1{{font-size:clamp(40px,10cqi,112px);line-height:.96;max-width:12ch}}
.rail{{position:relative}}.rail-inner{{display:flex;flex-wrap:wrap;gap:0 18px}}.identity{{flex:1 1 160px}}.family{{flex:1 1 520px;justify-content:flex-start}}
@container(max-width:54rem){{.hero,.section-head{{grid-template-columns:minmax(0,1fr)}}.hero{{min-height:0}}.grid,.split,.stats{{grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr))}}}}
@container(max-width:30rem){{.instrument-copy{{grid-template-columns:minmax(0,1fr)}}.reading{{border-right:0;border-bottom:1px solid var(--line)}}.reading:last-child{{border-bottom:0}}}}
@media(pointer:coarse){{a,button{{min-height:48px}}}}@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{animation:none!important;transition:none!important;scroll-behavior:auto!important}}}}@media(forced-colors:active){{.instrument::before{{display:none}}}}
{NATIVE_INTERFACE_CSS}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to intelligence room</a>
<header class="rail"><div class="rail-inner"><a class="identity" href="/">{NATIVE_ICON_HTML}<strong>SZL / {_esc(product['product'])}</strong></a><nav class="family" aria-label="Vertical intelligence rooms">{_vertical_nav(canonical)}</nav></div></header>
<main id="main">
<div class="shell"><section class="hero"><div><p class="eyebrow">{_esc(product['domain'])} · GOVERNED INTELLIGENCE</p><h1>{_esc(experience['title'])}</h1><p class="lede">{_esc(intel['primary_job'])}</p><div class="actions"><a class="button primary" href="/experience/{_esc(canonical)}">Open command surface</a><a class="button" href="/api/verticals/{_esc(canonical)}/intelligence">Inspect contract</a><a class="button" href="/api/verticals/{_esc(canonical)}/second-brain">Second Brain API</a></div></div><aside class="instrument" aria-label="Vertical intelligence instrument"><div class="instrument-copy"><div class="reading"><small>Model bindings</small><strong>{bound_models}/{len(models)} BOUND</strong></div><div class="reading"><small>Kernel contracts</small><strong>{len(intel['kernels'])} ACTIVE</strong></div><div class="reading"><small>Authority</small><strong>HUMAN BIND</strong></div></div></aside></section></div>
<div class="band"><div class="shell stats"><div class="stat"><strong>{len(tasks)}</strong><small>bounded model tasks</small></div><div class="stat"><strong>{len(models)}</strong><small>approved model assets</small></div><div class="stat"><strong>{len(intel['kernels'])}</strong><small>kernel contracts</small></div><div class="stat"><strong>{intel['policy']['lambda_floor']:.2f}</strong><small>advisory inference floor</small></div></div></div>
<div class="shell"><section><div class="section-head"><div><p class="eyebrow">PRODUCT WEDGE</p><h2>The job others leave fragmented.</h2></div><p>{_esc(intel['unserved_job'])}</p></div><div class="split"><article class="thesis"><span class="micro">PRIMARY JOB</span><h3>{_esc(intel['primary_job'])}</h3><p>One bounded workflow, one source identity, one session scope, and one review receipt.</p></article><article class="thesis"><span class="micro">SIGNATURE VIEW</span><h3>{_esc(experience['signature_view'])}</h3><p>{_esc(experience['benchmark'])}. This view combines product clarity with evidence-native operating controls.</p></article></div></section>
{_catalog_search()}
{_dataset_inventory(canonical)}
<section><div class="section-head"><div><p class="eyebrow">MODEL ROUTING</p><h2>Use the right model, not every model.</h2></div><p>Operator model routes require a fixed endpoint, credential and exact revision. The separate public Khipu GGUF route accepts only a consented numeric market brief. The public interface cannot supply an endpoint.</p></div><div class="grid">{_cards(models, kind='model')}</div></section>
{_public_market_brief(canonical)}
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
