"""Replay-correctness tests for the Killinchu identity lifecycle contract.

Designation state and deduplication are scoped to (entity, source). A caller's
``chain_complete`` claim is necessary but never sufficient: only an injected
history verifier can establish complete history, and none is configured by
default. Unknown prior state stays explicit instead of rendering as an empty
active-designation list.

New symbols are read from the module inside each test so that, on a base that
lacks them, every test fails on its own instead of failing collection.
"""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from deploy.szl_verticals import frontier_contracts as fc

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
ENTITY_A = "imo-1000001"
ENTITY_B = "imo-2000002"
OFAC = "ofac-snapshot"
UN = "un-sc-snapshot"


def ev(
    event_id,
    kind,
    *,
    entity=ENTITY_A,
    source=OFAC,
    designation="sdn-1",
    time="2026-10-20T00:00:00Z",
    revision="rev-1",
    state="OBSERVED",
    payload=None,
):
    return fc.IdentityEvent(
        event_id=event_id,
        entity_id=entity,
        event_time=time,
        kind=kind,
        source_id=source,
        source_revision=revision,
        source_state=state,
        payload=payload if payload is not None else {"designation_id": designation},
    )


def replay(events, *, prior=(), chain_complete=True, **kwargs):
    return fc.replay_identity_lifecycle(
        prior_event_ids=list(prior),
        incoming=list(events),
        chain_complete=chain_complete,
        now=NOW,
        **kwargs,
    )


def trust_all(entity_id, source_id, events, snapshot):
    """Test-only stand-in for an owner-approved history verifier."""
    return True


def keys(result):
    return [
        (row["entity_id"], row["source_id"], row["designation_id"])
        for row in result["active_designations_by_entity"]
    ]


# -- entity / source namespacing ----------------------------------------------


def test_entity_b_removal_does_not_clear_entity_a_designation():
    result = replay(
        [
            ev("add-a", "DESIGNATION_ADDED", entity=ENTITY_A, time="2026-10-20T00:00:00Z"),
            ev("rm-b", "DESIGNATION_REMOVED", entity=ENTITY_B, time="2026-10-21T00:00:00Z"),
        ]
    )
    assert "sdn-1" in result["active_designations"]
    assert result["screening_state"] != "CLEAR"
    assert result["definitive_clear_screening"] is False
    assert keys(result) == [(ENTITY_A, OFAC, "sdn-1")]


def test_entity_b_removal_does_not_clear_entity_a_even_with_verified_history():
    result = replay(
        [
            ev("add-a", "DESIGNATION_ADDED", entity=ENTITY_A, time="2026-10-20T00:00:00Z"),
            ev("rm-b", "DESIGNATION_REMOVED", entity=ENTITY_B, time="2026-10-21T00:00:00Z"),
        ],
        history_verifier=trust_all,
    )
    assert keys(result) == [(ENTITY_A, OFAC, "sdn-1")]
    assert result["screening_state"] == "REVIEW_REQUIRED"
    assert [
        (row["entity_id"], row["source_id"], row["designation_id"])
        for row in result["unmatched_removals"]
    ] == [(ENTITY_B, OFAC, "sdn-1")]


def test_same_event_id_from_two_sources_is_not_a_duplicate():
    result = replay(
        [
            ev("e-1", "DESIGNATION_ADDED", source=OFAC, designation="sdn-1"),
            ev("e-1", "DESIGNATION_ADDED", source=UN, designation="un-7"),
        ]
    )
    assert result["duplicate_event_ids"] == []
    assert len(result["recovered_events"]) == 2
    assert result["active_designations"] == ["sdn-1", "un-7"]


def test_same_event_id_for_two_entities_is_not_a_duplicate():
    result = replay(
        [
            ev("e-1", "DESIGNATION_ADDED", entity=ENTITY_A),
            ev("e-1", "DESIGNATION_ADDED", entity=ENTITY_B),
        ]
    )
    assert result["duplicate_event_ids"] == []
    assert len(result["recovered_events"]) == 2
    assert keys(result) == [(ENTITY_A, OFAC, "sdn-1"), (ENTITY_B, OFAC, "sdn-1")]


