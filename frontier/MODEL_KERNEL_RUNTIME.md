# Governed Model and Kernel Runtime

The Vertical Frontier has two deliberately separate intelligence states:

1. **Route-only** — the default public state. It discloses the source-bound SZL
   model and kernel route but does not fabricate a model response.
2. **OpenAI-compatible inference** — an operator-configured state for a private
   vLLM deployment, dedicated Hugging Face endpoint, or another compatible
   endpoint whose host and credential are explicitly bound.

The model never authorizes or executes. The kernel stack never authorizes or
executes. The public runtime has no effectors.

## Decision sequence

```text
bounded request
    │
    ▼
evidence + action + risk gates
    │
    ├── prohibited / no evidence ──> HOLD; no model call
    │
    ▼
source-bound model selection
    │
    ▼
proposal-only chat request; no tools
    │
    ▼
provider text + request/output hashes
    │
    ▼
embedded SZL kernel reference stack
    │
    ▼
canonical v2 receipt
    │
    ▼
operator-owned human binding remains required
```

## Live model gateway

The gateway in `model_gateway.py` accepts no caller-supplied URL and no
caller-supplied model identifier. The vertical registry selects the model. The
operator selects the endpoint through environment configuration.

### Default

```bash
SZL_INFERENCE_MODE=route_only
```

This is the safe public default. The response contains the selected model, role,
request digest, and explicit `ROUTE_ONLY` state. It contains no invented model
text.

### Private vLLM or compatible local endpoint

```bash
export SZL_INFERENCE_MODE=openai_compatible
export SZL_INFERENCE_BASE_URL=http://127.0.0.1:8000
export SZL_INFERENCE_ALLOWED_HOSTS=127.0.0.1
export SZL_INFERENCE_CHAT_PATH=/v1/chat/completions
python -I -P runtime.py
```

A local HTTP endpoint is permitted only for loopback hosts.

### Remote compatible endpoint

```bash
export SZL_INFERENCE_MODE=openai_compatible
export SZL_INFERENCE_BASE_URL=https://<operator-owned-host>
export SZL_INFERENCE_ALLOWED_HOSTS=<operator-owned-host>
export SZL_INFERENCE_CHAT_PATH=/v1/chat/completions
export SZL_INFERENCE_TOKEN=<secret-from-runtime-secret-store>
python -I -P runtime.py
```

Non-local endpoints must use HTTPS and must provide a token. The token is never
returned in capabilities, proposal receipts, logs written by this code, or model
prompts.

For the current Hugging Face Inference Providers OpenAI-compatible router, the
operator may bind the official router host and a Hugging Face token at deploy
time. The exact host, API contract, provider availability, model compatibility,
pricing, and terms must be reverified against current official Hugging Face
documentation before enabling it. The public repository does not commit a token
or assume that every SZL model is provider-served.

## Model selection

The caller may request a **declared role**, such as `planner`, but cannot submit
an arbitrary model ID. The gateway selects only from `verticals.json`.

| Vertical | Primary route | Secondary route |
| --- | --- | --- |
| A11oy | `SZLHOLDINGS/szl-nemo` — planner | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2` — receipt composer |
| Killinchu | `SZLHOLDINGS/A11OY-MINI` — bounded analyst | `SZLHOLDINGS/szl-nemo` — mission planner |
| Lyte | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2` — incident narrative | `SZLHOLDINGS/szl-nemo` — outcome reasoner |
| Sentra | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2` — remediation drafter | `SZLHOLDINGS/A11OY-MINI` — evidence summarizer |
| Terra | `SZLHOLDINGS/szl-nemo` — diligence planner | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2` — record summarizer |
| PURIQ Finance | `SZLHOLDINGS/szl-nemo` — research planner | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2` — filing extractor |
| PRISM Counsel | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2` — citation composer | `SZLHOLDINGS/szl-nemo` — issue-spotting planner |
| Living Anatomy | `SZLHOLDINGS/szl-nemo` — system explainer | — |

