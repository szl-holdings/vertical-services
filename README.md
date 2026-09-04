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

| Route | Canonical vertical | Business engine | Required authoritative sources |
|---|---|---|---|
| `/sentra` | Sentra | Deny-by-default policy gates and receipted verdicts | CISA KEV + FIRST EPSS |
| `/lyte` | Lyte | Metric ingestion, summaries, percentiles, and drift | GitHub Actions telemetry |
| `/killinchu` | Killinchu | Defense policy plus maritime risk and evidence | NWS marine alerts + NOAA CO-OPS + OFAC + UN 1718 |
| `/finance` | PURIQ Finance | Volatility, drawdown, momentum, filings, and macro context | SEC + Treasury Fiscal Data + FRED |
| `/terra` | Terra | Property calculations and public-market context | Census ACS + OpenFEMA + FHFA HPI |
| `/counsel` | PRISM Counsel | Matters, obligations, public authority, and proof chains | Federal Register + CourtListener |

## Vessels consolidation

Vessels is **not** an independent vertical. Its maritime engine remains at
`/vessels` only as a compatibility route. The canonical product, source, public
Space, Second Brain, formula binding, and operational route are Killinchu:

- source: `szl-holdings/killinchu`
- public product: `SZLHOLDINGS/killinchu`
- canonical runtime: `/killinchu`
- maritime organ: `/killinchu/v1/maritime/*`
- defense policy organ: `/killinchu/v1/defense/evaluate`
- source health: `/killinchu/v1/intelligence/source-health`
- source contract: `/killinchu/v1/intelligence/source-contract`

## Common backend contract

Every vertical exposes the same governed surfaces:

- `/api/verticals/{vertical}/anatomy` — nine ordered Living Anatomy organs;
- `/api/verticals/{vertical}/formulas` — named math and implementation bindings;
- `/api/verticals/{vertical}/connectors` — fixed source-adapter catalog;
- `/api/verticals/{vertical}/source-contract` — authority, credential, freshness,
  size, licensing, and operational-role contract;
- `/api/verticals/{vertical}/source-health` — observed, fresh, stale, expired, or
  authentication-required state;
- `/api/verticals/{vertical}/sources/refresh` — bounded batch observation;
- `/api/verticals/{vertical}/second-brain` — session-scoped observation memory;
- `/api/verticals/{vertical}/readyz` — infrastructure and production-source gates;
- `/api/verticals/{vertical}/connectors/{connector}/fetch` — bounded observation.

The nine organs are **Sense → Normalize → Context → Formula → Policy → Decide →
Verify → Remember → Receipt**. Every successful observation carries an authority,
source URL, fetch time, payload SHA-256, normalized signal, truth label, and
deterministic receipt.

## Authoritative source mesh

The v3 source mesh includes NOAA/NWS alerts, NOAA CO-OPS, CISA KEV, NVD, FIRST
EPSS, OFAC SDN, UN Security Council 1718, Census ACS, OpenFEMA, FHFA HPI, SEC
EDGAR, Treasury Fiscal Data, FRED, Federal Register, CourtListener, Congress.gov,
GitHub Actions, and optional historical NOAA/USCG AIS metadata.

The transport is fixed-host and deny-by-default. Callers cannot supply URLs.
Downloads are timeout- and byte-bounded. XML uses `defusedxml`. Redirects are
rejected except for one exact connector-declared authority host. Secret query
parameters are redacted before receipts are built. Raw source payloads are not
stored; bounded normalized summaries and receipt metadata are stored in the
observation ledger.

See [`docs/AUTHORITATIVE_SOURCE_MESH.md`](docs/AUTHORITATIVE_SOURCE_MESH.md) for
the complete source matrix, environment variables, freshness semantics,
operational gates, and Killinchu boundary.

## Runtime readiness versus source operation

`/readyz` answers whether the service can safely accept traffic. It deliberately
does not flap because an external authority is temporarily unavailable.

Each vertical readiness record separately reports:

- `runtime_ready` — source-bound build, writable store, formula contract, signing
  where required, and connector code present;
- `production_ready` — runtime ready plus explicitly persistent storage,
  configured required credentials, and a fresh observation for every required
  source;
- `sources_operational` — required authoritative sources are currently fresh.

A green deployment is not represented as proof that every authority was
observed.

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

## Killinchu safety and data boundary

Killinchu may use current marine alerts, station observations, sanctions
candidate evidence, licensed or properly authorized AIS, and historical AIS
corpora for human-governed decision support.

- `NO_CANDIDATES_IN_QUERY` is not sanctions clearance.
- Historical NOAA AIS is not a live vessel feed.
- Public precise target tracking, autonomous targeting, weapon release, and
  public effector control are outside this runtime.
- `effectors_enabled=false`, `automation_authority=NONE`, and
  `human_approval_required=true` remain explicit.

A future Spire, Windward, or other commercial maritime data integration remains
`AUTH_REQUIRED` until a licensed contract, exact host, permitted fields,
retention policy, and write-only credentials are deliberately configured. No
proprietary provider data is bundled here.

## State and durability

Business working sets remain isolated process memory behind a caller-held
`X-SZL-Session` token. Source observations are written to a bounded SQLite
ledger under a hashed session scope.

The default is labeled `EPHEMERAL_FILE`. Production source operation requires:

```text
SZL_STATE_PATH=/mounted/persistent/path/vertical-services.sqlite3
SZL_STATE_DURABILITY=persistent
SZL_SOURCE_MAX_ROWS=20000
```

Required credentialed sources also need `FRED_API_KEY`, `CENSUS_API_KEY`, and
`COURTLISTENER_API_TOKEN`. Optional enrichments use `NVD_API_KEY`,
`GITHUB_READ_TOKEN`, and `CONGRESS_API_KEY`. Values are never returned.

## Verification and deployment

Deterministic tests cover the business engines, Vessels consolidation, Anatomy,
formula bindings, session isolation, authority normalization, exact OFAC
redirect handling, secret redaction, safe XML parsing, caching, stale-last-good
behavior, response hashing, missing credentials, and arbitrary-URL rejection.

`.github/workflows/hf-space.yml` compiles and tests the exact source, validates
each vertical, builds and smokes the image, routes publication through the
canonical Hugging Face writer, and records live probe evidence when the writer
is available.

Public runtime: `SZLHOLDINGS/vertical-services`.