def test_removal_from_one_source_does_not_clear_another_sources_designation():
    result = replay(
        [
            ev("add-ofac", "DESIGNATION_ADDED", source=OFAC, time="2026-10-20T00:00:00Z"),
            ev("rm-un", "DELISTED", source=UN, time="2026-10-21T00:00:00Z"),
        ]
    )
    assert result["active_designations"] == ["sdn-1"]
    assert result["screening_state"] != "CLEAR"
    assert keys(result) == [(ENTITY_A, OFAC, "sdn-1")]


# -- duplicates -----------------------------------------------------------------


def test_exact_duplicate_is_idempotent():
    result = replay(
        [
            ev("add-1", "DESIGNATION_ADDED"),
            ev("add-1", "DESIGNATION_ADDED"),
        ]
    )
    assert result["duplicate_event_ids"] == ["add-1"]
    assert len(result["recovered_events"]) == 1
    assert result["active_designations"] == ["sdn-1"]


def test_duplicate_with_equivalent_timestamp_spelling_is_not_a_conflict():
    result = replay(
        [
            ev("add-1", "DESIGNATION_ADDED", time="2026-10-20T00:00:00Z"),
            ev("add-1", "DESIGNATION_ADDED", time="2026-10-20T00:00:00+00:00"),
        ]
    )
    assert result["duplicate_event_ids"] == ["add-1"]
    assert len(result["recovered_events"]) == 1


@pytest.mark.parametrize(
    "changed",
    [
        {"payload": {"designation_id": "sdn-2"}},
        {"kind": "DESIGNATION_REMOVED"},
        {"time": "2026-10-20T00:00:01Z"},
        {"revision": "rev-2"},
        {"state": "STALE"},
    ],
    ids=["payload", "kind", "event_time", "source_revision", "source_state"],
)
def test_changed_duplicate_identity_is_rejected(changed):
    original = ev("add-1", "DESIGNATION_ADDED")
    changed = dict(changed)
    kind = changed.pop("kind", "DESIGNATION_ADDED")
    conflicting = ev("add-1", kind, **changed)
    with pytest.raises(ValueError, match="conflicting duplicate"):
        replay([original, conflicting])
    with pytest.raises(ValueError, match="conflicting duplicate"):
        replay([conflicting, original])


# -- caller completeness is not trusted -------------------------------------------


def test_lone_removal_without_authenticated_history_is_not_clear():
    result = replay([ev("rm-1", "DELISTED")], chain_complete=True)
    assert result["screening_state"] == "REVIEW_REQUIRED"
    assert result["definitive_clear_screening"] is False
    assert result["truth_label"] != "MEASURED"
    assert result["chain_complete"] is False
    assert result["chain_complete_claimed"] is True
    assert result["history_verified"] is False
    assert result["designation_state"] == "UNKNOWN_PRIOR_STATE"
    assert "UNVERIFIED_HISTORY" in result["unknown_state_reasons"]
    assert "UNMATCHED_REMOVAL" in result["unknown_state_reasons"]


def test_lone_removal_with_verified_history_is_still_an_anomaly():
    result = replay([ev("rm-1", "DELISTED")], history_verifier=trust_all)
    assert result["history_verified"] is True
    assert result["screening_state"] == "REVIEW_REQUIRED"
    assert result["unknown_state_reasons"] == ["UNMATCHED_REMOVAL"]


def test_verified_complete_history_can_clear():
    result = replay(
        [
            ev("add-1", "DESIGNATION_ADDED", time="2026-10-20T00:00:00Z"),
            ev("rm-1", "DESIGNATION_REMOVED", time="2026-10-21T00:00:00Z"),
        ],
        history_verifier=trust_all,
    )
    assert result["screening_state"] == "CLEAR"
    assert result["definitive_clear_screening"] is True
    assert result["designation_state"] == "KNOWN"
    assert result["unknown_state_reasons"] == []
    assert result["history_state"] == "FULL_REPLAY"
    assert result["chain_complete"] is True
    assert result["truth_label"] == "MEASURED"


