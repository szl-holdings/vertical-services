# Hatun scoped evidence admission v2

This is the bounded Hatun successor to PR #36's existing intelligence repair. It advances issue #35; it does not close deployment, source semantics, browser acceptance, or the entire issue.

## Source and ownership

Parent reviewed: `5505567e121c0fb81e7b70697656dfa01f155653`; parent tree `2fdc6321dae30bc7786849b6529e7c632919a790`. The actual mounted route remains `POST /api/verticals/{vertical}/hatun/evaluate` in the existing `deploy/szl_verticals/frontier.py`. No duplicate service, router endpoint, Space, publisher, external model, network call, training action or effector is introduced. The existing HTML experience generator and its route are byte-for-byte unchanged by this successor.

`vertical-services` owns shared Python. `platform` owns durable matters. A11oy owns product assembly and the canonical HF projection, while a11oy-net owns measured proof. PR #34's caller-text claim-integrity boundary remains separate.

## Request and receipt migration

Supply `evidence_sha256`: at most 32 unique, exact lowercase 64-character SHA-256 payload digests returned by an existing authorized connector observation. The same caller-held `X-SZL-Session` and canonical vertical must resolve those digests. Aliases are canonicalized before lookup. No caller URL is fetched.

The old `evidence_refs` field remains accepted only for redacted compatibility diagnostics. Any supplied legacy handle adds `LEGACY_REFERENCES_UNRESOLVED`, even alongside valid payload digests. Migrate the caller instead of fabricating a handle-to-payload association. `evidence_ref_sha256` hashes only these legacy handles; it is not evidence qualification.

The review basis and receipt use v2 schemas because their counting semantics changed. `session_observation_count` now means distinct requested payloads resolved in this scope, explicitly labelled by `session_observation_count_unit`. It is not the session's historical total. UNAVAILABLE is null, observed empty is zero, and partial resolution never qualifies a convenient valid subset.

One immutable snapshot from the existing resolver is bound into the receipt through `evidence_resolution`, its snapshot hash, selected record identities and normalized-summary hashes. Neither raw summaries, full source URLs, session tokens nor scope tokens are returned. `evidence_resolved_at`, `review_assessed_at` and `evidence_fresh_at_review` distinguish resolution from the final freshness assessment. Expiry at assessment is exclusive; a regressing assessment clock blocks review. Database/readiness errors are redacted, not translated into qualifying zero counts.

Only REVIEW and ABSTAIN are possible. Caller axes remain advisory/caller-reported, not authenticated measurements. Normalized-axis collisions are rejected. Rejected frontier requests remain HTTP 422 but no longer echo invalid Unicode, raw input, handles or credentials in error bodies. This redaction does not suppress validation or claim to implement a transport byte/time limit.

## Verification

35 new route-and-real-SQLite regressions passed locally on CPython 3.13.5, both normal and optimized execution with pytest assertion rewriting. Exact original core, frontier, resolver and store source blobs were verified before editing. The local harness used the actual route, validators, hashed-session dependency, immutable resolver and SQLite implementation; ancillary readiness, connector specification and formula summary were synthetic. It was not a full deployment application test. The shipped tests import the real deployment app in native CI; no local harness or stubs are shipped.

The existing positive Hatun test still requires REVIEW, source/canonical vertical identity and disabled effectors, but now seeds a correctly hash-addressed observation through the existing receipt producer and requests its actual payload digest. The arbitrary-handle assertion is replaced by exact payload and resolution assertions. All unrelated tests remain untouched.

Run the normal unchanged repository CI on the final exact candidate, including `python -m pytest tests -q` under Python 3.12.10. Inspect actual jobs: a green PR workflow with skipped publication is not a deployment receipt. Do not mark source admission, browser journeys, provider qualification or runtime publication complete from local results alone.

## Remaining bounds and rollout

Unkeyed receipt hashes are not signatures. Normalized snapshots do not reverify historical payload bytes or parser revisions, establish independent sources, prove legal authority, or establish semantic entailment. General inbound HTTP streaming limits, other routes' error boundaries, outbound provider streaming bounds, licensed-source authorization and operator-declared model identity remain separate review obligations.

Keep draft/EVALUATION/HOLD until normal review and source checks permit advancement. After protected source admission, use the existing publisher, verify the exact resulting HF runtime, then product, then proof. Never push a draft candidate straight to HF. A regression calls for an additive protected repair or disabling affected review admission through the existing operational controls, not restoration of hash-count admission. Preserve historical receipts and previous deployment evidence.
