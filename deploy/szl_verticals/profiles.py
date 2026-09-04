"""Canonical product, anatomy, experience, and consolidation profiles."""
from __future__ import annotations

from typing import Any

CANONICAL_VERTICALS = ("sentra", "lyte", "killinchu", "finance", "terra", "counsel")
ALIASES = {
    "vessels": "killinchu",
    "aegis": "sentra",
    "immune": "sentra",
    "puriq": "finance",
    "markets": "finance",
    "real-estate": "terra",
    "business-observability": "lyte",
    "prism": "counsel",
}
TRUTH_LABELS = ("MEASURED", "REPORTED", "MODELED", "SAMPLE", "ROADMAP", "UNAVAILABLE")

ANATOMY_ORGANS = (
    {
        "order": 1,
        "id": "sense",
        "contract": "Acquire caller-supplied or allowlisted authoritative observations.",
    },
    {
        "order": 2,
        "id": "normalize",
        "contract": "Validate schemas, units, identifiers, timestamps, and source boundaries.",
    },
    {
        "order": 3,
        "id": "context",
        "contract": "Bind each observation to its vertical, source, revision, and session scope.",
    },
    {
        "order": 4,
        "id": "formula",
        "contract": "Apply named deterministic formulas and preserve proof-status boundaries.",
    },
    {
        "order": 5,
        "id": "policy",
        "contract": "Evaluate deny-by-default gates before any recommendation or effect.",
    },
    {
        "order": 6,
        "id": "decide",
        "contract": "Produce a bounded recommendation with confidence and truth labels.",
    },
    {
        "order": 7,
        "id": "verify",
        "contract": "Check source identity, invariants, freshness, and expected outcome.",
    },
    {
        "order": 8,
        "id": "remember",
        "contract": "Persist observation metadata and summaries under a hashed session scope.",
    },
    {
        "order": 9,
        "id": "receipt",
        "contract": "Mint a deterministic hash-addressed receipt without recording secrets.",
    },
)

