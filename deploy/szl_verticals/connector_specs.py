"""Allowlisted official-source connector specifications."""
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
BOROUGHS = {"MN", "BX", "BK", "QN", "SI", "MANHATTAN", "BRONX", "BROOKLYN", "QUEENS", "STATEN ISLAND"}
DEFAULT_USER_AGENT = os.environ.get(
    "SZL_HTTP_USER_AGENT",
    "SZL-Vertical-Services/2.0 (+https://a-11-oy.com)",
).strip()
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "SZL Holdings vertical-services https://a-11-oy.com",
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


CONNECTORS: dict[str, ConnectorSpec] = {
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
        description="NVD CVE 2.0 enrichment; an NVD_API_KEY is optional and used only as a header.",
        builder="nvd",
    ),
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
        required=True,
        auth_env=None,
        description="Official 2025 nationwide AIS metadata and distribution references. It is historical planning data, not a live vessel feed.",
        builder="noaa",
    ),
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
        description="Real-time EDGAR company submissions history from data.sec.gov.",
        builder="sec-submissions",
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
        required=True,
        auth_env=None,
        description="Current Primary Land Use Tax Lot Output records through NYC Open Data.",
        builder="pluto",
    ),
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
        description="Congress.gov bill metadata. Requires a configured api.data.gov key.",
        builder="congress",
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
