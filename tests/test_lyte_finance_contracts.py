"""Tests for revision-bound profiling and permission-scoped finance access."""
from datetime import datetime, timezone

from deploy.szl_verticals.frontier_contracts import (
    authorize_finance_read,
    profiling_evidence,
)


DIGEST = "a" * 64


def test_profiling_requires_live_traffic_and_stays_revision_bound():
    blocked = profiling_evidence(
        worker_id="lyte-worker",
        deployed_revision="worker@42",
        captured_at="2026-10-27T12:00:00Z",
        duration_seconds=30,
        traffic_observed=False,
        source_map_state="AVAILABLE",
        cpu_profile_sha256=DIGEST,
        heap_profile_sha256=DIGEST,
    )
    assert blocked["evidence_state"] == "BLOCKED_TRAFFIC_PRECONDITION"
    assert blocked["historical_replay_claimed"] is False
    assert blocked["ready_for_analysis"] is False


def test_complete_profile_is_bound_to_revision_and_capture_window():
    result = profiling_evidence(
        worker_id="lyte-worker",
        deployed_revision="worker@42",
        captured_at="2026-10-27T12:00:00Z",
        duration_seconds=30,
        traffic_observed=True,
        source_map_state="AVAILABLE",
        cpu_profile_sha256=DIGEST,
        heap_profile_sha256=DIGEST,
    )
    assert result["evidence_state"] == "OBSERVED"
    assert result["scope"] == "REVISION_BOUND"
    assert result["deployed_revision"] == "worker@42"
    assert result["ready_for_analysis"] is True


def test_finance_adapter_rejects_writes_and_unscoped_access():
    written = authorize_finance_read(
        actor_id="user-1",
        tenant_id="tenant-1",
        scopes=["read:balances"],
        field_scopes=["balance"],
        query="select balance",
        source_revision="finance@1",
        observed_at="2026-10-27T11:59:00Z",
        freshness_seconds=3600,
        approval_id="approval-1",
        write_requested=True,
        now=datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc),
    )
    assert written["decision"] == "DENY_WRITE"
    assert written["writes_enabled"] is False
    unscoped = authorize_finance_read(
        actor_id="user-1",
        tenant_id="tenant-1",
        scopes=["balances"],
        field_scopes=["balance"],
        query="select balance",
        source_revision="finance@1",
        observed_at="2026-10-27T11:59:00Z",
        freshness_seconds=3600,
        approval_id="approval-1",
        now=datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc),
    )
    assert unscoped["decision"] == "DENY_SCOPE"


def test_finance_adapter_requires_freshness_and_human_receipt():
    result = authorize_finance_read(
        actor_id="user-1",
        tenant_id="tenant-1",
        scopes=["read:balances"],
        field_scopes=["balance"],
        query="select balance",
        source_revision="finance@1",
        observed_at="2026-10-27T11:59:00Z",
        freshness_seconds=3600,
        now=datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc),
    )
    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["human_approval_required"] is True
    assert len(result["audit_receipt_sha256"]) == 64
