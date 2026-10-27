"""Tests for identity lifecycle replay and Terra freshness coverage."""
from datetime import datetime, timezone

from deploy.szl_verticals.frontier_contracts import (
    IdentityEvent,
    evaluate_coverage,
    replay_identity_lifecycle,
)


def event(event_id, kind, state="OBSERVED", payload=None):
    return IdentityEvent(
        event_id=event_id,
        entity_id="imo-123",
        event_time="2026-10-20T00:00:00Z",
        kind=kind,
        source_id="ofac-snapshot",
        source_revision="ofac@2026-10-20",
        source_state=state,
        payload=payload or {},
    )


def test_identity_replay_deduplicates_and_never_clears_incomplete_chain():
    result = replay_identity_lifecycle(
        prior_event_ids=["add-1"],
        incoming=[
            event("add-1", "DESIGNATION_ADDED", payload={"designation_id": "sdn-1"}),
            event("remove-1", "DESIGNATION_REMOVED", payload={"designation_id": "sdn-1"}),
        ],
        chain_complete=False,
        now=datetime(2026, 10, 27, tzinfo=timezone.utc),
    )
    assert result["duplicate_event_ids"] == ["add-1"]
    assert result["active_designations"] == []
    assert result["screening_state"] == "REVIEW_REQUIRED"
    assert result["definitive_clear_screening"] is False
    assert result["deadline_state_changed"] is False


def test_identity_replay_refuses_clear_with_stale_or_degraded_source():
    result = replay_identity_lifecycle(
        prior_event_ids=[],
        incoming=[event("add-1", "DESIGNATION_ADDED", state="STALE")],
        chain_complete=True,
        now=datetime(2026, 10, 27, tzinfo=timezone.utc),
    )
    assert result["screening_state"] == "UNAVAILABLE"
    assert result["definitive_clear_screening"] is False


def test_identity_replay_can_clear_only_complete_observed_chain():
    result = replay_identity_lifecycle(
        prior_event_ids=[],
        incoming=[event("remove-1", "DELISTED", payload={"designation_id": "sdn-1"})],
        chain_complete=True,
        now=datetime(2026, 10, 27, tzinfo=timezone.utc),
    )
    assert result["screening_state"] == "CLEAR"
    assert result["definitive_clear_screening"] is True


def test_terra_coverage_is_scoped_and_stale_data_is_unavailable():
    fresh = evaluate_coverage(
        source_id="nyc-pluto",
        jurisdiction="NYC",
        observed_at="2026-10-27T11:59:00Z",
        freshness_seconds=3600,
        record_count=10,
        expected_scope="NYC PLUTO 2026 Q4",
        now=datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc),
    )
    assert fresh["coverage_state"] == "BOUND"
    assert fresh["coverage_claim"] == "SCOPED_EVIDENCE_ONLY"
    stale = evaluate_coverage(
        source_id="nyc-pluto",
        jurisdiction="NYC",
        observed_at="2026-10-25T12:00:00Z",
        freshness_seconds=3600,
        record_count=10,
        expected_scope="NYC PLUTO",
        now=datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc),
    )
    assert stale["coverage_state"] == "UNAVAILABLE"
    assert stale["truth_label"] == "UNAVAILABLE"

def test_opaque_prior_ids_cannot_produce_definitive_clear():
    result = replay_identity_lifecycle(
        prior_event_ids=["unreplayed-add"],
        incoming=[
            event(
                "remove-1",
                "DELISTED",
                payload={"designation_id": "sdn-1"},
            )
        ],
        chain_complete=True,
        now=datetime(2026, 10, 27, tzinfo=timezone.utc),
    )
    assert result["history_state"] == "OPAQUE_PRIOR_IDS"
    assert result["screening_state"] == "REVIEW_REQUIRED"
    assert result["definitive_clear_screening"] is False
