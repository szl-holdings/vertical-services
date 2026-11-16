"""Deployed proposal controls preserve explicit scope and session identity."""
from szl_verticals.showcase import _public_governed_review
from test_catalog_search_surface import CLIENT, _run_js


SCRIPT = _public_governed_review("lyte").split("<script>", 1)[1].split("</script>", 1)[0]
EVENTS = "const documentEvents = {}; document.addEventListener = (name, fn) => { documentEvents[name] = fn; };\n"
RESULT = r"""
const proposal = {output: '<img src=x onerror=alert(1)>', local_evidence_forwarded: false, effectors_enabled: false,
  provider_verification: {provider_state: 'PROPOSAL', output_complete: true,
    hash_consistency_verified: true, authenticity_established: false}};
get('dataset-session').value = 'a'.repeat(64);
get('governed-review-consent').checked = true;
"""


def test_deployed_rooms_show_distinct_governed_proposal_and_retired_market_action():
    finance = CLIENT.get("/intelligence/finance").text
    lyte = CLIENT.get("/intelligence/lyte").text
    assert "Market echo retired" in finance
    assert 'id="public-brief-run"' not in finance
    assert 'id="governed-review-run"' not in finance
    assert 'id="governed-review-run"' in lyte
    assert "This does not analyze or qualify the datasets" in lyte
    assert "semantic grounding are not established" in lyte
    assert "khipu-gguf-public" not in SCRIPT
    assert "innerHTML" not in SCRIPT


def test_governed_panel_uses_one_session_and_renders_model_text_as_text():
    _run_js(EVENTS + SCRIPT, RESULT + r"""
globalThis.fetch = async (path, options) => {
  calls.push({path, options});
  if (path.endsWith('/fetch')) return response({receipt: {payload_sha256: String(calls.length).repeat(64)}});
  if (path.endsWith('/plan')) return response({decision: 'READY_FOR_INFERENCE'});
  return response(proposal);
};
await get('governed-review-run').events.click();
assert.equal(calls.length, 4);
assert.ok(calls.every(call => call.path.startsWith('/api/verticals/lyte/')));
assert.ok(calls.every(call => call.options.headers['X-SZL-Session'] === 'a'.repeat(64)));
const sent = JSON.parse(calls[3].options.body);
assert.equal(sent.task, 'governed-evidence-review');
assert.equal(sent.preferred_model, 'khipu-governed-public');
assert.equal(get('governed-review-output').textContent, proposal.output);
assert.equal(get('governed-review-output').hidden, false);
assert.match(get('governed-review-status').textContent, /semantic grounding remain unavailable/);
""")


def test_late_response_cannot_reappear_after_inventory_session_changes():
    _run_js(EVENTS + SCRIPT, RESULT + r"""
let finish;
globalThis.fetch = async (path, options) => {
  calls.push({path, options});
  if (path.endsWith('/fetch')) return response({receipt: {payload_sha256: String(calls.length).repeat(64)}});
  if (path.endsWith('/plan')) return response({decision: 'READY_FOR_INFERENCE'});
  return new Promise(resolve => { finish = resolve; });
};
const pending = get('governed-review-run').events.click();
await new Promise(resolve => setImmediate(resolve));
assert.equal(typeof finish, 'function');
get('dataset-session').value = 'b'.repeat(64);
documentEvents.input({target: {id: 'dataset-session'}});
assert.equal(calls[3].options.signal.aborted, true);
finish(response(proposal));
await pending;
assert.equal(get('governed-review-output').hidden, true);
assert.equal(get('governed-review-output').textContent, '');
assert.match(get('governed-review-status').textContent, /Session changed/);
assert.equal(get('governed-review-run').disabled, false);
""")
