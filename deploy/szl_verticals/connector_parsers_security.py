"""Cybersecurity and CI/CD source normalizers."""
from __future__ import annotations

from typing import Any, Mapping

from fastapi import HTTPException

from .connector_parameters import _bounded_int, _safe_text
from .connector_specs import CVE

def _limit(parameters: Mapping[str, Any], default: int = 10, high: int = 100) -> int:
    return _bounded_int(parameters, "limit", default, 1, high)


def _parse_cisa(payload: Any, parameters: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("vulnerabilities"), list):
        raise HTTPException(502, "CISA KEV payload schema is not recognized")
    cve = _safe_text(parameters, "cve").upper()
    vendor = _safe_text(parameters, "vendor", max_length=100).casefold()
    rows = payload["vulnerabilities"]
    if cve:
        if CVE.fullmatch(cve) is None:
            raise HTTPException(422, "cve must use CVE-YYYY-NNNN format")
        rows = [row for row in rows if str(row.get("cveID", "")).upper() == cve]
    if vendor:
        rows = [row for row in rows if vendor in str(row.get("vendorProject", "")).casefold()]
    selected = []
    for row in rows[: _limit(parameters, 20, 100)]:
        selected.append(
            {
                key: row.get(key)
                for key in (
                    "cveID",
                    "vendorProject",
                    "product",
                    "vulnerabilityName",
                    "dateAdded",
                    "dueDate",
                    "knownRansomwareCampaignUse",
                    "requiredAction",
                )
            }
        )
    return {
        "catalog_version": payload.get("catalogVersion"),
        "date_released": payload.get("dateReleased"),
        "matched": len(rows),
        "items": selected,
    }


def _parse_nvd(payload: Any, _: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("vulnerabilities"), list):
        raise HTTPException(502, "NVD payload schema is not recognized")
    rows = []
    for wrapper in payload["vulnerabilities"][:20]:
        cve = wrapper.get("cve", {}) if isinstance(wrapper, dict) else {}
        descriptions = cve.get("descriptions", [])
        description = next(
            (item.get("value") for item in descriptions if item.get("lang") == "en"),
            None,
        )
        rows.append(
            {
                "id": cve.get("id"),
                "published": cve.get("published"),
                "last_modified": cve.get("lastModified"),
                "vuln_status": cve.get("vulnStatus"),
                "description": description,
                "metrics": cve.get("metrics", {}),
            }
        )
    return {
        "total_results": payload.get("totalResults"),
        "results_per_page": payload.get("resultsPerPage"),
        "items": rows,
    }


def _parse_github(payload: Any, _: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list):
        raise HTTPException(502, "GitHub Actions payload schema is not recognized")
    rows = []
    for run in payload["workflow_runs"][:50]:
        rows.append(
            {
                key: run.get(key)
                for key in (
                    "id",
                    "name",
                    "display_title",
                    "event",
                    "status",
                    "conclusion",
                    "head_branch",
                    "head_sha",
                    "run_number",
                    "created_at",
                    "updated_at",
                    "html_url",
                )
            }
        )
    completed = [row for row in rows if row["status"] == "completed"]
    failed = [
        row
        for row in completed
        if row["conclusion"] not in {"success", "neutral", "skipped"}
    ]
    return {
        "total_count": payload.get("total_count"),
        "returned": len(rows),
        "completed": len(completed),
        "failed_or_cancelled": len(failed),
        "success_rate": round((len(completed) - len(failed)) / len(completed), 4)
        if completed
        else None,
        "runs": rows,
    }
