# Authoritative Source Mesh — Leader Architecture Alignment

This document records architecture patterns, not claims of proprietary data access.

## Maritime intelligence

The production pattern used by established maritime-intelligence platforms is a layered system rather than a single undifferentiated feed:

1. licensed observation transport (satellite/terrestrial AIS or another authorized provider);
2. normalized vessel and voyage identity;
3. separate ownership, sanctions, environmental, and behavioral-risk evidence;
4. source timestamps, geographic coverage, and freshness state on every observation;
5. human compliance review for identity ambiguity, ownership resolution, sanctions decisions, and operational action.

SZL applies that pattern through fixed provider adapters, explicit credential states, source-separated receipts, and a canonical Killinchu decision surface. No proprietary provider data is claimed until an authorized credential is configured and a live receipt is observed.

## Cyber exposure

The source mesh treats CISA KEV, NVD, and FIRST EPSS as different evidence planes:

- KEV: observed exploitation catalog evidence;
- NVD: vulnerability metadata and severity enrichment;
- EPSS: probabilistic exploitation estimate.

They are never collapsed into one invented certainty score. Each keeps its own source, timestamp, truth label, and parser version before any governed advisory roll-up.

## Government and regulated data

Official government APIs remain the authority for weather, tides, sanctions, filings, fiscal data, housing, disaster, census, and rulemaking observations. The runtime does not scrape around an unavailable API, silently follow unapproved redirects, or substitute synthetic values.

## Public defense boundary

Killinchu is observational and advisory in the public runtime:

- precise public live military tracking is excluded;
- targeting and engagement logic are excluded;
- weapon release and public effector control are excluded;
- `effectors_enabled=false`;
- `human_approval_required=true`;
- AIS is historical, aggregated, delayed, or properly licensed.

## Readiness meaning

`runtime_ready` means the service is source-bound, writable, and capable of serving the contract.

`production_source_ready` means the required connector has produced a fresh or policy-accepted stale-last-good observation, required credentials are present, and the observation receipt is visible in the scoped ledger.

A configured adapter without a successful observation is not called live.
