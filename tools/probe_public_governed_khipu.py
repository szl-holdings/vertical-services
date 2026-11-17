#!/usr/bin/env python3
"""Witness the distinct fixed-question governed protocol through Lyte.

This does not witness a finance echo, model quality, semantic grounding, private
memory access, or dataset training admission. Session tokens are never recorded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import time
from pathlib import Path

import httpx

INPUT_SCOPE = "FIXED_GOVERNANCE_QUERY_PROVIDER_PUBLIC_CORPUS_ONLY"
MODEL_REVISION = "67d60ec577730747055491640cfb91fc4a4b5d25"
SOURCE_REVISION = "c94e9218093e0815745cbd5dccaddea1797379a3"


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def verify_invocation(result, plan):
    """Check application receipts and explicit limits of the provider witness."""
    basis = {key: value for key, value in result.items() if key not in (
        "output", "receipt", "raw_context_returned", "raw_context_stored", "truth_label")}
    plan_basis = {key: value for key, value in plan.items() if key not in ("receipt", "truth_label")}
    verified = result["provider_verification"]
    if (plan["receipt"]["basis_sha256"] != sha(plan_basis)
            or plan["decision"] != "READY_FOR_INFERENCE"
            or plan["inference_input_scope"] != INPUT_SCOPE
            or plan["local_evidence_forwarded"] is not False
            or plan["selected_model"]["alias"] != "khipu-governed-public"
            or result["output_sha256"] != hashlib.sha256(result["output"].encode()).hexdigest()
            or result["receipt"]["basis_sha256"] != sha(basis)
            or result["plan_receipt_sha256"] != plan["receipt"]["basis_sha256"]
            or result["inference_input_sha256"] != plan["inference_input_sha256"]
            or result["model_repo_id"] != "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF"
            or result["model_revision"] != MODEL_REVISION
            or result["protocol"] != "szl-public-governed-v3"
            or result["truth_label"] != "MODELED"
            or result["inference_input_scope"] != INPUT_SCOPE
            or result["local_evidence_forwarded"] is not False
            or result["effectors_enabled"] is not False or result["can_execute"] is not False
            or result["human_approval_required"] is not True
            or verified["state"] != "UNSIGNED_CONTRACT_CONSISTENT"
            or verified["provider_state"] != "PROPOSAL"
            or verified["source_revision"] != SOURCE_REVISION
            or verified["provider_identity"]["source_revision"] != SOURCE_REVISION
            or verified["provider_identity"]["source_claim_matches_pin"] is not True
            or verified["model_identity_consistent_with_pins"] is not True
            or verified["hash_consistency_verified"] is not True
            or verified["request_hash_verified"] is not True or verified["output_hash_verified"] is not True
            or verified["nemo_text_input_hash_verified"] is not True
            or verified["output_complete"] is not True or verified["finish_reason"] != "stop"
            or verified["signature_status"] != "UNSIGNED_LOCAL"
            or verified["authenticity_established"] is not False
            or verified["runtime_binary_attested"] is not False
            or verified["local_evidence_forwarded"] is not False
            or verified["quality_evidence"] != "UNAVAILABLE"
            or verified["semantic_entailment"] != "UNAVAILABLE"
            or verified["training_admission"] != "NOT_ADMITTED"
            or verified["authority_state"] != "NO_ACTION_AUTHORITY" or verified["executed"] is not False
            or verified["nemo_envelope_hashes_independently_recomputed"] is not False
            or verified["provider_corpus_hashes_independently_recomputed"] is not False):
        raise RuntimeError("governed invocation receipt consistency failed")


def observe(client, report):
    identity = client.get("/api/build-info")
    identity.raise_for_status()
    if identity.json()["build"]["revision"] != report["source_revision"]:
        raise RuntimeError("source revision mismatch")
    refs = []
    receipts = []
    for connector, parameters in (("hf-datasets", {}),
                                  ("github-actions", {"repository": "vertical-services", "limit": 5})):
        response = client.post(f"/api/verticals/lyte/connectors/{connector}/fetch",
                               json={"parameters": parameters, "force_refresh": True})
        response.raise_for_status()
        receipt = response.json()["receipt"]
        if receipt["state"] != "OBSERVED":
            raise RuntimeError("session source observation unavailable")
        refs.append(receipt["payload_sha256"])
        receipts.append(receipt)
    report["session_gate_observations"] = receipts
    request = {"task": "governed-evidence-review", "objective": "Review the fixed public governance proposal.",
               "context": "", "axes": {"evidence": .9, "freshness": .9, "reversibility": .9},
               "evidence_sha256": refs, "preferred_model": "khipu-governed-public",
               "public_demo_consent": True}
    planned = client.post("/api/verticals/lyte/intelligence/plan", json=request)
    planned.raise_for_status()
    plan = planned.json()
    report["plan"] = plan
    if plan["decision"] != "READY_FOR_INFERENCE":
        raise RuntimeError("governed invocation plan withheld")
    invoked = client.post("/api/verticals/lyte/intelligence/invoke",
                          json={**request, "max_new_tokens": 32, "temperature": 0})
    invoked.raise_for_status()
    result = invoked.json()
    verify_invocation(result, plan)
    report["invocation"] = result
    denied = client.post("/api/verticals/lyte/intelligence/plan", json=request,
                         headers={"X-SZL-Session": secrets.token_urlsafe(32)})
    denied.raise_for_status()
    if denied.json()["decision"] != "ABSTAIN":
        raise RuntimeError("cross-session evidence isolation failed")
    report["cross_session_evidence_rejected"] = True
    report["state"] = "VERIFIED_LIVE_PROTOCOL_ONLY"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://szlholdings-vertical-services.hf.space")
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", default="artifacts/public-governed-khipu-probe.json")
    args = parser.parse_args()
    report = {"schema": "szl.public-governed-khipu-live-probe/v1", "observed_at": time.time(),
              "source_revision": args.expected_revision, "state": "WITHHELD_OR_UNAVAILABLE",
              "session_token_recorded": False, "effectors_enabled": False,
              "inference_input_scope": INPUT_SCOPE, "local_evidence_forwarded": False,
              "quality_evidence": "UNAVAILABLE", "semantic_entailment": "UNAVAILABLE",
              "training_admission": "NOT_ADMITTED", "authenticity_established": False}
    try:
        with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=90,
                          follow_redirects=False, trust_env=False,
                          headers={"X-SZL-Session": secrets.token_urlsafe(32)}) as client:
            observe(client, report)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        report["error_class"] = type(exc).__name__
        if isinstance(exc, httpx.HTTPStatusError):
            report["http_status"] = exc.response.status_code
            report["path"] = exc.request.url.path
        elif isinstance(exc, RuntimeError):
            report["error"] = str(exc)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"state": report["state"], "output": str(output)}))
    return 0 if report["state"] == "VERIFIED_LIVE_PROTOCOL_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
