from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable

from .types import (
    ClaimState,
    ConnectorSpec,
    EffectMode,
    KernelBinding,
    ModelBinding,
    ThemeSpec,
    VerticalSpec,
    as_public_dict,
)


_COMMON_MODELS = {
    "receipt": ModelBinding(
        repo_id="SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2",
        role="Structure evidence-linked proposals and receipt summaries.",
        runtime_state=ClaimState.DECLARED,
    ),
    "mini": ModelBinding(
        repo_id="SZLHOLDINGS/A11OY-MINI",
        role="Small governed-assistant candidate for bounded local workflows.",
        runtime_state=ClaimState.DECLARED,
    ),
    "nemo": ModelBinding(
        repo_id="SZLHOLDINGS/szl-nemo",
        role="Reasoning-runtime candidate for complex synthesis and planning.",
        runtime_state=ClaimState.DECLARED,
    ),
}

_COMMON_KERNELS = {
    "invariants": KernelBinding(
        repo_id="SZLHOLDINGS/szl-invariants",
        role="Validate required fields, source identity, and non-equivocation invariants.",
        enforcement="BLOCKING_INVARIANT",
        runtime_state=ClaimState.DECLARED,
    ),
    "lambda": KernelBinding(
        repo_id="SZLHOLDINGS/szl-lambda-gate",
        role="Compute an advisory weighted-geometric decision signal; never grant authority.",
        enforcement="ADVISORY_SCORE",
        runtime_state=ClaimState.DECLARED,
    ),
    "blocked": KernelBinding(
        repo_id="SZLHOLDINGS/szl-blocked",
        role="Enforce hard-deny and restricted-effect policy boundaries.",
        enforcement="BLOCKING_POLICY",
        runtime_state=ClaimState.DECLARED,
    ),
    "meter": KernelBinding(
        repo_id="SZLHOLDINGS/governed-inference-meter",
        role="Measure inference/runtime energy only when readable instrumentation exists.",
        enforcement="MEASUREMENT_ONLY",
        runtime_state=ClaimState.DECLARED,
    ),
    "norm": KernelBinding(
        repo_id="SZLHOLDINGS/szl-governed-norm",
        role="Normalize heterogeneous evidence while preserving missingness and provenance.",
        enforcement="ADVISORY_NORMALIZATION",
        runtime_state=ClaimState.DECLARED,
    ),
    "suite": KernelBinding(
        repo_id="SZLHOLDINGS/szl-kernels",
        role="Portable kernel family and shared deterministic correctness harness.",
        enforcement="CORRECTNESS_HARNESS",
        runtime_state=ClaimState.DECLARED,
    ),
}


def _theme(
    ident: str,
    grammar: str,
    accent: str,
    accent_2: str,
    modules: tuple[str, ...],
    *,
    surface: str = "#07090D",
    elevated: str = "#10141A",
    text: str = "#F4F1E8",
    muted: str = "#97A0AA",
    danger: str = "#D36B67",
    display_font: str = "Instrument Serif",
    body_font: str = "IBM Plex Sans",
    motion: str = "measured parallax, evidence-first transitions, reduced-motion equivalent",
    density: str = "operator-dense with progressive disclosure",
) -> ThemeSpec:
    return ThemeSpec(
        id=ident,
        visual_grammar=grammar,
        display_font=display_font,
        body_font=body_font,
        mono_font="IBM Plex Mono",
        tokens={
            "surface": surface,
            "surface_elevated": elevated,
            "text": text,
            "muted": muted,
            "accent": accent,
            "accent_secondary": accent_2,
            "danger": danger,
            "focus": accent,
        },
        signature_modules=modules,
        motion_language=motion,
        density=density,
    )


