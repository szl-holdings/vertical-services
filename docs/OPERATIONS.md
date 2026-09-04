# Operations — SZL Vertical Services

**Version:** 1.1.0 · **Updated:** 2026-09-03 · **Doctrine:** v11 · **Truth labels:** MEASURED / REPORTED / MODELED

## Architecture

Six governed vertical engines behind one FastAPI service, each mounted as a prefixed APIRouter:

- **sentra** — policy gates: deny-by-default, eight gates (actor present, action present, resource scoped, authenticated, tier allowed, risk threshold, evidence cited, not destructive-unattended) plus a rate-limit gate; HMAC-SHA256 signed verdicts.
- **lyte** — observability: metric ingestion, percentile summaries (p50/p95/p99), split-window z-shift drift detection.
- **vessels** — maritime risk: position ingestion, >1h dark-activity gaps, haversine implied-speed anomalies (>28 kn), low-SOG loitering, fleet risk ranking. Transitional engine — the vessels vertical is retired into killinchu.
- **finance** — portfolio analytics: price observations, log-return annualized volatility, max drawdown, momentum, LONG/SHORT/FLAT signals.
- **terra** — real estate intel: listings with price-per-sqft and cap rate, comparable-market statistics.
- **counsel** — legal matter command: matter intake, obligation mapping ranked by severity, SHA-256 hash-chained receipts, docket prioritization.

## API reference

| Engine | Endpoints |
|---|---|
| root | `GET /` (landing page), `GET /healthz` (engine registry) |
| sentra | `GET /sentra/healthz`, `POST /sentra/v1/evaluate`, `GET /sentra/v1/verdicts` |
| lyte | `GET /lyte/healthz`, `POST /lyte/v1/metrics`, `GET /lyte/v1/summary?stream=`, `GET /lyte/v1/drift?stream=` |
| vessels | `GET /vessels/healthz`, `POST /vessels/v1/positions`, `GET /vessels/v1/vessel/risk?imo=`, `GET /vessels/v1/fleet/risk` |
| finance | `GET /finance/healthz`, `POST /finance/v1/observations`, `GET /finance/v1/symbol/brief?symbol=`, `GET /finance/v1/portfolio/brief` |
| terra | `GET /terra/healthz`, `POST /terra/v1/listings`, `GET /terra/v1/market/analysis?market=` |
| counsel | `GET /counsel/healthz`, `POST /counsel/v1/matters`, `POST /counsel/v1/matters/{id}/obligations`, `GET /counsel/v1/matters/{id}`, `GET /counsel/v1/docket` |

## Truth-label contract

Every response carries exactly one label:

- **MEASURED** — computed from data ingested in this runtime (statistics, verdicts, receipts).
- **REPORTED** — stored as given by the caller, not independently verified (positions, listings, ownership declarations).
- **MODELED** — a derived signal, not a measurement (risk scores, signals). Never presented as fact.

No fabricated data, ever. Fail-closed paths return explicit errors or BLOCKED_PENDING rather than optimistic defaults.

## Testing

Ten-test pytest suite in `tests/test_engines.py` covering every engine: allow/deny behavior, signature shape, percentile bounds, dark-gap and implied-speed anomaly (1 degree latitude = 60 nm = 30 kn over 2h), the 3-point finance minimum, PSF/cap-rate medians, and receipt-chain ordering.

```bash
pip install -r requirements.txt -r requirements-test.txt
python -m pytest tests -q
```

## CI

`.github/workflows/ci.yml` runs on every push and PR to main: Python 3.12, dependency install, `compileall services deploy`, `pytest`. No secrets, no deploy steps — CI validates, the Hub deploys.

## Deployment record

| Artifact | Commit |
|---|---|
| v1.0.0 app (six engines) | HF Space `b845ca63` |
| Dockerfile (python:3.12-slim, port 7860) | HF Space `3c290a5b` |
| Deployment record | HF Space `88e86a73` |
| v1.1.0 (landing page) | HF Space `0cf72fa7` |
| GitHub source parity (v1.1.0) | GitHub `c5ffc356` |
| Test suite + CI | GitHub `96c4ffa8` |

Live: https://szlholdings-vertical-services.hf.space (GitHub canonical, Hub mirror).

## Changelog

- **1.1.0** (2026-09-03) — dark-theme landing page at `GET /`: engine cards with live healthz links, truth-label legend, source and doctrine footer.
- **1.0.0** (2026-09-03) — initial six-engine service.

## Secrets

`SENTRA_SIGNING_KEY` (Space secret): when set, sentra signs verdicts with a persistent key and `/sentra/healthz` reports `signing_key_source: env`. Without it, an ephemeral development key is generated per restart and every receipt says so. Generate: `python -c "import secrets; print(secrets.token_hex(32))"`. Never commit the value.

## Vessels retirement

The vessels vertical was retired into killinchu on 2026-09-03. Charter: `szl-holdings/killinchu` — `docs/VESSELS_DOMAIN.md` (commit `985b8a30`, tests `42da99ec`). The `/vessels/*` routes here are the transitional engine.
