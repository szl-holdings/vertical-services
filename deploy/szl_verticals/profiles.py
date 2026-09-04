"""Canonical product, anatomy, and consolidation profiles."""
from __future__ import annotations

from typing import Any

CANONICAL_VERTICALS = ("sentra", "lyte", "killinchu", "finance", "terra", "counsel")
ALIASES = {"vessels": "killinchu"}
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
        "product": "Sentra",
        "domain": "cybersecurity",
        "canonical_repository": "szl-holdings/szl-defensive-control-plane",
        "public_space": "SZLHOLDINGS/sentra",
        "mission": "Turn threat and control observations into fail-closed, receipted decisions.",
        "formula_ids": (
            "sentra.gate_conjunction",
            "sentra.risk_threshold",
            "szl.lambda_advisory",
            "szl.receipt_hash",
        ),
        "required_connectors": ("cisa-kev",),
        "optional_connectors": ("nvd-cve",),
    },
    "lyte": {
        "product": "Lyte",
        "domain": "business-observability",
        "canonical_repository": "szl-holdings/lyte-lattice",
        "public_space": "SZLHOLDINGS/lyte",
        "mission": "Convert operating telemetry into drift, priority, and outcome signals.",
        "formula_ids": (
            "lyte.percentiles",
            "lyte.z_shift",
            "lyte.drift_gate",
            "szl.lambda_advisory",
            "szl.receipt_hash",
        ),
        "required_connectors": ("github-actions",),
        "optional_connectors": (),
    },
    "killinchu": {
        "product": "Killinchu",
        "domain": "defense-and-maritime",
        "canonical_repository": "szl-holdings/killinchu",
        "public_space": "SZLHOLDINGS/killinchu",
        "mission": "Fuse defense policy and maritime observations into governed command decisions.",
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
        "domain": "financial-intelligence",
        "canonical_repository": "szl-holdings/puriq-live",
        "public_space": "SZLHOLDINGS/finance",
        "mission": "Ground market and filing analysis in public-company evidence and explicit math.",
        "formula_ids": (
            "finance.log_return",
            "finance.annualized_volatility",
            "finance.max_drawdown",
            "finance.momentum",
            "finance.signal_gate",
            "szl.lambda_advisory",
            "szl.receipt_hash",
        ),
        "required_connectors": ("sec-submissions",),
        "optional_connectors": ("sec-companyfacts",),
    },
    "terra": {
        "product": "Terra",
        "domain": "real-estate-intelligence",
        "canonical_repository": "szl-holdings/szl-real-estate",
        "public_space": "SZLHOLDINGS/terra",
        "mission": "Turn parcel and underwriting evidence into comparable, governed property signals.",
        "formula_ids": (
            "terra.price_per_sqft",
            "terra.cap_rate",
            "terra.comp_dispersion",
            "szl.lambda_advisory",
            "szl.receipt_hash",
        ),
        "required_connectors": ("nyc-pluto",),
        "optional_connectors": (),
    },
    "counsel": {
        "product": "PRISM Counsel",
        "domain": "legal-intelligence",
        "canonical_repository": "szl-holdings/counsel",
        "public_space": "SZLHOLDINGS/counsel",
        "mission": "Map matters, deadlines, obligations, and public legal authority into proof chains.",
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
    },
}
