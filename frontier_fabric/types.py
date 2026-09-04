from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class ClaimState(str, Enum):
    """Truth state carried by a capability or result."""

    LIVE = "LIVE"
    MEASURED = "MEASURED"
    DECLARED = "DECLARED"
    ADVISORY = "ADVISORY"
    SIMULATED = "SIMULATED"
    UNAVAILABLE = "UNAVAILABLE"
    BLOCKED = "BLOCKED"


class Decision(str, Enum):
    ALLOW = "ALLOW"
    HOLD = "HOLD"
    DENY = "DENY"


class EffectMode(str, Enum):
    READ_ONLY = "READ_ONLY"
    ADVISORY_ONLY = "ADVISORY_ONLY"
    SIMULATED_ONLY = "SIMULATED_ONLY"
    HUMAN_BOUND = "HUMAN_BOUND"


@dataclass(frozen=True, slots=True)
class ThemeSpec:
    id: str
    visual_grammar: str
    display_font: str
    body_font: str
    mono_font: str
    tokens: Mapping[str, str]
    signature_modules: tuple[str, ...]
    motion_language: str
    density: str


@dataclass(frozen=True, slots=True)
class ConnectorSpec:
    id: str
    provider: str
    purpose: str
    endpoint_template: str | None
    allowed_hosts: tuple[str, ...]
    allowed_path_prefixes: tuple[str, ...]
    path_params: Mapping[str, str] = field(default_factory=dict)
    query_params: tuple[str, ...] = ()
    max_bytes: int = 2_000_000
    media_types: tuple[str, ...] = ("application/json",)
    required_headers: Mapping[str, str] = field(default_factory=dict)
    state: ClaimState = ClaimState.DECLARED
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ModelBinding:
    repo_id: str
    role: str
    runtime_state: ClaimState
    decision_authority: bool = False
    required_evaluation: str = "Task-specific evaluation required before production reliance."


@dataclass(frozen=True, slots=True)
class KernelBinding:
    repo_id: str
    role: str
    enforcement: str
    runtime_state: ClaimState


@dataclass(frozen=True, slots=True)
class VerticalSpec:
    id: str
    display_name: str
    product_class: str
    lane: str
    operator_outcome: str
    unmet_need: str
    differentiator: str
    theme: ThemeSpec
    experience_modules: tuple[str, ...]
    connectors: tuple[ConnectorSpec, ...]
    models: tuple[ModelBinding, ...]
    kernels: tuple[KernelBinding, ...]
    effect_mode: EffectMode
    requires_human_bind: bool
    public_actuation: ClaimState
    evidence_contract: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceRef:
    connector_id: str
    locator: str
    revision: str | None = None
    digest: str | None = None


@dataclass(frozen=True, slots=True)
class Proposal:
    summary: str
    model_id: str | None
    model_revision: str | None
    confidence: float | None
    citations: tuple[SourceRef, ...]
    state: ClaimState
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class KernelResult:
    kernel_id: str
    passed: bool
    blocking: bool
    state: ClaimState
    reason: str
    evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvaluationRequest:
    vertical_id: str
    signal_id: str
    session_id: str
    actor_id: str
    payload: Mapping[str, Any]
    sources: tuple[SourceRef, ...] = ()
    proposal: Proposal | None = None
    requested_effect: str | None = None
    human_bind: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    vertical_id: str
    signal_id: str
    decision: Decision
    state: ClaimState
    reason: str
    proposal: Proposal
    kernel_results: tuple[KernelResult, ...]
    effect_mode: EffectMode
    human_bind_required: bool
    receipt: Mapping[str, Any]


def as_public_dict(value: Any) -> Any:
    """Recursively convert dataclasses/enums into JSON-safe public objects."""

    from dataclasses import fields, is_dataclass

    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: as_public_dict(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): as_public_dict(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, Sequence)) and not isinstance(value, (str, bytes, bytearray)):
        return [as_public_dict(item) for item in value]
    return value
