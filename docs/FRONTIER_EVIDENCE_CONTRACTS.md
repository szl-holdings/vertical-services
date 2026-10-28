# Frontier evidence contracts

The service exposes three bounded contracts for the next operational layer:

- POST /killinchu/v1/identity/replay replays dated sanctions, designation, identity, flag, name, ownership, and delisting events. It keeps the source revision on every event and refuses a definitive clear screen when the chain is incomplete, unverified, conflicted, stale, or unavailable. See "Identity replay state" below.
- POST /terra/v1/coverage/evaluate returns freshness, jurisdiction, record count, conflict count, and a scoped coverage state. It uses SCOPED_EVIDENCE_ONLY; it never claims universal parcel or distress coverage.
- GET /api/provenance/contract publishes the required source-to-decision envelope fields and fail-closed states.

These routes accept caller-provided, already-authorized observations. They do not connect a provider, establish a license, claim live AIS, issue legal advice, trade, or enable an effector. A CLEAR screening state is only emitted for a complete, verified, observed event chain with no active designation; it is an evidence-bounded product state and not a legal determination.

- POST /lyte/v1/profiling/evidence binds CPU and heap profiles to an exact worker revision, capture window, traffic precondition, and source-map state; it never represents a profile as historical replay.
- POST /finance/v1/adapter/authorize returns a read-only authorization receipt with actor, tenant, scopes, freshness, source revision, and an audit hash. Writes always deny and missing human approval remains review-required.

## Identity replay state

- Designation state and deduplication are scoped to `(entity_id, source_id)`. A removal for one entity or source never clears another's designation.
- An event identity is `(entity_id, source_id, event_id)`. An exact repeat is reported in `duplicate_event_ids`; the same identity with different content (time, kind, revision, source state, or payload) is rejected with HTTP 422.
- `chain_complete` in the request is the caller's claim, echoed as `chain_complete_claimed`. It is necessary but not sufficient: history counts as complete only when the server's history verifier accepts every `(entity, source)` stream. No verifier is configured by default, so the route does not emit CLEAR or a MEASURED replay label until an owner-approved verifier is wired. The response `chain_complete` is the server's determination.
- `prior_event_ids` are opaque: they carry no state and no entity/source scope, so they never suppress an incoming event (matches are listed in `opaque_prior_id_matches`) and they keep prior state UNKNOWN.
- `designation_state` is `KNOWN` only when no entry appears in `unknown_state_reasons` (`OPAQUE_PRIOR_IDS`, `UNVERIFIED_HISTORY`, `CALLER_REPORTED_INCOMPLETE`, `IDENTITY_CONFLICTS`, `DEGRADED_SOURCE`, `UNMATCHED_REMOVAL`, `ORDERING_AMBIGUITY`). Otherwise it is `UNKNOWN_PRIOR_STATE`, and an empty `active_designations` list is a lower bound, not an all-clear.
- `designation_snapshots` gives each stream's resulting state. Passing them back as `prior_snapshots` continues the replay; later events must be strictly after the snapshot's `as_of`. The snapshot digest is a content-integrity check, not a signature, and does not authenticate the snapshot.
- An add and a removal of the same designation at the same instant are an ordering ambiguity and keep the state UNKNOWN.

## Time admission

Killinchu replay, Terra coverage, and Finance authorization admit observation timestamps against an injected server clock (`contract_clock`):

- A timestamp must be ISO-8601 with an explicit UTC offset; timezone-naive or invalid timestamps are rejected with HTTP 422.
- A timestamp may be at most `ALLOWED_FUTURE_SKEW_SECONDS` (300) ahead of the clock. Exactly at the boundary is admitted; anything later is rejected with HTTP 422 and is never clamped to fresh.
- Admitted future skew is reported in `future_skew_seconds` (rounded up, so any future skew is at least 1), with `time_admission` and `allowed_future_skew_seconds`.
- Staleness rules are unchanged.
