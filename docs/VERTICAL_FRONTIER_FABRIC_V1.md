# SZL Vertical Frontier Fabric v1

## Status

This package is the shared, typed backend and experience contract for the SZL
flagship and vertical estate. It does not claim that every individual product
front end has already consumed the contract. Each product still requires its
own implementation PR, tests, deployment receipt, and live verification.

## System boundary

The fabric separates six concerns that are commonly collapsed into one AI
application:

1. **Experience** — the unique visual grammar, workflow modules, operator
   outcome, and evidence contract for a vertical.
2. **Source** — a named official or operator-owned connector with a fixed host,
   path, parameters, response type, and size boundary.
3. **Proposal** — a model output carrying model identity, exact revision,
   confidence, source references, and an explicit truth state.
4. **Policy** — independent blocking and advisory kernels that never inherit
   authority from the proposing model.
5. **Human binding** — an explicit approver, scope, decision, policy revision,
   and timestamp for consequential action.
6. **Receipt** — a deterministic append-only integrity record that can be
   replayed and checked without being misrepresented as proof of truth.

```text
official or operator-owned source
              │
              ▼
     bounded normalized signal
              │
              ▼
 model proposal + citations + revision
              │
              ▼
 independent kernels and policy boundary
              │
        ┌─────┴─────┐
        │           │
      HOLD         DENY
        │           │
        └─────┬─────┘
              │ complete human bind, declared scope only
              ▼
       bounded effect adapter
              │
              ▼
 receipt → verification → measured outcome
```

The default package contains **no public effect adapter**. Missing model or
kernel bindings are reported as `UNAVAILABLE`. Consequential effects default to
`HOLD` until all declared SZL kernels are bound and the human binding is
complete.

## Canonical vertical lanes

### A11oy — governed decision infrastructure

- **Signature front end:** quiet editorial command system, decision trajectory,
  policy chamber, human-bind rail, receipt drawer.
- **Core object:** typed decision trajectory.
- **Models:** SZL Nemo candidate, A11OY-MINI candidate, ReceiptAgent candidate.
- **Kernels:** invariants, blocked-policy gate, Lambda advisory gate, inference
  meter.
- **Effect boundary:** human-bound; no public effector.

### Hatun — executive cognition

- **Signature front end:** midnight copper constellation, council chamber,
  commitment knots, retrospective calibration.
- **Core object:** temporal decision constellation.
- **Edge:** joins intent, evidence, decisions, delegation, commitments,
  confidence changes, and measured outcomes instead of acting as a generic
  note-taking assistant.

### Killinchu — defense and maritime decision intelligence

- **Signature front end:** carbon radar field, cyan tracks, infrared warnings,
  rules-boundary ring, mission clock, simulation comparison.
- **Core object:** uncertainty- and policy-aware track.
- **Official public source:** NOAA historical Nationwide AIS index for research,
  planning, and simulation only.
- **Effect boundary:** public mode is `SIMULATED_ONLY`; weapon, launch, strike,
  target, and other non-simulated effect requests fail closed.

### Sentra — cyber risk and response

- **Signature front end:** electric nervous-system graph, causal path tracing,
  exposure pulse, incident replay, control proof stack.
- **Core object:** business-consequence attack path.
- **Official public sources:** CISA Known Exploited Vulnerabilities and optional
  NIST NVD enrichment.
- **Effect boundary:** human-bound response adapters only.

### Lyte — business observability

- **Signature front end:** calm aurora trace river, change lens, customer-impact
  map, outcome replay.
- **Core object:** change-to-business-outcome causal chain.
- **Sources:** user-owned GitHub Actions telemetry, user-owned
  OpenTelemetry-compatible backends, and operator evidence.
- **Edge:** every conclusion preserves the query, cohort, deployment revision,
  action, and measured post-action outcome.

### PURIQ Finance — evidence-backed market research

- **Signature front end:** deep emerald research terminal, ivory reading planes,
  amber scenario bands, filing footnotes.
- **Core object:** versioned thesis evidence graph.
- **Official public sources:** SEC EDGAR submissions and Company Facts.
- **Effect boundary:** advisory research only; no trade execution.

### Terra — parcel and civic change intelligence

- **Signature front end:** cartographic strata, ownership lattice, zoning delta,
  scenario terrain.
- **Core object:** time-aware parcel twin.
- **Official public source:** NYC PLUTO through NYC Open Data.
- **Effect boundary:** advisory analysis and reviewed exports only.

### PRISM Counsel — matter and argument command

- **Signature front end:** graphite legal chamber, parchment planes, issue prism,
  argument lattice, deadline and authority rail.
- **Core object:** source-linked matter twin.
- **Official public sources:** Federal Register and optional Congress.gov API.
- **Effect boundary:** human-reviewed work product; no autonomous filing or
  legal conclusion.

### Living Anatomy — system-body intelligence

- **Signature front end:** bioluminescent organs, dependency circulation, injury
  simulator, recovery replay.
