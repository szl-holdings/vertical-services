# SZL Vertical Intelligence Fabric v1

## Purpose

This release turns six domain engines into six differentiated product lanes on one governed Python fabric:

1. **Aegis / Sentra** — cyber-resilience and attack-path review.
2. **Lyte** — business observability and outcome causality.
3. **Killinchu** — defense and maritime common-operating-picture review.
4. **PURIQ Finance** — filing, market, scenario, and thesis intelligence.
5. **Terra** — parcel-to-capital and property evidence twins.
6. **PRISM Counsel** — authority, obligation, argument, and matter intelligence.

A11oy remains the product and control-plane origin. These verticals are domain lanes, not six competing governance implementations. Hatun remains a review layer and cannot authorize. The Second Brain remains session-scoped. Living Anatomy, formulas, receipts, source binding, and effect boundaries are shared.

## Design synthesis

The interface system learns from public product patterns without copying proprietary source, private data, logos, or trade dress:

- restrained, task-first enterprise communication;
- common operating pictures and scenario rehearsal;
- digital-twin and what-if interaction models;
- telemetry joined to business and operational context;
- graph-based attack paths and blast radius;
- authoritative-source research with citation validation;
- connect-once, consume-many data integration;
- high-cardinality event investigation and causal context.

Each vertical applies those patterns to a unique product job, motif, color system, signature view, data contract, and model route. Shared components remain subordinate to the domain experience.

## Frontend contract

Every intelligence room must provide:

- a domain-native hero and visual instrument;
- one primary customer job and one explicit unserved job;
- bounded task routes;
- model and kernel state visibility;
- source, evidence, authority, and limitation boundaries;
- mobile, tablet, and desktop layouts;
- keyboard focus, skip navigation, 44–48 pixel targets, reduced-motion behavior, and forced-color compatibility;
- terminal states for unavailable model bindings rather than fabricated readiness.

Public routes:

```text
/intelligence/sentra
/intelligence/lyte
/intelligence/killinchu
/intelligence/finance
/intelligence/terra
/intelligence/counsel
```

Aliases resolve to the same canonical runtime:

```text
aegis, defend              -> sentra (capability plane; public home is Killinchu /defend)
immune                     -> migration required; no silent alias
business-observability     -> lyte
vessels                    -> killinchu
puriq, markets             -> finance
real-estate                -> terra
prism                      -> counsel
```

## Python backend contract

The backend is FastAPI and Python 3.12. It exposes a read-only catalog, per-vertical profile, deterministic planning gate, and optionally bound inference route:

```text
GET  /api/intelligence
GET  /api/verticals/{vertical}/intelligence
POST /api/verticals/{vertical}/intelligence/plan
POST /api/verticals/{vertical}/intelligence/invoke
```

The plan route performs no provider mutation. It hashes the objective and context, applies source/readiness/evidence/context/model/advisory gates, returns `READY_FOR_INFERENCE` or `ABSTAIN`, and mints a deterministic SHA-256 receipt.

The invoke route remains fail-closed until an operator binds all of the following through environment variables:

- a fixed HTTPS endpoint;
- an allowlisted host;
- an approved protocol;
- a credential;
- an exact 40-character declared model revision.

The public API cannot supply or override a model endpoint. Redirects, endpoint query strings, embedded credentials, oversized responses, non-JSON responses, and unsupported provider shapes are rejected.

An exact revision value is currently **operator-declared**. It is not represented as independently observed from the provider unless a future provider-specific attestation adapter supplies that evidence.

## Approved model assets

