"""Named SZL formula bindings and proof-status boundaries."""
from __future__ import annotations

from typing import Any

FORMULAS: dict[str, dict[str, Any]] = {
    "szl.lambda_advisory": {
        "name": "SZL Lambda advisory roll-up",
        "equation": "Λ_w(x) = ∏ x_i ^ w_i, Σw_i = 1, x_i ∈ [0,1]",
        "implementation": "operational.advisory_lambda",
        "source_repository": "szl-holdings/szl-formulas",
        "source_formula": "lambda_aggregate",
        "status": "ADVISORY",
        "proof_boundary": "Lambda uniqueness remains Conjecture 1 (open); never treated as proven trust.",
    },
    "szl.receipt_hash": {
        "name": "Canonical observation receipt",
        "equation": "r = SHA-256(canonical_json(metadata))",
        "implementation": "operational._receipt",
        "source_repository": "szl-holdings/governed-receipt-spec",
        "status": "DETERMINISTIC_IMPLEMENTATION",
    },
    "sentra.gate_conjunction": {
        "name": "Deny-by-default gate conjunction",
        "equation": "ALLOW ⇔ ∧ gate_i; otherwise DENY",
        "implementation": "szl_verticals.sentra.sentra_evaluate",
        "status": "TESTED_IMPLEMENTATION",
    },
    "sentra.risk_threshold": {
        "name": "Sentra risk threshold",
        "equation": "gate_risk = (risk_score < 0.75)",
        "implementation": "szl_verticals.sentra.GATES",
        "status": "POLICY_PARAMETER",
    },
    "lyte.percentiles": {
        "name": "Operational distribution summary",
        "equation": "p_q = ordered_values[round((n-1)q)]",
        "implementation": "szl_verticals.lyte._percentile",
        "status": "TESTED_IMPLEMENTATION",
    },
    "lyte.z_shift": {
        "name": "Normalized mean shift",
        "equation": "z = (μ_recent - μ_baseline) / max(σ_baseline, ε)",
        "implementation": "szl_verticals.lyte.lyte_drift",
        "status": "TESTED_IMPLEMENTATION",
    },
    "lyte.drift_gate": {
        "name": "Lyte drift gate",
        "equation": "drift = |z| > 2",
        "implementation": "szl_verticals.lyte.lyte_drift",
        "status": "ADVISORY_THRESHOLD",
    },
    "killinchu.haversine_nm": {
        "name": "Great-circle nautical distance",
        "equation": "d = 2R asin(√h), R = 3440.065 nautical miles",
        "implementation": "szl_verticals.vessels._haversine_nm",
        "status": "TESTED_IMPLEMENTATION",
    },
    "killinchu.dark_gap": {
        "name": "AIS dark-gap detector",
        "equation": "dark_gap = Δt > 3600 seconds",
        "implementation": "szl_verticals.vessels._assess_vessel",
        "status": "ADVISORY_THRESHOLD",
    },
    "killinchu.implied_speed": {
        "name": "AIS implied speed",
        "equation": "v_kn = distance_nm / (Δt / 3600)",
        "implementation": "szl_verticals.vessels._assess_vessel",
        "status": "TESTED_IMPLEMENTATION",
    },
    "killinchu.voyage_risk": {
        "name": "Bounded maritime anomaly score",
        "equation": "min(1, 0.3·dark_gaps + 0.4·speed_anomaly + 0.05·slow_fixes)",
        "implementation": "szl_verticals.vessels._assess_vessel",
        "status": "MODELED_ADVISORY",
    },
    "finance.log_return": {
        "name": "Log return",
        "equation": "r_t = ln(P_t / P_(t-1))",
        "implementation": "szl_verticals.finance._finance_metrics",
        "status": "TESTED_IMPLEMENTATION",
    },
    "finance.annualized_volatility": {
        "name": "Annualized volatility",
        "equation": "σ_ann = pstdev(log_returns) · √252",
        "implementation": "szl_verticals.finance._finance_metrics",
        "status": "MODELED",
    },
    "finance.max_drawdown": {
        "name": "Maximum drawdown",
        "equation": "MDD = min_t(P_t / running_peak_t - 1)",
        "implementation": "szl_verticals.finance._finance_metrics",
        "status": "TESTED_IMPLEMENTATION",
    },
    "finance.momentum": {
        "name": "Bounded lookback momentum",
        "equation": "m = P_t / P_(t-k) - 1, k = min(20, n-1)",
        "implementation": "szl_verticals.finance._finance_metrics",
        "status": "MODELED",
    },
    "finance.signal_gate": {
        "name": "PURIQ signal gate",
        "equation": "LONG if m>0.02∧σ<0.60; SHORT if m<-0.02; else FLAT",
        "implementation": "szl_verticals.finance._finance_metrics",
        "status": "ADVISORY_THRESHOLD",
    },
    "terra.price_per_sqft": {
        "name": "Price per square foot",
        "equation": "PPSF = price / square_feet",
        "implementation": "szl_verticals.terra.terra_add",
        "status": "TESTED_IMPLEMENTATION",
    },
    "terra.cap_rate": {
        "name": "Capitalization rate",
        "equation": "cap_rate = annual_NOI / price",
        "implementation": "szl_verticals.terra.terra_add",
        "status": "TESTED_IMPLEMENTATION",
    },
    "terra.comp_dispersion": {
        "name": "Comparable-property dispersion",
        "equation": "σ_comp = pstdev(PPSF_comps)",
        "implementation": "szl_verticals.terra.terra_analysis",
        "status": "MODELED",
    },
    "counsel.deadline_slack": {
        "name": "Deadline slack",
        "equation": "slack_days = (deadline_ts - now) / 86400",
        "implementation": "operational._signal_counsel",
        "status": "MODELED",
    },
    "counsel.obligation_priority": {
        "name": "Obligation priority",
        "equation": "priority = severity_rank × deadline_pressure",
        "implementation": "szl_verticals.counsel.counsel_docket",
        "status": "MODELED_ADVISORY",
    },
    "counsel.exposure_rank": {
        "name": "Matter exposure ordering",
        "equation": "sort by (-high_severity_count, -exposure_usd)",
        "implementation": "szl_verticals.counsel.counsel_docket",
        "status": "TESTED_IMPLEMENTATION",
    },
    "counsel.hash_chain": {
        "name": "Matter receipt chain",
        "equation": "h_n = SHA-256(h_(n-1) | step | payload)",
        "implementation": "szl_verticals.counsel._chain",
        "status": "TESTED_IMPLEMENTATION",
    },
}
