"""Real planner/invoke boundaries retain declared release blocks after config."""
import asyncio
import json

import pytest
from fastapi import HTTPException

from test_evidence_resolution import DIGESTS, SCOPE, ledger, put
from test_intelligence_evidence_admission import request, runtime


@pytest.mark.parametrize("alias,blocker", [
    ("khipu-1.5b", "KHIPU_ABSTENTION_GATE_FAILED"),
    ("a11oy-mini", "A11OY_MINI_PUBLICATION_INELIGIBLE"),
])
@pytest.mark.parametrize("protocol", ["hf-text-generation", "openai-chat"])
def test_complete_operator_config_cannot_activate_an_ineligible_model(
    runtime, ledger, monkeypatch, alias, blocker, protocol,
):
    spec = runtime.MODEL_ASSETS[alias]
    monkeypatch.setenv(spec["endpoint_env"], "https://router.huggingface.co/models/fixture")
    monkeypatch.setenv(spec["revision_env"], "d" * 40)
    monkeypatch.setenv(spec["protocol_env"], protocol)
    monkeypatch.setenv(spec["token_env"], "synthetic-secret-never-expose")
    for digest in DIGESTS[:2]:
        put(ledger, digest)
    calls = []

    async def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("release-blocked model must not reach its provider")

    monkeypatch.setattr(runtime, "_invoke_provider", forbidden)
    payload = request(runtime, preferred_model=alias)
    plan = runtime.build_intelligence_plan("finance", payload, SCOPE)
    binding = runtime._model_binding(alias)

    assert plan["evidence_resolution"]["state"] == "COMPLETE"
    assert plan["gates"]["evidence_floor_met"] is True
    assert binding["credential_present"] is True
    assert binding["revision"] == "d" * 40
    assert binding["state"] == "BLOCKED"
    assert binding["publication_eligible"] is False
    assert binding["qualification_truth_label"] == "DECLARED"
    assert blocker in plan["blockers"] and blocker in binding["blockers"]
    assert plan["decision"] == "ABSTAIN"
    assert plan["can_execute"] is False and plan["effectors_enabled"] is False
    assert "synthetic-secret-never-expose" not in json.dumps(plan) + json.dumps(binding)
    with pytest.raises(HTTPException) as error:
        asyncio.run(runtime.vertical_intelligence_invoke("finance", payload, SCOPE))
    assert error.value.status_code == 503
    assert not calls


@pytest.mark.parametrize("alias,blocker", [
    ("khipu-1.5b", "KHIPU_ABSTENTION_GATE_FAILED"),
    ("a11oy-mini", "A11OY_MINI_PUBLICATION_INELIGIBLE"),
])
def test_unavailable_model_still_exposes_its_qualification_block(
    runtime, monkeypatch, alias, blocker,
):
    spec = runtime.MODEL_ASSETS[alias]
    monkeypatch.delenv(spec["endpoint_env"], raising=False)
    monkeypatch.delenv(spec["revision_env"], raising=False)
    monkeypatch.delenv(spec["token_env"], raising=False)
    binding = runtime._model_binding(alias)
    assert binding["state"] == "UNAVAILABLE"
    assert {blocker, "ENDPOINT_UNAVAILABLE", "EXACT_MODEL_REVISION_REQUIRED",
            "MODEL_CREDENTIAL_UNAVAILABLE"} <= set(binding["blockers"])