VERTICALS: dict[str, dict[str, Any]] = {
    "sentra": {
        "product": "Killinchu / Defend",
        "domain": "cyber-resilience",
        "canonical_repository": "szl-holdings/szl-defensive-control-plane",
        "public_space": "SZLHOLDINGS/killinchu",
        "public_route": "/defend",
        "component_engine": "Sentra",
        "portfolio_name": "Aegis",
        "mission": (
            "Turn threat, control, asset, and Immune-organ observations into "
            "fail-closed, receipted response review."
        ),
        "formula_ids": (
            "sentra.gate_conjunction",
            "sentra.risk_threshold",
            "szl.lambda_advisory",
            "szl.receipt_hash",
        ),
        "required_connectors": ("cisa-kev",),
        "optional_connectors": ("nvd-cve",),
        "experience": {
            "title": "Killinchu Defend Plane",
            "kicker": "KILLINCHU / DEFEND",
            "archetype": "cyber-physical resilience command",
            "motif": "threat-shield",
            "background": "#050608",
            "panel": "#11131a",
            "accent": "#ff5f78",
            "accent_secondary": "#8b7cff",
            "signature_view": "Attack path → bounded proposal → human approval",
            "benchmark": "coverage · connectivity · causality · governed response",
        },
        "consolidation": {
            "public_product": "KILLINCHU",
            "public_runtime": "SZLHOLDINGS/killinchu",
            "public_route": "/defend",
            "aegis_status": "PORTFOLIO_NAME",
            "sentra_status": "COMPONENT_ENGINE",
            "standalone_sentra_space": "RETIRE_AFTER_LIVE_PARITY",
            "immune_status": "COMPATIBILITY_ALIAS_MIGRATION_REQUIRED",
            "immune_compatibility_alias": "/api/verticals/immune",
            "aegis_compatibility_alias": "/api/verticals/aegis",
            "effectors": "DISABLED",
            "human_approval_required": True,
        },
    },
    "lyte": {
        "product": "Lyte",
        "domain": "business-observability",
        "canonical_repository": "szl-holdings/lyte-lattice",
        "public_space": "SZLHOLDINGS/lyte",
        "mission": (
            "Convert service, delivery, operating, and economic telemetry into "
            "drift, priority, decision, and outcome signals."
        ),
        "formula_ids": (
            "lyte.percentiles",
            "lyte.z_shift",
            "lyte.drift_gate",
            "szl.lambda_advisory",
            "szl.receipt_hash",
        ),
        "required_connectors": ("github-actions",),
        "optional_connectors": (),
        "experience": {
            "title": "Lyte Signal Lattice",
            "kicker": "LYTE",
            "archetype": "business observability",
            "motif": "service-lattice",
            "background": "#03080a",
            "panel": "#0b1518",
            "accent": "#4df4d0",
            "accent_secondary": "#b8ff6a",
            "signature_view": "Signal → causal context → economic outcome",
            "benchmark": "revenue · cost · service · risk",
        },
    },
    "killinchu": {
        "product": "Killinchu",
        "domain": "defense-and-maritime",
        "canonical_repository": "szl-holdings/killinchu",
        "public_space": "SZLHOLDINGS/killinchu",
        "mission": (
            "Fuse defense policy and maritime observations into governed command "
            "decisions with explicit source and action boundaries."
        ),
        "formula_ids": (
            "killinchu.haversine_nm",
            "killinchu.dark_gap",
            "killinchu.implied_speed",
            "killinchu.voyage_risk",
            "sentra.gate_conjunction",
            "szl.lambda_advisory",
            "szl.receipt_hash",
        ),
        "required_connectors": ("noaa-ais-2025",),
        "optional_connectors": (),
        "experience": {
            "title": "Killinchu Voyage Radar",
            "kicker": "KILLINCHU",
            "archetype": "defense and maritime command",
            "motif": "voyage-radar",
            "background": "#03070c",
            "panel": "#0c1520",
            "accent": "#53c8ff",
            "accent_secondary": "#f6b85f",
            "signature_view": "Track → anomaly → policy → command review",
            "benchmark": "route · identity · risk · evidence",
        },
        "consolidation": {
            "vessels_status": "CONSOLIDATED",
            "legacy_product": "Vessels",
            "legacy_route": "/vessels",
            "canonical_route": "/killinchu",
            "legacy_repository": "szl-holdings/szl-fleet-overlay",
            "legacy_repository_role": "HISTORICAL_SOURCE",
        },
    },
    "finance": {
        "product": "PURIQ Finance",
        "domain": "financial-and-prediction-market-intelligence",
        "canonical_repository": "szl-holdings/puriq-live",
        "public_space": "SZLHOLDINGS/finance",
        "mission": (
            "Ground market, filing, rate, crypto, and prediction-market analysis "
            "in public evidence, explicit math, and non-executing review."
        ),
        "formula_ids": (
            "finance.log_return",
            "finance.annualized_volatility",
            "finance.max_drawdown",
            "finance.momentum",
            "finance.signal_gate",
            "finance.market_entropy",
            "finance.probability_edge",
            "szl.lambda_advisory",
            "szl.receipt_hash",
        ),
        "required_connectors": ("sec-submissions",),
        "optional_connectors": (
            "sec-companyfacts",
            "polymarket-markets",
            "coinbase-spot",
            "treasury-average-rates",
        ),
        "experience": {
            "title": "PURIQ Market Chamber",
            "kicker": "PURIQ",
            "archetype": "markets and capital intelligence",
            "motif": "probability-orbit",
            "background": "#07050c",
            "panel": "#151020",
            "accent": "#b989ff",
            "accent_secondary": "#f5c86b",
            "signature_view": "Evidence → probability → risk → review",
            "benchmark": "filings · rates · spot · prediction markets",
        },
        "consolidation": {
            "trading": "DISABLED",
            "custody": "DISABLED",
            "prediction_market_mode": "PUBLIC_READ_ONLY",
            "puriq_compatibility_alias": "/api/verticals/puriq",
        },
    },
    "terra": {
        "product": "Terra",
        "domain": "real-estate-intelligence",
        "canonical_repository": "szl-holdings/szl-real-estate",
        "public_space": "SZLHOLDINGS/terra",
        "mission": (
            "Turn parcel, building-condition, ownership, and underwriting evidence "
            "into comparable, governed property and pipeline signals."
        ),
        "formula_ids": (
            "terra.price_per_sqft",
            "terra.cap_rate",
            "terra.comp_dispersion",
            "terra.distress_load",
            "szl.lambda_advisory",
            "szl.receipt_hash",
        ),
        "required_connectors": ("nyc-pluto",),
        "optional_connectors": ("nyc-hpd-violations", "nyc-dob-violations"),
        "experience": {
            "title": "Terra Parcel Loom",
            "kicker": "TERRA",
            "archetype": "real estate operating intelligence",
            "motif": "parcel-grid",
            "background": "#040807",
            "panel": "#0d1713",
            "accent": "#74e6a8",
            "accent_secondary": "#db9d69",
            "signature_view": "Parcel → distress → underwriting → deal review",
            "benchmark": "portfolio · distress · ownership · pipeline",
        },
    },
    "counsel": {
        "product": "PRISM Counsel",
        "domain": "legal-intelligence",
        "canonical_repository": "szl-holdings/a11oy/verticals/counsel",
        "public_space": "SZLHOLDINGS/counsel",
        "mission": (
            "Map matters, deadlines, obligations, and public legal authority into "
            "proof chains while preserving attorney-led decision boundaries."
        ),
        "formula_ids": (
            "counsel.deadline_slack",
            "counsel.obligation_priority",
            "counsel.exposure_rank",
            "counsel.hash_chain",
            "szl.lambda_advisory",
            "szl.receipt_hash",
        ),
        "required_connectors": ("federal-register",),
        "optional_connectors": ("congress-bills",),
        "experience": {
            "title": "PRISM Authority Chain",
            "kicker": "PRISM COUNSEL",
            "archetype": "matter and authority intelligence",
            "motif": "authority-chain",
            "background": "#06070c",
            "panel": "#111522",
            "accent": "#8ca8ff",
            "accent_secondary": "#e8d8b6",
            "signature_view": "Authority → obligation → work product → proof",
            "benchmark": "matter · deadline · authority · verification",
        },
        "consolidation": {
            "decision_boundary": "ATTORNEY_LED",
            "legal_advice": "NOT_PROVIDED_BY_RUNTIME",
            "prism_compatibility_alias": "/api/verticals/prism",
        },
    },
}
