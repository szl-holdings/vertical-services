"""The deployed catalog and inventory UI use real, scoped runtime routes."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
sys.path.insert(0, str(DEPLOY))
_STATE = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "catalog-ui-test-key")
os.environ.setdefault("SZL_SOURCE_REVISION", "a" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_STATE.name) / "state.sqlite3"))

from fastapi.testclient import TestClient  # noqa: E402
import app as vertical  # noqa: E402
from frontier_fabric.showcase import render_vertical_showcase  # noqa: E402
from szl_verticals.showcase import CATALOG_SEARCH_JS, DATASET_INVENTORY_JS  # noqa: E402

CLIENT = TestClient(vertical.app)


def test_catalog_search_is_mounted_with_the_deployed_ui_and_honest_scope():
    for name in ("sentra", "lyte", "killinchu", "finance", "terra", "counsel"):
        page = CLIENT.get(f"/intelligence/{name}")
        assert page.status_code == 200
        assert 'id="catalog-search-form"' in page.text
        assert 'action="/api/verticals/search"' in page.text
        assert ('data-dataset-inventory' in page.text.split('</style>', 1)[1]) == (name == "lyte")
    result = CLIENT.get("/api/verticals/search", params={"q": "dataset"})
    assert result.status_code == 200
    body = result.json()
    assert body["live_binding"] == "CATALOG_METADATA"
    assert body["receipt_backed"] is False
    assert body["telemetry_included"] is False
    assert body["dataset_inventory_requires_session"] is True
    assert body["dataset_inventory_state"] == "PUBLIC_INVENTORY_CONNECTOR_AVAILABLE"
    assert any(item["canonical_id"] == "connector:hf-datasets" for item in body["items"])
    assert not any(item["kind"] == "dataset" for item in body["items"])
    terra = CLIENT.get("/api/verticals/search", params={"q": "terra"}).json()
    assert next(item for item in terra["items"] if item["kind"] == "vertical")["telemetry_route"] is None


def test_standalone_frontier_does_not_advertise_an_absent_search_route():
    document = render_vertical_showcase("lyte")
    assert "/api/verticals/search" not in document
    assert "standalone concept has no operational search" in document
    assert "receipt-backed search" not in document


_DOM = r"""
const assert = require('node:assert/strict');
globalThis.crypto = require('node:crypto').webcrypto;
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.events = {}; this.value = ''; this.textContent = ''; }
  addEventListener(name, handler) { this.events[name] = handler; }
  append(...nodes) { for (const node of nodes) this.children.push(...(node.tag === 'fragment' ? node.children : [node])); }
  replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
  get childElementCount() { return this.children.length; }
}
const elements = {};
const get = id => elements[id] || (elements[id] = new Element(id));
globalThis.document = {getElementById: get, createElement: tag => new Element(tag), createDocumentFragment: () => new Element('fragment')};
const calls = [];
const response = body => ({ok: true, json: async () => body});
"""


def _run_js(script: str, scenario: str) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable for the browser behavior contract")
    completed = subprocess.run(
        [node, "--input-type=commonjs"],
        input=_DOM + script + "\n(async () => {\n" + scenario + "\n})().catch(error => { console.error(error); process.exitCode = 1; });",
        capture_output=True, text=True, timeout=15, check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_catalog_ui_renders_text_and_drops_unsafe_source_links():
    _run_js(CATALOG_SEARCH_JS, r"""
globalThis.fetch = async (path, options) => {
  calls.push({path, options});
  return response({schema: 'szl.operational-search/v1', live_binding: 'CATALOG_METADATA', items: [
    {name: '<img src=x onerror=alert(1)>', kind: 'model', state: 'CONFIGURED', href: 'javascript:alert(1)'},
    {name: 'Lyte', kind: 'vertical', state: 'CONFIGURED', canonical_id: 'vertical:lyte', href: '/api/verticals/lyte/anatomy'}
  ]});
};
get('catalog-query').value = 'lyte & other';
await get('catalog-search-form').events.submit({preventDefault() {}});
assert.equal(calls[0].path, '/api/verticals/search?q=lyte%20%26%20other&limit=12');
assert.equal(calls[0].options.credentials, 'same-origin');
assert.equal(get('catalog-results').children.length, 2);
assert.equal(get('catalog-results').children[0].children[0].textContent, '<img src=x onerror=alert(1)>');
assert.equal(get('catalog-results').children[0].children.length, 2);
assert.equal(get('catalog-results').children[1].children[2].href, '/api/verticals/lyte/anatomy');
assert.match(get('catalog-status').textContent, /configuration metadata/);
""")


def test_inventory_reuses_one_session_and_one_source_digest_through_brain_and_hatun():
    _run_js(DATASET_INVENTORY_JS, r"""
const inventory = {schema: 'szl.public-dataset-inventory/v1', owner: 'SZLHOLDINGS', items: [
  {id: 'SZLHOLDINGS/example', revision: 'c'.repeat(40), license_tags: ['apache-2.0']}
]};
const receipt = {payload_sha256: 'a'.repeat(64), receipt_id: 'b'.repeat(64), state: 'OBSERVED'};
globalThis.fetch = async (path, options) => {
  calls.push({path, options});
  if (path.endsWith('/fetch')) return response({observation: inventory, receipt});
  if (path.includes('/second-brain')) return response({memory: {observations: [
    {connector_id: 'hf-datasets', summary: inventory, withdrawn: false, ...receipt}
  ]}});
  return response({decision: 'ABSTAIN', can_authorize: false, can_execute: false,
    blockers: ['LAMBDA_BELOW_REVIEW_FLOOR'], receipt: {basis_sha256: 'd'.repeat(64)}});
};
await get('dataset-new-session').events.click();
const session = get('dataset-session').value;
assert.match(session, /^[a-f0-9]{64}$/);
await get('dataset-observe').events.click();
assert.equal(get('dataset-results').children.length, 1);
assert.match(get('dataset-summary').textContent, /one public catalog observation/);
await get('dataset-brain').events.click();
assert.match(get('dataset-status').textContent, /same session/);
await get('dataset-review').events.click();
assert.equal(calls.length, 3);
assert.ok(calls.every(call => call.options.headers['X-SZL-Session'] === session));
const review = JSON.parse(calls[2].options.body);
assert.deepEqual(review.evidence_sha256, [receipt.payload_sha256]);
assert.equal(review.requested_action, 'review-dataset-metadata');
assert.equal(review.axes.content_quality, 0);
assert.equal(review.axes.training_rights, 0);
assert.match(get('dataset-status').textContent, /Hatun: ABSTAIN/);
assert.match(get('dataset-proof').textContent, /One source observation/);
get('dataset-session').value = 'z'.repeat(64);
get('dataset-session').events.input();
assert.equal(get('dataset-results').children.length, 0);
assert.equal(get('dataset-review').disabled, true);
""")
