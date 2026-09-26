"""Component contracts for real planner/provider code; network is a mock transport."""
from __future__ import annotations

import asyncio
import hashlib
import importlib
import itertools
import json
import sqlite3
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deploy"))
from test_evidence_resolution import CLOCK, CONNECTORS, DIGESTS, SCOPE, ledger, put, resolve


@pytest.fixture
def runtime(monkeypatch, ledger):
    module = importlib.import_module("szl_verticals.intelligence")
    monkeypatch.setattr(module, "STORE", ledger)
    monkeypatch.setattr(module, "CONNECTORS", CONNECTORS)
    monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: CLOCK))
    # Other independent gates are fixed true to isolate evidence admission.
    monkeypatch.setattr(module, "vertical_readiness", lambda *a, **kw: {
        "ready": True, "requirements": {"source_bound": True}})
    monkeypatch.setattr(module, "build_info", lambda: {"build": {"state": "OBSERVED", "revision": "d"*40}})
    monkeypatch.setenv("SZL_MODEL_ENDPOINT_KHIPU_1_5B", "https://router.huggingface.co/models/fixture")
    monkeypatch.setenv("SZL_MODEL_REVISION_KHIPU_1_5B", "d"*40)
    monkeypatch.setenv("SZL_MODEL_PROTOCOL_KHIPU_1_5B", "openai-chat")
    monkeypatch.setenv("HF_TOKEN", "synthetic-test-token")
    monkeypatch.setattr(importlib.import_module("szl_verticals.evidence"), "time", SimpleNamespace(time=lambda: CLOCK))
    return module


def request(runtime, digests=None, **overrides):
    values = dict(task="scenario-analysis", objective="Review a synthetic observation.",
                  context="Caller-reported text", axes={"evidence": .99, "freshness": .99},
                  evidence_sha256=DIGESTS[:2] if digests is None else digests)
    values.update(overrides)
    return runtime.IntelligenceInvokeRequest(**values)


def test_fabricated_refs_fail_in_actual_planner_and_invoke(runtime, monkeypatch):
    calls = []
    async def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("provider must not be called")
    monkeypatch.setattr(runtime, "_invoke_provider", forbidden)
    payload = request(runtime)
    plan = runtime.build_intelligence_plan("finance", payload, SCOPE)
    assert plan["decision"] == "ABSTAIN"
    assert plan["gates"]["evidence_floor_met"] is False
    with pytest.raises(HTTPException) as error:
        asyncio.run(runtime.vertical_intelligence_invoke("finance", payload, SCOPE))
    assert error.value.status_code == 503
    assert not calls


def test_one_stored_payload_cannot_be_added_to_its_reference(runtime, ledger):
    put(ledger)
    plan = runtime.build_intelligence_plan("finance", request(runtime, DIGESTS[:1]), SCOPE)
    assert plan["decision"] == "ABSTAIN"
    assert plan["session_observation_count"] == 1
    assert plan["gates"]["evidence_floor_met"] is False


def test_ready_plan_binds_distinct_snapshot_without_exposing_text(runtime, ledger):
    for digest in DIGESTS[:2]:
        put(ledger, digest)
    payload = request(runtime)
    first = runtime.build_intelligence_plan("finance", payload, SCOPE)
    second = runtime.build_intelligence_plan("finance", payload, SCOPE)
    assert first["decision"] == "READY_FOR_INFERENCE"
    assert first["receipt"] == second["receipt"]
    assert first["evidence_resolution"]["resolved_count"] == 2
    assert "source observation" not in json.dumps(first)
    assert "Caller-reported text" not in json.dumps(first)
    assert first["effectors_enabled"] is False
    assert first["selected_model"]["revision_evidence"] == "OPERATOR_DECLARED"


@pytest.mark.parametrize("axes", [{"a": .99, " A ": .99}, {"Evidence": .99, "evidence": .99}])
def test_normalized_axis_collisions_are_rejected(runtime, axes):
    with pytest.raises(ValidationError):
        request(runtime, axes=axes)


def test_invalid_unicode_rejected_before_hashing(runtime):
    with pytest.raises(ValidationError):
        request(runtime, context="\ud800")


def test_scope_mismatched_internal_snapshot_fails_closed(runtime, ledger):
    put(ledger)
    snapshot = resolve(ledger, DIGESTS[:1])
    with pytest.raises(HTTPException):
        runtime.build_intelligence_plan("finance", request(runtime), SCOPE, _evidence=snapshot)


