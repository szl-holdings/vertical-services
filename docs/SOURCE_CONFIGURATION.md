# Source Configuration Contract

The source mesh never substitutes synthetic values for missing credentials or licenses.

## Keyless public authorities

These adapters are expected to operate without tenant credentials, subject to the authority's public service availability and rate limits:

- NOAA/NWS marine alerts
- NOAA CO-OPS observations
- CISA Known Exploited Vulnerabilities
- OFAC sanctions publication
- United Nations sanctions publication
- Census ACS
- OpenFEMA
- FHFA House Price Index
- NVD (lower anonymous rate limit; optional `NVD_API_KEY`)
- FIRST EPSS
- Federal Register
- SEC EDGAR submissions and company facts
- Treasury Fiscal Data

## Explicit credentials

- `COURTLISTENER_API_TOKEN` — CourtListener authenticated API access where required.
- `FRED_API_KEY` — FRED series observations.
- `CONGRESS_API_KEY` — Congress.gov API.
- `GITHUB_READ_TOKEN` — optional higher-rate GitHub Actions telemetry.
- `NVD_API_KEY` — optional higher-rate NVD access.
- `SPIRE_MARITIME_API_TOKEN` — optional licensed current maritime provider adapter when its contract is enabled.
- `AISSTREAM_API_KEY` or `SZL_AISSTREAM_API_KEY` — optional authorized AISStream transport in the canonical Killinchu runtime.

A missing credential is reported as `AUTH_REQUIRED`. It is never represented as zero results, healthy, connected, or live.

## Persistent state

Set both values only when the hosting environment actually supplies durable storage:

```text
SZL_STATE_PATH=/mounted/persistent/path/vertical-services.sqlite3
SZL_STATE_DURABILITY=persistent
```

Without both, the ledger remains honestly labeled `EPHEMERAL_FILE`.

## Licensing

Current AIS and proprietary maritime intelligence require an authorized provider contract. Historical NOAA AIS metadata is official evidence but is not a current vessel-position feed. Public outputs must remain historical, aggregated, delayed, or licensed and must not expose precise military tracking, targeting, weapon-release, or effector-control capability.
