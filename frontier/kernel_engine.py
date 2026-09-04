#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deterministic SZL kernel execution boundary for vertical proposals.

This module executes a compact, dependency-free reference implementation of the
control properties represented by the public SZL kernel cards. It deliberately
does not claim that a remote Hugging Face artifact or compiled extension was
loaded unless a deployment adds and verifies that implementation separately.

The embedded kernels normalize bounded inputs, evaluate advisory weighted-
geometric routing, enforce hard-deny conditions, check invariant preservation,
and meter runtime honestly. None of those operations grants authorization.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

ZERO_SHA256: Final = "0" * 64
DEFAULT_KERNEL_IDS: Final = (
    "SZLHOLDINGS/szl-invariants",
    "SZLHOLDINGS/szl-lambda-gate",
    "SZLHOLDINGS/szl-blocked",
    "SZLHOLDINGS/szl-governed-norm",
    "SZLHOLDINGS/szl-kernels",
    "SZLHOLDINGS/governed-inference-meter",
)
RAPL_ROOTS: Final = (
    Path("/sys/class/powercap/intel-rapl:0/energy_uj"),
    Path("/sys/class/powercap"),
)


def canonical_json(value: Any) -> bytes:
    """Encode a value into deterministic JSON suitable for a receipt digest."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical_json(value)
    return hashlib.sha256(raw).hexdigest()


def clamp01(value: Any, *, default: float = 0.0) -> float:
    """Convert finite numeric input to the closed unit interval."""
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return min(1.0, max(0.0, number))


def weighted_geometric_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    """Return a bounded WGM or zero when its domain/invariants are invalid."""
    if not values or len(values) != len(weights):
        return 0.0
    if any(not math.isfinite(value) or value <= 0.0 or value > 1.0 for value in values):
        return 0.0
    if any(not math.isfinite(weight) or weight < 0.0 for weight in weights):
        return 0.0
    total = sum(weights)
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
        return 0.0
    result = math.exp(sum(weight * math.log(value) for value, weight in zip(values, weights)))
    return result if math.isfinite(result) and 0.0 <= result <= 1.0 else 0.0


def _read_rapl_uj() -> int | None:
    candidates: list[Path] = [RAPL_ROOTS[0]]
    root = RAPL_ROOTS[1]
    try:
        if root.is_dir():
            candidates.extend(sorted(root.glob("intel-rapl:*/energy_uj")))
    except OSError:
        return None
    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        try:
            if path.is_file():
                value = int(path.read_text(encoding="utf-8").strip())
                if value >= 0:
                    return value
        except (OSError, ValueError):
            continue
    return None


def _estimate_tokens(text: str) -> int:
    """Expose only a coarse estimate, never a tokenizer-specific measured count."""
    if not text:
        return 0
    return max(1, math.ceil(len(text.encode("utf-8")) / 4))


def _unique_kernel_ids(bindings: Iterable[Mapping[str, Any]]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for row in bindings:
        identifier = str(row.get("id", "")).strip()
        if identifier and identifier not in seen:
            values.append(identifier)
            seen.add(identifier)
    return values


def _evidence_quality(evidence: Any) -> tuple[float, dict[str, Any]]:
    if not isinstance(evidence, list) or not evidence:
        return 0.0, {
            "count": 0,
            "with_source": 0,
            "with_claim": 0,
            "with_digest": 0,
            "quality": 0.0,
        }
    count = len(evidence)
    with_source = 0
    with_claim = 0
    with_digest = 0
    for row in evidence:
        if not isinstance(row, dict):
            continue
        if str(row.get("source", "")).strip():
            with_source += 1
        if str(row.get("claim", "")).strip():
            with_claim += 1
        digest = str(row.get("sha256", "")).strip().lower()
        if len(digest) == 64 and all(char in "0123456789abcdef" for char in digest):
            with_digest += 1
    axes = (
        max(1e-6, with_source / count),
        max(1e-6, with_claim / count),
        max(1e-6, with_digest / count),
    )
    quality = weighted_geometric_mean(axes, (1 / 3, 1 / 3, 1 / 3))
    return quality, {
        "count": count,
        "with_source": with_source,
        "with_claim": with_claim,
        "with_digest": with_digest,
        "quality": round(quality, 8),
    }


def _model_output_safety(model_result: Any) -> tuple[bool, list[str]]:
    """Reject provider outputs that attempt tool/effect escalation."""
    if not isinstance(model_result, dict):
        return True, []
    reasons: list[str] = []
    if model_result.get("tool_calls"):
        reasons.append("MODEL_TOOL_CALLS_REFUSED")
    if model_result.get("authorization") not in (None, "NONE"):
        reasons.append("MODEL_AUTHORIZATION_FIELD_REFUSED")
    if model_result.get("execution_performed") not in (None, False):
        reasons.append("MODEL_EXECUTION_CLAIM_REFUSED")
    text = str(model_result.get("content", "")).lower()
    escalation_markers = (
        "authorization granted",
        "approved for execution",
        "execute immediately",
        "weapon fired",
        "trade executed",
        "filing submitted",
        "credentials obtained",
    )
    matched = [marker for marker in escalation_markers if marker in text]
    reasons.extend(f"MODEL_ESCALATION_TEXT:{marker}" for marker in matched)
    return not reasons, reasons


@dataclass(frozen=True)
class KernelContext:
    vertical: str
    risk: float
    evidence: list[dict[str, Any]]
    human_approved: bool
    preexisting_blocks: list[str]
    model_result: dict[str, Any] | None
    bindings: list[dict[str, Any]]


def evaluate_kernel_stack(
    *,
    vertical: Mapping[str, Any],
    proposal_receipt: Mapping[str, Any],
    model_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute the embedded kernel reference and return an immutable audit object."""
    started = time.perf_counter()
    energy_before = _read_rapl_uj()

    proposal = proposal_receipt.get("proposal") if isinstance(proposal_receipt, Mapping) else None
    proposal = proposal if isinstance(proposal, Mapping) else {}
    evidence = proposal_receipt.get("evidence") if isinstance(proposal_receipt, Mapping) else None
    evidence_list = [row for row in evidence if isinstance(row, dict)] if isinstance(evidence, list) else []
    preexisting = proposal_receipt.get("blocks") if isinstance(proposal_receipt, Mapping) else None
    preexisting_blocks = [str(item) for item in preexisting] if isinstance(preexisting, list) else []
    bindings = vertical.get("kernels") if isinstance(vertical, Mapping) else None
    binding_rows = [row for row in bindings if isinstance(row, dict)] if isinstance(bindings, list) else []

    context = KernelContext(
        vertical=str(vertical.get("slug", "unknown")),
        risk=clamp01(proposal.get("risk"), default=1.0),
        evidence=evidence_list,
        human_approved=proposal_receipt.get("human_approved_input") is True,
        preexisting_blocks=preexisting_blocks,
        model_result=dict(model_result) if isinstance(model_result, Mapping) else None,
        bindings=binding_rows,
    )

    evidence_quality, evidence_report = _evidence_quality(context.evidence)
    normalized = {
        "risk": round(context.risk, 8),
        "risk_complement": round(max(0.0, 1.0 - context.risk), 8),
        "evidence_quality": round(evidence_quality, 8),
        "human_binding_signal": 1.0 if context.human_approved else 0.0,
        "preexisting_policy_clean": 1.0 if not context.preexisting_blocks else 0.0,
    }

    epsilon = 1e-6
    lambda_axes = (
        max(epsilon, normalized["risk_complement"]),
        max(epsilon, normalized["evidence_quality"]),
        max(epsilon, normalized["human_binding_signal"]),
        max(epsilon, normalized["preexisting_policy_clean"]),
    )
    advisory_lambda = weighted_geometric_mean(lambda_axes, (0.25, 0.25, 0.25, 0.25))

    model_safe, model_reasons = _model_output_safety(context.model_result)
    invariant_checks = {
        "authorization_none": proposal_receipt.get("authorization") == "NONE",
        "execution_false": proposal_receipt.get("execution_performed") is False,
        "public_effectors_false": proposal_receipt.get("public_effectors_enabled") is False,
        "lambda_open": proposal_receipt.get("lambda_uniqueness") == "CONJECTURE_1_OPEN",
        "model_output_non_authorizing": model_safe,
        "vertical_bound": context.vertical == str(vertical.get("slug", "")),
    }

    kernel_blocks = list(context.preexisting_blocks)
    kernel_blocks.extend(model_reasons)
    if evidence_quality <= 0.0:
        kernel_blocks.append("KERNEL_NO_EVIDENCE_QUALITY")
    if context.risk >= 0.65:
        kernel_blocks.append("KERNEL_ELEVATED_RISK")
    if not context.human_approved:
        kernel_blocks.append("KERNEL_HUMAN_BINDING_ABSENT")
    if not all(invariant_checks.values()):
        kernel_blocks.append("KERNEL_INVARIANT_FAILURE")
    kernel_blocks = sorted(set(kernel_blocks))

    elapsed = time.perf_counter() - started
    energy_after = _read_rapl_uj()
    energy_j: float | None = None
    energy_state = "UNAVAILABLE"
    if energy_before is not None and energy_after is not None:
        energy_j = max(0.0, (energy_after - energy_before) / 1_000_000.0)
        energy_state = "MEASURED"

    model_text = ""
    if isinstance(context.model_result, dict):
        model_text = str(context.model_result.get("content", ""))

    executed = [
        {
            "artifact": "SZLHOLDINGS/szl-governed-norm",
            "operation": "clamp-and-normalize-bounded-features",
            "implementation": "EMBEDDED_REFERENCE",
            "result": normalized,
        },
        {
            "artifact": "SZLHOLDINGS/szl-lambda-gate",
            "operation": "weighted-geometric-advisory-routing",
            "implementation": "EMBEDDED_REFERENCE",
            "formula_status": "ADVISORY_NOT_UNIQUE",
            "value": round(advisory_lambda, 8),
        },
        {
            "artifact": "SZLHOLDINGS/szl-invariants",
            "operation": "authority-and-execution-invariants",
            "implementation": "EMBEDDED_REFERENCE",
            "checks": invariant_checks,
        },
        {
            "artifact": "SZLHOLDINGS/szl-blocked",
            "operation": "hard-deny-policy-aggregation",
            "implementation": "EMBEDDED_REFERENCE",
            "blocks": kernel_blocks,
        },
        {
            "artifact": "SZLHOLDINGS/governed-inference-meter",
            "operation": "runtime-and-energy-observation",
            "implementation": "EMBEDDED_REFERENCE",
            "duration_seconds": round(elapsed, 8),
            "input_token_estimate": _estimate_tokens(str(proposal.get("summary", ""))),
            "output_token_estimate": _estimate_tokens(model_text),
            "energy_state": energy_state,
            "energy_j": energy_j,
        },
    ]

    declared_ids = _unique_kernel_ids(binding_rows)
    undeclared_executed = [row["artifact"] for row in executed if row["artifact"] not in declared_ids]
    body = {
        "schema": "szl.kernel-stack-evaluation.v1",
        "vertical": context.vertical,
        "state": "HOLD" if kernel_blocks else "ADVISORY_CLEAR",
        "authorization": "NONE",
        "execution_performed": False,
        "public_effectors_enabled": False,
        "declared_bindings": binding_rows,
        "executed_reference_kernels": executed,
        "undeclared_reference_helpers": undeclared_executed,
        "evidence_report": evidence_report,
        "advisory_lambda": round(advisory_lambda, 8),
        "lambda_uniqueness": "CONJECTURE_1_OPEN",
        "proven_trust": False,
        "blocks": kernel_blocks,
        "artifact_execution_claim": "EMBEDDED_REFERENCE_ONLY",
        "external_kernel_artifact_loaded": False,
        "source_revision": os.getenv("SZL_GIT_SHA", "REVISION_UNAVAILABLE"),
    }
    return {**body, "evaluation_sha256": sha256(body)}


