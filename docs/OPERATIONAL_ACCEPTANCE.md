# Authoritative Source Mesh — Production Acceptance

A source is operational only when all applicable gates pass:

1. **Adapter** — fixed HTTPS destination, bounded parameters, known schema, byte and timeout limits.
2. **Transport** — redirects are rejected except an explicitly pinned same-authority redirect contract.
3. **Normalization** — source-specific parser emits bounded fields and rejects malformed or hostile payloads.
4. **Provenance** — observation includes authority, redacted URL, timestamp, payload SHA-256, parser identity, freshness, and receipt ID.
5. **State** — `LIVE`, `CACHED`, `STALE_LAST_GOOD`, `AUTH_REQUIRED`, or `UNAVAILABLE`; no silent zero substitution.
6. **Readiness** — adapter wiring and production observation readiness are reported separately.
7. **Memory** — only bounded normalized summaries and source-safe receipt metadata enter the scoped ledger.
8. **Governance** — formulas remain advisory, external writes are disabled, and human approval is mandatory.
9. **Deployment** — exact protected-main revision is published by the single canonical writer.
10. **Live proof** — the deployed runtime returns a valid source receipt and the same source-bound revision.

Killinchu additionally requires the public defense boundary: no precise public military tracking, targeting, weapon release, autonomous interdiction, or public effector control. AIS is historical, aggregated, delayed, or licensed.
