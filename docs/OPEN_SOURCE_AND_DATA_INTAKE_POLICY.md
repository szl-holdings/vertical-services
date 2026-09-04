# Open-Source and Public-Data Intake Policy

## Objective

Give SZL products a defensible technical edge without importing legal,
security, provenance, or truth debt. Every external component or dataset must
remain attributable, replaceable, bounded, and independently reviewable.

## Allowed intake classes

### Official public data

Government and standards-body sources may be connected when their access terms,
rate limits, attribution requirements, revision model, and data limitations are
recorded. Examples in the current contract include CISA KEV, NIST NVD, SEC
EDGAR, NOAA historical AIS, NYC PLUTO, the Federal Register, Congress.gov, and
GitHub's documented APIs.

Official does not mean complete, current for every use, suitable for operational
targeting, or sufficient for a consequential decision. The receipt must retain
the provider, locator, retrieval time, provider revision when available, content
digest, and known limitations.

### Permissively licensed open source

Apache-2.0, MIT, BSD, ISC, and similarly permissive components may be evaluated
for reuse. Before merge, the intake record must include:

- upstream repository and exact commit or release;
- license and notice obligations;
- copied or adapted file list;
- local modifications;
- dependency and vulnerability review;
- test evidence;
- replacement boundary and responsible SZL owner.

A package's popularity or public GitHub visibility is not a license.

### Operator-owned information

Private documents, telemetry, meetings, customer records, and systems of record
may enter only through an explicit operator connector. The connector must define
scope, authorization, retention, tenancy, audit, redaction, and deletion. The
public runtime never assumes that operator data exists.

### Public product research

Public websites and documentation may be studied to understand jobs-to-be-done,
information architecture, interaction patterns, terminology, and category
expectations. The resulting implementation must use original SZL code, visual
assets, copy, data structures, and interaction details.

## Prohibited intake

The following are not accepted into the estate:

- stolen, leaked, confidential, or access-controlled source code or datasets;
- credentials, session tokens, private keys, or authentication bypasses;
- proprietary model weights or datasets without explicit rights;
- code copied from a public repository without a compatible license;
- scraping that violates access controls, contractual restrictions, provider
  rate limits, robots directives, or applicable law;
- distinctive competitor copy, illustrations, component geometry, visual
  sequencing, animation assets, or trade dress;
- benchmarks whose prompts, evaluation version, hardware, or source revision
  cannot be reconstructed;
- data whose collection purpose is incompatible with the vertical's declared
  operator outcome;
- live defense targeting or effect data in a public demonstration surface.

## Intake receipt

Each reusable external input should carry a record shaped like:

```json
{
  "schema": "szl.external-intake/v1",
  "class": "OFFICIAL_PUBLIC_DATA",
  "name": "CISA Known Exploited Vulnerabilities",
  "upstream": "provider-controlled locator",
  "retrieved_at": "RFC3339 timestamp",
  "upstream_revision": "provider revision or UNAVAILABLE",
  "content_sha256": "64 lowercase hexadecimal characters",
  "license_or_terms": "identified terms reference",
  "allowed_uses": ["risk prioritization", "source-linked analysis"],
  "prohibited_uses": ["automatic authorization"],
  "transformation": "normalization description",
  "limitations": ["provider-defined scope", "not a complete vulnerability universe"],
  "reviewer": "hashed or access-controlled reviewer identity"
}
```

The receipt proves only the recorded intake and digest under its declared scope.
It does not prove factual truth, completeness, safety, performance, compliance,
or authorization.

## Transformation standard

External material becomes an SZL capability only after it passes all of these
steps:

1. **Classify** the source, license, rights, and intended use.
2. **Pin** the exact upstream revision or record that the revision is
   unavailable.
3. **Bound** hosts, paths, parameters, content types, body size, timeout, and
   redirects.
4. **Normalize** into a typed internal object while preserving missingness and
   source identity.
5. **Separate** observed facts, provider assertions, model inferences, human
   conclusions, and simulated values.
6. **Evaluate** the transformation on representative, missing, malformed,
   adversarial, and stale inputs.
7. **Attach** the vertical's independent model, kernel, policy, human-bind, and
   receipt boundaries.
8. **Verify** the deployed revision and public claims after merge.

## Data minimization

The connector must retrieve the smallest source window needed for the declared
question. Full-dataset mirrors require a documented operational reason,
retention plan, update strategy, deletion path, and storage budget. Personal or
sensitive information must not be collected merely because it is publicly
reachable.

## Model and kernel distinction

- A **model** proposes, classifies, extracts, summarizes, or ranks.
- A **kernel** validates, measures, normalizes, or enforces a declared boundary.
- A **policy** determines whether the proposed scope is permitted.
- A **human binding** authorizes or denies consequential action.
- A **receipt** records the chain and its integrity scope.

A model may not impersonate a policy kernel. A kernel's public repository does
not make it live. A signature does not make a claim true. A Lambda score remains
advisory, and Lambda uniqueness remains Conjecture 1 — open.

## Visual and product originality review

Before releasing a vertical front end, reviewers compare it against the public
references recorded in `CHAMPION_PATTERN_LEDGER.md` and answer:

- Is the layout and workflow recognizably SZL rather than a near-copy?
- Are all illustrations, icons, diagrams, copy, and motion sequences original
  or properly licensed?
- Does the vertical have a distinct operator object and signature interaction?
- Does presentation expose evidence and limitations rather than obscure them?
- Could a user distinguish observed, measured, inferred, simulated, unavailable,
  denied, and authorized states without reading source code?

A failed originality review blocks publication.