def _connector(
    ident: str,
    provider: str,
    purpose: str,
    endpoint: str | None,
    hosts: tuple[str, ...],
    paths: tuple[str, ...],
    *,
    path_params: dict[str, str] | None = None,
    query_params: tuple[str, ...] = (),
    max_bytes: int = 2_000_000,
    media_types: tuple[str, ...] = ("application/json",),
    headers: dict[str, str] | None = None,
    notes: str = "",
) -> ConnectorSpec:
    return ConnectorSpec(
        id=ident,
        provider=provider,
        purpose=purpose,
        endpoint_template=endpoint,
        allowed_hosts=hosts,
        allowed_path_prefixes=paths,
        path_params=path_params or {},
        query_params=query_params,
        max_bytes=max_bytes,
        media_types=media_types,
        required_headers=headers or {},
        notes=notes,
    )


CONNECTORS = {
    "github-org": _connector(
        "github-org",
        "GitHub",
        "Public source, repository, release, and workflow inventory for the SZL estate.",
        "https://api.github.com/orgs/{org}/repos",
        ("api.github.com",),
        ("/orgs/",),
        path_params={"org": r"[A-Za-z0-9_.-]{1,39}"},
        query_params=("per_page", "page", "sort", "direction", "type"),
        headers={"Accept": "application/vnd.github+json"},
    ),
    "github-actions": _connector(
        "github-actions",
        "GitHub Actions",
        "User-owned delivery telemetry for causal deployment and incident analysis.",
        "https://api.github.com/repos/{owner}/{repo}/actions/runs",
        ("api.github.com",),
        ("/repos/",),
        path_params={
            "owner": r"[A-Za-z0-9_.-]{1,39}",
            "repo": r"[A-Za-z0-9_.-]{1,100}",
        },
        query_params=("branch", "event", "status", "per_page", "page", "created"),
        headers={"Accept": "application/vnd.github+json"},
    ),
    "hf-models": _connector(
        "hf-models",
        "Hugging Face",
        "Public model inventory and provider metadata.",
        "https://huggingface.co/api/models",
        ("huggingface.co",),
        ("/api/models",),
        query_params=("author", "search", "limit", "sort", "direction", "full"),
        max_bytes=5_000_000,
    ),
    "hf-spaces": _connector(
        "hf-spaces",
        "Hugging Face",
        "Public Space inventory and runtime metadata.",
        "https://huggingface.co/api/spaces",
        ("huggingface.co",),
        ("/api/spaces",),
        query_params=("author", "search", "limit", "sort", "direction", "full"),
        max_bytes=5_000_000,
    ),
    "hf-datasets": _connector(
        "hf-datasets",
        "Hugging Face",
        "Public dataset inventory and provider metadata.",
        "https://huggingface.co/api/datasets",
        ("huggingface.co",),
        ("/api/datasets",),
        query_params=("author", "search", "limit", "sort", "direction", "full"),
        max_bytes=5_000_000,
    ),
    "cisa-kev": _connector(
        "cisa-kev",
        "CISA",
        "Authoritative catalog of known exploited vulnerabilities.",
        "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
        ("www.cisa.gov",),
        ("/sites/default/files/feeds/",),
        max_bytes=8_000_000,
    ),
    "nvd-cves": _connector(
        "nvd-cves",
        "NIST NVD",
        "Optional CVE enrichment for vulnerability context and affected products.",
        "https://services.nvd.nist.gov/rest/json/cves/2.0",
        ("services.nvd.nist.gov",),
        ("/rest/json/cves/2.0",),
        query_params=(
            "cveId",
            "keywordSearch",
            "lastModStartDate",
            "lastModEndDate",
            "pubStartDate",
            "pubEndDate",
            "resultsPerPage",
            "startIndex",
        ),
        max_bytes=8_000_000,
    ),
    "noaa-ais-2025": _connector(
        "noaa-ais-2025",
        "NOAA Office for Coastal Management",
        "Historical Nationwide AIS dataset index for planning, research, and simulation.",
        "https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2025/index.html",
        ("coast.noaa.gov",),
        ("/htdata/CMSP/AISDataHandler/2025/",),
        max_bytes=2_000_000,
        media_types=("text/html",),
        notes="Historical official planning data; not a live vessel-position feed and not a targeting source.",
    ),
    "sec-submissions": _connector(
        "sec-submissions",
        "U.S. SEC EDGAR",
        "Company filing history and accession metadata.",
        "https://data.sec.gov/submissions/CIK{cik}.json",
        ("data.sec.gov",),
        ("/submissions/",),
        path_params={"cik": r"[0-9]{10}"},
        max_bytes=10_000_000,
        headers={"User-Agent": "SZL Holdings research contact@a-11-oy.com"},
    ),
    "sec-companyfacts": _connector(
        "sec-companyfacts",
        "U.S. SEC EDGAR",
        "Structured XBRL company facts for source-linked financial analysis.",
        "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        ("data.sec.gov",),
        ("/api/xbrl/companyfacts/",),
        path_params={"cik": r"[0-9]{10}"},
        max_bytes=20_000_000,
        headers={"User-Agent": "SZL Holdings research contact@a-11-oy.com"},
    ),
    "nyc-pluto": _connector(
        "nyc-pluto",
        "NYC Open Data / Department of City Planning",
        "Tax-lot land-use, zoning, ownership, and built-form attributes.",
        "https://data.cityofnewyork.us/resource/64uk-42ks.json",
        ("data.cityofnewyork.us",),
        ("/resource/64uk-42ks",),
        query_params=("$select", "$where", "$limit", "$offset", "$order", "$q"),
        max_bytes=12_000_000,
    ),
    "federal-register": _connector(
        "federal-register",
        "Federal Register",
        "Rules, notices, executive actions, and source-linked regulatory developments.",
        "https://www.federalregister.gov/api/v1/documents.json",
        ("www.federalregister.gov",),
        ("/api/v1/documents",),
        query_params=(
            "per_page",
            "page",
            "order",
            "conditions[term]",
            "conditions[type][]",
            "conditions[agencies][]",
            "conditions[publication_date][gte]",
            "conditions[publication_date][lte]",
        ),
        max_bytes=8_000_000,
    ),
    "congress-bills": _connector(
        "congress-bills",
        "Congress.gov API",
        "Optional legislative enrichment for legal and policy monitoring.",
        "https://api.congress.gov/v3/bill",
        ("api.congress.gov",),
        ("/v3/bill",),
        query_params=("fromDateTime", "toDateTime", "sort", "offset", "limit", "format"),
        max_bytes=8_000_000,
        notes="An operator-supplied Congress.gov API key is required; no silent credential fallback.",
    ),
    "operator-evidence": _connector(
        "operator-evidence",
        "Operator-owned evidence plane",
        "Internal documents, telemetry, meetings, and approved systems of record.",
        None,
        (),
        (),
        notes="Bound by the operator at deployment. Arbitrary public URLs are not accepted.",
    ),
    "otel": _connector(
        "otel",
        "OpenTelemetry-compatible operator backend",
        "User-owned traces, metrics, and logs for high-cardinality causal analysis.",
        None,
        (),
        (),
        notes="Bound to an operator-owned collector/query endpoint at deployment; unavailable by default.",
    ),
    "local-anatomy": _connector(
        "local-anatomy",
        "SZL Living Anatomy",
        "Local organ health, bounded state transitions, and failure-injection evidence.",
        None,
        (),
        (),
        notes="Local-only interface; no network fetch is performed by the public connector client.",
    ),
}


