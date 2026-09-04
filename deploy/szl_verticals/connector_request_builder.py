"""Fixed request builders for allowlisted official sources."""
from __future__ import annotations

import os
from typing import Any, Mapping

from fastapi import HTTPException

from .connector_parameters import _bounded_int, _reject_unknown, _safe_text
from .connector_specs import (
    BBL, BOROUGHS, CIK, CVE, DEFAULT_USER_AGENT, GITHUB_REPOSITORIES,
    SAFE_REPO, SEC_USER_AGENT, ConnectorSpec,
)

def _request_definition(spec: ConnectorSpec, parameters: Mapping[str, Any]) -> tuple[str, dict[str, str], dict[str, str]]:
    """Return URL, query parameters, and headers for an allowlisted connector."""
    headers = {
        "Accept": "application/json, application/xml;q=0.9, text/xml;q=0.8",
        "User-Agent": DEFAULT_USER_AGENT,
    }
    query: dict[str, str] = {}

    if spec.builder == "cisa":
        allowed = {"cve", "vendor", "limit"}
        _reject_unknown(parameters, allowed)
        return (
            "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
            query,
            headers,
        )

    if spec.builder == "nvd":
        allowed = {"cve", "keyword", "limit"}
        _reject_unknown(parameters, allowed)
        cve = _safe_text(parameters, "cve").upper()
        keyword = _safe_text(parameters, "keyword", max_length=100)
        if not cve and not keyword:
            raise HTTPException(422, "nvd-cve requires cve or keyword")
        if cve and CVE.fullmatch(cve) is None:
            raise HTTPException(422, "cve must use CVE-YYYY-NNNN format")
        query["resultsPerPage"] = str(_bounded_int(parameters, "limit", 10, 1, 20))
        if cve:
            query["cveId"] = cve
        if keyword:
            query["keywordSearch"] = keyword
        api_key = os.environ.get("NVD_API_KEY", "").strip()
        if api_key:
            headers["apiKey"] = api_key
        return "https://services.nvd.nist.gov/rest/json/cves/2.0", query, headers

    if spec.builder == "github":
        allowed = {"repository", "limit", "branch", "status"}
        _reject_unknown(parameters, allowed)
        repository = _safe_text(parameters, "repository", "a11oy", 100).lower()
        if SAFE_REPO.fullmatch(repository) is None or repository not in GITHUB_REPOSITORIES:
            raise HTTPException(422, "repository is not in the SZL observability allowlist")
        query["per_page"] = str(_bounded_int(parameters, "limit", 20, 1, 50))
        branch = _safe_text(parameters, "branch", max_length=100)
        status = _safe_text(parameters, "status", max_length=32)
        if branch:
            query["branch"] = branch
        if status:
            if status not in {"completed", "in_progress", "queued", "requested", "waiting", "pending"}:
                raise HTTPException(422, "unsupported workflow-run status")
            query["status"] = status
        token = os.environ.get("GITHUB_READ_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["X-GitHub-Api-Version"] = "2022-11-28"
        return f"https://api.github.com/repos/szl-holdings/{repository}/actions/runs", query, headers

    if spec.builder == "noaa":
        _reject_unknown(parameters, set())
        headers["Accept"] = "application/xml, text/xml;q=0.9"
        return (
            "https://www.fisheries.noaa.gov/inportserve/waf/noaa/nos/ocm/inport-xml/xml/77594.xml",
            query,
            headers,
        )

    if spec.builder in {"sec-submissions", "sec-companyfacts"}:
        allowed = {"cik", "limit", "concept"}
        _reject_unknown(parameters, allowed)
        cik = _safe_text(parameters, "cik")
        if CIK.fullmatch(cik) is None:
            raise HTTPException(422, "cik must contain 1 to 10 digits")
        cik = cik.zfill(10)
        headers["User-Agent"] = SEC_USER_AGENT
        headers["Accept-Encoding"] = "gzip, deflate"
        if spec.builder == "sec-submissions":
            return f"https://data.sec.gov/submissions/CIK{cik}.json", query, headers
        return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", query, headers

    if spec.builder == "pluto":
        allowed = {"bbl", "borough", "zipcode", "limit"}
        _reject_unknown(parameters, allowed)
        query["$limit"] = str(_bounded_int(parameters, "limit", 20, 1, 100))
        query["$select"] = ",".join(
            (
                "bbl",
                "borough",
                "block",
                "lot",
                "address",
                "zipcode",
                "zonedist1",
                "landuse",
                "bldgclass",
                "ownername",
                "lotarea",
                "bldgarea",
                "yearbuilt",
                "assessland",
                "assesstot",
                "latitude",
                "longitude",
            )
        )
        clauses: list[str] = []
        bbl = _safe_text(parameters, "bbl")
        if bbl:
            if BBL.fullmatch(bbl) is None:
                raise HTTPException(422, "bbl must contain exactly 10 digits")
            clauses.append(f"bbl='{bbl}'")
        borough = _safe_text(parameters, "borough", max_length=32).upper()
        if borough:
            if borough not in BOROUGHS:
                raise HTTPException(422, "borough is not recognized")
            clauses.append(f"upper(borough)='{borough.replace(chr(39), chr(39)*2)}'")
        zipcode = _safe_text(parameters, "zipcode", max_length=10)
        if zipcode:
            if not zipcode.isdigit():
                raise HTTPException(422, "zipcode must be numeric")
            clauses.append(f"zipcode='{zipcode}'")
        if not clauses:
            raise HTTPException(422, "nyc-pluto requires bbl, borough, or zipcode")
        query["$where"] = " AND ".join(clauses)
        return "https://data.cityofnewyork.us/resource/64uk-42ks.json", query, headers

    if spec.builder == "federal-register":
        allowed = {"term", "agency", "limit"}
        _reject_unknown(parameters, allowed)
        query["per_page"] = str(_bounded_int(parameters, "limit", 10, 1, 20))
        query["order"] = "newest"
        term = _safe_text(parameters, "term", max_length=120)
        agency = _safe_text(parameters, "agency", max_length=80)
        if term:
            query["conditions[term]"] = term
        if agency:
            query["conditions[agencies][]"] = agency
        return "https://www.federalregister.gov/api/v1/documents.json", query, headers

    if spec.builder == "congress":
        allowed = {"congress", "bill_type", "limit"}
        _reject_unknown(parameters, allowed)
        key = os.environ.get("CONGRESS_API_KEY", "").strip()
        if not key:
            raise HTTPException(503, "CONGRESS_API_KEY is not configured")
        query["api_key"] = key
        query["format"] = "json"
        query["limit"] = str(_bounded_int(parameters, "limit", 10, 1, 20))
        congress = _safe_text(parameters, "congress", max_length=3)
        bill_type = _safe_text(parameters, "bill_type", max_length=16).lower()
        path = "https://api.congress.gov/v3/bill"
        if congress:
            if not congress.isdigit():
                raise HTTPException(422, "congress must be numeric")
            path += f"/{congress}"
            if bill_type:
                if bill_type not in {"hr", "s", "hjres", "sjres", "hconres", "sconres", "hres", "sres"}:
                    raise HTTPException(422, "unsupported bill_type")
                path += f"/{bill_type}"
        elif bill_type:
            raise HTTPException(422, "bill_type requires congress")
        return path, query, headers

    raise HTTPException(500, f"connector builder is not implemented: {spec.builder}")