def test_provider_consumes_exact_planned_snapshot_when_basis_is_unchanged(runtime, ledger, monkeypatch):
    original = [put(ledger, digest, summary={"finding": "original"}) for digest in DIGESTS[:2]]
    payload = request(runtime)
    expected = runtime.build_intelligence_plan("finance", payload, SCOPE)
    real_client = httpx.AsyncClient
    seen = []
    def response(req):
        body = json.loads(req.content)
        user = body["messages"][1]["content"]
        system = body["messages"][0]["content"]
        seen.append((user, system))
        assert hashlib.sha256(user.encode()).hexdigest() == expected["inference_input_sha256"]
        assert hashlib.sha256(system.encode()).hexdigest() == expected["system_instruction_sha256"]
        data = json.loads(user)
        assert data["evidence_snapshot_sha256"] == expected["evidence_resolution"]["snapshot_sha256"]
        assert all(row["summary"]["finding"] == "original" for row in data["connector_observations"])
        assert data["context_provenance"] == "CALLER_REPORTED_NOT_AUTHENTICATED"
        return httpx.Response(200, json={"choices": [{"message": {"content": "Synthetic output"}}]})
    def client_factory(**kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        return real_client(transport=httpx.MockTransport(response), **kwargs)
    monkeypatch.setattr(runtime.httpx, "AsyncClient", client_factory)
    result = asyncio.run(runtime.vertical_intelligence_invoke("finance", payload, SCOPE))
    assert len(seen) == 1
    assert result["inference_input_sha256"] == expected["inference_input_sha256"]
    assert result["evidence_snapshot_sha256"] == expected["evidence_resolution"]["snapshot_sha256"]
    assert result["model_revision_evidence"] == "OPERATOR_DECLARED"
    assert result["effectors_enabled"] is False
    assert result["evidence_fresh_at_response"] is True


@pytest.mark.parametrize("change", ["summary", "withdrawal", "change-then-restore"])
def test_changed_basis_before_dispatch_prevents_network(runtime, ledger, monkeypatch, change):
    original = [put(ledger, digest, summary={"finding": "original"}) for digest in DIGESTS[:2]]
    real_client = httpx.AsyncClient
    seen = []
    def response(req):
        seen.append(req)
        raise AssertionError("obsolete evidence must not leave the process")
    def factory(**kwargs):
        if change in {"summary", "change-then-restore"}:
            ledger.put(original[0], {"finding": "changed after planning"})
            if change == "change-then-restore":
                ledger.put(original[0], {"finding": "original"})
        else:
            ledger.withdraw_payloads(vertical="finance", session_scope=SCOPE,
                                     payload_digests=DIGESTS[:1], now=CLOCK)
        return real_client(transport=httpx.MockTransport(response), **kwargs)
    monkeypatch.setattr(runtime.httpx, "AsyncClient", factory)
    with pytest.raises(HTTPException) as error:
        asyncio.run(runtime.vertical_intelligence_invoke("finance", request(runtime), SCOPE))
    assert error.value.status_code == 409
    assert not seen


def test_withdrawal_during_provider_call_withholds_output(runtime, ledger, monkeypatch):
    for digest in DIGESTS[:2]:
        put(ledger, digest)
    real_client = httpx.AsyncClient
    seen = []
    def response(req):
        seen.append(req)
        ledger.withdraw_payloads(vertical="finance", session_scope=SCOPE,
                                 payload_digests=DIGESTS[:1], now=CLOCK)
        return httpx.Response(200, json={"choices": [{"message": {"content": "WITHHOLD_THIS"}}]})
    monkeypatch.setattr(runtime.httpx, "AsyncClient",
                        lambda **kwargs: real_client(transport=httpx.MockTransport(response), **kwargs))
    with pytest.raises(HTTPException) as error:
        asyncio.run(runtime.vertical_intelligence_invoke("finance", request(runtime), SCOPE))
    assert error.value.status_code == 409 and len(seen) == 1
    assert "WITHHOLD_THIS" not in str(error.value.detail)


def test_expiry_before_dispatch_prevents_network(runtime, ledger, monkeypatch):
    for digest in DIGESTS[:2]:
        put(ledger, digest)
    real_client = httpx.AsyncClient
    seen = []
    def response(req):
        seen.append(req)
        raise AssertionError("expired evidence must not leave the process")
    def factory(**kwargs):
        monkeypatch.setattr(runtime, "time", SimpleNamespace(time=lambda: CLOCK+50.0))
        return real_client(transport=httpx.MockTransport(response), **kwargs)
    monkeypatch.setattr(runtime.httpx, "AsyncClient", factory)
    with pytest.raises(HTTPException) as error:
        asyncio.run(runtime.vertical_intelligence_invoke("finance", request(runtime), SCOPE))
    assert error.value.status_code == 503
    assert not seen


def test_serialized_observations_count_against_real_context_budget(runtime, ledger, monkeypatch):
    for digest in DIGESTS[:2]:
        put(ledger, digest, summary={"text": "界" * 1000})
    monkeypatch.setitem(runtime.VERTICAL_INTELLIGENCE["finance"], "context_budget_bytes", 6800)
    plan = runtime.build_intelligence_plan("finance", request(runtime), SCOPE)
    assert plan["decision"] == "ABSTAIN"
    assert not plan["gates"]["context_budget_met"] or "EVIDENCE_CONTEXT_BUDGET_EXCEEDED" in plan["blockers"]


def test_plan_refuses_a_registration_that_is_not_current(runtime, ledger, monkeypatch):
    for digest in DIGESTS[:2]:
        put(ledger, digest)
    monkeypatch.setattr(ledger, "register_assessment", lambda **kwargs: {
        "state": "REVALIDATION_REQUIRED", "original_decision": "READY_FOR_INFERENCE"})
    with pytest.raises(HTTPException) as error:
        runtime.build_intelligence_plan("finance", request(runtime), SCOPE)
    assert error.value.status_code == 409


def test_malformed_stored_plan_assessment_is_unavailable_not_a_raw_error(runtime, ledger):
    for digest in DIGESTS[:2]:
        put(ledger, digest)
    payload = request(runtime)
    assert runtime.build_intelligence_plan("finance", payload, SCOPE)["decision"] == "READY_FOR_INFERENCE"
    with sqlite3.connect(ledger.path) as connection:
        connection.execute("UPDATE evidence_assessments SET dependencies_json='not json'")
    with pytest.raises(HTTPException) as error:
        runtime.build_intelligence_plan("finance", payload, SCOPE)
    assert error.value.status_code == 503


def _isolate_layer(runtime, ledger, monkeypatch, keep):
    """Neutralise every dispatch check except `keep`, so each layer has its own test."""
    if keep != "assessment":
        monkeypatch.setattr(ledger, "assessment_status", lambda **kwargs: {"state": "CURRENT"})
    if keep != "reresolve":
        real, pinned = runtime._resolve_plan_evidence, []
        def first_snapshot(*args, **kwargs):
            if not pinned:
                pinned.append(real(*args, **kwargs))
            return pinned[0]
        monkeypatch.setattr(runtime, "_resolve_plan_evidence", first_snapshot)


def _change(ledger, original, how):
    if how == "withdraw":
        ledger.withdraw_payloads(vertical="finance", session_scope=SCOPE,
                                 payload_digests=DIGESTS[:1], now=CLOCK)
    else:
        ledger.put(original[0], {"finding": "changed"})


@pytest.mark.parametrize("keep,how", [("assessment", "withdraw"), ("reresolve", "summary")])
def test_each_pre_dispatch_layer_alone_keeps_obsolete_evidence_in_process(runtime, ledger, monkeypatch, keep, how):
    original = [put(ledger, digest, summary={"finding": "original"}) for digest in DIGESTS[:2]]
    _isolate_layer(runtime, ledger, monkeypatch, keep)
    real_client, seen = httpx.AsyncClient, []
    def response(req):
        seen.append(req)
        return httpx.Response(200, json={"choices": [{"message": {"content": "LEAKED"}}]})
    def factory(**kwargs):
        _change(ledger, original, how)
        return real_client(transport=httpx.MockTransport(response), **kwargs)
    monkeypatch.setattr(runtime.httpx, "AsyncClient", factory)
    with pytest.raises(HTTPException) as error:
        asyncio.run(runtime.vertical_intelligence_invoke("finance", request(runtime), SCOPE))
    assert error.value.status_code == 409
    assert not seen


@pytest.mark.parametrize("keep,how", [("assessment", "withdraw"), ("reresolve", "summary"), ("fresh", "expire")])
def test_each_post_response_layer_alone_withholds_output(runtime, ledger, monkeypatch, keep, how):
    original = [put(ledger, digest, summary={"finding": "original"}) for digest in DIGESTS[:2]]
    _isolate_layer(runtime, ledger, monkeypatch, keep)
    real_client, seen = httpx.AsyncClient, []
    def response(req):
        seen.append(req)
        if how == "expire":
            monkeypatch.setattr(runtime, "time", SimpleNamespace(time=lambda: CLOCK + 50.0))
        else:
            _change(ledger, original, how)
        return httpx.Response(200, json={"choices": [{"message": {"content": "WITHHOLD_THIS"}}]})
    monkeypatch.setattr(runtime.httpx, "AsyncClient",
                        lambda **kwargs: real_client(transport=httpx.MockTransport(response), **kwargs))
    with pytest.raises(HTTPException) as error:
        asyncio.run(runtime.vertical_intelligence_invoke("finance", request(runtime), SCOPE))
    assert error.value.status_code == 409 and len(seen) == 1
    assert "WITHHOLD_THIS" not in str(error.value.detail)


def test_plan_and_dispatch_hand_the_store_a_clock_not_a_pre_read_value(runtime, ledger, monkeypatch):
    # A time read before the store's lock can predate a concurrent reader's check
    # and falsely latch ASSESSMENT_CLOCK_REGRESSED (see the racing-reader test in
    # test_evidence_replay.py), so every replay call must pass the clock itself.
    for digest in DIGESTS[:2]:
        put(ledger, digest)
    seen = []
    for name in ("register_assessment", "assessment_status"):
        def wrapper(*, _real=getattr(ledger, name), _name=name, **kwargs):
            seen.append((_name, callable(kwargs["now"])))
            return _real(**kwargs)
        monkeypatch.setattr(ledger, name, wrapper)
    real_client = httpx.AsyncClient
    ok = httpx.Response(200, json={"choices": [{"message": {"content": "Synthetic output"}}]})
    monkeypatch.setattr(runtime.httpx, "AsyncClient",
                        lambda **kwargs: real_client(transport=httpx.MockTransport(lambda req: ok), **kwargs))
    asyncio.run(runtime.vertical_intelligence_invoke("finance", request(runtime), SCOPE))
    assert {name for name, _ in seen} == {"register_assessment", "assessment_status"}
    assert all(is_clock for _, is_clock in seen), seen



def test_concurrent_identical_plans_never_poison_their_own_assessment(runtime, ledger, monkeypatch):
    # A plan's basis is deterministic, so identical plans share one assessment.
    # Just before this plan's registration takes the store lock, a second
    # identical plan runs to completion. A caller that read the clock before
    # the lock would now present an older time than the committed last check,
    # latch ASSESSMENT_CLOCK_REGRESSED and 409 this plan for the rest of the
    # session. A clock read inside the transaction comes after the racer's.
    for digest in DIGESTS[:2]:
        put(ledger, digest)
    ticks, tick_lock = itertools.count(1), threading.Lock()
    def clock():
        with tick_lock:
            return CLOCK + next(ticks) / 1e6
    monkeypatch.setattr(runtime, "time", SimpleNamespace(time=clock))
    payload = request(runtime)
    assert runtime.build_intelligence_plan("finance", payload, SCOPE)["decision"] == "READY_FOR_INFERENCE"
    racer = {}

    def race():
        try:
            racer["decision"] = runtime.build_intelligence_plan("finance", payload, SCOPE)["decision"]
        except HTTPException as error:
            racer["decision"] = error.status_code

    class RacingLock:
        def __init__(self, inner):
            self.inner = inner
        def __enter__(self):
            if "thread" not in racer and sys._getframe(1).f_code.co_name == "register_assessment":
                racer["thread"] = threading.Thread(target=race)
                racer["thread"].start()
                racer["thread"].join(timeout=30)
            return self.inner.__enter__()
        def __exit__(self, *exc):
            return self.inner.__exit__(*exc)

    monkeypatch.setattr(ledger, "_lock", RacingLock(ledger._lock))
    try:
        first = runtime.build_intelligence_plan("finance", payload, SCOPE)["decision"]
    except HTTPException as error:
        first = error.status_code
    assert (first, racer["decision"]) == ("READY_FOR_INFERENCE", "READY_FOR_INFERENCE")
    assert runtime.build_intelligence_plan("finance", payload, SCOPE)["decision"] == "READY_FOR_INFERENCE"
