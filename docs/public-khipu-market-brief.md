# Public Khipu market brief

Open `/intelligence/finance`, consent to the public demo, and select **Generate
public market brief**. Python fetches fresh public Coinbase spot and Treasury
rate observations into the same session ledger. The planner checks the original
source, readiness, evidence, freshness, minimum count and advisory Lambda gates.
It forwards only a typed numeric projection to the public model, then verifies
the returned identity, request digest, output digest and unsigned execution record.
Any failed gate or inconsistent response withholds the output.

This explicitly selects `khipu-gguf-public` for `risk-summary`; it does not replace
or claim to serve `khipu-1.5b`, `receipt-agent` or `a11oy-mini`. Their operator
bindings remain required. No model credentials are sent to this public endpoint,
even if `HF_TOKEN` is configured for other work.

The reviewed serving contract is
`https://szlholdings-szl-model-inference-lab.hf.space/.well-known/szl-inference-contract.json`.
Canonical Python source is
`szl-holdings/szl-forge/spaces/szl-model-inference-lab`. The model is
`SZLHOLDINGS/SZL-Khipu-1.5B-GGUF@67d60ec577730747055491640cfb91fc4a4b5d25`,
file `SZL-Khipu-1.5B-Q4_K_M.gguf`, SHA-256
`13c1a1993063e1dff92f7413ccf48eaca6d48efc8801ae9af35961ae3396623a`.

For API clients, fetch `coinbase-spot` and `treasury-average-rates` in one
`X-SZL-Session`, then submit their distinct `receipt.payload_sha256` values to
the plan and invoke APIs. Select `preferred_model: "khipu-gguf-public"`,
`task: "risk-summary"`, `public_demo_consent: true`, and empty `context`.
For invocation also supply `max_new_tokens: 32` and `temperature: 0`.
The local objective is hashed in the plan but is not forwarded; this workflow
always uses a fixed public market prompt. Arbitrary caller prose, axes, raw
ledger text and private context are excluded from the public projection.

The demo permits 1,200 combined message characters, 800 formatted prompt tokens,
8,192 request bytes, greedy generation and at most 32 completion tokens. The
client enforces characters, bytes and generation settings; the serving endpoint
enforces its tokenizer budget. It is single-concurrency, best effort, without
an SLA. Busy, unavailable or rejected requests remain errors. Replies are
unsigned: content consistency is verified, authorship and investment quality
are not established. Every output requires human review; trading, custody and
consequential effectors remain disabled. The UI's 0.90 advisory preset is
explicitly disclosed and is not an empirical investment-quality measurement.
