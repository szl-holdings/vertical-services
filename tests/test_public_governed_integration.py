"""Real planner, scoped ledger, and bounded HTTP dispatch with synthetic replies."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException

from governed_fixtures import identity, reply, reseal
from test_evidence_resolution import CLOCK, DIGESTS, OTHER_SCOPE, SCOPE, ledger
from test_intelligence_evidence_admission import runtime


@pytest.fixture
def governed_runtime(runtime, ledger, monkeypatch):
    from szl_verticals.connector_specs import CONNECTORS
    from szl_verticals.official_connectors import _receipt
    monkeypatch.setattr(runtime, "CONNECTORS", CONNECTORS)
    for index, (connector, source) in enumerate((
        ("hf-datasets", "https://huggingface.co/api/datasets?author=SZLHOLDINGS&limit=500&full=true"),
        ("github-actions", "https://api.github.com/repos/szl-holdings/vertical-services/actions/runs"),
    )):
        receipt = _receipt(spec=CONNECTORS[connector], session_scope=SCOPE,
                           query_hash="c" * 64, source_url=source, http_status=200,
                           payload_sha256=DIGESTS[index], observed_at=CLOCK - 10,
                           state="OBSERVED")
        ledger.put(receipt, {"synthetic_local_data": "PRIVATE_LOCAL_VALUE_NOT_FOR_PROVIDER"})
    return runtime


def request(runtime, **overrides):
    values = dict(task="governed-evidence-review", objective="PRIVATE_LOCAL_OBJECTIVE_NOT_FOR_PROVIDER",
                  context="", axes={"evidence": .95, "freshness": .95},
                  evidence_sha256=DIGESTS[:2], preferred_model="khipu-governed-public",
                  public_demo_consent=True, max_new_tokens=32, temperature=0.0)
    values.update(overrides)
    return runtime.IntelligenceInvokeRequest(**values)


def install_provider(runtime, monkeypatch, *, hook=None, status=200):
    k = runtime.public_governed_khipu
    contract, health = identity(k)
    real_client = httpx.AsyncClient
    seen = []

    def respond(req):
        seen.append((req.method, str(req.url)))
        assert "authorization" not in req.headers
        assert "x-szl-session" not in req.headers
        assert req.headers["accept-encoding"] == "identity"
        assert "PRIVATE_LOCAL" not in req.content.decode()
        if hook:
            hook(req)
        if str(req.url) == k.CONTRACT_URL:
            return httpx.Response(200, json=contract)
        if str(req.url) == k.HEALTH_URL:
            return httpx.Response(200, json=health)
        assert req.method == "POST" and str(req.url) == k.ENDPOINT
        sent = json.loads(req.content)
        assert sent == {"prompt": k.PROMPT, "max_new_tokens": 32, "k": 3}
        if status != 200:
            return httpx.Response(status, json={"state": "ABSTAIN", "private": "MUST_NOT_ECHO"})
        return httpx.Response(200, json=reply(k, sent))

    def factory(**kwargs):
        assert kwargs["follow_redirects"] is False and kwargs["trust_env"] is False
        return real_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(runtime.httpx, "AsyncClient", factory)
    return seen, health


def test_scoped_local_receipts_gate_fixed_public_query_without_being_forwarded(governed_runtime, monkeypatch):
    r = governed_runtime
    plan = r.build_intelligence_plan("lyte", request(r), SCOPE)
    assert plan["decision"] == "READY_FOR_INFERENCE"
    assert plan["local_evidence_forwarded"] is False
    assert plan["inference_input_scope"] == r.public_governed_khipu.INPUT_SCOPE
    seen, _ = install_provider(r, monkeypatch)
    result = asyncio.run(r.vertical_intelligence_invoke("lyte", request(r), SCOPE))
    assert len(seen) == 3 and seen[-1][0] == "POST"
    verification = result["provider_verification"]
    assert verification["provider_identity"]["source_claim_matches_pin"] is True
    assert verification["hash_consistency_verified"] is True
    assert verification["authenticity_established"] is False
    assert verification["semantic_entailment"] == verification["quality_evidence"] == "UNAVAILABLE"
    assert verification["training_admission"] == "NOT_ADMITTED"
    assert verification["output_complete"] is True
    assert result["local_evidence_forwarded"] is result["effectors_enabled"] is result["can_execute"] is False
    assert result["truth_label"] == "MODELED"
    assert result["plan_receipt_sha256"] == plan["receipt"]["basis_sha256"]
    assert r.build_intelligence_plan("lyte", request(r), OTHER_SCOPE)["decision"] == "ABSTAIN"


@pytest.mark.parametrize("overrides", [
    {"public_demo_consent": False}, {"context": "private context"}, {"task": "business-impact"},
    {"max_new_tokens": 384}, {"temperature": .1}, {"evidence_sha256": DIGESTS[:1]},
    {"evidence_sha256": ["e" * 64, "f" * 64]},
])
def test_contract_failure_prevents_all_provider_requests(governed_runtime, monkeypatch, overrides):
    r = governed_runtime
    seen, _ = install_provider(r, monkeypatch)
    with pytest.raises(HTTPException) as error:
        asyncio.run(r.vertical_intelligence_invoke("lyte", request(r, **overrides), SCOPE))
    assert error.value.status_code == 503 and seen == []


def test_identity_drift_withholds_inference_before_post(governed_runtime, monkeypatch):
    r = governed_runtime
    seen, health = install_provider(r, monkeypatch)
    health["source_revision"] = "f" * 40
    with pytest.raises(HTTPException) as error:
        asyncio.run(r.vertical_intelligence_invoke("lyte", request(r), SCOPE))
    assert error.value.status_code == 502
    assert all(method == "GET" for method, _ in seen)


@pytest.mark.parametrize("phase", ["preflight", "inference"])
def test_withdrawal_during_network_withholds_output(governed_runtime, ledger, monkeypatch, phase):
    r = governed_runtime
    k = r.public_governed_khipu
    target = k.HEALTH_URL if phase == "preflight" else k.ENDPOINT
    def hook(req):
        if str(req.url) == target:
            ledger.withdraw_payloads(vertical="lyte", session_scope=SCOPE, payload_digests=DIGESTS[:1])
    seen, _ = install_provider(r, monkeypatch, hook=hook)
    with pytest.raises(HTTPException) as error:
        asyncio.run(r.vertical_intelligence_invoke("lyte", request(r), SCOPE))
    assert error.value.status_code == 409
    assert len(seen) == (2 if phase == "preflight" else 3)
    assert "Synthetic public proposal" not in str(error.value.detail)


@pytest.mark.parametrize("status", [409, 422, 503])
def test_provider_refusal_is_unavailable_without_output_or_receipt(governed_runtime, monkeypatch, status):
    r = governed_runtime
    install_provider(r, monkeypatch, status=status)
    with pytest.raises(HTTPException) as error:
        asyncio.run(r.vertical_intelligence_invoke("lyte", request(r), SCOPE))
    assert error.value.status_code == 502
    assert error.value.detail == f"model provider returned HTTP {status}"
    assert "MUST_NOT_ECHO" not in str(error.value.detail)


def test_retired_exact_echo_never_dispatches_or_silently_changes_protocol(runtime, monkeypatch):
    r = runtime
    from test_public_khipu_integration import request as historical_request
    calls = []
    async def forbidden(*args, **kwargs):
        calls.append(True)
    monkeypatch.setattr(r, "_invoke_provider", forbidden)
    binding = r.public_khipu.binding()
    assert binding["state"] == "RETIRED"
    assert binding["protocol"] == "szl-public-openai-chat"
    plan = r.build_intelligence_plan("finance", historical_request(r), SCOPE)
    assert plan["decision"] == "ABSTAIN"
    assert "PUBLIC_EXACT_ECHO_PROTOCOL_RETIRED" in plan["blockers"]
    with pytest.raises(HTTPException) as error:
        asyncio.run(r.vertical_intelligence_invoke("finance", historical_request(r), SCOPE))
    assert error.value.status_code == 503 and calls == []


def test_pinned_controller_canonicalizes_no_adapter_revision_to_lowercase(runtime):
    k = runtime.public_governed_khipu
    assert k.ADAPTER_REVISION == "none"
    value = reply(k)
    assert value["model"]["adapter_revision"] == "none"
    k.verify_reply(value, k.payload(k.SYSTEM, k.PROMPT))
    value["model"]["adapter_revision"] = "NONE"
    reseal(k, value)
    with pytest.raises(HTTPException) as error:
        k.verify_reply(value, k.payload(k.SYSTEM, k.PROMPT))
    assert error.value.status_code == 502
