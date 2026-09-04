# Authoritative Source Mesh v3

This release promotes the shared source plane from a connectivity inventory to an operational, receipt-bearing service.

## Coverage

- NOAA/NWS marine alerts and NOAA CO-OPS environmental observations
- CISA KEV, NVD, and FIRST EPSS cyber evidence
- OFAC and United Nations sanctions publications
- Census ACS, OpenFEMA, and FHFA housing/disaster context
- Federal Register and CourtListener public-law evidence
- SEC EDGAR, Treasury Fiscal Data, and FRED financial/economic evidence
- historical NOAA AIS metadata plus explicit seams for properly licensed current AIS

## Runtime behavior

- fixed allowlisted destinations and bounded parameters
- provider-specific normalization
- payload hashing and deterministic receipts
- fresh-cache and stale-last-good behavior
- explicit `AUTH_REQUIRED` and `UNAVAILABLE` states
- separate runtime readiness and production-source readiness
- Killinchu-local source contract and health surfaces
- no caller-supplied URLs, secret values, fabricated data, or public effectors

## Deployment gate

The release is accepted only after deterministic tests, container smoke checks, exact-head CI, protected-main merge, canonical Hugging Face publication, and deployed source-receipt probes.
