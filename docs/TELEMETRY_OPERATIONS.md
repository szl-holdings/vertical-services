# Telemetry, dataset inventory, and evidence surfaces

The operational API distinguishes three kinds of records. The distinction must
survive search, Second Brain projection, Anatomy, and Hatun review.

| Record | Meaning | Evidence boundary |
| --- | --- | --- |
| Catalog metadata | A connector, vertical, model, or kernel is configured in this source revision. | Configuration does not prove a running model, collected telemetry, or a dataset's contents. |
| Caller telemetry | A session supplied a bounded observation envelope. | A SHA-256 receipt binds the envelope and session. It is unsigned and does not authenticate a provider. |
| Connector observation | The runtime fetched a fixed, allowlisted source and retained its bounded normalized response. | The payload digest resolves through the existing session-scoped observation ledger and evidence rules. |

## Routes and presentation

`GET /api/verticals/search?q=lyte` searches public configuration metadata. It
does not search private session history. The search panel is mounted in the
deployed `/intelligence/{vertical}` pages, alongside its same-origin API.
The separate `frontier_app.py` runtime must not advertise an API it does not
mount.

`POST /lyte/v1/telemetry` accepts the strict `szl.lyte-telemetry/v1` envelope.
The matching GET and `/search` routes require the caller-held `X-SZL-Session`
header. Equivalent routes exist under `/api/verticals/lyte/telemetry`.
Search filters the complete retained history before applying the result limit.

The Lyte Second Brain response includes the same telemetry projection. Anatomy
describes its actual availability and scope. Other verticals do not silently
claim that a Lyte telemetry collector is attached to them.

## Receipt and freshness invariants

- The immutable receipt basis includes the session scope and original metadata.
- The returned observation must agree with the hashed basis. A changed or
  cross-session record is excluded.
- Read-time age and effective freshness are derived anew on every read. Aging
  can change `effective_state` to `STALE` without rewriting the original
  observation or minting a replacement receipt.
- The caller's `source_state` is preserved as a report. It cannot establish
  provider authenticity or become Hatun connector evidence.
- Future timestamps beyond five seconds of tolerated clock skew, invalid UTC
  conversions, unknown fields, non-finite numbers, and oversize fields are
  rejected.
- Canonical truth labels remain `REPORTED`, `MODELED`, `MEASURED`, and
  `UNAVAILABLE`. Caller provenance is a separate field.

Caller telemetry is retained in process memory, at most 512 records per
session. A process restart loses that history. This is not a durable collector
or an assertion that OTLP export succeeded. Existing connector observations
use the SQLite ledger; its status states the configured durability rather than
assuming a persistent disk.

## Public Hugging Face dataset inventory

The optional Lyte `hf-datasets` connector reads the public
`SZLHOLDINGS` dataset catalog from a fixed Hugging Face endpoint. It accepts no
caller-supplied owner, URL, redirect, or credential. The existing transport byte
budget, normalization limits, session scope, cache, and receipt policy apply.

The inventory retains dataset identifiers, declared revisions, source links,
license metadata, and public metadata availability. It does not download data
rows, execute repository code, verify licensing rights, prove training use, or
admit data into a training run. An unknown license or revision remains unknown.
The bounded page and private-repository coverage remain explicit.

An inventory response containing many datasets is **one source observation**.
Its single payload digest is the evidence reference for Second Brain and
Hatun; the number of datasets must never inflate the number of independent
sources. Hatun can return `REVIEW` or `ABSTAIN` under its existing freshness,
source, and authority rules. Neither decision authorizes an action.

## Release verification

Run the repository's exact Python gate, `python -m pytest tests -q`, after
installing the committed hash-locked dependencies. Also run the existing
compile, container, responsive-layout, backend-contract, and source-identity
checks through GitHub CI. The unqualified `pytest` command additionally
collects the standalone frontier runtime and is not the CI collection target.

Merge through the repository's protected pull-request path. Publish through
the established `hf-space.yml` writer, or its declared canonical A11oy writer,
then independently compare `/api/build-info` with the merged source SHA.

After publication, verify in one fresh session that a public dataset fetch
produces a receipt, the same digest and inventory appear in Second Brain,
Anatomy names the connector, and Hatun resolves exactly that source observation.
Use a second session to verify isolation. A successful source merge alone is
not a live-runtime result.

## Design references

- [OpenTelemetry HTTP semantic conventions](https://opentelemetry.io/docs/specs/semconv/http/http-spans/): route templates, response codes, trace correlation, and accurate error semantics.
- [Azure Digital Twins 3D Scenes Studio](https://learn.microsoft.com/en-us/azure/digital-twins/concepts-3d-scenes-studio): bind visual elements to observed properties and make refresh behavior explicit.
- [Palantir observability](https://www.palantir.com/docs/foundry/observability/overview): connect resource health, execution history, and trace inspection in the operational interface.

The SZL implementation adds source revisions, session-bound receipts, explicit
freshness, and authority limits to those interaction patterns. Procedural 3D
positions remain illustrative; they are not measured causal topology.