def self_test() -> dict[str, Any]:
    value = weighted_geometric_mean((0.9, 0.8), (0.5, 0.5))
    assert 0.84 < value < 0.86
    assert weighted_geometric_mean((0.0, 0.8), (0.5, 0.5)) == 0.0
    assert weighted_geometric_mean((0.8, 0.8), (0.4, 0.4)) == 0.0
    vertical = {
        "slug": "a11oy",
        "kernels": [{"id": kernel, "role": "test"} for kernel in DEFAULT_KERNEL_IDS],
    }
    receipt = {
        "proposal": {"risk": 0.2, "summary": "test"},
        "evidence": [{"source": "test", "claim": "fact", "sha256": sha256(b"fact")}],
        "blocks": [],
        "human_approved_input": True,
        "authorization": "NONE",
        "execution_performed": False,
        "public_effectors_enabled": False,
        "lambda_uniqueness": "CONJECTURE_1_OPEN",
    }
    result = evaluate_kernel_stack(vertical=vertical, proposal_receipt=receipt)
    assert result["state"] == "ADVISORY_CLEAR"
    assert result["authorization"] == "NONE"
    assert result["execution_performed"] is False
    assert result["external_kernel_artifact_loaded"] is False
    assert len(result["evaluation_sha256"]) == 64
    return {"ok": True, "evaluation_sha256": result["evaluation_sha256"]}


if __name__ == "__main__":
    print(json.dumps(self_test(), indent=2))
