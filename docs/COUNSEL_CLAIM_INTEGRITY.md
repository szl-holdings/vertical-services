# PRISM Counsel: claim-to-passage integrity

Status: EVALUATION. Source implementation, not production admission or a legal-capability benchmark.

## Actual integration

The existing `szl_verticals.counsel.counsel` router mounts `counsel_review`.
The normal application that mounts Counsel therefore receives:

- `GET /counsel/review`: static accessible review workbench, no third-party scripts or browser persistence, hash-based CSP.
- `POST /counsel/v1/claim-integrity`: bounded JSON request using the existing `X-SZL-Session` dependency.

No duplicate repository, Space, publisher, workflow, inference endpoint, or replacement matter store is introduced. The reusable `claim_integrity.py` engine is owned here; product integration must consume it rather than fork it.

## What the engine measures

Caller-supplied documents carry expected UTF-8 SHA-256 digests. Each claim carries explicit Unicode-code-point spans, exact quotations, and caller-reported SUPPORT / ADVERSE / CONTEXT relationships. The engine checks digest identity, range, and literal quotation equality without normalization. It exposes every missing/mismatched anchor, preserves adverse text, and prevents hash-identical document aliases from inflating content-anchor counts.

Textual anchor coverage = claims with at least one matching reported SUPPORT passage / all submitted claims. It is not a probability, semantic-entailment score, legal accuracy, independent-authority count, or proof of Conjecture 1. Lambda remains advisory; no theorem or uniqueness claim is added.

The receipt binds full input digest, source revision, all output rows, metrics, blockers, and explicit capability bounds. Recompute `SHA256(canonical_json(response_without_receipt))`. This is an unsigned content digest, not a signature, an authenticated source attestation, or a durable audit log. Hashes of low-entropy confidential text may be guessable; do not publish sensitive receipts indiscriminately.

## Safety and confidentiality boundaries

The handler streams at most 512000 bytes within a five-second read budget, rejects duplicate JSON keys/non-finite constants, validates strict bounded schemas, and returns redacted validation errors. Up to 16 documents, 64000 UTF-8 bytes per document, 256000 corpus bytes, 64 claims and 16 anchors per claim are accepted. It makes no external calls, stores no submitted documents, and returns digests rather than raw passages. This handler-level property does not qualify upstream proxy, host logging, transport, enterprise identity, retention, or privilege controls.

Source authentication, citation existence, citation treatment, jurisdiction, semantic entailment, and deadline computation remain explicitly NOT VERIFIED / NOT EVALUATED. No court filing, legal advice, trade, remediation, or physical action is available. Use public or synthetic text until tenant isolation, OIDC/RBAC, privilege boundaries, retention/deletion, and operational review are independently qualified.

The existing intelligence planner's client-digest/count evidence admission requires separate remediation before this textual check may be incorporated into an inference workflow. A matching submitted quote must never be converted into an authenticated connector observation or independent legal authority.

## Reproducible tests

From repository root, in the repository's normal installed runtime:

```sh
python -m pytest tests/test_counsel_claim_integrity.py -q
python -m compileall -q services deploy tools tests
python -m pytest tests -q
```

Initial local result: 40 network-free cases passed under Python 3.13.5, FastAPI 0.128.2, Pydantic 2.13.4, HTTPX 0.28.1, pytest 9.0.2. Baseline `core.py` and `counsel.py` were reconstructed from connected GitHub reads and their Git blob digests verified before the two-line router integration. This is not the pinned Python 3.12.10 runtime or a full-repository test result. Native CI remains required and unchanged. Local browser execution was UNAVAILABLE because the Chromium executable was absent; HTML/CSP and API integration assertions are not substituted for browser evidence.

Before readiness, execute browser journeys at 320x568, 375x812, 768x1024 and 1440x900. Verify Unicode offsets, ambiguous-quote rejection, cancellation/clear races, actual same-origin POST, CSP, keyboard/focus, forced-colors/reduced-motion, overflow and touch targets. Record failures, not a synthetic pass.

## Primary research and original implementation

Public patterns were studied, not proprietary source code or corpora copied:

- Harvey: document/research/workflow separation and collaborative review, https://www.harvey.ai/
- CoCounsel: assertion-to-source checking, https://www.thomsonreuters.com/en-us/posts/innovation/cocounsel-legal-august-2026-releases/
- LegalBench-RAG: retrieval of precise supporting spans, https://arxiv.org/abs/2408.10343
- Claim-level auditability perspective: provenance coverage, soundness and contradiction transparency, https://arxiv.org/abs/2602.13855
- Free Law Project: public legal APIs and citation extraction, https://free.law/

These sources inform evaluation design. No upstream dependency or dataset is imported by this change. Any later Eyecite, LegalBench-RAG, CourtListener, CUAD, or ContractNLI integration requires exact upstream revision, separate code/data license review, source permissions/rate limits, and non-contaminated held-out evaluation. Extraction is not citation validation; citation existence is not good-law treatment. No competitor-superiority result exists yet.

## Canonical publication and rollback

GitHub source admission precedes HF projection. Preserve the existing central A11oy flagship writer and existing `SZLHOLDINGS/counsel` target; do not revive archived `counsel` or publish `counsel-assurance` as a duplicate. `platform` retains durable matter/business ownership; this repository owns shared Python review primitives. A11oy owns product assembly and its canonical projection. `a11oy-net` owns proof publication.

After normal source review and complete exact-head checks, use existing canonical deploy controls. Bind the shared-runtime revision separately from the A11oy product revision; do not require unrelated repositories to share a SHA. Verify actual mounted routes and projection bytes, not only HTTP 200. Update product status only after HF/runtime readback, then proof only after same-scope evidence. Preserve the prior admitted source vector for ordinary rollback. No deployment, secrets, defaults, branch protections, hardware, visibility or weight publication is performed by this feature.
