# SZL Vertical Frontier

Eight original command systems, one governed evidence fabric.

The Vertical Frontier is a dependency-free Python 3.12 reference runtime and
responsive public experience for:

1. **A11oy** — governed AI command fabric
2. **Killinchu** — defense and maritime decision intelligence
3. **Lyte** — business observability and execution intelligence
4. **Sentra** — cyber exposure and remediation command
5. **Terra** — property and place intelligence
6. **PURIQ Finance** — evidence-first financial research
7. **PRISM Counsel** — citation-first legal matter command
8. **Living Anatomy** — system health and governed cognition

It does not paint one generic dashboard eight colors. Each vertical owns a
separate spatial model, visual instrument, interaction cadence, operating wedge,
source boundary, model route, kernel route, and prohibited-action contract.

## Product architecture

```text
official or operator-bound source
             │
             ▼
   bounded source adapter
             │
             ▼
 source state + freshness + digest
             │
             ▼
  model proposal route (no authority)
             │
             ▼
 kernel checks + invariant gates
             │
             ▼
 human review signal / operator binding
             │
             ▼
 deterministic receipt + verification
```

The public reference runtime never executes a trade, legal filing, remediation,
production mutation, target selection, physical effect, or weapon command.
Models propose. Kernels check. Humans bind consequential action in a separately
governed operator-owned system.

## Eight distinct front ends

| Vertical | Composition | Primary instrument | Product lane |
| --- | --- | --- | --- |
| A11oy | Decision ribbon | Proof lattice | Reconstructable proposal → policy → approval → verification |
| Killinchu | Theater map | Orbital maritime radar | Maritime and mission evidence without public physical actuation |
| Lyte | Signal waterfall | Outcome topology | Technical signal → business commitment → owner → outcome |
| Sentra | Exposure graph | Blast-radius prism | Exploitability, path, criticality, control, and closure evidence |
| Terra | Parcel stack | Terrain ledger | Parcel, ownership, constraint, hazard, and scenario diligence |
| PURIQ Finance | Research terminal | Thesis tape | Filing evidence, assumptions, counterevidence, and monitored falsification |
| PRISM Counsel | Citation rail | Matter chronology | Authority, fact, issue, jurisdiction, deadline, and human work product |
| Living Anatomy | Organ body | Living-system map | Memory, evidence, policy, runtime, and downstream decision health |

Every composition is implemented locally in `static/app.js` and
`static/themes.css`. There are no copied vendor assets, external JavaScript
frameworks, tracking scripts, remote fonts, or proprietary UI packages.

## Shared advantage

The products remain distinct, while these capabilities compound across the
estate:

- one cross-vertical evidence ontology;
- exact source and freshness labels independent of model confidence;
- deterministic proposal and verification receipts;
- nine-organ Living Anatomy compatibility;
- bounded session-scoped Second-Brain memory contract;
- portable SZL models and kernels rather than one provider lock-in;
- explicit human binding for consequential decisions;
- fail-closed prohibited-action classes.

The registry in `verticals.json` is the public contract. Startup fails if two
verticals reuse the same layout, instrument, or palette, or if a vertical lacks
its model, kernel, source, wedge, or refusal boundary.

## Governed model and kernel routing

The first release binds existing public SZL assets by role rather than making
unsupported performance claims.

### Model routes

- `SZLHOLDINGS/szl-nemo` — bounded planning and system explanation
- `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2` — extraction, narrative, and
  receipt composition
- `SZLHOLDINGS/A11OY-MINI` — bounded analysis and evidence summarization

Every model route is `PROPOSAL_ONLY`. A model response cannot authorize or
execute an effect.

### Kernel routes

- `SZLHOLDINGS/szl-invariants` — vertical policy and state invariants
- `SZLHOLDINGS/szl-lambda-gate` — advisory routing only
- `SZLHOLDINGS/szl-blocked` — hard-deny policy controls
- `SZLHOLDINGS/szl-governed-norm` — bounded feature normalization
- `SZLHOLDINGS/szl-kernels` — portable organ and compute primitives
- `SZLHOLDINGS/governed-inference-meter` — inference and energy receipts when a
  readable counter exists

