# Correction-aware assessment replay

Status: implemented source experiment, dependent on the scoped evidence work in
PR #36. Source tests do not establish production admission, provider identity,
licensed external-model use, or a deployed feature.

When an operator withdraws evidence in their existing caller session, old
intelligence plans and Hatun reviews that depended on it become
`REVALIDATION_REQUIRED`. Their original receipts remain historical facts. A
corrected result must be generated through the ordinary plan/review routes
using newly admitted evidence. Neither withdrawal nor status retrieval invokes
a model or an effector.

## Mounted API

Use the same `X-SZL-Session` token as the connector observations and assessments.
Aliases such as `puriq` resolve to the canonical `finance` scope.

1. Call the existing `POST /api/verticals/{vertical}/intelligence/plan` or
   `POST /api/verticals/{vertical}/hatun/evaluate` with actual scoped evidence.
   Eligible responses add `receipt.evidence_replay`; their existing
   `receipt.basis_sha256` is the assessment ID. Blocked responses are explicitly
   `NOT_TRACKED` and are never upgraded by a replay status read.
2. Inspect `GET /api/verticals/{vertical}/evidence/assessments/{assessment_id}`.
   `CURRENT` means the recorded direct evidence still matches at the checked
   time and under the current connector policy. It is not a complete re-run of
   model binding, readiness, formula policy, or business authorization.
3. Withdraw one to 64 exact payload digests with
   `POST /api/verticals/{vertical}/evidence/withdraw` and JSON
   `{"evidence_sha256":["<64 lowercase hex characters>"]}`. This withdraws use
   only in that session and vertical. It does not declare a global source
   retraction. Missing and foreign records return the same 404; a mixed request
   changes nothing. Repeating a successful withdrawal is idempotent.
4. Read the old assessment to see exact changed dependency digests and reasons.
   Fetch/ingest a corrected new payload through the existing authorized source
   pipeline, then call the normal plan/review endpoint for a new receipt.

## Persistence and invalidation

Two additive tables live in the existing observation database. Only dependency
hashes, times, kind and invalidation reasons are stored for assessments. Raw
prompts, normalized source summaries, generated model output and raw session
tokens are not copied into these tables.

Each eligible assessment records at most the resolver's 64 direct dependencies.
There is a hard capacity of 10,000 historical assessments per canonical vertical
and session; new registration fails closed at capacity. This is not a global
storage quota. Existing observation storage, session lifecycle, retention and
deployment resource limits still need their owning operational policy. No
automatic pruning silently forgets withdrawal tombstones or old invalidations.

SQLite transactions serialize registration, withdrawals and observation writes.
Changing a recorded payload's selected receipt or normalized summary latches
invalidation during `put`, including change-then-restore writes. Status reads
also detect expiry, missing/tampered rows, clock regression and current
connector-policy disagreement. Temporary unavailable storage is an error, not
an empty/current result and not a permanent proof of invalidity.

Withdrawals survive repeat observation of identical payload bytes. Connector
cache reads inspect the latest query result first, so withdrawing it cannot
silently resurrect an older cached answer. A new source payload can qualify
only through a new normal assessment; old invalidation is never cleared.

Provider invocation checks both immutable snapshot identity and the persisted
assessment's terminal state after entering the HTTP client, immediately before
dispatch, and after the response. A changed basis prevents dispatch or withholds
the output. These checks cannot retract already transmitted content or promise
atomicity with a remote provider. The old snapshot is never replaced silently
with a different source summary.

## Scope and validation

This is direct-dependency currentness for existing intelligence plans, their
linked invocation receipts, and Hatun reviews. It is not a complete graph of
arbitrary claims, exports, external copies or durable matters. Old unregistered
receipts are `NOT_FOUND`, not implicitly current. The existing session token is
a possession-based scope; this change does not establish enterprise tenant
identity. The default SQLite durability remains `EPHEMERAL_FILE` unless the
operator explicitly configures persistent storage. Durable matters remain the
platform owner's responsibility.

The prior mutation-positive provider test is deliberately split: unchanged
evidence still proves exact model-input identity; changed evidence now denies
the call instead of sending the earlier snapshot. Regressions use real SQLite,
mounted application routes and HTTPX's in-process mock transport. Readiness is
fixed in focused fixtures to isolate this gate. No real source or model traffic
is needed. Run the whole native test suite as well as optimized-Python focused
tests; native CI uses Python 3.12.10 whereas local Windows verification may use
a different recorded Python version.

Rollback must preserve the evidence withdrawal policy: do not deploy old code
that ignores tombstones while continuing to serve affected inference. Preserve
the database and disable affected inference until a compatible admitted build
is restored. No destructive schema migration or provider deployment is included.
