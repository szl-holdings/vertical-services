"""Synthetic governed replies, plus captured public contract reference fixtures.

The synthetic output is not a live inference or evidence of model quality.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path


def identity(k):
    root = Path(__file__).parent / "fixtures" / "governed"
    return tuple(json.loads((root / name).read_text()) for name in (
        "governed_contract.json", "governed_health.json"))


def reseal(k, value):
    """Rehash a mutated public fixture; retain its semantic claims as provided."""
    value["output_sha256"] = k.text_digest(value["output"]) if value["output"] is not None else None
    value["claims_sha256"] = k.digest(value["claims"])
    value["citations_sha256"] = k.digest(value["citations"])
    if value.get("metrics", {}).get("nemo_text_witness"):
        value["metrics"]["nemo_text_witness"]["input_hash"] = "sha256:" + k.digest({
            "prompt": k.PROMPT, "answer": value["output"]})
    shared = (
        "request_id", "state", "authority_state", "prompt_sha256", "principal_id_sha256",
        "tenant_id_sha256", "policy_revision", "retrieval_query_sha256", "ranking_receipt_sha256",
        "evidence_set_sha256", "formula_binding", "model", "runtime", "output_sha256",
        "claims_sha256", "citations_sha256", "nemo", "tool_intent_sha256",
        "action_admission_sha256", "action_receipt_sha256", "executed",
    )
    receipt = value["receipt"]
    receipt["payload"] = {"schema": "szl.forge.production-governed-inference/v2",
                          **{key: copy.deepcopy(value[key]) for key in shared}}
    receipt["receipt_sha256"] = k.digest(receipt["payload"])
    event = value["anatomy_observation"]["event"]
    for key in ("request_id", "state", "authority_state", "prompt_sha256", "principal_id_sha256",
                "tenant_id_sha256", "policy_revision", "evidence_set_sha256", "output_sha256",
                "claims_sha256", "tool_intent_sha256"):
        event[key] = value[key]
    event["formula_ids"] = copy.deepcopy(value["formula_binding"]["requested_ids"])
    event["model_revision"] = (value["model"] or {}).get("revision")
    event["runtime_engine"] = (value["runtime"] or {}).get("engine")
    event["nemo_decisions"] = [{"stage": item["stage"], "decision": item["decision"]}
                               for item in value["nemo"]]
    body = {key: item for key, item in value.items() if key != "public_export_receipt"}
    value["public_export_receipt"] = {
        "schema": "szl.forge.public-transcript-export-receipt/v1", "state": "EXPORTED",
        "policy": "strict-v1-private-continuation-omitted",
        "source_schema": "szl.forge.production-governed-inference/v2",
        "public_sha256": k.digest(body), "signature_status": "UNSIGNED_LOCAL",
    }
    return value


def reply(k, sent=None):
    sent = k.payload(k.SYSTEM, k.PROMPT) if sent is None else sent
    text = "Synthetic public proposal [synthetic:1]."
    value = {
        "schema": "szl.forge.public-governed-inference/v3",
        "request_id": k.text_digest(f"public\0public-anonymous\0{k.POLICY_REVISION}\0{sent['prompt']}")[:24],
        "prompt_sha256": k.text_digest(sent["prompt"]),
        "principal_id_sha256": k.text_digest("public-anonymous"),
        "tenant_id_sha256": k.text_digest("public"), "policy_revision": k.POLICY_REVISION,
        "retrieval_query_sha256": k.text_digest(sent["prompt"]),
        "ranking_receipt_sha256": "a" * 64, "evidence_set_sha256": "b" * 64,
        "formula_binding": copy.deepcopy(k.FORMULA_BINDING),
        "executed": False, "state": "PROPOSAL", "authority_state": "NO_ACTION_AUTHORITY",
        "reason_codes": [],
        "nemo": [{"stage": stage, "decision": "ALLOW", "rule_version": "doctrine-v11/E1-E10",
                  "input_hash": "sha256:" + "c" * 64, "violated_rules": [], "reasons": []}
                 for stage in ("PRE_GENERATION", "POST_GENERATION")],
        "output": text, "output_schema": "szl.answer-with-node-citations/v2",
        "claims": [{"label": "MODELED", "statement_sha256": k.text_digest(text),
                    "supporting_node_ids": ["synthetic:1"]}],
        "citations": ["synthetic:1"],
        "model": {"id": k.MODEL_ID, "revision": k.REVISION, "adapter_revision": k.ADAPTER_REVISION,
                  "tokenizer_revision": k.REVISION, "template_revision": k.SOURCE_REVISION,
                  "quantization_revision": "sha256:" + k.MODEL_SHA256},
        "runtime": {"engine": "llama-cpp-python", "version": "synthetic-1.0",
                    "hardware_fingerprint": "sha256:" + "d" * 64},
        "metrics": {"elapsed_ms": 10.0, "prompt_tokens": 300, "completion_tokens": 10,
                    "finish_reason": "stop", "nemo_text_witness": {
                        "decision": "ALLOW", "rule_version": "doctrine-v11/R1-R5",
                        "input_hash": "sha256:" + "e" * 64, "violated_rules": [], "reasons": []}},
        "evidence_handles": [{"nodeId": "synthetic:1", "nodeKind": "INDEX",
                              "label": "SAMPLE", "note": "synthetic public fixture"}],
        "tool_intent_sha256": None, "action_admission_sha256": None, "action_receipt_sha256": None,
        "anatomy_observation": {"delivery": "DELIVERED", "event": {
            "schema": "szl.anatomy.production-inference-observation/v2",
            "raw_prompt_present": False, "hydrated_content_present": False,
            "private_reasoning_present": False, "observer_authority": "NONE"}},
        "receipt": {"schema": "szl.forge.production-inference-receipt/v2",
                    "canonicalization": "utf8-json-sort-keys-compact", "algorithm": "sha256",
                    "signature": {"status": "UNSIGNED_LOCAL",
                                  "must_be_signed_before_consequential_action": True}},
    }
    return reseal(k, value)
