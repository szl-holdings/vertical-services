"""The canonical live witness accepts only the distinct bounded protocol claim."""
import asyncio
import copy
from pathlib import Path

import pytest

from test_public_governed_integration import governed_runtime, install_provider, request
from test_intelligence_evidence_admission import runtime
from test_evidence_resolution import SCOPE, ledger
from tools.probe_public_governed_khipu import sha, verify_invocation


@pytest.fixture
def observed(governed_runtime, monkeypatch):
    r = governed_runtime
    plan = r.build_intelligence_plan("lyte", request(r), SCOPE)
    install_provider(r, monkeypatch)
    result = asyncio.run(r.vertical_intelligence_invoke("lyte", request(r), SCOPE))
    return result, plan


def test_live_witness_verifies_actual_application_receipts(observed):
    verify_invocation(*observed)


@pytest.mark.parametrize("key,value", [
    ("authenticity_established", True), ("quality_evidence", "VERIFIED"),
    ("semantic_entailment", "VERIFIED"), ("training_admission", "ADMITTED"),
    ("local_evidence_forwarded", True), ("output_complete", False),
    ("nemo_envelope_hashes_independently_recomputed", True),
])
def test_live_witness_rejects_overclaim_even_with_rehashed_application_receipt(observed, key, value):
    result, plan = copy.deepcopy(observed)
    result["provider_verification"][key] = value
    basis = {key: value for key, value in result.items() if key not in (
        "output", "receipt", "raw_context_returned", "raw_context_stored", "truth_label")}
    result["receipt"]["basis_sha256"] = sha(basis)
    with pytest.raises(RuntimeError):
        verify_invocation(result, plan)


def test_canonical_publish_uses_new_protocol_witness_and_keeps_historical_script():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/hf-space.yml").read_text()
    assert "tools/probe_public_governed_khipu.py" in workflow
    assert "tools/probe_public_khipu.py" not in workflow
    assert "market brief" not in workflow
    assert (root / "tools/probe_public_khipu.py").is_file()