def test_verified_history_without_caller_completeness_claim_is_not_clear():
    result = replay(
        [
            ev("add-1", "DESIGNATION_ADDED", time="2026-10-20T00:00:00Z"),
            ev("rm-1", "DESIGNATION_REMOVED", time="2026-10-21T00:00:00Z"),
        ],
        chain_complete=False,
        history_verifier=trust_all,
    )
    assert result["screening_state"] == "REVIEW_REQUIRED"
    assert result["chain_complete"] is False


@pytest.mark.parametrize(
    "verifier",
    [
        lambda *args: False,
        lambda *args: "yes",
        lambda *args: 1,
        lambda *args: (_ for _ in ()).throw(RuntimeError("verifier down")),
    ],
    ids=["false", "truthy-string", "truthy-int", "raises"],
)
def test_history_verifier_fails_closed(verifier):
    result = replay(
        [
            ev("add-1", "DESIGNATION_ADDED", time="2026-10-20T00:00:00Z"),
            ev("rm-1", "DESIGNATION_REMOVED", time="2026-10-21T00:00:00Z"),
        ],
        history_verifier=verifier,
    )
    assert result["history_verified"] is False
    assert result["screening_state"] == "REVIEW_REQUIRED"


def test_history_verifier_must_accept_every_stream():
    calls = []

    def only_entity_a(entity_id, source_id, events, snapshot):
        calls.append((entity_id, source_id, tuple(item.event_id for item in events)))
        return entity_id == ENTITY_A

    result = replay(
        [
            ev("add-a", "DESIGNATION_ADDED", entity=ENTITY_A, time="2026-10-20T00:00:00Z"),
            ev("rm-a", "DESIGNATION_REMOVED", entity=ENTITY_A, time="2026-10-21T00:00:00Z"),
            ev("add-b", "DESIGNATION_ADDED", entity=ENTITY_B, time="2026-10-20T00:00:00Z"),
            ev("rm-b", "DESIGNATION_REMOVED", entity=ENTITY_B, time="2026-10-21T00:00:00Z"),
        ],
        history_verifier=only_entity_a,
    )
    assert sorted(calls) == [
        (ENTITY_A, OFAC, ("add-a", "rm-a")),
        (ENTITY_B, OFAC, ("add-b", "rm-b")),
    ]
    assert result["history_verified"] is False
    assert result["screening_state"] == "REVIEW_REQUIRED"


# -- opaque prior IDs -------------------------------------------------------------


def test_opaque_prior_ids_keep_prior_state_explicitly_unknown():
    result = replay([ev("rm-1", "DELISTED")], prior=["unreplayed-add"], history_verifier=trust_all)
    assert result["history_state"] == "OPAQUE_PRIOR_IDS"
    assert result["active_designations"] == []
    assert result["designation_state"] == "UNKNOWN_PRIOR_STATE"
    assert "OPAQUE_PRIOR_IDS" in result["unknown_state_reasons"]
    assert result["screening_state"] == "REVIEW_REQUIRED"
    assert result["truth_label"] != "MEASURED"


def test_opaque_prior_id_does_not_suppress_an_event_from_another_source():
    result = replay(
        [ev("e-1", "DESIGNATION_ADDED", source=UN, designation="un-7")],
        prior=["e-1"],
    )
    assert result["duplicate_event_ids"] == []
    assert result["opaque_prior_id_matches"] == ["e-1"]
    assert [item["event_id"] for item in result["recovered_events"]] == ["e-1"]
    assert result["active_designations"] == ["un-7"]
    assert result["designation_state"] == "UNKNOWN_PRIOR_STATE"


# -- snapshot continuation ----------------------------------------------------------


FIRST = [
    ev("add-1", "DESIGNATION_ADDED", designation="sdn-1", time="2026-10-01T00:00:00Z"),
    ev("add-2", "DESIGNATION_ADDED", designation="sdn-2", time="2026-10-02T00:00:00Z"),
]
SECOND = [
    ev("rm-1", "DESIGNATION_REMOVED", designation="sdn-1", time="2026-10-03T00:00:00Z"),
    ev("add-b", "DESIGNATION_ADDED", entity=ENTITY_B, designation="sdn-9", time="2026-10-03T00:00:00Z"),
]