- **Core object:** stateful organ with health, dependency, failure, recovery,
  policy, and evidence.
- **Effect boundary:** bounded simulation only.

### SZL Atlas — public estate explorer

- **Signature front end:** cobalt artifact constellation, source-binding beacon,
  evidence route, precise artifact lens.
- **Core object:** provider-observed artifact linked to canonical source and
  limitations.
- **Effect boundary:** read-only.

## Package layout

```text
frontier_fabric/
  catalog.py          # verticals, themes, model/kernel bindings, connectors
  connectors.py       # fixed-source bounded fetch client
  engine.py           # proposal → policy → human bind → receipt evaluation
  fastapi_router.py   # optional HTTP integration
  receipts.py         # canonical JSON and append-only SHA-256 integrity chain
  types.py            # typed public contracts
scripts/
  export_vertical_frontier_contract.py
tests/
  test_frontier_fabric.py
```

## Python integration

```python
from fastapi import FastAPI
from frontier_fabric.fastapi_router import create_router

app = FastAPI()
app.include_router(create_router())
```

Public routes:

```text
GET  /api/vertical-fabric/v1/healthz
GET  /api/vertical-fabric/v1/verticals
GET  /api/vertical-fabric/v1/verticals/{vertical_id}
GET  /api/vertical-fabric/v1/verticals/{vertical_id}/experience
POST /api/vertical-fabric/v1/evaluate
POST /api/vertical-fabric/v1/receipts/verify
```

## Model adapter contract

A model is not considered live because its Hugging Face repository exists. An
adapter must be registered against its exact `SZLHOLDINGS/...` identity and
must return:

- model repository identity;
- exact model revision;
- explicit confidence or `None`;
- declared source references;
- truth state such as `ADVISORY`, `MEASURED`, or `UNAVAILABLE`;
- a bounded structured payload.

The model cannot produce an approval object, alter the policy kernel set, or
write an authorization receipt.

## Kernel adapter contract

Each declared kernel is independently registered by exact repository identity.
The adapter returns a structured `KernelResult` with:

- exact kernel identity;
- pass/fail;
- blocking or advisory behavior;
- explicit truth state;
- reason and evidence.

The strict effect gate is enabled by default. A consequential effect cannot
advance while any declared SZL kernel remains unbound.

## Connector contract

The public connector client accepts a connector ID, not a URL. It enforces:

- HTTPS;
- exact host allowlists;
- path-prefix allowlists;
- regular-expression-constrained path parameters;
- query-key allowlists;
- bounded timeouts and response sizes;
- declared response media types;
- no automatic redirects;
- no silent credential fallback.

Operator evidence, OpenTelemetry, and local Anatomy connectors are declared but
unavailable until an operator binds them in the deployment environment.

## Front-end definition of done

A vertical front end is not complete merely because it uses the right colors.
Its implementation PR must prove:

- a unique information architecture and signature interaction from this
  contract, rather than a reskinned shared dashboard;
- responsive behavior at 320×568, 375×812, 768×1024, and 1440×900;
- no horizontal overflow outside intentionally scrollable evidence regions;
- keyboard navigation, visible focus, semantic landmarks, and 44-pixel minimum
  primary controls;
- reduced-motion equivalence and high-contrast legibility;
- loading, partial, unavailable, denied, stale, and tampered states;
- source, model revision, kernel state, policy revision, human binding, and
  receipt access at the point of decision;
- no fabricated counts, benchmark claims, customer claims, energy readings, or
  authorization state;
- source-bound deployment and live route verification after merge.

## Novel cross-vertical objects

The shared fabric enables product concepts that remain distinct by lane:

- **Decision trajectory:** one replayable object spanning evidence, model,
  policy, human bind, effect, and verification.
- **Confidence drift ledger:** show exactly what evidence changed a model or
  human assessment over time.
- **Counterfactual receipt:** preserve the inputs and policy state for simulated
  alternatives without claiming the simulation predicted reality.
- **Outcome graph:** connect an approved action to the later measured outcome,
  not merely to task completion.
- **Evidence debt:** identify claims, decisions, or twins whose supporting
  source is stale, partial, missing, or contradicted.
- **Cross-vertical event identity:** a permitted event can be referenced across
  Lyte, Sentra, Hatun, A11oy, and PRISM without merging their data stores or
  authority boundaries.
- **Anatomical failure projection:** map a missing source, model, kernel, policy,
  or approval to the organ and downstream decisions it invalidates.

## Verification

```bash
python -m compileall -q frontier_fabric scripts/export_vertical_frontier_contract.py
pytest -q tests/test_frontier_fabric.py
python scripts/export_vertical_frontier_contract.py --pretty \
  --output /tmp/vertical-experience-contract.v1.json
```

The generated digest establishes deterministic serialization of the declared
contract. It does not prove source availability, model quality, performance,
regulatory compliance, factual truth, or authorization.
