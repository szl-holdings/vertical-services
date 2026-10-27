"""Provider-neutral frontier contracts for identity lifecycle and coverage.

The routes in this module are deliberately bounded contracts. They accept
already-authorized observations and never create live-provider, sanctions,
trading, legal, or cyber-effecting authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
        > __import__("datetime").timedelta(days=365)
        for item in observed
    )
    complete = bool(chain_complete) and identity_conflicts == 0 and not degraded
    if not recovered or not observed:
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


__all__ = [
    "CoverageRequest",
    "IdentityEvent",
    "IdentityEventRequest",
    "IdentityReplayRequest",
    "evaluate_coverage",
    "frontier_contracts",
    "provenance_contract",
    "replay_identity_lifecycle",
]