def test_snapshot_continuation_matches_full_replay():
    full = replay(FIRST + SECOND, history_verifier=trust_all)
    first = replay(FIRST, history_verifier=trust_all)
    second = replay(
        SECOND,
        prior_snapshots=first["designation_snapshots"],
        history_verifier=trust_all,
    )
    assert keys(second) == keys(full) == [
        (ENTITY_A, OFAC, "sdn-2"),
        (ENTITY_B, OFAC, "sdn-9"),
    ]
    assert second["designation_snapshots"] == full["designation_snapshots"]
    assert second["history_state"] == "SNAPSHOT_CONTINUATION"
    assert second["designation_state"] == "KNOWN"
    assert second["unmatched_removals"] == []


def test_snapshot_is_handed_to_the_verifier_for_its_stream():
    first = replay(FIRST, history_verifier=trust_all)
    seen = {}

    def record(entity_id, source_id, events, snapshot):
        seen[(entity_id, source_id)] = snapshot
        return True

    replay(SECOND, prior_snapshots=first["designation_snapshots"], history_verifier=record)
    assert seen[(ENTITY_A, OFAC)] == first["designation_snapshots"][0]
    assert seen[(ENTITY_B, OFAC)] is None


def test_unverified_snapshot_carries_state_forward_but_cannot_clear():
    first = replay(FIRST, history_verifier=trust_all)
    second = replay(
        [ev("rm-2", "DESIGNATION_REMOVED", designation="sdn-2", time="2026-10-03T00:00:00Z")],
        prior_snapshots=first["designation_snapshots"],
    )
    assert second["active_designations"] == ["sdn-1"]
    assert second["designation_state"] == "UNKNOWN_PRIOR_STATE"
    assert "UNVERIFIED_HISTORY" in second["unknown_state_reasons"]
    assert second["screening_state"] == "REVIEW_REQUIRED"


def test_tampered_snapshot_is_rejected():
    first = replay(FIRST, history_verifier=trust_all)
    snapshot = dict(first["designation_snapshots"][0])
    snapshot["active_designations"] = ["sdn-2"]
    with pytest.raises(ValueError, match="snapshot digest"):
        replay(SECOND, prior_snapshots=[snapshot], history_verifier=trust_all)


@pytest.mark.parametrize(
    "field,value",
    [
        ("entity_id", ENTITY_B),
        ("source_id", UN),
        ("as_of", "2026-10-02T00:00:01+00:00"),
        ("active_designations", ["sdn-1"]),
    ],
)
def test_snapshot_digest_covers_each_field_independently(field, value):
    first = replay(FIRST, history_verifier=trust_all)
    snapshot = dict(first["designation_snapshots"][0])
    assert snapshot[field] != value
    snapshot[field] = value
    with pytest.raises(ValueError, match="snapshot digest"):
        replay([], prior_snapshots=[snapshot], history_verifier=trust_all)


def test_duplicate_snapshot_for_one_stream_is_rejected():
    first = replay(FIRST, history_verifier=trust_all)
    snapshot = first["designation_snapshots"][0]
    with pytest.raises(ValueError, match="duplicate snapshot"):
        replay(SECOND, prior_snapshots=[snapshot, snapshot], history_verifier=trust_all)


def test_event_at_or_before_snapshot_as_of_is_rejected():
    first = replay(FIRST, history_verifier=trust_all)
    with pytest.raises(ValueError, match="snapshot as_of"):
        replay(
            [ev("late", "DESIGNATION_REMOVED", designation="sdn-1", time="2026-10-02T00:00:00Z")],
            prior_snapshots=first["designation_snapshots"],
            history_verifier=trust_all,
        )


# -- reordered events -------------------------------------------------------------


ORDERED = [
    ev("add-1", "DESIGNATION_ADDED", designation="sdn-1", time="2026-10-01T00:00:00Z"),
    ev("rm-1", "DESIGNATION_REMOVED", designation="sdn-1", time="2026-10-02T00:00:00Z"),
    ev("add-2", "DESIGNATION_ADDED", designation="sdn-2", time="2026-10-03T00:00:00Z"),
    ev("add-b", "DESIGNATION_ADDED", entity=ENTITY_B, designation="sdn-1", time="2026-10-02T00:00:00Z"),
]