VERTICALS = (
    VerticalSpec(
        id="a11oy",
        display_name="A11oy",
        product_class="FLAGSHIP_COMMAND_FABRIC",
        lane="Governed decision infrastructure",
        operator_outcome="Move from evidence-linked model proposal to bounded, human-accountable action.",
        unmet_need="Organizations have copilots and dashboards, but no legible operating boundary between proposal, policy, approval, execution, and proof.",
        differentiator="A decision trajectory and receipt chain are first-class product objects; the proposing model never authors its own authority.",
        theme=_theme(
            "alloy-noir",
            "quiet editorial command system with iridescent evidence edges and an ontology-first action rail",
            "#D9E2EA",
            "#8E7CFF",
            ("decision trajectory", "policy chamber", "human bind rail", "receipt drawer"),
        ),
        experience_modules=("Command", "Signals", "Decisions", "Approvals", "Outcomes", "Evidence", "Atlas"),
        connectors=(CONNECTORS["github-org"], CONNECTORS["hf-models"], CONNECTORS["operator-evidence"]),
        models=(_COMMON_MODELS["nemo"], _COMMON_MODELS["mini"], _COMMON_MODELS["receipt"]),
        kernels=(_COMMON_KERNELS["invariants"], _COMMON_KERNELS["blocked"], _COMMON_KERNELS["lambda"], _COMMON_KERNELS["meter"]),
        effect_mode=EffectMode.HUMAN_BOUND,
        requires_human_bind=True,
        public_actuation=ClaimState.BLOCKED,
        evidence_contract=("source identity", "model revision", "policy revision", "human binding", "effect receipt", "verification result"),
    ),
    VerticalSpec(
        id="hatun",
        display_name="Hatun",
        product_class="EXECUTIVE_COGNITION_SYSTEM",
        lane="Executive memory, strategy, and governed delegation",
        operator_outcome="Turn meetings, research, decisions, commitments, and outcomes into a living strategic memory.",
        unmet_need="Executive tools remember documents or tasks, but rarely preserve why a decision was made, what changed it, and whether the promised outcome occurred.",
        differentiator="A temporal decision constellation links intent, evidence, commitments, delegated work, confidence changes, and retrospective calibration.",
        theme=_theme(
            "hatun-copper-constellation",
            "midnight strategy chamber with copper knot-lines, cream editorial surfaces, and temporal constellations",
            "#D7A66B",
            "#78D7C7",
            ("memory constellation", "council chamber", "commitment knots", "decision retrospective"),
            surface="#080706",
            elevated="#15110E",
            text="#F4EBDD",
            muted="#AA9B8C",
        ),
        experience_modules=("Today", "Council", "Memory", "Commitments", "Delegations", "Retrospectives", "Evidence"),
        connectors=(CONNECTORS["operator-evidence"], CONNECTORS["github-actions"]),
        models=(_COMMON_MODELS["nemo"], _COMMON_MODELS["receipt"]),
        kernels=(_COMMON_KERNELS["invariants"], _COMMON_KERNELS["lambda"], _COMMON_KERNELS["blocked"]),
        effect_mode=EffectMode.HUMAN_BOUND,
        requires_human_bind=True,
        public_actuation=ClaimState.BLOCKED,
        evidence_contract=("memory source", "decision context", "commitment owner", "due state", "retrospective calibration"),
    ),
    VerticalSpec(
        id="killinchu",
        display_name="Killinchu",
        product_class="DEFENSE_MARITIME_DECISION_INTELLIGENCE",
        lane="Bounded air and maritime situational intelligence",
        operator_outcome="Fuse public and operator-owned observations into explainable, simulation-safe mission decisions.",
        unmet_need="Operators receive tracks and alerts but lack one inspectable chain from observation quality through classification, policy, simulation, and review.",
        differentiator="Every track carries source quality, uncertainty, policy boundary, simulated alternatives, and a non-self-authorizing decision receipt.",
        theme=_theme(
            "killinchu-radar-carbon",
            "carbon mission board with radar depth, infrared warning layers, cyan track vectors, and explicit simulation boundaries",
            "#48E4D2",
            "#FF9B67",
            ("track lattice", "mission clock", "rules boundary ring", "simulation compare"),
            surface="#03070A",
            elevated="#081219",
            text="#EAF8F6",
            muted="#7897A0",
            danger="#FF6B6B",
            motion="track interpolation, scan sweeps, and state pulses with a zero-motion operational mode",
            density="high-density mission display with zoomable layers",
        ),
        experience_modules=("Mission", "Air", "Maritime", "Tracks", "Ownership", "Sanctions", "Simulations", "Receipts"),
        connectors=(CONNECTORS["noaa-ais-2025"], CONNECTORS["operator-evidence"]),
        models=(_COMMON_MODELS["nemo"], _COMMON_MODELS["receipt"]),
        kernels=(_COMMON_KERNELS["invariants"], _COMMON_KERNELS["blocked"], _COMMON_KERNELS["lambda"], _COMMON_KERNELS["suite"]),
        effect_mode=EffectMode.SIMULATED_ONLY,
        requires_human_bind=True,
        public_actuation=ClaimState.SIMULATED,
        evidence_contract=("observation source", "track uncertainty", "classification rationale", "policy boundary", "simulation seed", "human review"),
    ),
    VerticalSpec(
        id="sentra",
        display_name="Sentra",
        product_class="CYBER_RISK_AND_RESPONSE_FABRIC",
        lane="Causal exposure, incident, and control intelligence",
        operator_outcome="Prioritize exploitable attack paths and replay the evidence behind every response decision.",
        unmet_need="Security teams drown in findings while the causal path from vulnerable asset to business consequence remains fragmented.",
        differentiator="A nervous-system graph joins exploited-in-the-wild evidence, asset context, identity reachability, controls, response options, and proof of remediation.",
        theme=_theme(
            "sentra-electric-nervous-system",
            "graphite nervous system with electric path tracing, restrained alert red, and causal replay",
            "#6DB9FF",
            "#B38CFF",
            ("attack-path nerve map", "exposure pulse", "incident replay", "control proof stack"),
            surface="#05080D",
            elevated="#0C1420",
            text="#EDF5FF",
            muted="#8EA0B5",
        ),
        experience_modules=("Exposure", "Attack Paths", "Incidents", "Controls", "Response", "Replay", "Evidence"),
        connectors=(CONNECTORS["cisa-kev"], CONNECTORS["nvd-cves"], CONNECTORS["operator-evidence"]),
        models=(_COMMON_MODELS["mini"], _COMMON_MODELS["receipt"]),
        kernels=(_COMMON_KERNELS["invariants"], _COMMON_KERNELS["blocked"], _COMMON_KERNELS["norm"]),
        effect_mode=EffectMode.HUMAN_BOUND,
        requires_human_bind=True,
        public_actuation=ClaimState.BLOCKED,
        evidence_contract=("vulnerability source", "asset identity", "path rationale", "control state", "response approval", "remediation proof"),
    ),
    VerticalSpec(
        id="lyte",
        display_name="Lyte",
        product_class="BUSINESS_OBSERVABILITY_SYSTEM",
        lane="Causal delivery and service intelligence",
        operator_outcome="Explain what changed, what broke, who is affected, and which action has the strongest evidence.",
        unmet_need="Traditional observability correlates telemetry but often stops before business impact, accountable action, and verified outcome.",
        differentiator="A trace river links deployment, service behavior, customer consequence, decision, action, and post-action outcome in one replayable chain.",
        theme=_theme(
            "lyte-trace-aurora",
            "ultra-clean dark observability field with aurora traces, luminous causal edges, and calm editorial summaries",
            "#57E6C2",
            "#80A7FF",
            ("causal trace river", "change lens", "business impact map", "outcome replay"),
            surface="#050809",
            elevated="#0A1214",
            text="#EDFFFA",
            muted="#8DA6A2",
            density="progressive detail from executive signal to raw trace",
        ),
        experience_modules=("Signals", "Services", "Changes", "Journeys", "Impact", "Actions", "Outcomes", "Evidence"),
        connectors=(CONNECTORS["github-actions"], CONNECTORS["otel"], CONNECTORS["operator-evidence"]),
        models=(_COMMON_MODELS["mini"], _COMMON_MODELS["receipt"]),
        kernels=(_COMMON_KERNELS["meter"], _COMMON_KERNELS["norm"], _COMMON_KERNELS["invariants"], _COMMON_KERNELS["lambda"]),
        effect_mode=EffectMode.HUMAN_BOUND,
        requires_human_bind=True,
        public_actuation=ClaimState.BLOCKED,
        evidence_contract=("telemetry query", "deployment revision", "impact cohort", "recommended action", "approval", "outcome delta"),
    ),
    VerticalSpec(
        id="puriq-finance",
        display_name="PURIQ Finance",
        product_class="EVIDENCE_BACKED_MARKET_INTELLIGENCE",
        lane="Filings, events, scenarios, and governed investment research",
        operator_outcome="Move from filing evidence to a transparent thesis, scenario range, catalyst ledger, and monitored invalidation conditions.",
        unmet_need="Research products summarize documents, but often obscure source lineage, assumption drift, and the exact condition that should invalidate a thesis.",
        differentiator="Every thesis is a versioned evidence graph with scenario math, explicit assumptions, counter-evidence, catalysts, and invalidation receipts.",
        theme=_theme(
            "puriq-ledger-emerald",
            "deep emerald research terminal with ivory editorial pages, amber scenario bands, and source-footnote density",
            "#7FE0B0",
            "#E7B96A",
            ("filing mosaic", "thesis graph", "scenario slate", "catalyst and invalidation ledger"),
            surface="#050B08",
            elevated="#0B1711",
            text="#F4F0E4",
            muted="#91A69A",
            density="research-dense with footnotes always one action away",
        ),
        experience_modules=("Companies", "Filings", "Events", "Theses", "Scenarios", "Catalysts", "Invalidations", "Evidence"),
        connectors=(CONNECTORS["sec-submissions"], CONNECTORS["sec-companyfacts"], CONNECTORS["operator-evidence"]),
        models=(_COMMON_MODELS["nemo"], _COMMON_MODELS["receipt"]),
        kernels=(_COMMON_KERNELS["invariants"], _COMMON_KERNELS["norm"], _COMMON_KERNELS["lambda"]),
        effect_mode=EffectMode.ADVISORY_ONLY,
        requires_human_bind=True,
        public_actuation=ClaimState.BLOCKED,
        evidence_contract=("filing accession", "fact period", "assumption set", "scenario revision", "counter-evidence", "human decision"),
    ),
    VerticalSpec(
        id="terra",
        display_name="Terra",
        product_class="PROPERTY_AND_CIVIC_CHANGE_INTELLIGENCE",
        lane="Parcel, ownership, zoning, risk, and opportunity intelligence",
        operator_outcome="Explain how a property changed, who controls it, what constrains it, and which opportunity survives evidence review.",
        unmet_need="Property tools expose maps or comps, but rarely preserve a temporal chain across parcel facts, ownership, zoning, permits, risk, and investment decisions.",
        differentiator="A parcel twin is a time-aware evidence object with ownership lineage, regulatory deltas, risk layers, scenario assumptions, and a decision receipt.",
        theme=_theme(
            "terra-parcel-strata",
            "earth-toned cartographic field with ink contours, teal parcel highlights, and temporal strata",
            "#55C7B0",
            "#C99B61",
            ("parcel strata", "ownership lattice", "zoning delta", "scenario terrain"),
            surface="#080A08",
            elevated="#121611",
            text="#F0EEE4",
            muted="#9CA293",
        ),
        experience_modules=("Map", "Parcels", "Ownership", "Zoning", "Changes", "Risk", "Pipeline", "Evidence"),
        connectors=(CONNECTORS["nyc-pluto"], CONNECTORS["operator-evidence"]),
        models=(_COMMON_MODELS["mini"], _COMMON_MODELS["receipt"]),
        kernels=(_COMMON_KERNELS["norm"], _COMMON_KERNELS["invariants"], _COMMON_KERNELS["lambda"]),
        effect_mode=EffectMode.ADVISORY_ONLY,
        requires_human_bind=True,
        public_actuation=ClaimState.BLOCKED,
        evidence_contract=("parcel identifier", "dataset revision", "ownership source", "regulatory delta", "scenario assumptions", "review decision"),
    ),
    VerticalSpec(
        id="prism-counsel",
        display_name="PRISM Counsel",
        product_class="LEGAL_MATTER_AND_ARGUMENT_COMMAND",
        lane="Matter, deadline, authority, argument, and evidence intelligence",
        operator_outcome="Turn a matter into a source-linked timeline, issue tree, argument lattice, deadline system, and reviewable work product.",
        unmet_need="Legal AI drafts and retrieves, but teams still need a transparent chain from authority and record facts to argument, deadline, reviewer, and filed outcome.",
        differentiator="The matter twin separates record fact, allegation, authority, inference, counterargument, deadline, and approved work product as distinct evidence-bearing objects.",
        theme=_theme(
            "prism-parchment-lattice",
            "graphite legal chamber with warm parchment planes, prismatic issue edges, and citation-first reading",
            "#C9B7FF",
            "#E4C98C",
            ("matter timeline", "issue prism", "argument lattice", "deadline and authority rail"),
            surface="#09090B",
            elevated="#151419",
            text="#F6F0E4",
            muted="#AAA2A8",
        ),
        experience_modules=("Matters", "Timeline", "Issues", "Authorities", "Arguments", "Deadlines", "Work Product", "Evidence"),
        connectors=(CONNECTORS["federal-register"], CONNECTORS["congress-bills"], CONNECTORS["operator-evidence"]),
        models=(_COMMON_MODELS["nemo"], _COMMON_MODELS["receipt"]),
        kernels=(_COMMON_KERNELS["invariants"], _COMMON_KERNELS["blocked"], _COMMON_KERNELS["lambda"]),
        effect_mode=EffectMode.HUMAN_BOUND,
        requires_human_bind=True,
        public_actuation=ClaimState.BLOCKED,
        evidence_contract=("record citation", "authority citation", "inference label", "reviewer identity", "deadline source", "approved version"),
    ),
    VerticalSpec(
        id="living-anatomy",
        display_name="Living Anatomy",
        product_class="SYSTEM_BODY_AND_FAILURE_INTELLIGENCE",
        lane="Interactive system anatomy, dependencies, and failure behavior",
        operator_outcome="See a system as a living body, inject bounded failures, and understand how evidence and control propagate.",
        unmet_need="Architecture diagrams are static; they rarely show state, dependency injury, recovery, decision authority, and proof as one explorable object.",
        differentiator="Software, operations, policy, and evidence are mapped as organs with explicit health, dependency, failure, recovery, and non-self-authorizing boundaries.",
        theme=_theme(
            "anatomy-biolume",
            "bioluminescent anatomical field with translucent organs, dependency circulation, and bounded failure injection",
            "#65E8D1",
            "#FF8D8D",
            ("organ constellation", "circulation map", "injury simulator", "recovery replay"),
            surface="#030809",
            elevated="#071315",
            text="#E9FFFB",
            muted="#82A8A3",
            motion="slow biological pulse and circulation flow with complete reduced-motion parity",
        ),
        experience_modules=("Body", "Organs", "Dependencies", "Signals", "Injuries", "Recovery", "Receipts"),
        connectors=(CONNECTORS["local-anatomy"], CONNECTORS["operator-evidence"]),
        models=(_COMMON_MODELS["mini"],),
        kernels=(_COMMON_KERNELS["suite"], _COMMON_KERNELS["invariants"], _COMMON_KERNELS["lambda"], _COMMON_KERNELS["meter"]),
        effect_mode=EffectMode.SIMULATED_ONLY,
        requires_human_bind=True,
        public_actuation=ClaimState.SIMULATED,
        evidence_contract=("organ state", "dependency revision", "failure seed", "policy state", "recovery trace", "verification receipt"),
    ),
    VerticalSpec(
        id="szl-atlas",
        display_name="SZL Atlas",
        product_class="PUBLIC_ESTATE_EXPLORER",
        lane="Public discovery, source binding, and evidence navigation",
        operator_outcome="Understand the SZL estate, inspect exact artifacts, and distinguish presentation from evidence.",
        unmet_need="Multi-product AI organizations often expose disconnected repositories and cards without one truthful map of what exists, runs, and remains unverified.",
        differentiator="The public estate is recaptured from provider metadata and linked to source, runtime, artifact class, evidence boundary, and verification routes.",
        theme=_theme(
            "atlas-evidence-cobalt",
            "cobalt evidence atlas with constellation navigation, precise artifact cards, and source-binding beacons",
            "#86A8FF",
            "#66E4CE",
            ("estate constellation", "artifact lens", "source-binding beacon", "evidence route"),
            surface="#05070C",
            elevated="#0B1120",
            text="#F0F4FF",
            muted="#8F9DB8",
        ),
        experience_modules=("Explore", "Models", "Kernels", "Datasets", "Spaces", "Collections", "Evidence"),
        connectors=(CONNECTORS["hf-models"], CONNECTORS["hf-spaces"], CONNECTORS["hf-datasets"], CONNECTORS["github-org"]),
        models=(),
        kernels=(_COMMON_KERNELS["invariants"], _COMMON_KERNELS["suite"]),
        effect_mode=EffectMode.READ_ONLY,
        requires_human_bind=False,
        public_actuation=ClaimState.BLOCKED,
        evidence_contract=("provider revision", "source URL", "artifact class", "runtime state", "limitations"),
    ),
)


