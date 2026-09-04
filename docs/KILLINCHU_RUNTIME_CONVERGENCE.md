# Killinchu runtime convergence

## Product authority

Killinchu is the sole public cyber-physical resilience product. The combined
vertical runtime preserves two independently testable engines without presenting
them as competing products:

- **Defend / Aegis** uses the existing `sentra` engine for defensive and cyber
  intelligence.
- **Maritime / Vessels** uses the existing `vessels` engine for maritime
  intelligence.

Compatibility prefixes retain their response payloads and source history. They
add headers naming Killinchu as the canonical product and identifying the lobe:

```text
X-SZL-Canonical-Product: killinchu
X-SZL-Product-Lobe: aegis | vessels
X-SZL-Standalone-Product: false
```

## Source-native routes

The combined FastAPI process exposes:

- `GET /killinchu/architecture`
- `GET /killinchu/aegis/healthz`
- `GET /killinchu/vessels/healthz`

The routes are read-only source contracts. A successful response proves only
that this process answered. It does not prove model quality, sensor freshness,
provider availability, downstream-system health, or operational authorization.

## Runtime assembly

The contract module lives under `deploy/szl_verticals/` and is therefore copied
by the existing container build. The public routes import the same module used by
tests; no root-only module or undeployed source copy is authoritative.

## Governance boundary

The exact locked formula identifiers remain:

```text
F1, F4, F7, F11, F12, F18, F19, F22
```

Lambda remains `CONJECTURE_1_ADVISORY`. Human authority and receipts remain
required. Destructive or offensive autonomy is false, and this identity layer
enables no effectors.
