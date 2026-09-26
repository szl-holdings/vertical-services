# Correction-aware assessment replay

Status: implemented source experiment, dependent on the scoped evidence work in
PR #36. The withdraw and assessment routes are mounted in
`deploy/szl_verticals/frontier.py` since #48, which also made receipt
registration and provider dispatch require a `CURRENT` assessment. Source tests
do not establish production admission, provider identity, licensed
external-model use, or a deployed feature.

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
   Eligible responses (a Hatun `REVIEW`, or a plan whose decision is
   `READY_FOR_INFERENCE`) add `receipt.evidence_replay`; their existing
   `receipt.basis_sha256` is the assessment ID. The assessment is registered
   before the receipt is returned, and a registration that is not `CURRENT`
   returns 409 instead of a receipt (see [Status codes](#status-codes)).
   Blocked responses are explicitly `NOT_TRACKED` and are never upgraded by a
   replay status read.
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

The machine-readable route list is `operational_fabric` in `/api/catalog`
(`evidence_withdraw`, `evidence_assessment`); `tests/test_route_catalog.py`
keeps it equal to the mounted routes.

## Status codes

Every `detail` below is the exact response text. Session-header and
unknown-vertical errors are the same as on the other session-scoped routes.
Before any POST handler runs, the app-wide request-body bounds in
`deploy/szl_verticals/http_bounds.py` can reject the request with 400, 408, 413
or 422 in their own `{"ok": false, "error": ..., "code": ...}` shape, for
example for a body over 128 KiB or for a body sent as `application/json` that
is not valid JSON or repeats an object key. Those responses apply to every POST
route and are not repeated in the tables.

`POST /api/verticals/{vertical}/evidence/withdraw`

| Status | `detail` | When |
|---|---|---|
| 200 | none (body below) | Every requested digest was withdrawn for this session and canonical vertical. |
| 404 | `evidence not found in this session` | Any requested digest has no observation in this session and vertical. Missing and foreign digests are indistinguishable, and nothing is written. |
| 422 | `invalid request` | The body is not exactly `{"evidence_sha256": [...]}` with 1 to 64 lowercase 64-hex digests. The request is not echoed. |
| 503 | `evidence replay unavailable` | See [What 503 means](#what-503-means). |

A 200 body is `{"state": "WITHDRAWN", "distinct_payloads": <n>, "scope":
"CALLER_SESSION_AND_CANONICAL_VERTICAL", "source_retracted_globally": false,
"automatic_replay": false}`. Duplicate digests in one request collapse.
Repeating a successful withdrawal is idempotent and returns 200 again.

`GET /api/verticals/{vertical}/evidence/assessments/{assessment_id}`

| Status | `detail` | When |
|---|---|---|
| 200 | none | Body is `szl.evidence-replay-status/v1` with `state` (`CURRENT` or `REVALIDATION_REQUIRED`), `changed_dependencies`, `checked_at` and the store `durability`. |
| 404 | `assessment not found` | The ID is not 64 lowercase hex characters, was never registered, or belongs to another session or vertical. |
| 503 | `evidence replay unavailable` | See [What 503 means](#what-503-means). |

`POST /api/verticals/{vertical}/hatun/evaluate` (only when the decision is
`REVIEW`) and `POST /api/verticals/{vertical}/intelligence/plan` (only when the
decision is `READY_FOR_INFERENCE`)

| Status | `detail` | When |
|---|---|---|
| 409 | `evidence changed during assessment` | The assessment registered for this receipt is not `CURRENT`. Either the evidence changed between resolution and registration, or this exact assessment was already invalidated. |
| 503 | `evidence replay unavailable` | The assessment could not be registered, including when the scope already holds 10,000 assessments. |

An `ABSTAIN` review or a plan that is not ready is not registered, carries
`evidence_replay.state = "NOT_TRACKED"`, and cannot return these codes.

`POST /api/verticals/{vertical}/intelligence/invoke` rebuilds the plan first, so
it can return the plan codes above. It then checks the evidence twice: inside
the HTTP client immediately before dispatch, and again after the provider
responds.

| Status | `detail` | When |
|---|---|---|
| 409 | `evidence assessment requires revalidation` | The plan's assessment is missing or not `CURRENT` at either check. After the provider has responded, the output is withheld. |
| 409 | `evidence changed before provider dispatch` | Evidence re-resolved just before dispatch no longer matches the plan's snapshot. Nothing is sent to the provider. |
| 409 | `evidence changed during provider invocation; output withheld` | After the provider responds, the re-resolved snapshot differs or the evidence has expired. The generated output is discarded. |
| 503 | `evidence replay unavailable` | Either assessment check could not be read. |

The invoke responses that predate #48 are unchanged, including 503
`{"error": "INFERENCE_NOT_READY", ...}`, 503
`evidence expired before provider dispatch` and the 502 provider errors. A 409
or 503 after dispatch cannot retract content already sent to the provider.

### What 503 means

`evidence replay unavailable` means the store could not answer. The causes are
an unavailable or locked SQLite ledger, a stored assessment whose
`dependencies_json` or `reasons_json` cannot be parsed or has the wrong shape,
a failing clock (see [Clock contract](#clock-contract)), current evidence
resolution returning `UNAVAILABLE`, or a registration that hit the per-scope
capacity or an identity conflict. The response is always exactly this text, and
no database detail is exposed.

A 503 never changes stored state. The store transaction is not committed, so no
withdrawal, invalidation or `last_checked_at` update is recorded, and the
condition is never reported as 404 or `CURRENT`. Retry once the fault clears.
Requests that need a malformed stored assessment keep returning 503 until it is
repaired.

## Clock contract

This section describes `main` as of #48.

- The replay clock is read inside the store transaction, never before it.
  `register_assessment`, `assessment_status` and `withdraw_payloads` sample it
  only after they take the store's process lock and open `BEGIN IMMEDIATE`. As
  a result, writes to an assessment's `last_checked_at` follow transaction
  order, and two concurrent status reads of unchanged evidence cannot record a
  false regression.
- Where the clock comes from: as of #48 each route passes the zero-argument
  clock `time.time` as `now`, and the store also accepts a plain finite,
  non-negative number for a fixed or replayed clock.
- A clock that raises, or that returns anything other than a finite,
  non-negative `int` or `float` (NaN, infinity, a negative value or a boolean,
  for example), is a store fault. The route returns 503
  `evidence replay unavailable` and nothing is written.
- `last_checked_at` never moves backwards. If a registration or status check
  samples a time earlier than the assessment's stored `last_checked_at`, it adds
  `{"payload_sha256": null, "reason": "ASSESSMENT_CLOCK_REGRESSED"}` and the
  assessment becomes `REVALIDATION_REQUIRED`. Like every invalidation, this is
  terminal: a later correct clock does not restore `CURRENT`. Generate a new
  plan or review to proceed.
- Hatun's own review-time clock check is separate. If assessment time is
  earlier than resolution time, the review gets the `ASSESSMENT_CLOCK_REGRESSED`
  blocker and returns `ABSTAIN` (see
  [HATUN_EVIDENCE_ADMISSION_V2.md](HATUN_EVIDENCE_ADMISSION_V2.md)).

## Withdrawn payloads in second-brain memory

`GET /api/verticals/{vertical}/second-brain` keeps the caller's own observation
history, including withdrawn payloads. Each `memory.observations[]` entry
carries `withdrawn: true|false`. The value is `true` when this session withdrew
that payload digest in this canonical vertical. A withdrawn entry keeps its
original `state`, receipt fields and summary as history. Treat
`withdrawn: true` as meaning the entry is no longer usable evidence; do not rely
on `state` alone.

## Persistence and invalidation

Two additive tables live in the existing observation database. Only dependency
hashes, times, kind and invalidation reasons are stored for assessments. Raw
prompts, normalized source summaries, generated model output and raw session
tokens are not copied into these tables.

Each eligible assessment records at most the resolver's 64 direct dependencies.
There is a hard capacity of 10,000 historical assessments per canonical vertical
and session; new registration fails closed at capacity with 503, while existing
assessments stay readable. This is not a global storage quota. Existing
observation storage, session lifecycle, retention and deployment resource
limits still need their owning operational policy. No automatic pruning
silently forgets withdrawal tombstones or old invalidations.

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
the output with 409 (see [Status codes](#status-codes)). These checks cannot
retract already transmitted content or promise atomicity with a remote provider.
The old snapshot is never replaced silently with a different source summary.

## Scope and validation

This is direct-dependency currentness for existing intelligence plans, their
linked invocation receipts, and Hatun reviews. It is not a complete graph of
arbitrary claims, exports, external copies or durable matters. Old unregistered
receipts return 404 `assessment not found`; they are not implicitly current.
The existing session token is a possession-based scope; this change does not
establish enterprise tenant identity. The default SQLite durability remains
`EPHEMERAL_FILE` unless the operator explicitly configures persistent storage.
Durable matters remain the platform owner's responsibility.

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
