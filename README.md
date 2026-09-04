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
- `/api/verticals/{vertical}/readyz` — exact readiness requirements and evidence;
- `/api/verticals/{vertical}/connectors/{connector}/fetch` — bounded live observation.

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
- `/api/build-info` — exact GitHub revision with `build.state=OBSERVED`
- `/.well-known/szl-source.json` — machine-readable source identity
- `/api/catalog` — canonical runtime and operational-fabric routes
- `/docs` — OpenAPI explorer

## Verification and deployment

`tests/test_deploy_app.py` and `tests/test_operational_fabric.py` cover the
business engines, Vessels consolidation, Living Anatomy, formula bindings,
session isolation, official-source normalization, caching, response hashing,
credential failure, and arbitrary-URL rejection.

`.github/workflows/hf-space.yml` then:

1. compiles and runs all deterministic tests;
2. validates each vertical in a six-way parallel matrix;
3. builds and smokes the Docker image;
4. preserves or creates the write-only Sentra/Killinchu signing key;
5. publishes the exact protected-main revision to
   `SZLHOLDINGS/vertical-services`;
6. restarts the Space and attests the source-bound runtime; and
7. exercises every required official source through the deployed service,
   uploading a secret-free live connector receipt.

Public runtime: `SZLHOLDINGS/vertical-services`.
