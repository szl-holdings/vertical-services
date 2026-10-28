"""Provider-neutral frontier contracts for identity lifecycle and coverage.

The routes in this module are deliberately bounded contracts. They accept
already-authorized observations and never create live-provider, sanctions,
trading, legal, or cyber-effecting authority.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from .core import StrictModel
from .evidence_contract import sha256_payload

frontier_contracts = APIRouter(tags=["frontier-contracts"])

# Time admission policy for Killinchu replay, Terra coverage and Finance
# authorization: an observation may be at most this many seconds ahead of the
# server clock. Anything later is rejected, never clamped to fresh. This is an
# explicit policy constant pending owner ratification; change it only together
# with tests/test_time_admission.py.
ALLOWED_FUTURE_SKEW_SECONDS = 300
IDENTITY_STALE_AFTER = timedelta(days=365)
DESIGNATION_SNAPSHOT_SCHEMA = "szl.killinchu-designation-snapshot/v1"

# (entity_id, source_id, events of that stream in replay order, prior snapshot
# or None) -> True only when that stream's history is authenticated as complete.
HistoryVerifier = Callable[[str, str, tuple["IdentityEvent", ...], "dict[str, Any] | None"], bool]


def contract_clock() -> datetime:
    """Server clock for time admission; routes depend on it so it can be injected."""
    return datetime.now(timezone.utc)


def identity_history_verifier() -> HistoryVerifier | None:
    """No verifier is configured: caller-supplied history is never authenticated.

    An owner-approved verifier (for example one backed by admitted source
    snapshots) may be provided through this dependency. Until then a caller's
    ``chain_complete`` claim cannot, on its own, produce a CLEAR screen.
    """
    return None


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


class DesignationSnapshotRequest(StrictModel):
    entity_id: str = Field(..., min_length=1, max_length=128)
    source_id: str = Field(..., min_length=1, max_length=128)
    as_of: str = Field(..., min_length=10, max_length=64)
    active_designations: list[Annotated[str, Field(min_length=1, max_length=256)]] = Field(
        default_factory=list, max_length=10_000
    )
    snapshot_sha256: str = Field(..., min_length=64, max_length=64)


class IdentityReplayRequest(StrictModel):
    prior_event_ids: list[str] = Field(default_factory=list, max_length=10_000)
    prior_snapshots: list[DesignationSnapshotRequest] = Field(
        default_factory=list, max_length=10_000
    )
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


def _parse_aware_time(value: Any, field: str) -> datetime:
    """Parse an ISO-8601 timestamp that carries an explicit UTC offset."""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _current_time(now: datetime | None) -> datetime:
    current = datetime.now(timezone.utc) if now is None else now
    if (
        not isinstance(current, datetime)
        or current.tzinfo is None
        or current.utcoffset() is None
    ):
        raise ValueError("the injected clock must return a timezone-aware datetime")
    return current.astimezone(timezone.utc)


def _admit_time(value: Any, *, now: datetime, field: str) -> tuple[datetime, int]:
    """Return (instant, future skew in whole seconds rounded up) or reject.

    A timestamp exactly ``ALLOWED_FUTURE_SKEW_SECONDS`` ahead of ``now`` is
    admitted; anything later is rejected. Any positive skew is reported as at
    least one second so that a future observation is never shown as present.
    """
    instant = _parse_aware_time(value, field)
    ahead = instant - now
    if ahead > timedelta(seconds=ALLOWED_FUTURE_SKEW_SECONDS):
        raise ValueError(
            f"{field} is later than the allowed future clock skew of "
            f"{ALLOWED_FUTURE_SKEW_SECONDS} seconds"
        )
    future_skew = math.ceil(ahead.total_seconds()) if ahead > timedelta(0) else 0
    return instant, future_skew


def _time_admission_fields(future_skew_seconds: int) -> dict[str, Any]:
    return {
        "time_admission": (
            "FUTURE_WITHIN_ALLOWED_SKEW" if future_skew_seconds else "PAST_OR_PRESENT"
        ),
        "future_skew_seconds": future_skew_seconds,
        "allowed_future_skew_seconds": ALLOWED_FUTURE_SKEW_SECONDS,
    }


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


_REMOVAL_KINDS = frozenset({"DESIGNATION_REMOVED", "DELISTED"})
_IDENTITY_CHANGE_KINDS = frozenset(
    {"IDENTITY_CHANGED", "NAME_CHANGED", "FLAG_CHANGED", "OWNERSHIP_CHANGED"}
)


def _designation_id(event: IdentityEvent) -> str:
    return str(
        event.payload.get("designation_id")
        or event.payload.get("target_event_id")
        or event.event_id
    )


def _event_fingerprint(event: IdentityEvent, instant: datetime) -> str:
    """Digest of everything but the event identity; equal digests are true duplicates."""
    try:
        return sha256_payload(
            {
                "event_time": instant.isoformat(),
                "kind": event.kind,
                "source_revision": event.source_revision,
                "source_state": event.source_state,
                "payload": event.payload,
            }
        )
    except (TypeError, ValueError):
        raise ValueError("event payload must be JSON-serialisable") from None


def _snapshot_digest(
    entity_id: str, source_id: str, as_of: str, active_designations: list[str]
) -> str:
    return sha256_payload(
        {
            "schema": DESIGNATION_SNAPSHOT_SCHEMA,
            "entity_id": entity_id,
            "source_id": source_id,
            "as_of": as_of,
            "active_designations": sorted(active_designations),
        }
    )


def designation_snapshot(
    entity_id: str, source_id: str, as_of: datetime, active_designations: Iterable[str]
) -> dict[str, Any]:
    """Build the per-stream state snapshot a later replay can continue from.

    The digest is a content-integrity check only. It is not a signature and
    does not authenticate the snapshot; only a history verifier can.
    """
    active = sorted(set(active_designations))
    as_of_text = as_of.astimezone(timezone.utc).isoformat()
    return {
        "entity_id": entity_id,
        "source_id": source_id,
        "as_of": as_of_text,
        "active_designations": active,
        "snapshot_sha256": _snapshot_digest(entity_id, source_id, as_of_text, active),
    }


def _admit_snapshot(
    raw: Mapping[str, Any] | DesignationSnapshotRequest, *, now: datetime
) -> tuple[dict[str, Any], datetime, int]:
    item = raw.model_dump() if isinstance(raw, DesignationSnapshotRequest) else dict(raw)
    if set(item) != {"entity_id", "source_id", "as_of", "active_designations", "snapshot_sha256"}:
        raise ValueError("snapshot fields are invalid")
    entity_id, source_id = item["entity_id"], item["source_id"]
    active = item["active_designations"]
    if (
        not isinstance(entity_id, str) or not entity_id
        or not isinstance(source_id, str) or not source_id
        or not isinstance(active, list)
        or not all(isinstance(value, str) and value for value in active)
        or not isinstance(item["snapshot_sha256"], str)
    ):
        raise ValueError("snapshot fields are invalid")
    if len(set(active)) != len(active):
        raise ValueError("snapshot active_designations must be unique")
    instant, future_skew = _admit_time(item["as_of"], now=now, field="snapshot as_of")
    snapshot = designation_snapshot(entity_id, source_id, instant, active)
    if snapshot["snapshot_sha256"] != item["snapshot_sha256"].lower():
        raise ValueError("snapshot digest does not match its content")
    return snapshot, instant, future_skew


def _stream_verified(
    verifier: HistoryVerifier,
    key: tuple[str, str],
    events: tuple[IdentityEvent, ...],
    snapshot: dict[str, Any] | None,
) -> bool:
    try:
        return verifier(key[0], key[1], events, snapshot) is True
    except Exception:  # a failing verifier is unverified history, never a 500
        return False


def replay_identity_lifecycle(
    *,
    prior_event_ids: list[str],
    incoming: list[IdentityEventRequest | IdentityEvent],
    chain_complete: bool,
    identity_conflicts: int = 0,
    now: datetime | None = None,
    prior_snapshots: Iterable[Mapping[str, Any] | DesignationSnapshotRequest] = (),
    history_verifier: HistoryVerifier | None = None,
) -> dict[str, Any]:
    """Replay identity/designation events without producing unsafe clear screens.

    Designation state and deduplication are scoped to (entity_id, source_id).
    The caller's ``chain_complete`` is a claim: it is necessary but never
    sufficient. History counts as complete only when ``history_verifier``
    accepts every (entity, source) stream. Unknown prior state is reported
    explicitly through ``designation_state`` and ``unknown_state_reasons``.
    """
    current = _current_time(now)
    max_future_skew = 0

    snapshots: dict[tuple[str, str], dict[str, Any]] = {}
    snapshot_instants: dict[tuple[str, str], datetime] = {}
    for raw_snapshot in prior_snapshots:
        snapshot, instant, future_skew = _admit_snapshot(raw_snapshot, now=current)
        key = (snapshot["entity_id"], snapshot["source_id"])
        if key in snapshots:
            raise ValueError("duplicate snapshot for one entity/source stream")
        snapshots[key] = snapshot
        snapshot_instants[key] = instant
        max_future_skew = max(max_future_skew, future_skew)

    opaque_prior_ids = set(prior_event_ids)
    by_identity: dict[tuple[str, str, str], tuple[IdentityEvent, datetime, str]] = {}
    duplicates: list[str] = []
    for raw in incoming:
        event = _identity_event(raw)
        instant, future_skew = _admit_time(event.event_time, now=current, field="event_time")
        max_future_skew = max(max_future_skew, future_skew)
        identity = (event.entity_id, event.source_id, event.event_id)
        fingerprint = _event_fingerprint(event, instant)
        existing = by_identity.get(identity)
        if existing is not None:
            if existing[2] != fingerprint:
                raise ValueError(
                    "conflicting duplicate event: the same entity, source and "
                    "event_id carry different content"
                )
            duplicates.append(event.event_id)
            if event.event_time < existing[0].event_time:
                # Equivalent spellings of one instant: keep one deterministically.
                by_identity[identity] = (event, instant, fingerprint)
            continue
        snapshot_instant = snapshot_instants.get((event.entity_id, event.source_id))
        if snapshot_instant is not None and instant <= snapshot_instant:
            raise ValueError("event_time must be later than its stream's snapshot as_of")
        by_identity[identity] = (event, instant, fingerprint)

    ordered = sorted(
        by_identity.values(),
        key=lambda row: (row[1], row[0].entity_id, row[0].source_id, row[0].event_id),
    )
    recovered = [row[0] for row in ordered]
    opaque_matches = sorted({item.event_id for item in recovered} & opaque_prior_ids)

    state: dict[tuple[str, str], set[str]] = {
        key: set(snapshot["active_designations"]) for key, snapshot in snapshots.items()
    }
    stream_events: dict[tuple[str, str], list[IdentityEvent]] = {}
    stream_as_of: dict[tuple[str, str], datetime] = dict(snapshot_instants)
    operations: dict[tuple[str, str, str, datetime], set[str]] = {}
    unmatched_removals: list[dict[str, str]] = []
    identity_changes: list[str] = []
    for event, instant, _ in ordered:
        key = (event.entity_id, event.source_id)
        stream_events.setdefault(key, []).append(event)
        stream_as_of[key] = max(stream_as_of.get(key, instant), instant)
        active = state.setdefault(key, set())
        designation = _designation_id(event)
        if event.kind == "DESIGNATION_ADDED":
            active.add(designation)
            operations.setdefault((*key, designation, instant), set()).add("ADD")
        elif event.kind in _REMOVAL_KINDS:
            operations.setdefault((*key, designation, instant), set()).add("REMOVE")
            if designation in active:
                active.discard(designation)
            else:
                unmatched_removals.append(
                    {
                        "entity_id": event.entity_id,
                        "source_id": event.source_id,
                        "designation_id": designation,
                        "event_id": event.event_id,
                    }
                )
        elif event.kind in _IDENTITY_CHANGE_KINDS:
            identity_changes.append(event.event_id)

    ordering_ambiguities = [
        {
            "entity_id": entity_id,
            "source_id": source_id,
            "designation_id": designation,
            "event_time": instant.isoformat(),
        }
        for (entity_id, source_id, designation, instant), kinds in sorted(operations.items())
        if kinds == {"ADD", "REMOVE"}
    ]

    streams = sorted(state)
    claimed_complete = bool(chain_complete)
    history_verified = False
    if history_verifier is not None and streams:
        verdicts = [
            _stream_verified(
                history_verifier, key, tuple(stream_events.get(key, ())), snapshots.get(key)
            )
            for key in streams
        ]
        history_verified = all(verdicts)

    observed = [row for row in ordered if row[0].source_state == "OBSERVED"]
    degraded = [row for row in ordered if row[0].source_state != "OBSERVED"]
    stale = bool(degraded) or any(
        current - instant > IDENTITY_STALE_AFTER for _, instant, _ in observed
    )
    # Opaque prior IDs carry no state payload, and a caller's completeness claim
    # is not authentication: neither can make the replayed history complete.
    complete = (
        claimed_complete
        and history_verified
        and not prior_event_ids
        and identity_conflicts == 0
        and not degraded
    )
    reasons: set[str] = set()
    if prior_event_ids:
        reasons.add("OPAQUE_PRIOR_IDS")
    if not history_verified:
        reasons.add("UNVERIFIED_HISTORY")
    if not claimed_complete:
        reasons.add("CALLER_REPORTED_INCOMPLETE")
    if identity_conflicts:
        reasons.add("IDENTITY_CONFLICTS")
    if degraded:
        reasons.add("DEGRADED_SOURCE")
    if unmatched_removals:
        reasons.add("UNMATCHED_REMOVAL")
    if ordering_ambiguities:
        reasons.add("ORDERING_AMBIGUITY")
    designation_known = not reasons

    active_rows = [
        {"entity_id": key[0], "source_id": key[1], "designation_id": designation}
        for key in streams
        for designation in sorted(state[key])
    ]
    if not recovered or not observed:
        screening_state = "UNAVAILABLE"
    elif designation_known and not active_rows and not stale:
        screening_state = "CLEAR"
    else:
        screening_state = "REVIEW_REQUIRED"

    if not observed:
        truth_label = "UNAVAILABLE"
    elif complete and not stale:
        truth_label = "MEASURED"
    else:
        truth_label = "REPORTED"

    if prior_event_ids:
        history_state = "OPAQUE_PRIOR_IDS"
    elif not history_verified:
        history_state = "UNVERIFIED_HISTORY"
    elif snapshots:
        history_state = "SNAPSHOT_CONTINUATION"
    else:
        history_state = "FULL_REPLAY"

    return {
        "schema": "szl.killinchu-identity-lifecycle/v1",
        "entity_ids": sorted({item.entity_id for item in recovered} | {key[0] for key in snapshots}),
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
        "duplicate_event_ids": sorted(duplicates),
        "active_designations": sorted({row["designation_id"] for row in active_rows}),
        "active_designations_by_entity": active_rows,
        "designation_state": "KNOWN" if designation_known else "UNKNOWN_PRIOR_STATE",
        "unknown_state_reasons": sorted(reasons),
        "unmatched_removals": unmatched_removals,
        "ordering_ambiguities": ordering_ambiguities,
        "opaque_prior_id_matches": opaque_matches,
        "designation_snapshots": [
            designation_snapshot(key[0], key[1], stream_as_of[key], state[key])
            for key in streams
        ],
        "identity_changes": identity_changes,
        "identity_state": (
            "COMPLETE" if complete else "CONFLICTED" if identity_conflicts else "INCOMPLETE"
        ),
        "source_state": "OBSERVED" if not degraded else "DEGRADED",
        "screening_state": screening_state,
        "definitive_clear_screening": screening_state == "CLEAR",
        "chain_complete": complete,
        "chain_complete_claimed": claimed_complete,
        "history_verified": history_verified,
        "history_state": history_state,
        "identity_conflicts": identity_conflicts,
        "deadline_state_changed": False,
        **_time_admission_fields(max_future_skew),
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
    """Return freshness and scope metadata without claiming universal coverage.

    ``observed_at`` must carry a UTC offset and may be at most
    ``ALLOWED_FUTURE_SKEW_SECONDS`` ahead of ``now``; a later observation is
    rejected rather than clamped to fresh. Admitted future skew is reported.
    """
    if state not in {"OBSERVED", "UNAVAILABLE", "STALE", "NOT_ATTEMPTED"}:
        raise ValueError(f"invalid source state: {state}")
    current = _current_time(now)
    observed, future_skew = _admit_time(observed_at, now=current, field="observed_at")
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
        **_time_admission_fields(future_skew),
        "truth_label": "MEASURED" if bound else "UNAVAILABLE",
        "unavailable_reason": (
            None
            if bound
            else "source is stale, unavailable, empty, or has unresolved conflicts"
        ),
    }


@frontier_contracts.post("/killinchu/v1/identity/replay")
def identity_replay(
    request: IdentityReplayRequest,
    now: Annotated[datetime, Depends(contract_clock)],
    history_verifier: Annotated[HistoryVerifier | None, Depends(identity_history_verifier)],
) -> dict[str, Any]:
    try:
        return replay_identity_lifecycle(
            prior_event_ids=request.prior_event_ids,
            incoming=request.events,
            chain_complete=request.chain_complete,
            identity_conflicts=request.identity_conflicts,
            now=now,
            prior_snapshots=request.prior_snapshots,
            history_verifier=history_verifier,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@frontier_contracts.post("/terra/v1/coverage/evaluate")
def terra_coverage(
    request: CoverageRequest,
    now: Annotated[datetime, Depends(contract_clock)],
) -> dict[str, Any]:
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
            now=now,
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
    """Authorize only fresh, scoped, read-only finance queries.

    ``observed_at`` must carry a UTC offset and may be at most
    ``ALLOWED_FUTURE_SKEW_SECONDS`` ahead of ``now``; a later observation is
    rejected rather than treated as fresh.
    """
    if not actor_id or not tenant_id or not query or not source_revision:
        raise ValueError("actor, tenant, query, and source revision are required")
    if freshness_seconds < 1:
        raise ValueError("freshness_seconds must be positive")
    current = _current_time(now)
    observed, future_skew = _admit_time(observed_at, now=current, field="observed_at")
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
        **_time_admission_fields(future_skew),
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
def finance_adapter(
    request: FinanceAdapterRequest,
    now: Annotated[datetime, Depends(contract_clock)],
) -> dict[str, Any]:
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
            now=now,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


__all__ = [
    "ALLOWED_FUTURE_SKEW_SECONDS",
    "CoverageRequest",
    "DesignationSnapshotRequest",
    "FinanceAdapterRequest",
    "HistoryVerifier",
    "IdentityEvent",
    "IdentityEventRequest",
    "IdentityReplayRequest",
    "ProfilingEvidenceRequest",
    "authorize_finance_read",
    "contract_clock",
    "designation_snapshot",
    "evaluate_coverage",
    "frontier_contracts",
    "identity_history_verifier",
    "provenance_contract",
    "profiling_evidence",
    "replay_identity_lifecycle",
]