| Alias | Artifact | Intended role | Runtime boundary |
|---|---|---|---|
| `khipu-1.5b` | `SZLHOLDINGS/SZL-Khipu-1.5B` | grounded synthesis and structured domain briefs | fixed remote endpoint and exact declared revision required |
| `receipt-agent` | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2` | citation, evidence, receipt, and structured-output review | fixed remote endpoint and exact declared revision required |
| `a11oy-mini` | `SZLHOLDINGS/A11OY-MINI` | bounded low-latency or edge-compatible brief | fixed remote endpoint and exact declared revision required |
| `nemo-recipe` | `SZLHOLDINGS/szl-nemo` | recipe-conformance evidence | not an inference checkpoint |

No model receives autonomous effect authority. Model text is `MODEL_GENERATED`, not measured truth.

## Kernel fabric

| Kernel | Role |
|---|---|
| `szl-kernels` | portable deterministic compute, feature, and chain primitives |
| `szl-lambda-gate` | weighted-geometric advisory gate; uniqueness remains Conjecture 1 |
| `szl-invariants` | source, schema, evidence, and authority invariants |
| `szl-blocked` | deny-by-default high-risk and compliance boundary |
| `szl-receipt-attn` | evidence coverage and receipt-linked output attention contract |
| `szl-block-kv` | bounded context and session-isolated memory contract |

Software kernels are packages and contracts, not trained models. Deprecated or superseded assets are not promoted into the active fabric.

## Vertical model routing

### Aegis / Sentra

Tasks: attack-path review, control-gap analysis, incident summary, remediation review.

Frontier delta:

- AI-action exposure graph from model or tool call to cloud blast radius;
- owner-resolved remediation packet with source and rollback receipts;
- counterfactual containment replay before an operator-approved change.

### Lyte

Tasks: root-cause hypothesis, business impact, SLO investigation, change risk.

Frontier delta:

- business-causality braid joining traces, decisions, customer journeys, and economic outcomes;
- agent/tool/model telemetry with token, latency, energy, quality, and outcome receipts;
- decision replay that distinguishes technical recovery from business recovery.

### Killinchu

Tasks: track-anomaly review, route risk, scenario rehearsal, debrief.

Frontier delta:

- truth-disagreement layer preserving sensor conflict and uncertainty;
- branching course-of-action rehearsal with simulated effects and signed debrief;
- degraded-network receipt continuity with later reconciliation.

Public physical actuation remains simulated. The runtime does not control effectors.

### PURIQ Finance

Tasks: filing research, scenario analysis, thesis review, risk summary.

Frontier delta:

- thesis-decay ledger recording assumption drift and contradictory evidence;
- filing-to-scenario graph with claims attached to source digests;
- decision-quality review separated from market outcome.

Trading and custody remain disabled.

### Terra

Tasks: parcel diligence, lease-obligation review, underwriting scenario, portfolio risk.

Frontier delta:

- parcel-to-capital twin spanning public facts, leases, condition, and assumptions;
- counterfactual underwriting with sensitivity receipts;
- constraint graph for permits, violations, climate exposure, and community impact.

Person-level prospecting remains disabled.

### PRISM Counsel

Tasks: authority research, deadline review, argument map, document issue spotting.

Frontier delta:

- authority graph carrying passage digests, treatment state, and jurisdiction;
- argument replay preserving supporting and adverse evidence side by side;
- matter twin joining deadlines, obligations, work product, approvals, and source receipts.

The runtime does not provide or file legal advice. Decisions remain attorney-led.

## Data and code adoption boundary

The estate may integrate authoritative public data and properly licensed open-source components through bounded adapters. Every adoption must preserve:

- upstream license and notice requirements;
- exact source version or revision;
- data rights, update cadence, geographic scope, and field lineage;
- schema normalization and source-specific parsers;
- rate, size, redirect, timeout, and credential boundaries;
- explicit truth labels and unavailable states;
- independent tests and rollback.

Copyleft or network-copyleft software is not copied into a proprietary serving path without a deliberate licensing decision. Proprietary competitor code, private data, reverse-engineered interfaces, logos, and trade dress are excluded.

## Authority boundary

```text
observation -> normalize -> context -> formula -> policy
            -> model proposal -> verify -> remember -> receipt
            -> Hatun REVIEW or ABSTAIN -> human decision
```

The model proposes. Deterministic policy constrains. Hatun reviews. A human binds consequential action. No formula, model output, signature, HTTP response, or polished frontend creates authority by itself.
