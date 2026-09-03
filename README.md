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

A source-bound FastAPI runtime for six governed SZL engines:

| Route | Engine | Operational contract |
|---|---|---|
| `/sentra` | Sentra | Nine policy gates and HMAC-SHA256 decision receipts |
| `/lyte` | Lyte | Metric ingestion, summaries, percentiles, and drift scoring |
| `/vessels` | Vessels engine | Maritime track-risk calculations; public product surface consolidated into Killinchu |
| `/finance` | PURIQ Finance | Volatility, drawdown, momentum, and signal calculations |
| `/terra` | Terra | Price-per-square-foot, cap-rate, and comp calculations |
| `/counsel` | PRISM Counsel | Matters, obligations, docket ranking, and hash-chained receipts |

## Live contract

- `/` — responsive operator/developer front door
- `/healthz` — liveness and engine catalog
- `/readyz` — fail-closed readiness: exact source binding plus persistent Sentra signing key
- `/api/build-info` — exact GitHub revision exposed as `build.state=OBSERVED`
- `/.well-known/szl-source.json` — machine-readable source identity
- `/docs` — OpenAPI explorer

## Honest operating boundary

The APIs perform real calculations over caller-supplied inputs. Runtime state is bounded process memory and is not represented as durable storage. No live AIS, exchange, MLS, PACER, or cybersecurity feed is claimed here. Derived analytics are labeled `MODELED`; caller inputs are `MEASURED` or `REPORTED` according to the endpoint contract.

Stateful routes require a caller-generated `X-SZL-Session` value so in-memory records are isolated by session scope. Generate a new high-entropy value with `python -c "import secrets; print(secrets.token_urlsafe(32))"` and send it on each related request. This header scopes transient state; it is not identity authentication or durable authorization.

## Source and deployment

GitHub is the source of truth. `.github/workflows/hf-space.yml` tests the runtime, ensures the Space has a persistent `SENTRA_SIGNING_KEY` without rotating an existing secret, deploys the Dockerfile-derived file set atomically, binds the exact protected-main SHA, restarts the Space, and attests the running Hugging Face commit and smoke routes.

Public runtime: `SZLHOLDINGS/vertical-services`.
