# Authoritative Source Mesh v3

## Purpose

This service turns the SZL source inventory into a bounded, observable runtime.
Each adapter owns one fixed authority, a strict parameter contract, a response
budget, a parser, a freshness window, a maximum stale window, a normalized
signal, and a content-addressed observation receipt.

A configured adapter is not automatically operational. The service distinguishes:

- **contract ready** — code, parser, source host and limits are registered;
- **credential configured** — the named environment variable exists, without
  exposing its value;
- **fresh** — a successful observation is inside the source freshness window;
- **stale** — a prior successful observation may be served as explicitly stale;
- **expired** — the prior value is outside the allowed stale window;
- **production ready** — all required credentials and required source
  observations are current, the store is explicitly persistent, the build is
  source-bound, and required signing material is configured.

`/readyz` remains an infrastructure-readiness probe: it does not flap merely
because an upstream authority is temporarily unavailable. Exact production
source status is exposed separately through `production_ready`,
`sources_operational`, and the source-health endpoints.

## Source catalog

| Vertical | Connector | Authority | Required | Credential | Data mode |
|---|---|---|---:|---|---|
| Sentra | `cisa-kev` | CISA Known Exploited Vulnerabilities | yes | none | current |
| Sentra | `first-epss` | FIRST EPSS | yes | none | current daily probability |
| Sentra | `nvd-cve` | NIST NVD CVE 2.0 | no | optional `NVD_API_KEY` | current enrichment |
| Lyte | `github-actions` | GitHub Actions | yes | optional `GITHUB_READ_TOKEN` | first-party current |
| Killinchu | `nws-marine-alerts` | NOAA/NWS Alerts API | yes | none | current active alerts |
| Killinchu | `noaa-coops` | NOAA CO-OPS Data API | yes | none | current station observation/prediction |
| Killinchu | `ofac-sdn` | U.S. Treasury OFAC SLS | yes | none | current sanctions list |
| Killinchu | `un-1718-sanctions` | UN Security Council 1718 Committee | yes | none | current consolidated list |
| Killinchu | `noaa-ais-2025` | NOAA/USCG InPort | no | none | historical official AIS metadata |
| Finance | `sec-submissions` | SEC EDGAR | yes | none | current submissions |
| Finance | `treasury-debt-to-penny` | Treasury Fiscal Data | yes | none | current fiscal series |
| Finance | `fred-series` | Federal Reserve Bank of St. Louis FRED | yes | `FRED_API_KEY` | current macro series |
| Finance | `sec-companyfacts` | SEC XBRL Company Facts | no | none | current facts |
| Terra | `census-acs5` | U.S. Census ACS 5-year | yes | `CENSUS_API_KEY` | published estimate vintage |
| Terra | `openfema-declarations` | OpenFEMA | yes | none | current public records |
| Terra | `fhfa-hpi-state` | FHFA HPI | yes | none | current state table |
| Terra | `nyc-pluto` | NYC Open Data PLUTO | no | none | current municipal records |
| Counsel | `federal-register` | Federal Register | yes | none | current federal publications |
| Counsel | `courtlistener-search` | Free Law Project CourtListener v4 | yes | `COURTLISTENER_API_TOKEN` | current public legal corpus |
| Counsel | `congress-bills` | Congress.gov | no | `CONGRESS_API_KEY` | current legislative metadata |

## Runtime routes

- `GET /api/verticals/source-health`
- `GET /api/verticals/{vertical}/source-health`
- `GET /api/verticals/{vertical}/source-contract`
- `POST /api/verticals/{vertical}/sources/refresh`
- `POST /api/verticals/{vertical}/connectors/{connector_id}/fetch`
- `GET /api/verticals/{vertical}/readyz`
- `GET /api/verticals/{vertical}/second-brain`

Killinchu also owns product-local aliases:

- `GET /killinchu/v1/intelligence/source-health`
- `GET /killinchu/v1/intelligence/source-contract`

