#!/usr/bin/env python3
"""Witness a real public market brief without recording the session token."""
import argparse
import hashlib
import json
import secrets
import time
from pathlib import Path

import httpx


CAPACITY_RETRY_SECONDS = 45


def is_public_model_capacity_response(response):
    """Recognize only the runtime's published mapping of lab HTTP 429."""
    if response.status_code != 502:
        return False
    try:
        return response.json().get("detail") == "model provider returned HTTP 429"
    except (ValueError, AttributeError):
        return False


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://szlholdings-vertical-services.hf.space")
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", default="artifacts/public-khipu-probe.json")
    args = parser.parse_args()
    report = {"schema": "szl.public-khipu-live-probe/v1", "observed_at": time.time(),
              "source_revision": args.expected_revision, "state": "FAILED",
              "session_token_recorded": False, "effectors_enabled": False}
    try:
        with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=90,
                          follow_redirects=False, trust_env=False,
                          headers={"X-SZL-Session": secrets.token_urlsafe(32)}) as client:
            identity = client.get("/api/build-info")
            identity.raise_for_status()
            if identity.json()["build"]["revision"] != args.expected_revision:
                raise RuntimeError("source revision mismatch")
            for attempt in range(2):
                refs = []
                observations = []
                for connector, parameters in (("coinbase-spot", {"base": "BTC", "currency": "USD"}),
                                              ("treasury-average-rates", {"limit": 5})):
                    response = client.post(f"/api/verticals/finance/connectors/{connector}/fetch",
                                           json={"parameters": parameters, "force_refresh": True})
                    response.raise_for_status()
                    receipt = response.json()["receipt"]
                    if receipt["state"] != "OBSERVED":
                        raise RuntimeError("public observation unavailable")
                    refs.append(receipt["payload_sha256"])
                    observations.append(receipt)
                report["observations"] = observations
                request = {"task": "risk-summary", "objective": "Review public market observations.",
                           "context": "", "axes": {"evidence": .9, "freshness": .9, "reversibility": .9},
                           "evidence_sha256": refs, "preferred_model": "khipu-gguf-public",
                           "public_demo_consent": True}
                plan_response = client.post("/api/verticals/finance/intelligence/plan", json=request)
                plan_response.raise_for_status()
                plan = plan_response.json()
                report["plan"] = plan
                if plan["decision"] != "READY_FOR_INFERENCE":
                    raise RuntimeError("public model plan withheld")
                invoke = client.post("/api/verticals/finance/intelligence/invoke",
                                     json={**request, "max_new_tokens": 32, "temperature": 0})
                try:
                    invoke.raise_for_status()
                except httpx.HTTPStatusError:
                    if attempt != 0 or not is_public_model_capacity_response(invoke):
                        raise
                    report["capacity_retry"] = {
                        "trigger": "model provider returned HTTP 429",
                        "wait_seconds": CAPACITY_RETRY_SECONDS,
                        "first_plan_receipt_sha256": plan["receipt"]["basis_sha256"],
                    }
                    time.sleep(CAPACITY_RETRY_SECONDS)
                    continue
                result = invoke.json()
                report["invocation"] = result
                break
            basis = {key: value for key, value in result.items() if key not in (
                "output", "receipt", "raw_context_returned", "raw_context_stored", "truth_label")}
            if (result["output_sha256"] != hashlib.sha256(result["output"].encode()).hexdigest()
                    or result["receipt"]["basis_sha256"] != sha(basis)
                    or result["plan_receipt_sha256"] != plan["receipt"]["basis_sha256"]
                    or not result["provider_verification"]["model_identity_verified"]
                    or not result["provider_verification"]["request_hash_verified"]
                    or not result["provider_verification"]["output_hash_verified"]
                    or result["effectors_enabled"] is not False):
                raise RuntimeError("invocation receipt consistency failed")
            # Cross-session references must remain unresolved after a success.
            denied = client.post("/api/verticals/finance/intelligence/plan", json=request,
                                 headers={"X-SZL-Session": secrets.token_urlsafe(32)})
            denied.raise_for_status()
            if denied.json()["decision"] != "ABSTAIN":
                raise RuntimeError("cross-session evidence isolation failed")
            report["cross_session_evidence_rejected"] = True
            report["state"] = "VERIFIED_LIVE"
    except (httpx.HTTPError, KeyError, ValueError, RuntimeError) as exc:
        report["error_class"] = type(exc).__name__
        if isinstance(exc, httpx.HTTPStatusError):
            report["http_status"] = exc.response.status_code
            report["path"] = exc.request.url.path
            report["response_excerpt"] = exc.response.text[:1500]
        elif isinstance(exc, RuntimeError):
            report["error"] = str(exc)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"state": report["state"], "output": str(output)}))
    return 0 if report["state"] == "VERIFIED_LIVE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
