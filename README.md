---
title: SZL Vertical Services
emoji: ⚙️
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 7860
pinned: true
license: apache-2.0
---

# SZL Vertical Services

A source-bound FastAPI operational fabric for six canonical SZL verticals.

> **Canonical defense authority:** Killinchu is the sole public cyber-physical
> resilience product. The `sentra` and `vessels` engines remain independently
> testable compatibility lobes named **Defend/Aegis** and **Maritime/Vessels**;
> they do not retain standalone product authority. See
> [`docs/KILLINCHU_RUNTIME_CONVERGENCE.md`](https://github.com/szl-holdings/vertical-services/blob/main/docs/KILLINCHU_RUNTIME_CONVERGENCE.md).

| Route | Canonical vertical | Business engine | Required official source |
|---|---|---|---|
| `/sentra` | Sentra | Nine deny-by-default policy gates and HMAC-SHA256 verdict receipts | CISA Known Exploited Vulnerabilities |
| `/lyte` | Lyte | Metric ingestion, percentiles, summaries, and drift scoring | GitHub Actions execution telemetry |
| `/killinchu` | Killinchu | Defense policy plus maritime track and voyage-risk calculations | NOAA / U.S. Coast Guard 2025 AIS metadata |
| `/finance` | PURIQ Finance | Volatility, drawdown, momentum, signals, and filing evidence | SEC EDGAR submissions |
| `/terra` | Terra | Price-per-square-foot, cap-rate, comps, and parcel evidence | NYC PLUTO |
| `/counsel` | PRISM Counsel | Matters, obligations, docket ranking, public authority, and receipt chains | Federal Register |

## Vessels consolidation

Vessels is **not** an independent vertical. Its maritime engine remains available
at `/vessels` only as a compatibility route. The canonical product, source,
public Space, second brain, formula binding, and operational route are Killinchu:

- source: `szl-holdings/killinchu`
- public product: `SZLHOLDINGS/killinchu`
- canonical runtime: `/killinchu`
- maritime organ: `/killinchu/v1/maritime/*`
- defense policy organ: `/killinchu/v1/defense/evaluate`

## Common backend contract

Every vertical exposes the same governed surfaces:

- `/api/verticals/{vertical}/anatomy` — nine ordered Living Anatomy organs;
- `/api/verticals/{vertical}/formulas` — named math and implementation bindings;
- `/api/verticals/{vertical}/connectors` — fixed official-source connector catalog;
- `/api/verticals/{vertical}/second-brain` — session-scoped observation memory;
  each observation carries `withdrawn` (`true` once this session withdrew it);
- `/api/verticals/{vertical}/readyz` — exact readiness requirements and evidence;
- `/api/verticals/{vertical}/connectors/{connector}/fetch` — bounded live observation;
- `POST /api/verticals/{vertical}/evidence/withdraw` — withdraw exact payload
  digests from this session's use (not a source-wide retraction);
- `GET /api/verticals/{vertical}/evidence/assessments/{assessment_id}` — whether a
  plan or Hatun review is still `CURRENT` or now `REVALIDATION_REQUIRED`.

A Hatun `REVIEW` and a `READY_FOR_INFERENCE` intelligence plan register a
replay assessment before they return a receipt, and invocation re-checks it
before and after provider dispatch. The 404, 409 and 503 responses, the replay
clock contract and the `withdrawn` flag are specified in
[`docs/CORRECTION_REPLAY.md`](https://github.com/szl-holdings/vertical-services/blob/main/docs/CORRECTION_REPLAY.md).
The machine-readable list of every per-vertical route, including the plan,
invoke, Hatun and HTML surfaces, is `operational_fabric` in `/api/catalog`.

The nine organs are **Sense → Normalize → Context → Formula → Policy → Decide →
Verify → Remember → Receipt**. Every observation carries a source URL, fetch
time, payload SHA-256, normalized signal, truth label, and deterministic receipt.

## Formula fabric

Vertical-specific operational math remains close to the code that executes it:
Sentra gate conjunctions, Lyte percentile and z-shift calculations, Killinchu
Haversine/dark-gap/implied-speed/risk formulas, PURIQ log-return/volatility/
drawdown/momentum formulas, Terra PPSF/cap-rate/comp dispersion, and Counsel
deadline/priority/exposure/hash-chain formulas.

The shared Lambda roll-up follows the weighted-geometric-mean shape published in
`szl-holdings/szl-formulas`. It is labeled **ADVISORY** everywhere. Lambda
uniqueness remains **Conjecture 1 (open)** and is never represented as proven
trust.

## Real-data connector boundary

Callers choose a connector identifier and bounded parameters; they can never
supply a URL. The runtime:

- resolves only fixed HTTPS destinations;
- rejects redirects and unknown parameters;
- enforces response byte and timeout budgets;
- keeps API keys in headers or redacted query parameters;
- never returns credential values;
- normalizes provider payloads into vertical signals;
- stores only bounded normalized summaries and receipt metadata;
- uses explicit `REPORTED`, `MODELED`, `MEASURED`, or `UNAVAILABLE` labels.

Required keyless sources are CISA KEV, GitHub Actions, NOAA InPort AIS metadata,
SEC EDGAR, NYC PLUTO, and the Federal Register. NVD enrichment is optional.
Congress.gov is optional and remains `AUTH_REQUIRED` until `CONGRESS_API_KEY` is
configured.

NOAA AIS is official historical planning data. It is **not** described as a
real-time vessel feed. A licensed or authorized live AIS transport must be
connected separately before Killinchu may claim live vessel positions.

## State and durability

Business working sets remain isolated process memory behind a caller-held
`X-SZL-Session` token. Official-source observations are written to a bounded
SQLite ledger under the hashed session scope.

The default SQLite file is labeled `EPHEMERAL_FILE`. The runtime emits
`PERSISTENT_CONFIGURED` only when an operator explicitly sets both:

```text
SZL_STATE_PATH=/mounted/persistent/path/vertical-services.sqlite3
SZL_STATE_DURABILITY=persistent
```

That label is a configuration assertion, not an automatic claim that a hosting
plan supplies durable storage.

## Live contract

- `/` — responsive user, developer, operator, and investor front door
- `/healthz` — liveness, canonical engine catalog, and state modes
- `/readyz` — fail-closed estate readiness
- `/api/build-info` — exact source/runtime identity with `build.state=OBSERVED`
- `/api/source` — compatibility route for the same source/runtime identity
- `/.well-known/szl-source.json` — well-known route for the same identity
- `/api/catalog` — canonical runtime and operational-fabric routes
- `/docs` — OpenAPI explorer

The three machine-readable identity documents and `/healthz` carry the same
top-level source repository, observed source revision, runtime source repository,
runtime source revision, disabled-effector boundary, and required-human-approval
boundary. The provider repository remains separately identified by `hf_repository`.
An unbound or disagreeing revision is reported as `UNAVAILABLE` rather than guessed.

## Verification and deployment

`tests/test_deploy_app.py` and `tests/test_operational_fabric.py` cover the
business engines, Vessels consolidation, Living Anatomy, formula bindings,
session isolation, official-source normalization, caching, response hashing,
credential failure, and arbitrary-URL rejection.

On every pull request to `main` and every `main` push, `.github/workflows/hf-space.yml`
compiles and runs all deterministic tests, validates each vertical in a six-way
parallel matrix, and builds and smokes the Docker image.

It publishes only after a push to `main` (or a manual dispatch on `main`), and
only when a Hugging Face token secret is available to this repository. Without a
token, it records a `DELEGATED` receipt, publishes nothing, and names the a11oy
`hf-sync.yml` `publish-vertical-flagships` job as the writer. That job runs only
on a manual, plan-gated dispatch in `szl-holdings/a11oy`.
[`deploy/DEPLOYED.md`](https://github.com/szl-holdings/vertical-services/blob/main/deploy/DEPLOYED.md)
describes both paths. A green workflow run is not a deployment receipt. The
running Space's `/api/build-info` is.

Public runtime: `SZLHOLDINGS/vertical-services`.
