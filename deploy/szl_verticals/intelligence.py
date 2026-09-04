"""Model and kernel fabric for the six canonical SZL verticals.

The fabric is source-bound and fail-closed. It prepares or invokes a domain
model only when an operator has bound a fixed HTTPS endpoint, allowlisted host,
protocol, credential, and exact declared model revision through environment
variables. Caller-supplied URLs are never accepted. Consequential effectors
remain disabled and all model output requires human review.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import Field, field_validator

from .contract import advisory_lambda, canonical_vertical
from .core import SHA40, SessionScope, StrictModel, build_info
from .operational import STORE, vertical_readiness
from .profiles import ALIASES, VERTICALS

intelligence = APIRouter(tags=["vertical-intelligence"])

HEX64 = re.compile(r"^[0-9a-f]{64}$")
AXIS_ID = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
MODEL_ALIAS = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
DEFAULT_ALLOWED_HOSTS = frozenset(
    {"router.huggingface.co", "api-inference.huggingface.co"}
)
MAX_PROVIDER_BYTES = 2_000_000
MAX_GENERATED_CHARS = 12_000

MODEL_ASSETS: dict[str, dict[str, Any]] = {
    "khipu-1.5b": {
        "repo_id": "SZLHOLDINGS/SZL-Khipu-1.5B",
        "artifact_class": "TRAINED_MODEL",
        "runtime": "REMOTE_EXACT_REVISION_REQUIRED",
        "role": "grounded domain synthesis and structured decision briefs",
        "license": "apache-2.0",
        "endpoint_env": "SZL_MODEL_ENDPOINT_KHIPU_1_5B",
        "revision_env": "SZL_MODEL_REVISION_KHIPU_1_5B",
        "protocol_env": "SZL_MODEL_PROTOCOL_KHIPU_1_5B",
        "token_env": "HF_TOKEN",
    },
    "receipt-agent": {
        "repo_id": "SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2",
        "artifact_class": "TRAINED_ADAPTER",
        "runtime": "REMOTE_EXACT_REVISION_REQUIRED",
        "role": "citation, evidence, receipt, and structured-output review",
        "license": "apache-2.0",
        "endpoint_env": "SZL_MODEL_ENDPOINT_RECEIPT_AGENT",
        "revision_env": "SZL_MODEL_REVISION_RECEIPT_AGENT",
        "protocol_env": "SZL_MODEL_PROTOCOL_RECEIPT_AGENT",
        "token_env": "HF_TOKEN",
    },
    "a11oy-mini": {
        "repo_id": "SZLHOLDINGS/A11OY-MINI",
        "artifact_class": "QUANTIZED_DERIVATIVE",
        "runtime": "REMOTE_EXACT_REVISION_REQUIRED",
        "role": "low-latency bounded edge brief and offline-compatible fallback",
        "license": "apache-2.0",
        "endpoint_env": "SZL_MODEL_ENDPOINT_A11OY_MINI",
        "revision_env": "SZL_MODEL_REVISION_A11OY_MINI",
        "protocol_env": "SZL_MODEL_PROTOCOL_A11OY_MINI",
        "token_env": "HF_TOKEN",
    },
    "nemo-recipe": {
        "repo_id": "SZLHOLDINGS/szl-nemo",
        "artifact_class": "RECIPE_CONFORMANCE",
        "runtime": "NOT_AN_INFERENCE_CHECKPOINT",
        "role": "training and serving recipe-conformance review",
        "license": "apache-2.0",
        "invokable": False,
    },
}

KERNEL_ASSETS: dict[str, dict[str, Any]] = {
    "kernel-suite": {
        "repo_id": "SZLHOLDINGS/szl-kernels",
        "role": "portable feature, chain, and deterministic compute primitives",
        "execution_state": "LOCAL_CONTRACT_BOUND",
    },
    "lambda-gate": {
        "repo_id": "SZLHOLDINGS/szl-lambda-gate",
        "role": "weighted geometric advisory gate; uniqueness remains Conjecture 1",
        "execution_state": "LOCAL_REFERENCE_IMPLEMENTATION",
    },
    "invariants": {
        "repo_id": "SZLHOLDINGS/szl-invariants",
        "role": "source, evidence, schema, and authority invariants",
        "execution_state": "LOCAL_REFERENCE_IMPLEMENTATION",
    },
    "blocked": {
        "repo_id": "SZLHOLDINGS/szl-blocked",
        "role": "deny-by-default high-risk and compliance boundary",
        "execution_state": "LOCAL_REFERENCE_IMPLEMENTATION",
    },
    "receipt-attn": {
        "repo_id": "SZLHOLDINGS/szl-receipt-attn",
        "role": "evidence coverage and receipt-linked output attention",
        "execution_state": "LOCAL_REFERENCE_IMPLEMENTATION",
    },
    "block-kv": {
        "repo_id": "SZLHOLDINGS/szl-block-kv",
        "role": "bounded context budget and session-isolated memory contract",
        "execution_state": "LOCAL_REFERENCE_IMPLEMENTATION",
    },
}

VERTICAL_INTELLIGENCE: dict[str, dict[str, Any]] = {
    "sentra": {
        "primary_job": "Explain the shortest evidence-backed path from exposure to business blast radius.",
        "unserved_job": "Join code, identity, cloud, runtime, control, owner, and business impact in one reviewable attack path.",
        "reference_patterns": [
            "Wiz security graph",
            "Cortex XSIAM unified SecOps",
            "New Relic operational context",
        ],
        "models": ["receipt-agent", "khipu-1.5b", "a11oy-mini"],
        "kernels": ["blocked", "invariants", "lambda-gate", "receipt-attn", "block-kv"],
        "tasks": {
            "attack-path-review": "receipt-agent",
            "control-gap-analysis": "khipu-1.5b",
            "incident-summary": "a11oy-mini",
            "remediation-review": "receipt-agent",
        },
        "minimum_evidence": 2,
        "lambda_floor": 0.82,
        "context_budget_bytes": 96_000,
        "novel_capabilities": [
            "AI action exposure graph from model or tool call to cloud blast radius",
            "owner-resolved remediation packet with source and rollback receipts",
            "counterfactual containment replay before an operator-approved change",
        ],
    },
    "lyte": {
        "primary_job": "Trace a technical signal to the customer journey and economic outcome it changes.",
        "unserved_job": "Unify service, agent, delivery, customer, revenue, cost, and risk telemetry without flattening causality into a dashboard.",
        "reference_patterns": [
            "New Relic intelligent observability",
            "Honeycomb high-cardinality investigations",
            "Boss business observability",
            "Dynatrace causal context",
        ],
        "models": ["khipu-1.5b", "receipt-agent", "a11oy-mini"],
        "kernels": ["kernel-suite", "invariants", "lambda-gate", "receipt-attn", "block-kv"],
        "tasks": {
            "root-cause-hypothesis": "khipu-1.5b",
            "business-impact": "khipu-1.5b",
            "slo-investigation": "a11oy-mini",
            "change-risk": "receipt-agent",
        },
        "minimum_evidence": 2,
        "lambda_floor": 0.78,
        "context_budget_bytes": 128_000,
        "novel_capabilities": [
            "business-causality braid linking traces, decisions, journeys, and outcomes",
            "agent, tool, and model trace with token, latency, energy, quality, and outcome receipts",
            "decision replay comparing what changed, why, and whether the business recovered",
        ],
    },
    "killinchu": {
        "primary_job": "Fuse conflicting observations into a bounded common operating picture and rehearse options under human authority.",
        "unserved_job": "Show sensor disagreement, uncertainty, policy, communications degradation, and decision lineage together instead of hiding them behind one risk score.",
        "reference_patterns": [
            "True Anomaly Mosaic",
            "Anduril Lattice",
            "Windward all-source maritime intelligence",
            "NVIDIA digital twins",
        ],
        "models": ["a11oy-mini", "khipu-1.5b", "receipt-agent"],
        "kernels": ["blocked", "invariants", "lambda-gate", "receipt-attn", "block-kv", "kernel-suite"],
        "tasks": {
            "track-anomaly-review": "a11oy-mini",
            "route-risk": "khipu-1.5b",
            "scenario-rehearsal": "khipu-1.5b",
            "debrief": "receipt-agent",
        },
        "minimum_evidence": 3,
        "lambda_floor": 0.86,
        "context_budget_bytes": 96_000,
        "novel_capabilities": [
            "truth-disagreement layer preserving which sensors conflict and why",
            "branching course-of-action rehearsal with simulated effects and signed debrief",
            "degraded-network receipt continuity with later reconciliation and no public actuation",
        ],
    },
    "finance": {
        "primary_job": "Turn filings and market observations into a source-linked thesis, scenario tree, and risk review without placing a trade.",
        "unserved_job": "Keep thesis history, contradictory evidence, assumptions, probability changes, and decision quality in one auditable ledger.",
        "reference_patterns": [
            "Bloomberg Terminal and ASKB",
            "BQuant research sandbox",
            "OpenBB connect-once data integration",
        ],
        "models": ["khipu-1.5b", "receipt-agent", "a11oy-mini"],
        "kernels": ["blocked", "invariants", "lambda-gate", "receipt-attn", "block-kv", "kernel-suite"],
        "tasks": {
            "filing-research": "receipt-agent",
            "scenario-analysis": "khipu-1.5b",
            "thesis-review": "khipu-1.5b",
            "risk-summary": "a11oy-mini",
        },
        "minimum_evidence": 2,
        "lambda_floor": 0.80,
        "context_budget_bytes": 128_000,
        "novel_capabilities": [
            "thesis-decay ledger recording assumption drift and contradictory evidence",
            "filing-to-scenario graph with every claim attached to a source digest",
            "decision-quality review separated from market outcome with trading disabled",
        ],
    },
    "terra": {
        "primary_job": "Build a parcel-to-capital evidence twin that makes assumptions and constraints inspectable.",
        "unserved_job": "Join parcel, ownership, lease, condition, permitting, underwriting, climate, and community constraints before a deal reaches approval.",
        "reference_patterns": [
            "VTS asset and lease intelligence",
            "Overture Maps shared geospatial schema",
            "NVIDIA digital twins",
        ],
        "models": ["khipu-1.5b", "receipt-agent", "a11oy-mini"],
        "kernels": ["kernel-suite", "invariants", "lambda-gate", "receipt-attn", "block-kv"],
        "tasks": {
            "parcel-diligence": "receipt-agent",
            "lease-obligation-review": "receipt-agent",
            "underwriting-scenario": "khipu-1.5b",
            "portfolio-risk": "a11oy-mini",
        },
        "minimum_evidence": 2,
        "lambda_floor": 0.80,
        "context_budget_bytes": 128_000,
        "novel_capabilities": [
            "parcel-to-capital twin spanning public facts, lease obligations, condition, and assumptions",
            "counterfactual underwriting with sensitivity receipts instead of one opaque valuation",
            "constraint graph for permits, violations, climate exposure, and community impact",
        ],
    },
    "counsel": {
        "primary_job": "Turn authority and matter evidence into an attorney-reviewable argument and obligation graph.",
        "unserved_job": "Preserve source passage, citation status, counterargument, deadline, obligation, and work-product lineage in one matter twin.",
        "reference_patterns": [
            "Harvey Agents, Vault, Knowledge, and Spaces",
            "Lexis citation validation",
            "CourtListener and RECAP public authority graph",
        ],
        "models": ["receipt-agent", "khipu-1.5b", "a11oy-mini"],
        "kernels": ["blocked", "invariants", "lambda-gate", "receipt-attn", "block-kv"],
        "tasks": {
            "authority-research": "receipt-agent",
            "deadline-review": "a11oy-mini",
            "argument-map": "khipu-1.5b",
            "document-issue-spotting": "receipt-agent",
        },
        "minimum_evidence": 2,
        "lambda_floor": 0.84,
        "context_budget_bytes": 128_000,
        "novel_capabilities": [
            "authority graph carrying passage digests, treatment state, and jurisdiction",
            "argument replay preserving supporting and adverse evidence side by side",
            "matter twin joining deadlines, obligations, work product, approvals, and source receipts",
        ],
    },
}


class IntelligencePlanRequest(StrictModel):
    """Bounded model-planning request; raw context is never returned or stored."""

    task: str = Field(min_length=2, max_length=64)
    objective: str = Field(min_length=1, max_length=800)
    context: str = Field(default="", max_length=12_000)
    axes: dict[str, float]
    evidence_sha256: list[str] = Field(default_factory=list, max_length=64)
    preferred_model: str | None = Field(default=None, max_length=64)

    @field_validator("task")
    @classmethod
    def normalize_task(cls, value: str) -> str:
        normalized = value.strip().lower()
        if MODEL_ALIAS.fullmatch(normalized) is None:
            raise ValueError("task must be a lowercase bounded identifier")
        return normalized

    @field_validator("objective")
    @classmethod
    def normalize_objective(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("objective must not be blank")
        return normalized

    @field_validator("axes")
    @classmethod
    def validate_axes(cls, value: dict[str, float]) -> dict[str, float]:
        if not 2 <= len(value) <= 16:
            raise ValueError("axes must contain between 2 and 16 measurements")
        clean: dict[str, float] = {}
        for key, item in value.items():
            normalized = key.strip().lower()
            numeric = float(item)
            if AXIS_ID.fullmatch(normalized) is None:
                raise ValueError(f"invalid axis identifier: {key!r}")
            if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
                raise ValueError(f"axis {normalized!r} must be finite and within [0,1]")
            clean[normalized] = numeric
        return clean

    @field_validator("evidence_sha256")
    @classmethod
    def validate_evidence(cls, value: list[str]) -> list[str]:
        clean = [item.strip().lower() for item in value]
        if any(HEX64.fullmatch(item) is None for item in clean):
            raise ValueError("every evidence reference must be an exact SHA-256 digest")
        if len(clean) != len(set(clean)):
            raise ValueError("evidence SHA-256 digests must be unique")
        return clean

    @field_validator("preferred_model")
    @classmethod
    def validate_preferred_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if MODEL_ALIAS.fullmatch(normalized) is None:
            raise ValueError("preferred_model must be a bounded model alias")
        return normalized


class IntelligenceInvokeRequest(IntelligencePlanRequest):
    max_new_tokens: int = Field(default=384, ge=32, le=1024)
    temperature: float = Field(default=0.0, ge=0.0, le=0.7)


def _allowed_hosts() -> set[str]:
    configured = {
        item.strip().lower()
        for item in os.environ.get("SZL_INFERENCE_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    }
    return set(DEFAULT_ALLOWED_HOSTS) | configured


def _model_binding(alias: str) -> dict[str, Any]:
    spec = MODEL_ASSETS[alias]
    if spec.get("invokable") is False:
        return {
            **spec,
            "alias": alias,
            "state": "NOT_INVOKABLE",
            "endpoint": None,
            "revision": "UNAVAILABLE",
            "revision_evidence": "NOT_APPLICABLE",
            "protocol": None,
            "credential_present": False,
            "credential_value_exposed": False,
            "blockers": ["NOT_AN_INFERENCE_CHECKPOINT"],
        }

    endpoint = os.environ.get(spec["endpoint_env"], "").strip()
    revision = os.environ.get(spec["revision_env"], "").strip().lower()
    protocol = os.environ.get(spec["protocol_env"], "hf-text-generation").strip().lower()
    token = os.environ.get(spec["token_env"], "").strip()
    state = "BOUND"
    blockers: list[str] = []
    host = ""

    if not endpoint:
        state = "UNAVAILABLE"
        blockers.append("ENDPOINT_UNAVAILABLE")
    else:
        parsed = urlparse(endpoint)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            state = "INVALID"
            blockers.append("INVALID_HTTPS_ENDPOINT")
        if parsed.query or parsed.fragment:
            state = "INVALID"
            blockers.append("ENDPOINT_QUERY_OR_FRAGMENT_FORBIDDEN")
        if host not in _allowed_hosts():
            state = "BLOCKED"
            blockers.append("ENDPOINT_HOST_NOT_ALLOWLISTED")
    if SHA40.fullmatch(revision) is None:
        if state == "BOUND":
            state = "UNPINNED"
        blockers.append("EXACT_MODEL_REVISION_REQUIRED")
    if protocol not in {"hf-text-generation", "openai-chat"}:
        state = "INVALID"
        blockers.append("UNSUPPORTED_PROTOCOL")
    if not token:
        if state == "BOUND":
            state = "AUTH_REQUIRED"
        blockers.append("MODEL_CREDENTIAL_UNAVAILABLE")

    return {
        **spec,
        "alias": alias,
        "state": state,
        "endpoint": endpoint or None,
        "endpoint_host": host or None,
        "revision": revision if SHA40.fullmatch(revision) else "UNAVAILABLE",
        "revision_evidence": "OPERATOR_DECLARED" if SHA40.fullmatch(revision) else "UNAVAILABLE",
        "protocol": protocol,
        "credential_present": bool(token),
        "credential_value_exposed": False,
        "blockers": sorted(set(blockers)),
    }


def intelligence_profile(vertical: str) -> dict[str, Any]:
    canonical = canonical_vertical(vertical)
    profile = VERTICAL_INTELLIGENCE[canonical]
    return {
        "schema": "szl.vertical-intelligence-profile/v1",
        "vertical": canonical,
        "product": VERTICALS[canonical]["product"],
        "primary_job": profile["primary_job"],
        "unserved_job": profile["unserved_job"],
        "reference_patterns": [
            {
                "pattern": item,
                "source_class": "PUBLIC_PRODUCT_PATTERN",
                "proprietary_code_copied": False,
                "proprietary_data_copied": False,
            }
            for item in profile["reference_patterns"]
        ],
        "tasks": dict(profile["tasks"]),
        "models": [_model_binding(alias) for alias in profile["models"]],
        "kernels": [
            {"alias": alias, **KERNEL_ASSETS[alias]}
            for alias in profile["kernels"]
        ],
        "novel_capabilities": [
            {"name": item, "state": "CONTRACT_READY"}
            for item in profile["novel_capabilities"]
        ],
        "policy": {
            "minimum_evidence": profile["minimum_evidence"],
            "lambda_floor": profile["lambda_floor"],
            "context_budget_bytes": profile["context_budget_bytes"],
            "caller_supplied_model_endpoints_allowed": False,
            "public_or_licensed_data_only": True,
            "effectors_enabled": False,
            "human_approval_required": True,
        },
        "truth_label": "MEASURED",
    }


def _select_model(canonical: str, request: IntelligencePlanRequest) -> str:
    profile = VERTICAL_INTELLIGENCE[canonical]
    if request.task not in profile["tasks"]:
        allowed = ", ".join(sorted(profile["tasks"]))
        raise HTTPException(
            422,
            f"task {request.task!r} is not allowed; choose one of: {allowed}",
        )
    selected = profile["tasks"][request.task]
    if request.preferred_model is not None:
        if request.preferred_model not in profile["models"]:
            raise HTTPException(422, "preferred_model is not approved for this vertical")
        if MODEL_ASSETS[request.preferred_model].get("invokable") is False:
            raise HTTPException(422, "preferred_model is not an inference checkpoint")
        selected = request.preferred_model
    return selected


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_intelligence_plan(
    vertical: str,
    request: IntelligencePlanRequest,
    session_scope: str,
) -> dict[str, Any]:
    requested = vertical.strip().lower()
    canonical = canonical_vertical(requested)
    profile = VERTICAL_INTELLIGENCE[canonical]
    selected = _select_model(canonical, request)
    binding = _model_binding(selected)
    readiness = vertical_readiness(canonical, session_scope=session_scope)
    observations = STORE.counts(vertical=canonical, session_scope=session_scope)
    lambda_result = advisory_lambda(request.axes)
    context_bytes = len(request.context.encode("utf-8"))

    gates = {
        "task_allowlisted": True,
        "source_bound": readiness["requirements"]["source_bound"],
        "vertical_ready": readiness["ready"],
        "model_endpoint_bound": binding["state"] == "BOUND",
        "model_revision_declared": binding["revision"] != "UNAVAILABLE",
        "evidence_floor_met": (
            len(request.evidence_sha256) + observations["observations"]
            >= profile["minimum_evidence"]
        ),
        "lambda_floor_met": lambda_result["score"] >= profile["lambda_floor"],
        "context_budget_met": context_bytes <= profile["context_budget_bytes"],
        "effectors_disabled": True,
    }
    blockers: list[str] = []
    blocker_map = {
        "source_bound": "SOURCE_UNBOUND",
        "vertical_ready": "VERTICAL_NOT_READY",
        "model_endpoint_bound": "MODEL_ENDPOINT_NOT_BOUND",
        "model_revision_declared": "MODEL_REVISION_NOT_DECLARED",
        "evidence_floor_met": "EVIDENCE_BELOW_MINIMUM",
        "lambda_floor_met": "LAMBDA_BELOW_INFERENCE_FLOOR",
        "context_budget_met": "CONTEXT_BUDGET_EXCEEDED",
        "effectors_disabled": "EFFECTOR_BOUNDARY_BROKEN",
    }
    for gate, blocker in blocker_map.items():
        if not gates[gate]:
            blockers.append(blocker)
    blockers.extend(binding.get("blockers", []))
    blockers = sorted(set(blockers))

    basis = {
        "schema": "szl.vertical-intelligence-plan/v1",
        "requested_vertical": requested,
        "vertical": canonical,
        "task": request.task,
        "objective_sha256": hashlib.sha256(request.objective.encode("utf-8")).hexdigest(),
        "context_sha256": hashlib.sha256(request.context.encode("utf-8")).hexdigest(),
        "context_bytes": context_bytes,
        "evidence_sha256": request.evidence_sha256,
        "session_observation_count": observations["observations"],
        "lambda_advisory": lambda_result,
        "selected_model": {
            "alias": selected,
            "repo_id": binding["repo_id"],
            "revision": binding["revision"],
            "revision_evidence": binding["revision_evidence"],
            "state": binding["state"],
            "protocol": binding["protocol"],
        },
        "kernels": [
            {
                "alias": alias,
                "repo_id": KERNEL_ASSETS[alias]["repo_id"],
                "execution_state": KERNEL_ASSETS[alias]["execution_state"],
            }
            for alias in profile["kernels"]
        ],
        "gates": gates,
        "blockers": blockers,
        "decision": "READY_FOR_INFERENCE" if not blockers else "ABSTAIN",
        "can_execute": False,
        "effectors_enabled": False,
        "human_approval_required": True,
        "raw_context_returned": False,
        "raw_context_stored": False,
        "source": build_info()["build"],
    }
    basis_sha256 = hashlib.sha256(_canonical_json(basis).encode("utf-8")).hexdigest()
    return {
        **basis,
        "receipt": {
            "schema": "szl.vertical-intelligence-plan-receipt/v1",
            "algorithm": "SHA-256",
            "basis_sha256": basis_sha256,
            "persistent_signature_claimed": False,
            "session_token_recorded": False,
        },
        "truth_label": "MODELED",
    }


def _system_instruction(canonical: str, task: str) -> str:
    profile = VERTICAL_INTELLIGENCE[canonical]
    return (
        "You are a bounded SZL domain analyst. Use only supplied context and "
        "evidence identifiers. Separate observation, inference, uncertainty, and "
        "recommendation. Never claim authority, execute an action, place a trade, "
        "file legal work, remediate infrastructure, or control a physical effector. "
        f"Vertical: {canonical}. Task: {task}. Primary job: {profile['primary_job']} "
        "Return concise JSON with keys summary, observations, inferences, "
        "uncertainties, recommendation, and required_human_review."
    )


def _extract_generated_text(protocol: str, payload: Any) -> str:
    if protocol == "hf-text-generation":
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            value = payload[0].get("generated_text")
        elif isinstance(payload, dict):
            value = payload.get("generated_text")
        else:
            value = None
    else:
        try:
            value = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            value = None
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(502, "model provider returned no supported generated text")
    return value.strip()[:MAX_GENERATED_CHARS]


async def _invoke_provider(
    binding: dict[str, Any],
    canonical: str,
    request: IntelligenceInvokeRequest,
) -> tuple[str, int]:
    token = os.environ.get(binding["token_env"], "").strip()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "szl-vertical-intelligence/1.0",
        "X-SZL-Model-Revision": binding["revision"],
    }
    system = _system_instruction(canonical, request.task)
    user = _canonical_json(
        {
            "objective": request.objective,
            "context": request.context,
            "axes": request.axes,
            "evidence_sha256": request.evidence_sha256,
        }
    )
    if binding["protocol"] == "hf-text-generation":
        provider_payload = {
            "inputs": f"SYSTEM:\n{system}\n\nUSER:\n{user}\n\nASSISTANT:",
            "parameters": {
                "max_new_tokens": request.max_new_tokens,
                "temperature": request.temperature,
                "return_full_text": False,
            },
        }
    else:
        provider_payload = {
            "model": binding["repo_id"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": request.max_new_tokens,
            "temperature": request.temperature,
        }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=8.0),
            follow_redirects=False,
        ) as client:
            response = await client.post(
                binding["endpoint"], headers=headers, json=provider_payload
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            502,
            f"model provider unavailable: {exc.__class__.__name__}",
        ) from exc

    if 300 <= response.status_code < 400:
        raise HTTPException(502, "model provider redirect refused")
    if response.status_code < 200 or response.status_code >= 300:
        raise HTTPException(502, f"model provider returned HTTP {response.status_code}")
    if len(response.content) > MAX_PROVIDER_BYTES:
        raise HTTPException(502, "model provider response exceeded the bounded size")
    if "json" not in response.headers.get("content-type", "").lower():
        raise HTTPException(502, "model provider response was not JSON")
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(502, "model provider returned invalid JSON") from exc
    return _extract_generated_text(binding["protocol"], payload), response.status_code


@intelligence.get("/api/intelligence")
def intelligence_catalog() -> dict[str, Any]:
    return {
        "schema": "szl.vertical-intelligence-catalog/v1",
        "verticals": {
            vertical: {
                "product": VERTICALS[vertical]["product"],
                "profile": f"/api/verticals/{vertical}/intelligence",
                "plan": f"/api/verticals/{vertical}/intelligence/plan",
                "invoke": f"/api/verticals/{vertical}/intelligence/invoke",
                "showcase": f"/intelligence/{vertical}",
                "tasks": sorted(VERTICAL_INTELLIGENCE[vertical]["tasks"]),
            }
            for vertical in VERTICAL_INTELLIGENCE
        },
        "model_assets": MODEL_ASSETS,
        "kernel_assets": KERNEL_ASSETS,
        "aliases": ALIASES,
        "caller_supplied_endpoints_allowed": False,
        "effectors_enabled": False,
        "truth_label": "MEASURED",
    }


@intelligence.get("/api/verticals/{vertical}/intelligence")
def vertical_intelligence(vertical: str) -> dict[str, Any]:
    return intelligence_profile(vertical)


@intelligence.post("/api/verticals/{vertical}/intelligence/plan")
def vertical_intelligence_plan(
    vertical: str,
    request: IntelligencePlanRequest,
    session: SessionScope,
) -> dict[str, Any]:
    return build_intelligence_plan(vertical, request, session)


@intelligence.post("/api/verticals/{vertical}/intelligence/invoke")
async def vertical_intelligence_invoke(
    vertical: str,
    request: IntelligenceInvokeRequest,
    session: SessionScope,
) -> dict[str, Any]:
    plan = build_intelligence_plan(vertical, request, session)
    if plan["decision"] != "READY_FOR_INFERENCE":
        raise HTTPException(503, detail={"error": "INFERENCE_NOT_READY", "plan": plan})

    canonical = plan["vertical"]
    selected = plan["selected_model"]["alias"]
    binding = _model_binding(selected)
    generated, provider_status = await _invoke_provider(binding, canonical, request)
    output_sha256 = hashlib.sha256(generated.encode("utf-8")).hexdigest()
    invocation_basis = {
        "schema": "szl.vertical-intelligence-invocation/v1",
        "vertical": canonical,
        "task": request.task,
        "plan_receipt_sha256": plan["receipt"]["basis_sha256"],
        "model_repo_id": binding["repo_id"],
        "model_revision": binding["revision"],
        "model_revision_evidence": binding["revision_evidence"],
        "protocol": binding["protocol"],
        "provider_http_status": provider_status,
        "output_sha256": output_sha256,
        "can_execute": False,
        "effectors_enabled": False,
        "human_approval_required": True,
    }
    return {
        **invocation_basis,
        "output": generated,
        "receipt": {
            "schema": "szl.vertical-intelligence-invocation-receipt/v1",
            "algorithm": "SHA-256",
            "basis_sha256": hashlib.sha256(
                _canonical_json(invocation_basis).encode("utf-8")
            ).hexdigest(),
            "persistent_signature_claimed": False,
        },
        "raw_context_returned": False,
        "raw_context_stored": False,
        "truth_label": "MODEL_GENERATED",
    }


__all__ = [
    "IntelligenceInvokeRequest",
    "IntelligencePlanRequest",
    "KERNEL_ASSETS",
    "MODEL_ASSETS",
    "VERTICAL_INTELLIGENCE",
    "build_intelligence_plan",
    "intelligence",
    "intelligence_profile",
]
