"""Provider-neutral frontier contracts for identity lifecycle and coverage.

The routes in this module are deliberately bounded contracts. They accept
already-authorized observations and never create live-provider, sanctions,
trading, legal, or cyber-effecting authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field

from .core import StrictModel

frontier_contracts = APIRouter(tags=["frontier-contracts"])

IdentityKind = Literal[
    "DESIGNATION_ADDED",
    "DESIGNATION_REMOVED",
    "IDENTITY_CHANGED",
    "DELISTED",
    "NAME_CHANGED",
    "FLAG_CHANGED",
    "OWNERSHIP_CHANGED",
]
SourceState = Literal["OBSERVED", "UNAVAILABLE", "STALE", "NOT_ATTEMPTED"]


class IdentityEventRequest(StrictModel):
    event_id: str = Field(..., min_length=1, max_length=128)
    entity_id: str = Field(..., min_length=1, max_length=128)
    event_time: str = Field(..., min_length=10, max_length=64)
    kind: IdentityKind
    source_id: str = Field(..., min_length=1, max_length=128)
    source_revision: str = Field(..., min_length=1, max_length=128)
    source_state: SourceState = "OBSERVED"
    payload: dict[str, Any] = Field(default_factory=dict)


class IdentityReplayRequest(StrictModel):
    prior_event_ids: list[str] = Field(default_factory=list, max_length=10_000)
    events: list[IdentityEventRequest] = Field(default_factory=list, max_length=10_000)
    chain_complete: bool = False
    identity_conflicts: int = Field(0, ge=0, le=10_000)


class CoverageRequest(StrictModel):
    source_id: str = Field(..., min_length=1, max_length=128)
    jurisdiction: str = Field(..., min_length=1, max_length=256)
    observed_at: str = Field(..., min_length=10, max_length=64)
    freshness_seconds: int = Field(..., ge=1, le=31_536_000)
    record_count: int = Field(0, ge=0, le=100_000_000)
    expected_scope: str = Field(..., min_length=1, max_length=512)
    state: SourceState = "OBSERVED"
    conflict_count: int = Field(0, ge=0, le=10_000)


@dataclass(frozen=True)
class IdentityEvent:
    event_id: str
    entity_id: str
    event_time: str
    kind: str
    source_id: str
    source_revision: str
    source_state: str
    payload: dict[str, Any]


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamps must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _identity_event(item: IdentityEventRequest | IdentityEvent) -> IdentityEvent:
    if isinstance(item, IdentityEvent):
        return item
    return IdentityEvent(
        event_id=item.event_id,
        entity_id=item.entity_id,
        event_time=item.event_time,
        kind=item.kind,
        source_id=item.source_id,
        source_revision=item.source_revision,
        source_state=item.source_state,
        payload=dict(item.payload),
    )


def replay_identity_lifecycle(
    *,
    prior_event_ids: list[str],
    incoming: list[IdentityEventRequest | IdentityEvent],
    chain_complete: bool,
    identity_conflicts: int = 0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Replay identity/designation events without producing unsafe clear screens."""
    seen = set(prior_event_ids)
    recovered: list[IdentityEvent] = []
    duplicates: list[str] = []
    for raw in incoming:
        event = _identity_event(raw)
        _parse_time(event.event_time)
        if event.event_id in seen:
            duplicates.append(event.event_id)
            continue
        seen.add(event.event_id)
        recovered.append(event)
    recovered.sort(key=lambda item: (_parse_time(item.event_time), item.event_id))

    active_designations: set[str] = set()
    identity_changes: list[str] = []
    for event in recovered:
        designation = str(
            event.payload.get("designation_id")
            or event.payload.get("target_event_id")
            or event.event_id
        )
        if event.kind == "DESIGNATION_ADDED":
            active_designations.add(designation)
        elif event.kind in {"DESIGNATION_REMOVED", "DELISTED"}:
            active_designations.discard(designation)
        elif event.kind in {
            "IDENTITY_CHANGED",
            "NAME_CHANGED",
            "FLAG_CHANGED",
            "OWNERSHIP_CHANGED",
        }:
            identity_changes.append(event.event_id)

    observed = [item for item in recovered if item.source_state == "OBSERVED"]
    degraded = [item for item in recovered if item.source_state != "OBSERVED"]
    stale = bool(degraded) or any(
        (now or datetime.now(timezone.utc)) - _parse_time(item.event_time)
        > timedelta(days=365)
        for item in observed
    )
    # Prior IDs carry no state payload; treating them as complete would allow an\n    # unseen designation to be cleared by a later removal event.\n    complete = bool(chain_complete) and not prior_event_ids and identity_conflicts == 0 and not degraded\n    if not recovered or not observed:
        screening_state = "UNAVAILABLE"
    elif complete and not active_designations and not stale:
        screening_state = "CLEAR"
    else:
        screening_state = "REVIEW_REQUIRED"

    if not observed:
        truth_label = "UNAVAILABLE"
    elif complete and not stale:
        truth_label = "MEASURED"
    else:
        truth_label = "REPORTED"

    return {
        "schema": "szl.killinchu-identity-lifecycle/v1",
        "entity_ids": sorted({item.entity_id for item in recovered}),
        "recovered_events": [
            {
                "event_id": item.event_id,
                "entity_id": item.entity_id,
                "event_time": item.event_time,
                "kind": item.kind,
                "source_id": item.source_id,
                "source_revision": item.source_revision,
                "source_state": item.source_state,
                "payload": item.payload,
            }
            for item in recovered
        ],
        "duplicate_event_ids": duplicates,
        "active_designations": sorted(active_designations),
        "identity_changes": identity_changes,
        "identity_state": (
            "COMPLETE" if complete else "CONFLICTED" if identity_conflicts else "INCOMPLETE"
        ),
        "source_state": "OBSERVED" if not degraded else "DEGRADED",
        "screening_state": screening_state,
        "definitive_clear_screening": screening_state == "CLEAR",
        "chain_complete": bool(chain_complete),
        "history_state": "OPAQUE_PRIOR_IDS" if prior_event_ids else "FULL_REPLAY",
        "identity_conflicts": identity_conflicts,
        "deadline_state_changed": False,
        "truth_label": truth_label,
        "disclaimer": "Screening state is evidence-bounded and is not a legal determination.",
    }


