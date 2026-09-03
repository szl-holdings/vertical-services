# SZL Vertical Services

Deployable FastAPI products for the public Hugging Face vertical Spaces.
Each service has its own visual language. Backends stay Python. Frontends are
first-party HTML served from the same origin. No CDN fonts. No fabricated live feeds.

| Space | Service | Visual language | Engine |
|---|---|---|---|
| SZLHOLDINGS/sentra | Sentra | SOC carbon + crimson verdicts | 8-gate deny-by-default + HMAC receipts |
| SZLHOLDINGS/terra | Terra | Listing desk, warm paper | ppsf, cap-rate, comps |
| SZLHOLDINGS/finance | PURIQ Finance | Dense terminal tape | vol, drawdown, momentum |
| SZLHOLDINGS/vessels | Vessels | Night chart + AIS table | dark, speed, corridor, loiter |
| SZLHOLDINGS/lyte | Lyte | Observability slate | ingest, baseline, drift-z |
| SZLHOLDINGS/counsel | PRISM Counsel | Docket navy + parchment | fail-closed matter triage |

a11oy, killinchu, and david-leads stay in their own GitHub repos. This repo does not replace them.

## Run

```bash
docker build --build-arg SERVICE=sentra -t szl-sentra .
docker run --rm -p 7860:7860 -e SENTRA_SIGNING_KEY='set-in-secret-store' szl-sentra
```

`SERVICE` is one of: `sentra`, `terra`, `finance`, `vessels`, `lyte`, `counsel`.

## Truth posture

- Inputs are MEASURED or REPORTED.
- Derived analytics are MODELED.
- Sample books are labeled SAMPLE. They are not live MLS, AIS, PACER, or exchange feeds.
- Sentra uses an ephemeral key unless `SENTRA_SIGNING_KEY` is set.

## Hugging Face

This GitHub repo is the source. A Space rebuild needs an HF write token in the
existing GitHub-to-HF workflow. This change does not mutate Space runtime by itself.
