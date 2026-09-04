"""Allowlisted authoritative-source connector specifications.

The registry separates source contracts from observed source health. A connector
can be CONFIGURED without having produced a current observation; readiness is
computed from the observation ledger, never from this registry alone.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from pydantic import Field

from .core import StrictModel

CVE = re.compile(r"^CVE-\d{4}-\d{4,19}$", re.IGNORECASE)
CIK = re.compile(r"^\d{1,10}$")
SAFE_TOKEN = re.compile(r"^[A-Za-z0-9._:/ -]{1,128}$")
SAFE_REPO = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")
BBL = re.compile(r"^\d{10}$")
BOROUGHS = {
    "MN", "BX", "BK", "QN", "SI", "MANHATTAN", "BRONX",
    "BROOKLYN", "QUEENS", "STATEN ISLAND",
}
DEFAULT_USER_AGENT = os.environ.get(
    "SZL_HTTP_USER_AGENT",
    "SZL-Vertical-Services/3.0 (+https://a-11-oy.com; ops@a-11-oy.com)",
).strip()
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "SZL Holdings vertical-services https://a-11-oy.com ops@a-11-oy.com",
).strip()


@dataclass(frozen=True)
class ConnectorSpec:
    id: str
    vertical: str
    authority: str
    authority_url: str
    method: str
    response_format: str
    freshness_seconds: int
    max_bytes: int
    required: bool
    auth_env: str | None
    description: str
    builder: str
    source_class: str = "PUBLIC_AUTHORITY"
    data_mode: str = "CURRENT"
    operational_role: str = "EVIDENCE"
    max_stale_seconds: int = 86_400
    allowed_redirect_hosts: tuple[str, ...] = ()
    allowed_redirect_path_prefixes: tuple[str, ...] = ()
    license_required: bool = False


CONNECTORS: dict[str, ConnectorSpec] = {
    # SENTRA / cyber prioritization -------------------------------------------------
    "cisa-kev": ConnectorSpec(
        id="cisa-kev",
        vertical="sentra",
        authority="Cybersecurity and Infrastructure Security Agency",
        authority_url="https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        method="GET",
        response_format="json",
        freshness_seconds=3600,
        max_bytes=8_000_000,
        required=True,
        auth_env=None,
        description="Authoritative catalog of vulnerabilities known to be exploited in the wild.",
        builder="cisa",
        operational_role="EXPLOITATION_GROUND_TRUTH",
        max_stale_seconds=86_400,
    ),
    "nvd-cve": ConnectorSpec(
        id="nvd-cve",
        vertical="sentra",
        authority="National Institute of Standards and Technology",
        authority_url="https://nvd.nist.gov/developers/vulnerabilities",
        method="GET",
        response_format="json",
        freshness_seconds=3600,
        max_bytes=4_000_000,
        required=False,
        auth_env=None,
        description="NVD CVE 2.0 enrichment; NVD_API_KEY is optional and sent only as a header.",
        builder="nvd",
        operational_role="VULNERABILITY_ENRICHMENT",
        max_stale_seconds=86_400,
    ),
    "first-epss": ConnectorSpec(
        id="first-epss",
        vertical="sentra",
        authority="Forum of Incident Response and Security Teams",
        authority_url="https://www.first.org/epss/api",
        method="GET",
        response_format="json",
        freshness_seconds=86_400,
        max_bytes=2_000_000,
        required=True,
        auth_env=None,
        description="Daily EPSS exploitation-probability and percentile observations for explicit CVE lookups.",
        builder="epss",
        source_class="PUBLIC_RESEARCH_AUTHORITY",
        operational_role="EXPLOITATION_PROBABILITY",
        max_stale_seconds=259_200,
    ),

    # LYTE / delivery observability ------------------------------------------------
    "github-actions": ConnectorSpec(
        id="github-actions",
        vertical="lyte",
        authority="GitHub Actions",
        authority_url="https://docs.github.com/rest/actions/workflow-runs",
        method="GET",
        response_format="json",
        freshness_seconds=120,
        max_bytes=4_000_000,
        required=True,
        auth_env=None,
        description="First-party CI/CD execution telemetry for an allowlisted SZL repository.",
        builder="github",
        source_class="FIRST_PARTY_PLATFORM",
        operational_role="DELIVERY_OBSERVABILITY",
        max_stale_seconds=1800,
    ),

    # KILLINCHU / maritime environmental and compliance evidence ------------------
    "nws-marine-alerts": ConnectorSpec(
        id="nws-marine-alerts",
        vertical="killinchu",
        authority="NOAA National Weather Service",
        authority_url="https://www.weather.gov/documentation/services-web-alerts",
        method="GET",
        response_format="json",
        freshness_seconds=60,
        max_bytes=6_000_000,
        required=True,
        auth_env=None,
        description="Active NWS CAP/JSON-LD watches, warnings and advisories for an explicit marine scope.",
        builder="nws-alerts",
        operational_role="MARINE_HAZARD_ALERTING",
        max_stale_seconds=900,
    ),
    "noaa-coops": ConnectorSpec(
        id="noaa-coops",
        vertical="killinchu",
        authority="NOAA Center for Operational Oceanographic Products and Services",
        authority_url="https://api.tidesandcurrents.noaa.gov/api/prod/",
        method="GET",
        response_format="json",
        freshness_seconds=360,
        max_bytes=4_000_000,
        required=True,
        auth_env=None,
        description="Station-scoped water level, tide, current and meteorological observations or predictions.",
        builder="coops",
        operational_role="PORT_AND_COASTAL_CONDITIONS",
        max_stale_seconds=3600,
    ),
    "ofac-sdn": ConnectorSpec(
        id="ofac-sdn",
        vertical="killinchu",
        authority="U.S. Department of the Treasury, Office of Foreign Assets Control",
        authority_url="https://ofac.treasury.gov/sanctions-list-service",
        method="GET",
        response_format="xml",
        freshness_seconds=21_600,
        max_bytes=40_000_000,
        required=True,
        auth_env=None,
        description="Current OFAC SDN XML, normalized for entity and vessel screening evidence.",
        builder="ofac-sdn",
        operational_role="SANCTIONS_SCREENING_AUTHORITY",
        max_stale_seconds=172_800,
        allowed_redirect_hosts=(
            "wc2h-sls-prod-public-published.s3.us-gov-west-1.amazonaws.com",
        ),
        allowed_redirect_path_prefixes=("/Published/current/",),
    ),
    "un-1718-sanctions": ConnectorSpec(
        id="un-1718-sanctions",
        vertical="killinchu",
        authority="United Nations Security Council 1718 Sanctions Committee",
        authority_url="https://main.un.org/securitycouncil/en/sanctions/1718/materials",
        method="GET",
        response_format="xml",
        freshness_seconds=21_600,
        max_bytes=12_000_000,
        required=True,
        auth_env=None,
        description="Official machine-readable DPRK 1718 sanctions list; not a substitute for legal review.",
        builder="un-1718",
        operational_role="MULTILATERAL_SANCTIONS_AUTHORITY",
        max_stale_seconds=172_800,
    ),
    "noaa-ais-2025": ConnectorSpec(
        id="noaa-ais-2025",
        vertical="killinchu",
        authority="NOAA Office for Coastal Management / U.S. Coast Guard",
        authority_url="https://www.fisheries.noaa.gov/inport/item/77594",
        method="GET",
        response_format="xml",
        freshness_seconds=86_400,
        max_bytes=4_000_000,
        required=False,
        auth_env=None,
        description="Official 2025 nationwide AIS metadata and distribution references; historical planning data, never a live vessel feed.",
        builder="noaa",
        data_mode="HISTORICAL",
        operational_role="HISTORICAL_AIS_CORPUS",
        max_stale_seconds=604_800,
    ),

    # FINANCE ----------------------------------------------------------------------
    "sec-submissions": ConnectorSpec(
        id="sec-submissions",
        vertical="finance",
        authority="U.S. Securities and Exchange Commission",
        authority_url="https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
        method="GET",
        response_format="json",
        freshness_seconds=900,
        max_bytes=12_000_000,
        required=True,
        auth_env=None,
        description="Current EDGAR company submissions history from data.sec.gov.",
        builder="sec-submissions",
        operational_role="ISSUER_FILING_AUTHORITY",
        max_stale_seconds=86_400,
    ),
    "sec-companyfacts": ConnectorSpec(
        id="sec-companyfacts",
        vertical="finance",
        authority="U.S. Securities and Exchange Commission",
        authority_url="https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
        method="GET",
        response_format="json",
        freshness_seconds=900,
        max_bytes=24_000_000,
        required=False,
        auth_env=None,
        description="Extracted XBRL company facts from data.sec.gov.",
        builder="sec-companyfacts",
        operational_role="ISSUER_FACT_ENRICHMENT",
        max_stale_seconds=86_400,
    ),
    "treasury-debt-to-penny": ConnectorSpec(
        id="treasury-debt-to-penny",
        vertical="finance",
        authority="U.S. Department of the Treasury, Bureau of the Fiscal Service",
        authority_url="https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/debt-to-the-penny",
        method="GET",
        response_format="json",
        freshness_seconds=86_400,
        max_bytes=3_000_000,
        required=True,
        auth_env=None,
        description="Debt to the Penny observations from the Treasury Fiscal Data API.",
        builder="treasury-debt",
        operational_role="SOVEREIGN_DEBT_SERIES",
        max_stale_seconds=259_200,
    ),
    "fred-series": ConnectorSpec(
        id="fred-series",
        vertical="finance",
        authority="Federal Reserve Bank of St. Louis",
        authority_url="https://fred.stlouisfed.org/docs/api/fred/series_observations.html",
        method="GET",
        response_format="json",
        freshness_seconds=3600,
        max_bytes=4_000_000,
        required=True,
        auth_env="FRED_API_KEY",
        description="Explicit FRED series observations; requires an operator-provided FRED API key.",
        builder="fred",
        source_class="PUBLIC_AUTHORITY_CREDENTIALED",
        operational_role="MACROECONOMIC_SERIES",
        max_stale_seconds=86_400,
    ),

    # TERRA ------------------------------------------------------------------------
    "census-acs5": ConnectorSpec(
        id="census-acs5",
        vertical="terra",
        authority="U.S. Census Bureau",
        authority_url="https://api.census.gov/data/2024/acs/acs5.html",
        method="GET",
        response_format="json",
        freshness_seconds=86_400,
        max_bytes=4_000_000,
        required=True,
        auth_env="CENSUS_API_KEY",
        description="ACS five-year demographic, economic and housing estimates for an explicit geography.",
        builder="census-acs5",
        source_class="PUBLIC_AUTHORITY_CREDENTIALED",
        operational_role="DEMOGRAPHIC_AND_HOUSING_CONTEXT",
        max_stale_seconds=604_800,
    ),
    "openfema-declarations": ConnectorSpec(
        id="openfema-declarations",
        vertical="terra",
        authority="Federal Emergency Management Agency",
        authority_url="https://www.fema.gov/about/openfema/api",
        method="GET",
        response_format="json",
        freshness_seconds=1200,
        max_bytes=4_000_000,
        required=True,
        auth_env=None,
        description="OpenFEMA disaster declaration summaries for explicit state and incident filters.",
        builder="openfema",
        operational_role="DISASTER_DECLARATION_CONTEXT",
        max_stale_seconds=86_400,
    ),
    "fhfa-hpi-state": ConnectorSpec(
        id="fhfa-hpi-state",
        vertical="terra",
        authority="Federal Housing Finance Agency",
        authority_url="https://www.fhfa.gov/data/house-price-index",
        method="GET",
        response_format="json",
        freshness_seconds=86_400,
        max_bytes=2_000_000,
        required=True,
        auth_env=None,
        description="Current FHFA state HPI change table in JSON.",
        builder="fhfa-hpi-state",
        operational_role="HOUSE_PRICE_INDEX",
        max_stale_seconds=604_800,
    ),
    "nyc-pluto": ConnectorSpec(
        id="nyc-pluto",
        vertical="terra",
        authority="NYC Department of City Planning",
        authority_url="https://data.cityofnewyork.us/City-Government/Primary-Land-Use-Tax-Lot-Output-PLUTO-/64uk-42ks",
        method="GET",
        response_format="json",
        freshness_seconds=21_600,
        max_bytes=4_000_000,
        required=False,
        auth_env=None,
        description="Current Primary Land Use Tax Lot Output records through NYC Open Data.",
        builder="pluto",
        source_class="LOCAL_PUBLIC_AUTHORITY",
        operational_role="PARCEL_RECORDS",
        max_stale_seconds=172_800,
    ),

    # COUNSEL ----------------------------------------------------------------------
    "federal-register": ConnectorSpec(
        id="federal-register",
        vertical="counsel",
        authority="Office of the Federal Register",
        authority_url="https://www.federalregister.gov/developers/documentation/api/v1",
        method="GET",
        response_format="json",
        freshness_seconds=900,
        max_bytes=4_000_000,
        required=True,
        auth_env=None,
        description="Official Federal Register document API.",
        builder="federal-register",
        operational_role="FEDERAL_RULEMAKING_AUTHORITY",
        max_stale_seconds=86_400,
    ),
    "courtlistener-search": ConnectorSpec(
        id="courtlistener-search",
        vertical="counsel",
        authority="Free Law Project / CourtListener",
        authority_url="https://www.courtlistener.com/help/api/rest/",
        method="GET",
        response_format="json",
        freshness_seconds=900,
        max_bytes=6_000_000,
        required=True,
        auth_env="COURTLISTENER_API_TOKEN",
        description="Authenticated CourtListener v4 search over public opinions and dockets.",
        builder="courtlistener",
        source_class="PUBLIC_LEGAL_CORPUS_CREDENTIALED",
        operational_role="CASELAW_AND_DOCKET_RESEARCH",
        max_stale_seconds=86_400,
    ),
    "congress-bills": ConnectorSpec(
        id="congress-bills",
        vertical="counsel",
        authority="Library of Congress",
        authority_url="https://api.congress.gov/",
        method="GET",
        response_format="json",
        freshness_seconds=900,
        max_bytes=4_000_000,
        required=False,
        auth_env="CONGRESS_API_KEY",
        description="Congress.gov bill metadata; requires a configured api.data.gov key.",
        builder="congress",
        source_class="PUBLIC_AUTHORITY_CREDENTIALED",
        operational_role="LEGISLATIVE_AUTHORITY",
        max_stale_seconds=86_400,
    ),
}

GITHUB_REPOSITORIES = {
    "a11oy",
    "killinchu",
    "platform",
    "vertical-services",
    "lyte-lattice",
    "szl-real-estate",
    "puriq-live",
    "szl-defensive-control-plane",
    "counsel",
    "david-leads",
}


class ConnectorFetchRequest(StrictModel):
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    force_refresh: bool = False