## Request and transport controls

1. Callers select a connector identifier; they cannot supply a URL.
2. Unknown parameters fail with HTTP 422.
3. Destinations must be HTTPS and match an exact host allowlist.
4. Redirects are denied unless a connector declares an exact authority-owned
   redirect host. Only one redirect is permitted.
5. Responses stream through a connector-specific byte budget and bounded
   connect/total timeouts.
6. XML is parsed with `defusedxml`; entity expansion and external-entity attacks
   fail closed.
7. API keys are injected only from named environment variables. Secret query
   parameters are redacted before a source URL enters a receipt.
8. Successful payload bytes are SHA-256 addressed before normalization.
9. The observation ledger stores bounded summaries and receipt metadata, never
   access tokens or raw authority payloads.
10. A failed current fetch may use a last-good value only inside the connector's
    maximum stale window. The response is labeled `REPORTED_STALE`,
    `CACHED_STALE`, and `live_claimed=false`.

## Killinchu operational boundary

Killinchu may use the mesh for marine warnings, port/coastal observations,
sanctions candidate evidence, historical AIS corpus discovery, and cyber
exposure context. These are decision-support inputs, not action authority.

- `NO_CANDIDATES_IN_QUERY` is not sanctions clearance.
- A name or identifier match is a candidate requiring identity resolution and
  qualified human review.
- NOAA historical AIS metadata is not a live vessel feed.
- A licensed AIS provider can be integrated only as a separately credentialed,
  contract-bound source with explicit rights, retention, precision, and use
  restrictions.
- Public precise target tracking, autonomous targeting, weapon release, and
  effector control are outside this runtime.
- `effectors_enabled=false`, `automation_authority=NONE`, and
  `human_approval_required=true` remain part of Killinchu's public contract.

## Leader architecture translated into SZL

The implementation follows clean-room architectural lessons rather than copying
proprietary data or code:

- **Spire Maritime:** typed API contracts, explicit bearer-token authorization,
  query-bounded vessel access, and a separate licensed data plane.
- **Windward:** separate identity, ownership, sanctions, behavioral-risk, and
  alerting layers rather than collapsing every source into one opaque score.
- **SZL adaptation:** fixed public-authority adapters, source-specific parsers,
  per-source freshness, explicit truth labels, Second-Brain handles, formula
  bindings, human approval, and hash-addressed provenance.

No Spire or Windward data is included. Their names describe an architectural
benchmark only. A future commercial integration remains `AUTH_REQUIRED` until
its contract and credentials are deliberately configured.

## Required production configuration

```text
# Source-bound image
SZL_SOURCE_REVISION=<40-character Git commit SHA>

# Persistent observation ledger
SZL_STATE_PATH=/mounted/persistent/path/vertical-services.sqlite3
SZL_STATE_DURABILITY=persistent
SZL_SOURCE_MAX_ROWS=20000

# Existing decision-receipt key
SENTRA_SIGNING_KEY=<write-only secret>

# Required credentialed authorities
FRED_API_KEY=<secret>
CENSUS_API_KEY=<secret>
COURTLISTENER_API_TOKEN=<secret>

# Optional enrichment authorities
NVD_API_KEY=<secret>
GITHUB_READ_TOKEN=<secret>
CONGRESS_API_KEY=<secret>
```

The service never invents these values. Missing required credentials appear as
`AUTH_REQUIRED`; missing current observations appear as `UNOBSERVED`.

## Acceptance evidence

A release is operational only when all of the following are separately true:

1. deterministic parser, security, caching, and failure-mode tests pass;
2. exact-head CI and container smoke tests pass;
3. the protected/default-branch source revision is published;
4. the Space reports the exact source revision;
5. source-health shows current observations for each required source;
6. credentialed required sources are configured without exposing values;
7. the store reports `PERSISTENT_CONFIGURED`;
8. live route probes close with source-safe receipts.

A green build alone is not a claim that the authorities were observed.
