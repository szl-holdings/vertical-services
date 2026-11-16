"""Adversarial public-provider contracts, without network or live inference.

Recomputed unsigned hashes are deliberately insufficient when identity,
authority, privacy, or claim relationships change. Synthetic consistency must
also never be reported as provider authenticity or dataset qualification.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deploy"))
from szl_verticals import public_governed_khipu as k
from governed_fixtures import identity, reply, reseal


PRIVATE_MARKER = "synthetic-private-content-must-not-appear-in-errors"


def _at(value, path):
    for key in path:
        value = value[key]
    return value


def _set(value, path, replacement):
    _at(value, path[:-1])[path[-1]] = copy.deepcopy(replacement)


def _digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _rehash_export(value):
    value["public_export_receipt"]["public_sha256"] = _digest({
        key: item for key, item in value.items() if key != "public_export_receipt"
    })


def _reject(value):
    with pytest.raises(HTTPException) as error:
        k.verify_reply(value, k.payload(k.SYSTEM, k.PROMPT))
    assert error.value.status_code == 502
    assert PRIVATE_MARKER not in str(error.value.detail)


@pytest.mark.parametrize(("target", "path", "replacement"), [
    ("contract", ("model", "revision"), "a" * 40),
    ("contract", ("model", "gguf_sha256"), "a" * 64),
    ("contract", ("endpoint", "tools"), True),
    ("contract", ("authority", "model"), "EXECUTION_AUTHORITY"),
    ("contract", ("privacy", "raw_prompt_persisted"), True),
    ("health", ("source_revision",), k.SPACE_REVISION),
    ("health", ("status",), "UNAVAILABLE"),
    ("health", ("second_brain", "private_graph_present"), True),
    ("health", ("second_brain", "frontier", "training_authority"), "ALLOWED"),
    ("health", ("second_brain", "frontier", "execution_authority"), "ALLOWED"),
    ("health", ("dependency_status", "packages", "szl-nemo", "direct_url", "url"),
     "https://github.com/szl-holdings/szl-nemo/archive/main.tar.gz"),
])
def test_preflight_rejects_identity_authority_or_privacy_drift(target, path, replacement):
    contract, health = identity(k)
    _set(contract if target == "contract" else health, path, replacement)
    with pytest.raises(HTTPException) as error:
        k.verify_identity(contract, health)
    assert error.value.status_code == 502


@pytest.mark.parametrize("path", [
    ("endpoint", "tools"), ("authority", "model"),
    ("privacy", "raw_prompt_persisted"),
])
def test_preflight_missing_authority_or_privacy_declaration_is_unavailable(path):
    contract, health = identity(k)
    del _at(contract, path[:-1])[path[-1]]
    with pytest.raises(HTTPException) as error:
        k.verify_identity(contract, health)
    assert error.value.status_code == 502


@pytest.mark.parametrize(("path", "replacement"), [
    (("model", "id"), "different-model@" + k.REVISION),
    (("model", "revision"), "a" * 40),
    (("model", "tokenizer_revision"), "a" * 40),
    (("model", "template_revision"), k.SPACE_REVISION),
    (("model", "quantization_revision"), "sha256:" + "a" * 64),
    (("model", "adapter_revision"), "a" * 40),
    (("executed",), True),
    (("authority_state",), "A11OY_SIGNED_ADMISSION_VERIFIED"),
    (("tool_intent_sha256",), "a" * 64),
    (("action_admission_sha256",), "a" * 64),
    (("action_receipt_sha256",), "a" * 64),
    (("formula_binding", "authorization_basis_ids"), ["F1"]),
    (("formula_binding", "lambda_status"), "PROVEN"),
    (("prompt_sha256",), "a" * 64),
    (("retrieval_query_sha256",), "a" * 64),
    (("principal_id_sha256",), "a" * 64),
    (("tenant_id_sha256",), "a" * 64),
    (("policy_revision",), "sha256:" + "a" * 64),
    (("claims", 0, "label"), "MEASURED"),
    (("claims", 0, "statement_sha256"), "a" * 64),
    (("claims", 0, "supporting_node_ids"), ["not-returned:1"]),
    (("citations",), ["not-returned:1"]),
    (("nemo", 1, "decision"), "BLOCK"),
    (("nemo", 0, "rule_version"), "unrecognized-rules"),
    (("metrics", "nemo_text_witness", "violated_rules"), ["R1"]),
    (("metrics", "finish_reason"), "length"),
    (("metrics", "finish_reason"), None),
    (("metrics", "completion_tokens"), True),
    (("anatomy_observation", "event", "observer_authority"), "EXECUTE"),
    (("anatomy_observation", "event", "private_reasoning_present"), True),
    (("anatomy_observation", "delivery"), "UNAVAILABLE"),
])
def test_recomputed_unsigned_hashes_do_not_admit_changed_semantics(path, replacement):
    value = reply(k)
    _set(value, path, replacement)
    reseal(k, value)
    _reject(value)


@pytest.mark.parametrize("path", [
    (), ("model",), ("receipt", "payload"), ("anatomy_observation", "event"),
])
def test_unknown_private_fields_are_withheld_even_under_a_valid_export_hash(path):
    value = reply(k)
    _at(value, path)["raw_private_context"] = PRIVATE_MARKER
    _rehash_export(value)
    _reject(value)


@pytest.mark.parametrize("path", [
    ("executed",), ("authority_state",), ("action_admission_sha256",),
    ("receipt", "signature", "must_be_signed_before_consequential_action"),
    ("anatomy_observation", "event", "observer_authority"),
])
def test_missing_action_boundaries_are_withheld(path):
    value = reply(k)
    del _at(value, path[:-1])[path[-1]]
    _rehash_export(value)
    _reject(value)


@pytest.mark.parametrize("path", [
    ("output_sha256",), ("claims_sha256",), ("citations_sha256",),
    ("receipt", "receipt_sha256"),
])
def test_tampered_inner_hash_is_rejected_despite_recomputed_export_hash(path):
    value = reply(k)
    _set(value, path, "f" * 64)
    _rehash_export(value)
    _reject(value)


@pytest.mark.parametrize("path", [
    ("receipt", "payload", "prompt_sha256"),
    ("receipt", "payload", "model", "template_revision"),
    ("anatomy_observation", "event", "evidence_set_sha256"),
])
def test_self_consistent_nested_receipt_must_describe_the_same_public_result(path):
    value = reply(k)
    _set(value, path, "f" * 64)
    value["receipt"]["receipt_sha256"] = _digest(value["receipt"]["payload"])
    _rehash_export(value)
    _reject(value)


def test_export_is_unsigned_and_bound_to_the_entire_public_body():
    for field, replacement in (
        ("public_sha256", "f" * 64), ("signature_status", "SIGNED"),
        ("policy", "allow-private-continuation"),
    ):
        value = reply(k)
        value["public_export_receipt"][field] = replacement
        _reject(value)


@pytest.mark.parametrize("mismatch", ["different-prompt", "previous-output"])
def test_text_witness_must_bind_this_fixed_question_and_output(mismatch):
    value = reply(k)
    witness_input = {"prompt": k.PROMPT, "answer": value["output"]}
    if mismatch == "different-prompt":
        witness_input["prompt"] = "Another public question"
    else:
        witness_input["answer"] = "A previous synthetic output"
    value["metrics"]["nemo_text_witness"]["input_hash"] = "sha256:" + _digest(witness_input)
    # All public and production hashes still describe this output, but the
    # ALLOW witness describes a different pair. Rehash only the outer export.
    _rehash_export(value)
    _reject(value)


def test_valid_consistency_never_becomes_dataset_grounding_or_training_authority():
    # The pinned provider may fall back to a handle without a literal citation.
    # Such a consistent response remains modeled and semantically unqualified.
    value = reply(k)
    value["output"] = "Synthetic proposal without a literal citation."
    value["claims"][0]["statement_sha256"] = k.text_digest(value["output"])
    value["citations"] = []
    reseal(k, value)
    text, verification = k.verify_reply(value, k.payload(k.SYSTEM, k.PROMPT))
    assert text == value["output"]
    assert verification["hash_consistency_verified"] is True
    assert verification["authenticity_established"] is False
    assert verification["runtime_binary_attested"] is False
    assert verification["local_evidence_forwarded"] is False
    assert verification["local_evidence_role"] == "SESSION_SCOPED_INVOCATION_GATE_ONLY"
    assert verification["quality_evidence"] == "UNAVAILABLE"
    assert verification["semantic_entailment"] == "UNAVAILABLE"
    assert verification["training_admission"] == "NOT_ADMITTED"
    assert verification["authority_state"] == "NO_ACTION_AUTHORITY"
    assert verification["executed"] is False
    assert verification["nemo_text_input_hash_verified"] is True
    assert verification["nemo_envelope_hashes_independently_recomputed"] is False
    assert verification["provider_corpus_hashes_independently_recomputed"] is False
    assert verification["anatomy_delivery"] == "PROVIDER_REPORTED_DELIVERED"
    assert verification["citation_count"] == 0
