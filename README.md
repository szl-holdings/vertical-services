# SZL Vertical Services

Five deployable FastAPI services replacing upstream-probe shells with functional domain engines.

| Service | Capability | Core endpoints |
|---|---|---|
| Sentra | Deny-by-default 8-gate policy engine; signed verdicts | `POST /v1/evaluate`, `GET /v1/verdicts` |
| Lyte | Metrics ingest, baselines, drift detection | `POST /v1/metrics`, `GET /v1/summary`, `GET /v1/drift` |
| Vessels | Maritime dark-activity, speed, corridor, loitering risk | `POST /v1/positions`, `GET /v1/fleet/risk` |
| Finance | Volatility, drawdown and momentum analytics | `POST /v1/observations`, `GET /v1/portfolio/brief` |
| Terra | Price/sqft, cap-rate and comparable analytics | `POST /v1/listings`, `GET /v1/market/analysis` |

## Run

```bash
docker build --build-arg SERVICE=sentra -t szl-sentra .
docker run --rm -p 7860:7860 -e SENTRA_SIGNING_KEY='set-in-secret-store' szl-sentra
```

Replace `sentra` with `lyte`, `vessels`, `finance`, or `terra`.

## Truth posture

- Inputs are labeled MEASURED or REPORTED.
- Derived analytics are MODELED.
- No upstream response is represented as available when it cannot be obtained.
- Sentra uses an ephemeral development signing key unless `SENTRA_SIGNING_KEY` is configured. Production deployments must set that secret.
