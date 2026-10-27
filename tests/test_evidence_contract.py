"""Tests for source-to-decision provenance and continuity-safe replay."""
from deploy.szl_verticals.evidence_contract import (
    ContinuityEvent,
    SourceObservation,
    provenance_envelope,
    replay_continuity,
)


def test_unavailable_source_blocks_execution_and_preserves_boundary():
    source = SourceObservation.unavailable("pacer", "maintenance window")
    envelope = provenance_envelope(
        decision_id="matter-1", source=source, model_revision="model@1",
        formula_revision="formula@1", policy_result="REVIEW_REQUIRED",
        approval_required=True, freshness_seconds=None,
    )
    assert envelope["source"]["truth_label"] == "UNAVAILABLE"
    assert envelope["execution_state"] == "BLOCKED_UNAVAILABLE"
    assert envelope["approval_boundary"]["effectors_enabled"] is False


def test_observation_is_hash_addressed_and_revision_bound():
    source = SourceObservation.observed(
        "nyc-pluto", "pluto@2026-10-20", {"bbl": "1000010001", "lot": 1},
        observed_at="2026-10-27T12:00:00+00:00",
    )
    envelope = provenance_envelope(
        decision_id="parcel-1", source=source, model_revision="terra@7",
        formula_revision="formulas@3", policy_result="PASS",
        approval_required=True, freshness_seconds=120,
        execution_state="READY_FOR_REVIEW",
    )
    assert len(source.payload_sha256) == 64
    assert envelope["execution_state"] == "READY_FOR_REVIEW"
    assert envelope["envelope_sha256"] == provenance_envelope(
        decision_id="parcel-1", source=source, model_revision="terra@7",
        formula_revision="formulas@3", policy_result="PASS",
        approval_required=True, freshness_seconds=120,
        execution_state="READY_FOR_REVIEW",
    )["envelope_sha256"]


def test_replay_deduplicates_and_never_advances_deadline():
    events = [
        ContinuityEvent("f-1", "2026-10-22T01:00:00Z", "filing", {"document": "A"}),
        ContinuityEvent("f-2", "2026-10-23T01:00:00Z", "filing", {"document": "B"}),
    ]
    result = replay_continuity(
        prior_event_ids=["f-1"], incoming=events,
        source_state="OBSERVED", deadline_state="OPEN",
    )
    assert [item.event_id for item in result.recovered] == ["f-2"]
    assert result.duplicate_event_ids == ("f-1",)
    assert result.deadline_state_changed is False
    unavailable = replay_continuity(
        prior_event_ids=[], incoming=[], source_state="UNAVAILABLE",
        deadline_state="OPEN",
    )
    assert unavailable.source_unavailable is True
    assert unavailable.deadline_state_changed is False

def test_provenance_digest_covers_decision_controls():
    source = SourceObservation.observed(
        "sec", "sec@1", {"filing": "A"}, observed_at="2026-10-27T12:00:00+00:00"
    )
    base = provenance_envelope(
        decision_id="d-1", source=source, model_revision="m@1",
        formula_revision="f@1", policy_result="PASS",
        approval_required=True, freshness_seconds=60,
        execution_state="READY_FOR_REVIEW",
    )
    changed = provenance_envelope(
        decision_id="d-1", source=source, model_revision="m@1",
        formula_revision="f@1", policy_result="PASS",
        approval_required=False, freshness_seconds=120,
        execution_state="NOT_EXECUTED",
    )
    assert base["envelope_sha256"] != changed["envelope_sha256"]