@lru_cache(maxsize=1)
def by_id() -> dict[str, VerticalSpec]:
    return {vertical.id: vertical for vertical in VERTICALS}


def get_vertical(vertical_id: str) -> VerticalSpec:
    try:
        return by_id()[vertical_id]
    except KeyError as exc:
        raise KeyError(f"unknown vertical: {vertical_id}") from exc


def public_catalog() -> dict[str, object]:
    return {
        "schema": "szl.vertical-frontier-catalog/v1",
        "truth_boundary": {
            "model_proposes": True,
            "policy_decides": True,
            "human_binds_consequential_action": True,
            "lambda_uniqueness": "CONJECTURE_1_OPEN",
            "public_effectors_enabled": False,
        },
        "verticals": [as_public_dict(item) for item in VERTICALS],
    }


def validate_catalog(verticals: Iterable[VerticalSpec] = VERTICALS) -> list[str]:
    errors: list[str] = []
    vertical_list = list(verticals)
    ids = [item.id for item in vertical_list]
    themes = [item.theme.id for item in vertical_list]
    signatures = [tuple(item.theme.signature_modules) for item in vertical_list]

    if len(ids) != len(set(ids)):
        errors.append("vertical ids must be unique")
    if len(themes) != len(set(themes)):
        errors.append("theme ids must be unique")
    if len(signatures) != len(set(signatures)):
        errors.append("signature module sets must be unique")

    for vertical in vertical_list:
        if vertical.effect_mode is not EffectMode.READ_ONLY and not vertical.requires_human_bind:
            errors.append(f"{vertical.id}: non-read-only vertical must require human bind")
        if vertical.public_actuation is ClaimState.LIVE:
            errors.append(f"{vertical.id}: public actuation may not be LIVE")
        if len(vertical.theme.tokens) < 7:
            errors.append(f"{vertical.id}: incomplete theme token contract")
        if len(vertical.experience_modules) < 6:
            errors.append(f"{vertical.id}: experience must expose at least six modules")
        for connector in vertical.connectors:
            if connector.endpoint_template is None:
                continue
            if not connector.endpoint_template.startswith("https://"):
                errors.append(f"{vertical.id}/{connector.id}: endpoint must use HTTPS")
            for name, pattern in connector.path_params.items():
                try:
                    re.compile(pattern)
                except re.error as exc:
                    errors.append(f"{vertical.id}/{connector.id}/{name}: invalid regex: {exc}")
    return errors


CATALOG_ERRORS = validate_catalog()
if CATALOG_ERRORS:
    raise RuntimeError("invalid vertical frontier catalog: " + "; ".join(CATALOG_ERRORS))