Lambda uniqueness remains **Conjecture 1 — OPEN**. Kernel output does not grant
permission.

## Official-source contracts

The Python service permits only fixed HTTPS hosts, rejects redirects outside the
allowlist, caps source responses at 2 MiB, applies an eight-second timeout, and
never accepts a caller-supplied URL.

| Vertical | Reference source | State boundary |
| --- | --- | --- |
| Sentra | CISA Known Exploited Vulnerabilities | Known exploitation does not prove asset exposure |
| Lyte | GitHub Actions API | Workflow execution is not a business outcome |
| Killinchu | NOAA/USCG AIS 2025 reference | Historical planning data, not a live tactical feed |
| PURIQ Finance | SEC EDGAR submissions | Filing evidence, not investment advice or a trading signal |
| Terra | NYC PLUTO | Public parcel record, not appraisal, title, lending, or housing decision |
| PRISM Counsel | Federal Register | Authority research input; licensed legal review remains required |
| A11oy | Local vertical registry | Source-bound product and authority contract |
| Living Anatomy | Local runtime health | Process health is not end-to-end readiness |

Optional future adapters named in the registry include NVD, SEC Company Facts,
Treasury Fiscal Data, FRED, Congress.gov, CourtListener, FEMA, Census, USCG,
OFAC, and OpenTelemetry. They are not represented as connected until a bounded
adapter and evidence receipt exist.

### SEC operator identity

The SEC requests an identifying user agent. Configure it only in the runtime
environment:

```bash
export SEC_USER_AGENT="SZL Holdings engineering@example.com"
```

Do not commit tokens, email credentials, or private data.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/` | Responsive portfolio front door |
| `GET` | `/v/{slug}` | Distinct vertical experience |
| `GET` | `/healthz` | Process and source-binding health |
| `GET` | `/api/build-info` | Revision, runtime, registry digest, authority state |
| `GET` | `/api/v1/verticals` | Full public vertical contract |
| `GET` | `/api/v1/verticals/{slug}` | One vertical contract |
| `GET` | `/api/v1/verticals/{slug}/snapshot` | Bounded local or official-source observation |
| `GET` | `/api/v1/verticals/{slug}/route` | Model and kernel proposal route |
| `POST` | `/api/v1/decision` | Apply evidence, risk, action, and human-binding gates |
| `POST` | `/api/v1/verify` | Verify canonical JSON receipt integrity |

Receipt verification proves only that the supplied canonical JSON matches the
supplied SHA-256 digest. It does not prove truth, accuracy, safety, performance,
compliance, or authorization.

## Run locally

```bash
cd frontier
python -I -P app.py --self-test
python -I -P app.py --host 127.0.0.1 --port 7860
```

Open `http://127.0.0.1:7860`.

Run the blocking contract:

```bash
python -m pip install pytest==8.4.2
python -m pytest -q tests
```

Build the non-root container:

```bash
docker build -t szl-vertical-frontier .
docker run --rm -p 7860:7860 szl-vertical-frontier
```

## Security and privacy boundary

- no arbitrary URL fetching;
- no caller-selected source host;
- bounded request and response bodies;
- off-allowlist redirects rejected;
- no public effectors;
- no model or kernel authorization;
- no silent credential fallback;
- no secret values returned in receipts;
- no persistent user state in this reference runtime;
- no external scripts, fonts, pixels, or analytics on the public UI;
- CSP, clickjacking protection, content-type protection, referrer policy, and
  restrictive browser permissions headers.

## Pattern extraction, not copying

The research process studies public product behavior: editorial hierarchy,
mission-map legibility, system topology, evidence density, progressive
disclosure, keyboard operation, responsive navigation, and clear trust
boundaries. It does **not** copy proprietary code, private data, copyrighted
assets, non-public APIs, vendor copy, or recognizable trade dress.

Compatible open-source software may be adopted only after the exact revision,
license, dependency closure, security posture, and required attribution are
recorded. A public repository does not automatically grant permission to copy or
relicense its code.

## Truth boundary

This release establishes an original product and engineering contract. It does
not establish customer adoption, benchmark superiority, regulatory approval,
production authorization, funding, revenue, fame, or an investment outcome.
HTTP 200 establishes reachability only.
