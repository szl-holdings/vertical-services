# Scoped evidence admission repair — issue #35

Disposition: EVALUATION / HOLD. This is a source repair, not model qualification,
legal validation, a deployment receipt, or whole-estate completion.

## Actual integration

`ObservationStore.resolve_payloads` performs bounded, exact-digest, same-session,
same-vertical queries in one SQLite read transaction. It selects the latest
record for each requested content digest and does not fall back to an older
record when that latest observation is unqualified. The schema migration only
adds a lookup index. Historical `counts` remains historical and must not be
used for evidence admission.

`evidence.resolve_evidence` validates connector assignment, receipt identity,
HTTP/truth state, finite observation/expiry bounds and bounded normalized JSON.
Missing, wrong-scope, future-dated and stale records do not count. A store failure
is UNAVAILABLE with a null resolved count, not an observed zero. Duplicate
content never becomes independent evidence. Immutable serialized snapshots bind
normalized summaries and scope without exposing session tokens or summary text
in the plan response.

The existing intelligence plan and invoke routes use this resolver directly.
An invocation freezes one evidence snapshot and one operator model binding;
the exact normalized observations enter the model user content. The plan and
invocation bind the same snapshot digest, serialized user-content digest and
system-instruction digest. Freshness is checked again immediately before the
HTTP dispatch. The entire serialized context and system instruction count
against the context budget. Canonical-axis collisions and invalid Unicode are
rejected. Provider redirects remain refused and inherited proxy configuration
is disabled; no caller-selected endpoints or effectors were added.

The existing positive planner regression still requires READY_FOR_INFERENCE,
but now seeds two real SQLite observation rows under the test session instead
of treating two arbitrary hash strings as evidence.

## Evidence and limits

On Python 3.13.5 / pytest 9.0.2, 37 direct SQLite/resolver tests and 10 isolated
planner/provider component cases passed. The local component harness used the
actual changed planner, Pydantic validators and HTTPX provider implementation,
but isolated the unrelated readiness/profile dependency helpers. This is NOT
a full-package import, the pinned Python 3.12.10 CI result, browser acceptance,
GPU evaluation or a live inference. The local-only harness is not installed as
a runtime fallback and is not part of this PR. All changed source/test bytes
are checked against their resulting Git blob identities before branch creation.

Tests cover fabricated hashes, scope isolation, duplicate content, expired and
future observations, invalid latest records, receipt tampering, duplicate JSON
members, malformed/non-finite summaries, Unicode/byte budgets, unavailable vs
empty storage, source mutation after planning, normalized-axis collisions and
expiry before dispatch. Native test collection must run both new test modules
and the unchanged remainder of the suite; no skip, xfail or weakened gate is
permitted to conceal failures.

A connector receipt is not a digital signature. Historical raw payload bytes
and historical parser revisions are not stored here; the repair does not claim
they were reverified. Two content digests do not imply independent authorities,
semantic support, current case treatment, jurisdictional validity, or a legally
correct deadline. Caller context and axes remain caller-reported. Operator
model revisions remain OPERATOR_DECLARED, not proof of served model identity.

## Codex completion and promotion

Keep issue #35 open. Its Hatun review path in `deploy/szl_verticals/frontier.py`
still needs the same scoped resolver and a deliberate legacy-reference contract;
do not silently turn URL hashes into authenticated payloads. Add route-level
adversarial tests and preserve its non-authorizing boundary. The general
request-streaming and provider-response streaming limits require separate
inspection; existing provider POST buffering was not rewritten by this patch.

Run full native CI against the exact PR head, review the SQL/receipt/privacy
boundaries, and verify caller authorization/licensing for any normalized source
content sent to an external model. Observe actual model runtime identity and
licensed held-out domain evaluations before grounded production claims. The
pure caller-text Counsel workbench in PR #34 remains a separate narrow contract.

Owners remain: this repository for shared Python execution; `platform` for
durable matter state; `a11oy` for product assembly and canonical HF projection;
`a11oy-net` for proof. Preserve the existing single publisher. No direct HF push,
new Space, model-weight mirror, default model change, branch-control edit or
production promotion is included. Distinct repository source SHAs must retain
their meaning throughout GitHub -> Hugging Face -> a-11-oy.com -> a11oy.net.

After normal admission, stage and read back the exact deployed runtime, run
all six existing vertical frontend/API journeys, then publish fresh matching
proof with explicit scope and remaining bounds. Roll back through the existing
admitted-source procedure; never bypass evidence gates to recover a READY label.