def evaluate_coverage(
    *,
    source_id: str,
    jurisdiction: str,
    observed_at: str,
    freshness_seconds: int,
    record_count: int,
    expected_scope: str,
    state: str = "OBSERVED",
    conflict_count: int = 0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return freshness and scope metadata without claiming universal coverage."""
    if state not in {"OBSERVED", "UNAVAILABLE", "STALE", "NOT_ATTEMPTED"}:
        raise ValueError(f"invalid source state: {state}")
    observed = _parse_time(observed_at)
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_seconds = max(0, int((current - observed).total_seconds()))
    if state != "OBSERVED":
        freshness_state = state
    elif age_seconds <= freshness_seconds:
        freshness_state = "FRESH"
    else:
        freshness_state = "STALE"
    bound = (
        freshness_state == "FRESH"
        and bool(expected_scope.strip())
        and record_count > 0
        and conflict_count == 0
    )
    return {
        "schema": "szl.terra-coverage-contract/v1",
        "source_id": source_id,
        "jurisdiction": jurisdiction,
        "observed_at": observed.isoformat(),
        "age_seconds": age_seconds,
        "freshness_seconds": freshness_seconds,
        "freshness_state": freshness_state,
        "record_count": record_count,
        "expected_scope": expected_scope,
        "conflict_count": conflict_count,
        "coverage_state": "BOUND" if bound else "UNAVAILABLE",
        "coverage_claim": "SCOPED_EVIDENCE_ONLY",
        "truth_label": "MEASURED" if bound else "UNAVAILABLE",
        "unavailable_reason": (
            None
            if bound
            else "source is stale, unavailable, empty, or has unresolved conflicts"
        ),
    }


@frontier_contracts.post("/killinchu/v1/identity/replay")
def identity_replay(request: IdentityReplayRequest) -> dict[str, Any]:
    try:
        return replay_identity_lifecycle(
            prior_event_ids=request.prior_event_ids,
            incoming=request.events,
            chain_complete=request.chain_complete,
            identity_conflicts=request.identity_conflicts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@frontier_contracts.post("/terra/v1/coverage/evaluate")
def terra_coverage(request: CoverageRequest) -> dict[str, Any]:
    try:
        return evaluate_coverage(
            source_id=request.source_id,
            jurisdiction=request.jurisdiction,
            observed_at=request.observed_at,
            freshness_seconds=request.freshness_seconds,
            record_count=request.record_count,
            expected_scope=request.expected_scope,
            state=request.state,
            conflict_count=request.conflict_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@frontier_contracts.get("/api/provenance/contract")
def provenance_contract() -> dict[str, Any]:
    return {
        "schema": "szl.source-to-decision-provenance/v1",
        "required_fields": [
            "source.revision",
            "source.observed_at",
            "source.state",
            "source.truth_label",
            "source.payload_sha256",
            "model_revision",
            "formula_revision",
            "policy_result",
            "approval_boundary",
            "freshness_seconds",
            "execution_state",
        ],
        "fail_closed_states": ["UNAVAILABLE", "STALE", "NOT_ATTEMPTED"],
        "effectors_enabled": False,
        "truth_label": "MEASURED",
    }


class ProfilingEvidenceRequest(StrictModel):
    worker_id: str = Field(..., min_length=1, max_length=128)
    deployed_revision: str = Field(..., min_length=1, max_length=128)
    captured_at: str = Field(..., min_length=10, max_length=64)
    duration_seconds: int = Field(..., ge=1, le=86_400)
    traffic_observed: bool = False
    source_map_state: Literal["AVAILABLE", "UNAVAILABLE", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"
    state: SourceState = "OBSERVED"
    cpu_profile_sha256: str | None = None
    heap_profile_sha256: str | None = None


class FinanceAdapterRequest(StrictModel):
    actor_id: str = Field(..., min_length=1, max_length=256)
    tenant_id: str = Field(..., min_length=1, max_length=256)
    scopes: list[str] = Field(default_factory=list, max_length=64)
    field_scopes: list[str] = Field(default_factory=list, max_length=256)
    query: str = Field(..., min_length=1, max_length=2_000)
    source_revision: str = Field(..., min_length=1, max_length=256)
    observed_at: str = Field(..., min_length=10, max_length=64)
    freshness_seconds: int = Field(..., ge=1, le=31_536_000)
    approval_id: str | None = Field(None, max_length=256)
    write_requested: bool = False


def _digest_ok(value: str | None) -> bool:
    return bool(value) and len(value) == 64 and all(
        char in "0123456789abcdefABCDEF" for char in value
    )


def profiling_evidence(
    *,
    worker_id: str,
    deployed_revision: str,
    captured_at: str,
    duration_seconds: int,
    traffic_observed: bool,
    source_map_state: str,
    state: str = "OBSERVED",
    cpu_profile_sha256: str | None = None,
    heap_profile_sha256: str | None = None,
) -> dict[str, Any]:
    """Bind CPU/heap profiling to a live revision and traffic window."""
    if not worker_id or not deployed_revision or deployed_revision == "UNAVAILABLE":
        raise ValueError("worker and exact deployed revision are required")
    if duration_seconds < 1:
        raise ValueError("profiling duration must be positive")
    _parse_time(captured_at)
    if state not in {"OBSERVED", "UNAVAILABLE", "STALE", "NOT_ATTEMPTED"}:
        raise ValueError(f"invalid profiling state: {state}")
    if source_map_state not in {"AVAILABLE", "UNAVAILABLE", "NOT_ATTEMPTED"}:
        raise ValueError(f"invalid source-map state: {source_map_state}")
    complete = _digest_ok(cpu_profile_sha256) and _digest_ok(heap_profile_sha256)
    if state != "OBSERVED":
        evidence_state = "UNAVAILABLE"
    elif not traffic_observed:
        evidence_state = "BLOCKED_TRAFFIC_PRECONDITION"
    elif source_map_state != "AVAILABLE":
        evidence_state = "BLOCKED_SOURCE_MAP"
    elif not complete:
        evidence_state = "INCOMPLETE"
    else:
        evidence_state = "OBSERVED"
    ready = evidence_state == "OBSERVED"
    return {
        "schema": "szl.lyte-profiling-evidence/v1",
        "worker_id": worker_id,
        "deployed_revision": deployed_revision,
        "captured_at": _parse_time(captured_at).isoformat(),
        "duration_seconds": duration_seconds,
        "traffic_observed": traffic_observed,
        "source_map_state": source_map_state,
        "cpu_profile_sha256": cpu_profile_sha256,
        "heap_profile_sha256": heap_profile_sha256,
        "evidence_state": evidence_state,
        "scope": "REVISION_BOUND",
        "historical_replay_claimed": False,
        "ready_for_analysis": ready,
        "truth_label": "MEASURED" if ready else "UNAVAILABLE",
        "unavailable_reason": None if ready else evidence_state,
    }


def authorize_finance_read(
    *,
    actor_id: str,
    tenant_id: str,
    scopes: list[str],
    field_scopes: list[str],
    query: str,
    source_revision: str,
    observed_at: str,
    freshness_seconds: int,
    approval_id: str | None = None,
    write_requested: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Authorize only fresh, scoped, read-only finance queries."""
    if not actor_id or not tenant_id or not query or not source_revision:
        raise ValueError("actor, tenant, query, and source revision are required")
    if freshness_seconds < 1:
        raise ValueError("freshness_seconds must be positive")
    observed = _parse_time(observed_at)
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_seconds = max(0, int((current - observed).total_seconds()))
    freshness_state = "FRESH" if age_seconds <= freshness_seconds else "STALE"
    read_scopes = bool(scopes) and all(scope.startswith("read:") for scope in scopes)
    writes_allowed = False
    if write_requested:
        decision = "DENY_WRITE"
        reason = "write authority is outside the adapter contract"
    elif not read_scopes:
        decision = "DENY_SCOPE"
        reason = "every scope must be explicitly read-scoped"
    elif source_revision == "UNAVAILABLE":
        decision = "REVIEW_REQUIRED"
        reason = "source revision is unavailable"
    elif freshness_state != "FRESH":
        decision = "REVIEW_REQUIRED"
        reason = "source observation is stale"
    elif not approval_id:
        decision = "REVIEW_REQUIRED"
        reason = "human approval receipt is required before data release"
    else:
        decision = "ALLOW_READ"
        reason = None
    audit_material = {
        "actor_id": actor_id,
        "tenant_id": tenant_id,
        "scopes": sorted(scopes),
        "field_scopes": sorted(field_scopes),
        "query": query,
        "source_revision": source_revision,
        "observed_at": observed.isoformat(),
        "approval_id": approval_id,
        "write_requested": write_requested,
        "decision": decision,
    }
    from .evidence_contract import sha256_payload
    return {
        "schema": "szl.finance-read-only-adapter/v1",
        "actor_id": actor_id,
        "tenant_id": tenant_id,
        "scopes": sorted(scopes),
        "field_scopes": sorted(field_scopes),
        "source_revision": source_revision,
        "observed_at": observed.isoformat(),
        "age_seconds": age_seconds,
        "freshness_seconds": freshness_seconds,
        "freshness_state": freshness_state,
        "decision": decision,
        "reason": reason,
        "approval_id": approval_id,
        "human_approval_required": True,
        "writes_enabled": writes_allowed,
        "audit_receipt_sha256": sha256_payload(audit_material),
        "truth_label": "MEASURED",
    }


@frontier_contracts.post("/lyte/v1/profiling/evidence")
def lyte_profiling(request: ProfilingEvidenceRequest) -> dict[str, Any]:
    try:
        return profiling_evidence(
            worker_id=request.worker_id,
            deployed_revision=request.deployed_revision,
            captured_at=request.captured_at,
            duration_seconds=request.duration_seconds,
            traffic_observed=request.traffic_observed,
            source_map_state=request.source_map_state,
            state=request.state,
            cpu_profile_sha256=request.cpu_profile_sha256,
            heap_profile_sha256=request.heap_profile_sha256,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@frontier_contracts.post("/finance/v1/adapter/authorize")
def finance_adapter(request: FinanceAdapterRequest) -> dict[str, Any]:
    try:
        return authorize_finance_read(
            actor_id=request.actor_id,
            tenant_id=request.tenant_id,
            scopes=request.scopes,
            field_scopes=request.field_scopes,
            query=request.query,
            source_revision=request.source_revision,
            observed_at=request.observed_at,
            freshness_seconds=request.freshness_seconds,
            approval_id=request.approval_id,
            write_requested=request.write_requested,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


__all__ = [
    "CoverageRequest",
    "FinanceAdapterRequest",
    "IdentityEvent",
    "IdentityEventRequest",
    "IdentityReplayRequest",
    "ProfilingEvidenceRequest",
    "authorize_finance_read",
    "evaluate_coverage",
    "frontier_contracts",
    "provenance_contract",
    "profiling_evidence",
    "replay_identity_lifecycle",
]