def test_reordered_input_produces_identical_result():
    baseline = replay(ORDERED)
    for permutation in (ORDERED[::-1], ORDERED[1:] + ORDERED[:1], ORDERED[2:] + ORDERED[:2]):
        assert replay(permutation) == baseline
    assert baseline["active_designations"] == ["sdn-1", "sdn-2"]


def test_removal_earlier_in_time_than_add_does_not_cancel_it():
    result = replay(
        [
            ev("add-1", "DESIGNATION_ADDED", time="2026-10-02T00:00:00Z"),
            ev("rm-1", "DESIGNATION_REMOVED", time="2026-10-01T00:00:00Z"),
        ],
        history_verifier=trust_all,
    )
    assert result["active_designations"] == ["sdn-1"]
    assert len(result["unmatched_removals"]) == 1
    assert result["screening_state"] == "REVIEW_REQUIRED"


def test_add_and_remove_at_same_instant_is_ambiguous():
    result = replay(
        [
            ev("add-1", "DESIGNATION_ADDED", time="2026-10-02T00:00:00Z"),
            ev("rm-1", "DESIGNATION_REMOVED", time="2026-10-02T00:00:00+00:00"),
        ],
        history_verifier=trust_all,
    )
    assert result["screening_state"] != "CLEAR"
    assert result["designation_state"] == "UNKNOWN_PRIOR_STATE"
    assert "ORDERING_AMBIGUITY" in result["unknown_state_reasons"]


# -- HTTP route ---------------------------------------------------------------------


def _event_json(event_id, kind, **overrides):
    body = {
        "event_id": event_id,
        "entity_id": ENTITY_A,
        "event_time": "2026-10-20T00:00:00Z",
        "kind": kind,
        "source_id": OFAC,
        "source_revision": "rev-1",
        "source_state": "OBSERVED",
        "payload": {"designation_id": "sdn-1"},
    }
    body.update(overrides)
    return body


def _client():
    app = FastAPI()
    app.include_router(fc.frontier_contracts)
    return TestClient(app)


def test_route_rejects_changed_duplicate_with_422():
    response = _client().post(
        "/killinchu/v1/identity/replay",
        json={
            "events": [
                _event_json("add-1", "DESIGNATION_ADDED"),
                _event_json("add-1", "DESIGNATION_ADDED", payload={"designation_id": "sdn-2"}),
            ],
            "chain_complete": True,
        },
    )
    assert response.status_code == 422
    assert "conflicting duplicate" in response.json()["detail"]


def test_route_never_trusts_caller_chain_complete_by_default():
    response = _client().post(
        "/killinchu/v1/identity/replay",
        json={"events": [_event_json("rm-1", "DELISTED")], "chain_complete": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["screening_state"] == "REVIEW_REQUIRED"
    assert body["definitive_clear_screening"] is False


def test_route_snapshot_round_trip_and_existing_keys_are_preserved():
    client = _client()
    first = client.post(
        "/killinchu/v1/identity/replay",
        json={"events": [_event_json("add-1", "DESIGNATION_ADDED")], "chain_complete": True},
    )
    assert first.status_code == 200
    body = first.json()
    legacy_keys = {
        "schema", "entity_ids", "recovered_events", "duplicate_event_ids",
        "active_designations", "identity_changes", "identity_state", "source_state",
        "screening_state", "definitive_clear_screening", "chain_complete",
        "history_state", "identity_conflicts", "deadline_state_changed",
        "truth_label", "disclaimer",
    }
    assert legacy_keys <= set(body)
    assert body["schema"] == "szl.killinchu-identity-lifecycle/v1"
    second = client.post(
        "/killinchu/v1/identity/replay",
        json={
            "events": [
                _event_json("rm-1", "DESIGNATION_REMOVED", event_time="2026-10-21T00:00:00Z")
            ],
            "prior_snapshots": body["designation_snapshots"],
            "chain_complete": True,
        },
    )
    assert second.status_code == 200
    assert second.json()["active_designations"] == []
    assert second.json()["unmatched_removals"] == []
    assert second.json()["screening_state"] == "REVIEW_REQUIRED"
