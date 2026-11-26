"""Pinned public governed proposal; independent of the retired market echo.

Only one fixed, public governance question leaves this service. Local connector
receipts gate the invocation and stay local. Unsigned hashes establish internal
consistency, never provider authenticity, semantic grounding, or action rights.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException

from .governed_public_schema import SOURCE_SCHEMA, validate_public_body
from .public_khipu import MODEL_ID, MODEL_SHA256, REPO, REVISION, digest

ALIAS = "khipu-governed-public"
PROTOCOL = "szl-public-governed-v3"
ORIGIN = "https://szlholdings-szl-model-inference-lab.hf.space"
ENDPOINT = ORIGIN + "/api/v3/governed-infer"
CONTRACT_URL = ORIGIN + "/.well-known/szl-governed-inference-contract.json"
HEALTH_URL = ORIGIN + "/api/v2/governed-health"
SOURCE_REVISION = "2eb236117f5adf686abc50b16e5ca7dcbb6e5b0d"
SPACE_REVISION = "675d3fb83f0e1b765eeed5374e17faee656ecc6a"
CONTROLLER_REVISION = "9f227f6a10dac178b29130c742c98451b6ed8391"
SECOND_BRAIN_REVISION = "1d3960c69235f117b7ec2b5ea97472f81fb588f5"
NEMO_REVISION = "810231a531188bb569e3faa17396386eb0a5e260"
# The pinned controller lowercases revision fields during identity normalization.
ADAPTER_REVISION = "none"
CONTRACT_SHA256 = "2ff9fe042a569894c1ce07a19d1d79b3ca82442fb67d94f6bad4865c1950c8c3"
PROMPT = "Answer with exactly this status, then cite evidence: Lambda remains Conjecture 1, advisory only."
SYSTEM = ""  # The provider owns its pinned public retrieval template.
INPUT_SCOPE = "FIXED_GOVERNANCE_QUERY_PROVIDER_PUBLIC_CORPUS_ONLY"
POLICY_REVISION = "sha256:" + digest({
    "schema": "szl.public-memory-policy/v1", "principal": "public-anonymous",
    "tenant": "public", "second_brain_revision": SECOND_BRAIN_REVISION,
    "access": "PUBLIC_PROJECTION_ONLY", "tool_authority": "NONE",
})
FORMULA_BINDING = {
    "requested_ids": [], "authorization_basis_ids": [], "applications_sha256": digest([]),
    "locked_proven_ids": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "formal_source_commit": "c497b4ed402249f23da7f290426f0e21c70ab926",
    "kernel_source_commit": "46cfa948367e8133eaa8dd6bcfb781b19165b9bb",
    "lambda_status": "CONJECTURE_1_ADVISORY",
}
SPEC = {
    "repo_id": REPO, "artifact_class": "QUANTIZED_DERIVATIVE",
    "runtime": "PUBLIC_PINNED_GOVERNED_GGUF", "license": "apache-2.0",
    "role": "fixed public governance proposal; unsigned consistency checks, human review",
    "protocol": PROTOCOL, "serving_contract": CONTRACT_URL,
    "canonical_source": "szl-holdings/szl-forge/spaces/szl-model-inference-lab",
    "source_revision": SOURCE_REVISION, "reference_space_revision": SPACE_REVISION,
    "max_new_tokens": 32, "max_message_chars": 1200, "max_retrieval_handles": 3,
    "authentication": "PUBLIC_NO_CREDENTIALS", "service_level": "BEST_EFFORT_NO_SLA",
    "inference_input_scope": INPUT_SCOPE, "local_evidence_forwarded": False,
    "training_admission": "NOT_ADMITTED", "quality_evidence": "UNAVAILABLE",
}
_HEX = re.compile(r"^[0-9a-f]{64}$")
_PREFIXED_HEX = re.compile(r"^sha256:[0-9a-f]{64}$")


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def binding() -> dict[str, Any]:
    return {**SPEC, "alias": ALIAS, "state": "BOUND", "endpoint": ENDPOINT,
            "endpoint_host": urlsplit(ENDPOINT).hostname, "revision": REVISION,
            "revision_evidence": "SOURCE_PINNED_UNSIGNED_CONSISTENCY_REQUIRED",
            "credential_present": False, "credential_value_exposed": False, "blockers": []}


def messages(request: Any, evidence: Any) -> tuple[str, str]:
    # Evidence is resolved, scoped, and freshness checked by the caller. Neither
    # its normalized records nor caller objective/axes enter this request.
    if (not request.public_demo_consent or request.context
            or request.task != "governed-evidence-review"):
        raise ValueError("public governed review requires consent and empty context")
    return SYSTEM, PROMPT


def payload(system: str, user: str) -> dict[str, Any]:
    if system != SYSTEM or user != PROMPT:
        raise ValueError("public governed prompt must be the compiled fixed question")
    return {"prompt": PROMPT, "max_new_tokens": 32, "k": 3}


def verify_identity(contract: Any, health: Any) -> dict[str, Any]:
    """Require the observed public contract and exact source before dispatch."""
    try:
        brain = health["second_brain"]
        frontier = brain["frontier"]
        dependency = health["dependency_status"]
        if (digest(contract) != CONTRACT_SHA256
                or health["schema"] != "szl.model-inference-lab.governed-health/v2"
                or health["status"] != "READY" or health["legacy_model_runtime"] != "READY"
                or health["source_revision"] != SOURCE_REVISION
                or health["controller_revision"] != CONTROLLER_REVISION
                or dependency["ready"] is not True or dependency["contract_ready"] is not True
                or dependency["formula_atlas_ready"] is not True
                or health["component_error"] is not None
                or brain["ready"] is not True or brain["private_graph_present"] is not False
                or brain["content_access"] != "HANDLES_ONLY"
                or frontier["ready"] is not True or frontier["state"] != "REVIEW_REQUIRED"
                or frontier["training_authority"] != "NONE"
                or frontier["execution_authority"] != "NONE"
                or health["formula_atlas"]["formula_may_authorize"] is not False
                or health["nemo"] != {"version": "0.4.0", "envelope_rules": "doctrine-v11/E1-E10",
                                      "text_rules": "doctrine-v11/R1-R5"}):
            raise ValueError("public governed identity mismatch")
        for name, repo, version, revision in (
            ("szl-forge-inference", "szl-forge", "0.2.0", CONTROLLER_REVISION),
            ("szl-second-brain", "szl-second-brain", "1.3.0", SECOND_BRAIN_REVISION),
            ("szl-nemo", "szl-nemo", "0.4.0", NEMO_REVISION),
        ):
            package = dependency["packages"][name]
            if (package["expected"] != version or package["observed"] != version
                    or package["match"] is not True
                    or package["direct_url"]["url"] != f"https://github.com/szl-holdings/{repo}/archive/{revision}.tar.gz"):
                raise ValueError("public governed component mismatch")
        return {"contract_sha256": CONTRACT_SHA256, "health_sha256": digest(health),
                "source_revision": SOURCE_REVISION, "source_claim_matches_pin": True,
                "component_claims_match_pins": True, "authenticity_established": False}
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, AttributeError):
        raise HTTPException(502, "public governed provider identity verification failed") from None


def _witness(item: dict[str, Any], *, rule: str) -> bool:
    return (item["decision"] == "ALLOW" and item["rule_version"] == rule
            and _PREFIXED_HEX.fullmatch(item["input_hash"]) is not None
            and item["violated_rules"] == [] and item["reasons"] == [])


def verify_reply(value: Any, sent: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Withhold unsafe, incomplete, or inconsistent unsigned proposals."""
    try:
        if type(value) is not dict or sent != payload(SYSTEM, PROMPT):
            raise ValueError("invalid public governed request or response")
        export = value["public_export_receipt"]
        body = {key: item for key, item in value.items() if key != "public_export_receipt"}
        if export != {
            "schema": "szl.forge.public-transcript-export-receipt/v1", "state": "EXPORTED",
            "policy": "strict-v1-private-continuation-omitted", "source_schema": SOURCE_SCHEMA,
            "public_sha256": digest(body), "signature_status": "UNSIGNED_LOCAL",
        }:
            raise ValueError("public export mismatch")
        body = validate_public_body(body)
        output = body["output"]
        metrics = body["metrics"]
        model = body["model"]
        runtime = body["runtime"]
        if (body["state"] != "PROPOSAL" or body["authority_state"] != "NO_ACTION_AUTHORITY"
                or body["executed"] is not False or body["reason_codes"] != []
                or any(body[key] is not None for key in (
                    "tool_intent_sha256", "action_admission_sha256", "action_receipt_sha256"))
                or body["prompt_sha256"] != text_digest(PROMPT)
                or body["retrieval_query_sha256"] != text_digest(PROMPT)
                or body["principal_id_sha256"] != text_digest("public-anonymous")
                or body["tenant_id_sha256"] != text_digest("public")
                or body["policy_revision"] != POLICY_REVISION
                or body["request_id"] != text_digest(f"public\0public-anonymous\0{POLICY_REVISION}\0{PROMPT}")[:24]
                or body["formula_binding"] != FORMULA_BINDING
                or model != {"id": MODEL_ID, "revision": REVISION, "adapter_revision": ADAPTER_REVISION,
                             "tokenizer_revision": REVISION, "template_revision": SOURCE_REVISION,
                             "quantization_revision": "sha256:" + MODEL_SHA256}
                or runtime["engine"] != "llama-cpp-python"
                or not 1 <= len(runtime["version"]) <= 100
                or _PREFIXED_HEX.fullmatch(runtime["hardware_fingerprint"]) is None
                or not isinstance(output, str) or not output.strip() or len(output) > 12000
                or body["output_schema"] != "szl.answer-with-node-citations/v2"
                or metrics["finish_reason"] != "stop"
                or type(metrics["prompt_tokens"]) is not int or not 1 <= metrics["prompt_tokens"] <= 800
                or type(metrics["completion_tokens"]) is not int or not 1 <= metrics["completion_tokens"] <= 32
                or type(metrics["elapsed_ms"]) not in (float, int)
                or not math.isfinite(metrics["elapsed_ms"]) or not 0 <= metrics["elapsed_ms"] <= 60000
                or not _witness(metrics["nemo_text_witness"], rule="doctrine-v11/R1-R5")
                or metrics["nemo_text_witness"]["input_hash"] != "sha256:" + digest({"prompt": PROMPT, "answer": output})
                or [item["stage"] for item in body["nemo"]] != ["PRE_GENERATION", "POST_GENERATION"]
                or not all(_witness(item, rule="doctrine-v11/E1-E10") for item in body["nemo"])
                or body["anatomy_observation"]["delivery"] != "DELIVERED"
                or body["anatomy_observation"]["event"]["schema"] != "szl.anatomy.production-inference-observation/v2"):
            raise ValueError("public governed proposal mismatch")
        handles = body["evidence_handles"]
        node_ids = [item["nodeId"] for item in handles]
        if (not 1 <= len(handles) <= sent["k"] or len(set(node_ids)) != len(node_ids)
                or any(not node for node in node_ids)
                or any(len(value) > 4096 for item in handles for value in item.values())
                or len(body["claims"]) != 1
                or body["claims"][0]["label"] != "MODELED"
                or body["claims"][0]["statement_sha256"] != body["output_sha256"]
                or not body["claims"][0]["supporting_node_ids"]
                or not set(body["claims"][0]["supporting_node_ids"]) <= set(node_ids)
                or not set(body["citations"]) <= set(node_ids)
                or len(body["citations"]) != len(set(body["citations"]))
                or any(_HEX.fullmatch(body[key]) is None for key in (
                    "ranking_receipt_sha256", "evidence_set_sha256", "output_sha256"))):
            raise ValueError("public governed evidence linkage mismatch")
        return output, {
            "state": "UNSIGNED_CONTRACT_CONSISTENT", "provider_state": "PROPOSAL",
            "request_hash_verified": True, "output_hash_verified": True,
            "hash_consistency_verified": True, "public_export_sha256": export["public_sha256"],
            "execution_receipt_sha256": body["receipt"]["receipt_sha256"],
            "model_identity_consistent_with_pins": True, "source_revision": SOURCE_REVISION,
            "signature_status": "UNSIGNED_LOCAL", "authenticity_established": False,
            "runtime_binary_attested": False, "finish_reason": "stop", "output_complete": True,
            "inference_input_scope": INPUT_SCOPE, "local_evidence_forwarded": False,
            "local_evidence_role": "SESSION_SCOPED_INVOCATION_GATE_ONLY",
            "quality_evidence": "UNAVAILABLE", "semantic_entailment": "UNAVAILABLE",
            "training_admission": "NOT_ADMITTED", "authority_state": "NO_ACTION_AUTHORITY",
            "executed": False, "nemo_decisions": ["ALLOW", "ALLOW"],
            "nemo_text_input_hash_verified": True,
            "nemo_envelope_hashes_independently_recomputed": False,
            "provider_corpus_hashes_independently_recomputed": False,
            "anatomy_delivery": "PROVIDER_REPORTED_DELIVERED",
            "anatomy_observer_authority": "NONE", "anatomy_private_content_present": False,
            "evidence_handle_count": len(handles), "citation_count": len(body["citations"]),
            "service_level": "BEST_EFFORT_NO_SLA",
        }
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, AttributeError):
        raise HTTPException(502, "public governed Khipu response failed contract verification") from None