A declared route is not evidence that an endpoint is currently serving the
model, that the model card has production-ready weights, or that the model has
passed a vertical benchmark. `INFERENCE_LIVE` appears only after a compatible
endpoint returns a bounded text response.

## Prompt boundary

The gateway:

- caps the assembled prompt at 12,000 characters;
- includes only the vertical contract, objective, requested action, and up to
  twelve normalized evidence entries;
- instructs the model to separate observed evidence, inference, assumptions,
  counterevidence, and open questions;
- requires evidence references such as `[E1]`;
- sends `tools: []`;
- rejects any provider-returned tool call;
- requires proposal-only wording and an explicit `AUTHORIZATION: NONE` boundary;
- records request, provider-response, and content digests;
- caps response bytes and completion-token configuration;
- never submits provider or operator secrets in the prompt.

## Kernel execution

`kernel_engine.py` executes a deterministic embedded reference stack:

| Bound public artifact | Embedded operation | Claim status |
| --- | --- | --- |
| `SZLHOLDINGS/szl-governed-norm` | Clamp and normalize bounded proposal features | `EMBEDDED_REFERENCE` |
| `SZLHOLDINGS/szl-lambda-gate` | Weighted-geometric advisory routing | `ADVISORY_NOT_UNIQUE` |
| `SZLHOLDINGS/szl-invariants` | No-authorization, no-execution, no-effector invariants | `EMBEDDED_REFERENCE` |
| `SZLHOLDINGS/szl-blocked` | Aggregate hard-deny conditions | `EMBEDDED_REFERENCE` |
| `SZLHOLDINGS/governed-inference-meter` | Wall-clock, token estimate, and RAPL energy when readable | `EMBEDDED_REFERENCE` |

The receipt states:

```json
{
  "artifact_execution_claim": "EMBEDDED_REFERENCE_ONLY",
  "external_kernel_artifact_loaded": false,
  "authorization": "NONE",
  "execution_performed": false,
  "lambda_uniqueness": "CONJECTURE_1_OPEN",
  "proven_trust": false
}
```

This is intentional. A Hugging Face card binding explains lineage and intended
role; it is not falsely represented as an imported wheel, compiled extension,
or remote execution. A later deployment may replace an embedded operation with
an exact artifact only after the package name, hash, license, import path,
tests, and compatibility evidence are bound.

## API additions

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/runtime-capabilities` | Model mode, allowed hosts, kernel claim state, and no-execution boundary |
| `GET` | `/api/v1/model/capabilities` | Inference configuration state without exposing secrets |
| `GET` | `/api/v1/kernel/self-test` | Embedded deterministic kernel self-test |
| `POST` | `/api/v1/decision` | Full evidence gate → model route/call → kernel stack → v2 receipt |
| `POST` | `/api/v1/inference` | Proposal-only model/kernel response with decision receipt digest |
| `POST` | `/api/v1/kernel/evaluate` | Evaluate a supplied proposal receipt through the embedded stack |
| `POST` | `/api/v1/verify` | Verify canonical receipt integrity |

## Test coverage

The blocking test suite proves:

- route-only operation is explicit and non-authorizing;
- arbitrary or insecure remote endpoints are rejected;
- a local compatible endpoint can produce a receipted `INFERENCE_LIVE` result;
- provider tool calls are refused;
- the kernel reference stack executes without claiming remote artifact loading;
- the v2 receipt includes model and kernel evidence;
- prohibited Killinchu requests stop before a model call;
- the HTTP surface preserves `authorization: NONE`, `execution_performed: false`,
  and the integrity verifier.

## Production gate

A production deployment is not established merely by setting environment
variables. Before enabling `openai_compatible`, bind and verify:

1. exact model revision and license;
2. exact serving image digest;
3. endpoint ownership and TLS identity;
4. token scope and rotation policy;
5. maximum cost, tokens, latency, and concurrency;
6. vertical evaluation dataset and acceptance thresholds;
7. prompt-injection and evidence-exfiltration tests;
8. output policy and human-review workflow;
9. request/output retention and privacy policy;
10. rollback, disable switch, and incident receipt path.

Until those receipts exist, the public default remains `route_only`.
