"""Source-to-decision provenance and continuity-safe replay contracts.

These helpers are deliberately provider-neutral. They make evidence freshness,
source availability, and approval boundaries explicit without asserting that a
source is connected or that a decision is valid.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable, Mapping


TRUTH_LABELS = frozenset({"REPORTED", "MODELED", "MEASURED", "UNAVAILABLE"})
SOURCE_STATES = frozenset({"OBSERVED", "UNAVAILABLE", "STALE", "NOT_ATTEMPTED"})


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_payload(value: Any) -> str:
    """Return a deterministic digest for a JSON-compatible payload."""
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceObservation:
    source_id: str
    source_revision: str
    observed_at: str
    state: str
    truth_label: str
    payload_sha256: str | None = None
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if self.state not in SOURCE_STATES:
            raise ValueError(f"invalid source state: {self.state}")
        if self.truth_label not in TRUTH_LABELS:
            raise ValueError(f"invalid truth label: {self.truth_label}")
        if self.state == "OBSERVED" and not self.payload_sha256:
            raise ValueError("observed source requires payload_sha256")
        if self.state != "OBSERVED" and self.truth_label != "UNAVAILABLE":
            raise ValueError("unobserved source must be UNAVAILABLE")
        if self.state == "UNAVAILABLE" and not self.unavailable_reason:
            raise ValueError("unavailable source requires unavailable_reason")

    @classmethod
    def observed(cls, source_id: str, source_revision: str, payload: Any,
                 observed_at: str | None = None,
                 truth_label: str = "MEASURED") -> "SourceObservation":
        return cls(source_id, source_revision,
                   observed_at or datetime.now(timezone.utc).isoformat(),
                   "OBSERVED", truth_label, sha256_payload(payload))

    @classmethod
    def unavailable(cls, source_id: str, reason: str,
                    source_revision: str = "UNAVAILABLE",
                    observed_at: str | None = None) -> "SourceObservation":
        return cls(source_id, source_revision,
                   observed_at or datetime.now(timezone.utc).isoformat(),
                   "UNAVAILABLE", "UNAVAILABLE", None, reason)


def provenance_envelope(*, decision_id: str, source: SourceObservation,
                        model_revision: str, formula_revision: str,
                        policy_result: str, approval_required: bool,
                        freshness_seconds: int | None,
                        execution_state: str = "NOT_EXECUTED") -> dict[str, Any]:
    """Build a decision-bearing envelope with explicit evidence boundaries."""
    if not decision_id or not model_revision or not formula_revision:
        raise ValueError("decision, model, and formula revisions are required")
    if source.state != "OBSERVED":
        execution_state = "BLOCKED_UNAVAILABLE"
    return {
        "schema": "szl.source-to-decision-provenance/v1",
        "decision_id": decision_id,
        "source": {
            "id": source.source_id,
            "revision": source.source_revision,
            "observed_at": source.observed_at,
            "state": source.state,
            "truth_label": source.truth_label,
            "payload_sha256": source.payload_sha256,
            "unavailable_reason": source.unavailable_reason,
        },
        "model_revision": model_revision,
        "formula_revision": formula_revision,
        "policy_result": policy_result,
        "approval_boundary": {
            "required": approval_required,
            "effectors_enabled": False,
        },
        "freshness_seconds": freshness_seconds,
        "execution_state": execution_state,
        "envelope_sha256": sha256_payload({
            "decision_id": decision_id, "source": source.source_id,
            "source_revision": source.source_revision,
            "model_revision": model_revision, "formula_revision": formula_revision,
            "policy_result": policy_result,
        }),
    }


@dataclass(frozen=True)
class ContinuityEvent:
    event_id: str
    event_time: str
    kind: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class ReplayResult:
    recovered: tuple[ContinuityEvent, ...]
    duplicate_event_ids: tuple[str, ...]
    source_unavailable: bool
    deadline_state_changed: bool


def replay_continuity(*, prior_event_ids: Iterable[str],
                      incoming: Iterable[ContinuityEvent],
                      source_state: str,
                      deadline_state: str) -> ReplayResult:
    """Deduplicate a replay without changing deadline state."""
    if source_state not in SOURCE_STATES:
        raise ValueError(f"invalid source state: {source_state}")
    seen = set(prior_event_ids)
    recovered: list[ContinuityEvent] = []
    duplicates: list[str] = []
    for event in incoming:
        if event.event_id in seen:
            duplicates.append(event.event_id)
            continue
        seen.add(event.event_id)
        recovered.append(event)
    return ReplayResult(tuple(recovered), tuple(duplicates),
                        source_state != "OBSERVED", False)
