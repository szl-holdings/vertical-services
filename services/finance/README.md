# PURIQ Finance Engine v2

Provenance-first financial signal and portfolio analytics for the SZL finance
vertical. **Advisory-only. Paper-only. Not financial advice.**

Doctrine v11 contract, end to end:

- **Five-state honesty** — every response carries `state` ∈
  `MEASURED / BLOCKED / INVALID / FAILED / PROMOTED`. Missing data is
  `BLOCKED` with a reason, never fabricated.
- **Receipts** — every computation appends a hash-chained
  `UNSIGNED_HONEST` receipt; `/api/finance/v2/receipts/verify` replays the
  chain offline (`CONSISTENT` / `DIVERGENT` with the broken link).
- **Truth labels** — `advisory_only`, `paper_only`, `not_financial_advice`
  are present on every payload.
- **Fixture lane** — deterministic local series (`data_origin: "fixture"`)
  for offline verification; never presented as market data.

## Operate in five minutes

```bash
cd services/finance
pip install fastapi uvicorn pydantic
SZL_FINANCE_ORIGIN=fixture uvicorn app:app --port 7860
# open http://localhost:7860        -> signal console
# open http://localhost:7860/panels -> verification desk
```

Point at live data by omitting the env var (default lane pulls daily bars
from stooq, no API key). If stooq is unreachable the API returns
`state: BLOCKED` with the reason — by design.

The standalone image includes the engine, feed, receipt modules, and both HTML
surfaces. Build it from the repository root:

```bash
docker build --build-arg SERVICE=finance --tag szl-finance:local .
docker run --rm --publish 127.0.0.1:7861:7860 \
  --env SZL_FINANCE_ORIGIN=fixture szl-finance:local
# In another terminal:
python tools/verify_finance_engine.py --base-url http://127.0.0.1:7861
```

CI builds this image and exercises both pages, fixture computations, and the
unsigned receipt chain through HTTP. This verifies the standalone image only;
the shared `deploy/app.py` fabric and public Hugging Face publication have
separate source and deployment contracts. Fixture smoke does not establish
live market-data availability.

## Surface

| Route | What it does |
|---|---|
| `GET /` | Signal console UI (signals + risk strip, portfolio analyzer, chain verify) |
| `GET /panels` | Verification desk UI (chain integrity + full ledger) |
| `GET /healthz` | Liveness + schema + configured lane |
| `GET /api/finance/v2/signals/{symbol}?origin=stooq\|fixture` | SMA/RSI/MACD/Bollinger-z stack + advisory verdict + receipt |
| `GET /api/finance/v2/quote/{symbol}?benchmark={symbol}` | Last close, bars, vol, Sharpe, max drawdown; real beta vs an optional measured benchmark + receipt |
| `POST /api/finance/v2/portfolio` | `{holdings: {SYM: [closes...]}}` → per-asset + aggregate report + receipt |
| `GET /api/finance/v2/receipts` | Full hash-chained receipt ledger |
| `GET /api/finance/v2/receipts/verify` | Offline chain verification |

## Layout

```
services/finance/
  engine.py    # stdlib signal + portfolio math, fail-closed
  feed.py      # stooq live lane + deterministic fixture lane
  receipts.py  # UNSIGNED_HONEST hash-chained receipts
  app.py       # FastAPI surface (v2 routes, serves static UI)
  static/
    console.html  # signal console (signals + risk strip + portfolio)
    panels.html   # verification desk (chain integrity + ledger)
  .env.example
tests/test_finance_engine_v2.py  # fixture-gated, offline CI-safe
```

## Tests

```bash
pytest tests/test_finance_engine_v2.py -q
```

18 tests: known-math anchors (RSI rising = 100, beta(x,x) = 1, monotone
drawdown = 0), fixture determinism, five-state blocking, truth labels,
digest parity, and chain tamper/reorder detection.

Apache-2.0. Doctrine v11. The receipt chain is in-process by design —
persistence and export belong to the deployment plane (szl-lake); the chain
attests to what this process emitted since boot and says so on the ledger.
