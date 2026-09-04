#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""SZL Vertical Frontier reference runtime.

A dependency-free Python 3.12 service that exposes eight distinct public
vertical experiences, bounded official-source snapshots, governed model/kernel
routing, deterministic proposal receipts, and a fail-closed decision boundary.

The runtime deliberately does not execute trades, legal filings, remediation,
physical effects, or production mutations. Models and kernels can propose and
check; only an operator-owned system may bind and execute consequential action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Final, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT: Final = Path(__file__).resolve().parent
STATIC_ROOT: Final = ROOT / "static"
REGISTRY_PATH: Final = ROOT / "verticals.json"
MAX_REQUEST_BYTES: Final = 128 * 1024
MAX_RESPONSE_BYTES: Final = 2 * 1024 * 1024
FETCH_TIMEOUT_SECONDS: Final = 8.0
STARTED_AT: Final = time.monotonic()

SAFE_SLUG = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
SAFE_REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
SAFE_CIK = re.compile(r"^\d{1,10}$")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

CONTENT_TYPES: Final = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".webp": "image/webp",
}

STATIC_FILES: Final = {
    "/": "index.html",
    "/index.html": "index.html",
    "/static/base.css": "base.css",
    "/static/themes.css": "themes.css",
    "/static/app.js": "app.js",
}

ACTION_DENY_TERMS: Final = {
    "killinchu": (
        "fire weapon",
        "launch weapon",
        "engage target",
        "autonomous target",
        "disable vessel",
        "jam signal",
    ),
    "sentra": (
        "exploit host",
        "steal credential",
        "dump password",
        "deploy ransomware",
        "bypass authentication",
        "scan unauthorized",
    ),
    "puriq": (
        "execute trade",
        "buy shares",
        "sell shares",
        "guaranteed return",
        "place order",
    ),
    "prism": (
        "file with court",
        "submit filing",
        "give legal advice",
        "represent client",
        "sign pleading",
    ),
    "terra": (
        "deny housing",
        "protected class",
        "approve mortgage",
        "deny mortgage",
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical_json(value)
    return hashlib.sha256(raw).hexdigest()


def exact_source_revision() -> str:
    configured = os.getenv("SZL_GIT_SHA", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", configured):
        return configured
    try:
        value = subprocess.check_output(
            ["git", "-C", str(ROOT.parent), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip().lower()
    except (OSError, subprocess.SubprocessError):
        return "REVISION_UNAVAILABLE"
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else "REVISION_UNAVAILABLE"


def load_registry() -> dict[str, Any]:
    document = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if document.get("schema") != "szl.vertical-frontier.v1":
        raise RuntimeError("unexpected vertical registry schema")
    verticals = document.get("verticals")
    if not isinstance(verticals, list) or not verticals:
        raise RuntimeError("vertical registry is empty")
    slugs: set[str] = set()
    layouts: set[str] = set()
    instruments: set[str] = set()
    palettes: set[tuple[str, ...]] = set()
    for row in verticals:
        if not isinstance(row, dict):
            raise RuntimeError("vertical row must be an object")
        slug = row.get("slug")
        experience = row.get("experience")
        if not isinstance(slug, str) or not SAFE_SLUG.fullmatch(slug):
            raise RuntimeError(f"invalid vertical slug: {slug!r}")
        if slug in slugs:
            raise RuntimeError(f"duplicate vertical slug: {slug}")
        if not isinstance(experience, dict):
            raise RuntimeError(f"missing experience contract: {slug}")
        layout = experience.get("layout")
        instrument = experience.get("instrument")
        palette = experience.get("palette")
        if not isinstance(layout, str) or layout in layouts:
            raise RuntimeError(f"layout must be unique: {slug}")
        if not isinstance(instrument, str) or instrument in instruments:
            raise RuntimeError(f"instrument must be unique: {slug}")
        if not isinstance(palette, list) or len(palette) < 5:
            raise RuntimeError(f"palette must define at least five tokens: {slug}")
        palette_key = tuple(str(item).upper() for item in palette)
        if palette_key in palettes:
            raise RuntimeError(f"palette must be unique: {slug}")
        if not row.get("models") or not row.get("kernels") or not row.get("sources"):
            raise RuntimeError(f"missing model, kernel, or source bindings: {slug}")
        slugs.add(slug)
        layouts.add(layout)
        instruments.add(instrument)
        palettes.add(palette_key)
    authority = document.get("authority", {})
    if authority.get("model_may_authorize") is not False:
        raise RuntimeError("models must never authorize")
    if authority.get("kernel_may_authorize") is not False:
        raise RuntimeError("kernels must never authorize")
    if authority.get("public_effectors_enabled") is not False:
        raise RuntimeError("public effectors must remain disabled")
    return document


REGISTRY: Final = load_registry()
VERTICALS: Final = {row["slug"]: row for row in REGISTRY["verticals"]}
ALLOWED_FETCH_HOSTS: Final = {
    source["host"]
    for vertical in REGISTRY["verticals"]
    for source in vertical["sources"]
    if source["host"] not in {"localhost", "opentelemetry.io"}
}


class AllowlistedRedirects(HTTPRedirectHandler):
    """Reject any redirect that leaves the fixed official-source allowlist."""

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> Request | None:
        host = (urlparse(newurl).hostname or "").lower()
        if host not in ALLOWED_FETCH_HOSTS:
            raise URLError(f"redirect target is not allowlisted: {host}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER: Final = build_opener(AllowlistedRedirects())


@dataclass(frozen=True)
class Snapshot:
    vertical: str
    source: str
    state: str
    observed_at: str
    payload: dict[str, Any]
    source_url: str | None = None
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        body = {
            "schema": "szl.vertical-snapshot.v1",
            "vertical": self.vertical,
            "source": self.source,
            "state": self.state,
            "observed_at": self.observed_at,
            "payload": self.payload,
            "source_url": self.source_url,
            "note": self.note,
        }
        body["receipt_sha256"] = sha256(body)
        return body


def bounded_json(url: str, *, headers: Mapping[str, str] | None = None) -> tuple[Any, dict[str, str]]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_FETCH_HOSTS:
        raise ValueError(f"source host is not allowlisted: {host or 'missing'}")
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "SZL-Vertical-Frontier/1.0 (+https://github.com/szl-holdings/vertical-services)",
    }
    request_headers.update(headers or {})
    request = Request(url, headers=request_headers, method="GET")
    with OPENER.open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get("Content-Type", "")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("official-source response exceeded the bounded size limit")
        if "json" not in content_type.lower() and not raw.lstrip().startswith((b"{", b"[")):
            raise ValueError(f"expected JSON from official source, received {content_type!r}")
        metadata = {
            "content_type": content_type,
            "etag": response.headers.get("ETag", ""),
            "last_modified": response.headers.get("Last-Modified", ""),
            "bytes": str(len(raw)),
            "body_sha256": hashlib.sha256(raw).hexdigest(),
        }
        return json.loads(raw.decode("utf-8")), metadata


def snapshot_a11oy(_: Mapping[str, list[str]]) -> Snapshot:
    return Snapshot(
        vertical="a11oy",
        source="vertical-registry",
        state="LOCAL_VERIFIED",
        observed_at=utc_now(),
        payload={
            "vertical_count": len(VERTICALS),
            "shared_edge": REGISTRY["shared_edge"],
            "authority": REGISTRY["authority"],
        },
        note="Local source-bound registry; no external provider inference required.",
    )


def snapshot_sentra(_: Mapping[str, list[str]]) -> Snapshot:
    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    document, meta = bounded_json(url)
    vulnerabilities = document.get("vulnerabilities", []) if isinstance(document, dict) else []
    rows = [row for row in vulnerabilities if isinstance(row, dict)]
    rows.sort(key=lambda row: str(row.get("dateAdded", "")), reverse=True)
    recent = [
        {
            "cve": row.get("cveID"),
            "vendor": row.get("vendorProject"),
            "product": row.get("product"),
            "date_added": row.get("dateAdded"),
            "due_date": row.get("dueDate"),
            "known_ransomware": row.get("knownRansomwareCampaignUse"),
        }
        for row in rows[:12]
    ]
    return Snapshot(
        vertical="sentra",
        source="cisa-kev",
        state="LIVE_OFFICIAL",
        observed_at=utc_now(),
        source_url=url,
        payload={
            "catalog_title": document.get("title") if isinstance(document, dict) else None,
            "catalog_version": document.get("catalogVersion") if isinstance(document, dict) else None,
            "date_released": document.get("dateReleased") if isinstance(document, dict) else None,
            "vulnerability_count": len(rows),
            "recent": recent,
            "transport": meta,
        },
        note="CISA KEV establishes known exploitation, not asset exposure or authorization to remediate.",
    )


def snapshot_lyte(query: Mapping[str, list[str]]) -> Snapshot:
    repo = (query.get("repo") or ["szl-command-lab"])[0]
    if not SAFE_REPO.fullmatch(repo):
        raise ValueError("repo must be a simple GitHub repository name")
    url = f"https://api.github.com/repos/szl-holdings/{quote(repo, safe='')}/actions/runs?per_page=20"
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    document, meta = bounded_json(url, headers=headers)
    runs = document.get("workflow_runs", []) if isinstance(document, dict) else []
    recent = [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "event": row.get("event"),
            "status": row.get("status"),
            "conclusion": row.get("conclusion"),
            "head_sha": row.get("head_sha"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
        for row in runs[:20]
        if isinstance(row, dict)
    ]
    completed = [row for row in recent if row["status"] == "completed"]
    successful = [row for row in completed if row["conclusion"] == "success"]
    return Snapshot(
        vertical="lyte",
        source="github-actions",
        state="LIVE_OFFICIAL",
        observed_at=utc_now(),
        source_url=url,
        payload={
            "repository": f"szl-holdings/{repo}",
            "provider_total_count": document.get("total_count") if isinstance(document, dict) else None,
            "sample_count": len(recent),
            "completed_count": len(completed),
            "successful_count": len(successful),
            "sample_success_ratio": round(len(successful) / len(completed), 4) if completed else None,
            "recent": recent,
            "transport": meta,
        },
        note="Workflow status is execution telemetry; it does not establish business outcome or production readiness.",
    )


def snapshot_killinchu(_: Mapping[str, list[str]]) -> Snapshot:
    return Snapshot(
        vertical="killinchu",
        source="noaa-ais-2025",
        state="HISTORICAL_SOURCE_CONTRACT",
        observed_at=utc_now(),
        source_url="https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2025/index.html",
        payload={
            "live_positions_connected": False,
            "historical_planning_data": True,
            "public_effectors_enabled": False,
            "public_actuation": "SIMULATED",
            "sources": VERTICALS["killinchu"]["sources"],
        },
        note="The reference runtime does not present historical AIS as a live tactical feed.",
    )


def normalized_cik(query: Mapping[str, list[str]]) -> str:
    raw = (query.get("cik") or [""])[0].strip()
    if not SAFE_CIK.fullmatch(raw):
        raise ValueError("cik must contain one to ten digits")
    return raw.zfill(10)


def sec_headers() -> dict[str, str]:
    agent = os.getenv("SEC_USER_AGENT", "").strip()
    if not agent or "@" not in agent:
        raise RuntimeError("SEC_USER_AGENT must identify the operator and include a contact email")
    return {"User-Agent": agent, "Accept-Encoding": "gzip, deflate"}


def snapshot_puriq(query: Mapping[str, list[str]]) -> Snapshot:
    cik = normalized_cik(query)
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    document, meta = bounded_json(url, headers=sec_headers())
    recent = document.get("filings", {}).get("recent", {}) if isinstance(document, dict) else {}
    forms = recent.get("form", []) if isinstance(recent, dict) else []
    accession = recent.get("accessionNumber", []) if isinstance(recent, dict) else []
    filed = recent.get("filingDate", []) if isinstance(recent, dict) else []
    primary = recent.get("primaryDocument", []) if isinstance(recent, dict) else []
    items: list[dict[str, Any]] = []
    for index in range(min(20, len(forms), len(accession), len(filed), len(primary))):
        items.append(
            {
                "form": forms[index],
                "accession_number": accession[index],
                "filing_date": filed[index],
                "primary_document": primary[index],
            }
        )
    return Snapshot(
        vertical="puriq",
        source="sec-submissions",
        state="LIVE_OFFICIAL",
        observed_at=utc_now(),
        source_url=url,
        payload={
            "cik": cik,
            "name": document.get("name") if isinstance(document, dict) else None,
            "tickers": document.get("tickers", []) if isinstance(document, dict) else [],
            "sic": document.get("sic") if isinstance(document, dict) else None,
            "recent_filings": items,
            "transport": meta,
        },
        note="Filing metadata is research evidence, not investment advice or a trading signal.",
    )


def snapshot_terra(query: Mapping[str, list[str]]) -> Snapshot:
    limit_raw = (query.get("limit") or ["12"])[0]
    try:
        limit = max(1, min(25, int(limit_raw)))
    except ValueError as exc:
        raise ValueError("limit must be an integer") from exc
    url = f"https://data.cityofnewyork.us/resource/64uk-42ks.json?$limit={limit}"
    document, meta = bounded_json(url)
    rows = document if isinstance(document, list) else []
    allowed_keys = {
        "borough",
        "block",
        "lot",
        "address",
        "zipcode",
        "landuse",
        "bldgclass",
        "ownername",
        "yearbuilt",
        "assessland",
        "assesstot",
        "latitude",
        "longitude",
    }
    parcels = [
        {key: value for key, value in row.items() if key.lower() in allowed_keys}
        for row in rows
        if isinstance(row, dict)
    ]
    return Snapshot(
        vertical="terra",
        source="nyc-pluto",
        state="LIVE_OFFICIAL",
        observed_at=utc_now(),
        source_url=url,
        payload={"sample_count": len(parcels), "parcels": parcels, "transport": meta},
        note="Public parcel records are not an appraisal, title report, lending decision, or fair-housing decision.",
    )


def snapshot_prism(query: Mapping[str, list[str]]) -> Snapshot:
    term = (query.get("term") or [""])[0].strip()
    if len(term) > 80:
        raise ValueError("term exceeds 80 characters")
    suffix = f"&conditions[term]={quote(term)}" if term else ""
    url = f"https://www.federalregister.gov/api/v1/documents.json?per_page=20&order=newest{suffix}"
    document, meta = bounded_json(url)
    results = document.get("results", []) if isinstance(document, dict) else []
    documents = [
        {
            "document_number": row.get("document_number"),
            "title": row.get("title"),
            "type": row.get("type"),
            "publication_date": row.get("publication_date"),
            "agencies": [agency.get("name") for agency in row.get("agencies", []) if isinstance(agency, dict)],
            "html_url": row.get("html_url"),
        }
        for row in results[:20]
        if isinstance(row, dict)
    ]
    return Snapshot(
        vertical="prism",
        source="federal-register",
        state="LIVE_OFFICIAL",
        observed_at=utc_now(),
        source_url=url,
        payload={
            "term": term or None,
            "provider_count": document.get("count") if isinstance(document, dict) else None,
            "documents": documents,
            "transport": meta,
        },
        note="Federal Register material is authority research input; licensed legal review remains required.",
    )


def snapshot_anatomy(_: Mapping[str, list[str]]) -> Snapshot:
    return Snapshot(
        vertical="anatomy",
        source="runtime-health",
        state="LIVE_LOCAL",
        observed_at=utc_now(),
        payload={
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.system(),
            "uptime_seconds": round(time.monotonic() - STARTED_AT, 3),
            "registry_sha256": sha256(REGISTRY),
            "vertical_count": len(VERTICALS),
            "model_may_authorize": False,
            "kernel_may_authorize": False,
        },
        note="Local process health is not equivalent to end-to-end system readiness.",
    )


SNAPSHOTTERS: Final[dict[str, Callable[[Mapping[str, list[str]]], Snapshot]]] = {
    "a11oy": snapshot_a11oy,
    "killinchu": snapshot_killinchu,
    "lyte": snapshot_lyte,
    "sentra": snapshot_sentra,
    "terra": snapshot_terra,
    "puriq": snapshot_puriq,
    "prism": snapshot_prism,
    "anatomy": snapshot_anatomy,
}


def model_route(vertical: dict[str, Any], objective: str) -> dict[str, Any]:
    return {
        "schema": "szl.model-route.v1",
        "vertical": vertical["slug"],
        "objective_sha256": hashlib.sha256(objective.encode("utf-8")).hexdigest(),
        "models": vertical["models"],
        "kernels": vertical["kernels"],
        "mode": "PROPOSAL_ONLY",
        "authorization": "NONE",
        "human_binding_required": True,
        "reason": "Models draft and kernels check. Neither grants permission or executes an effect.",
    }


def normalize_evidence(raw: Any) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not isinstance(raw, list):
        return [], ["evidence must be a list"]
    if len(raw) > 12:
        return [], ["evidence exceeds the twelve-item bound"]
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(raw):
        if not isinstance(row, dict):
            warnings.append(f"evidence[{index}] is not an object")
            continue
        source = str(row.get("source", "")).strip()[:120]
        claim = str(row.get("claim", "")).strip()[:1000]
        uri = str(row.get("uri", "")).strip()[:1000]
        observed_at = str(row.get("observed_at", "")).strip()[:64]
        digest = str(row.get("sha256", "")).strip().lower()
        if not source or not claim:
            warnings.append(f"evidence[{index}] requires source and claim")
            continue
        if digest and not SHA256_HEX.fullmatch(digest):
            warnings.append(f"evidence[{index}] sha256 is invalid")
            continue
        normalized.append(
            {
                "source": source,
                "claim": claim,
                "uri": uri or None,
                "observed_at": observed_at or None,
                "sha256": digest or hashlib.sha256(claim.encode("utf-8")).hexdigest(),
            }
        )
    return normalized, warnings


def evaluate_proposal(payload: dict[str, Any]) -> dict[str, Any]:
    slug = str(payload.get("vertical", "")).strip().lower()
    if slug not in VERTICALS:
        raise ValueError("unknown vertical")
    objective = str(payload.get("objective", "")).strip()
    if not objective or len(objective) > 2000:
        raise ValueError("objective is required and must not exceed 2,000 characters")
    action = str(payload.get("requested_action", "review")).strip()[:500]
    risk_raw = payload.get("risk", 0.5)
    if isinstance(risk_raw, bool):
        raise ValueError("risk must be numeric")
    try:
        risk = float(risk_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("risk must be numeric") from exc
    if not 0.0 <= risk <= 1.0:
        raise ValueError("risk must be between 0 and 1")

    evidence, evidence_warnings = normalize_evidence(payload.get("evidence", []))
    human_approved = payload.get("human_approved") is True
    vertical = VERTICALS[slug]
    deny_terms = ACTION_DENY_TERMS.get(slug, ())
    combined = f"{objective} {action}".lower()
    matched_terms = [term for term in deny_terms if term in combined]

    blocks: list[str] = []
    if not evidence:
        blocks.append("NO_ADMISSIBLE_EVIDENCE")
    if evidence_warnings:
        blocks.append("EVIDENCE_VALIDATION_WARNING")
    if matched_terms:
        blocks.append("PROHIBITED_ACTION_CLASS")
    if risk >= 0.65:
        blocks.append("ELEVATED_RISK_REQUIRES_REVIEW")
    if not human_approved:
        blocks.append("HUMAN_BINDING_ABSENT")

    state = "HOLD" if blocks else "READY_FOR_OPERATOR_BINDING"
    proposal = {
        "objective": objective,
        "requested_action": action,
        "evidence_count": len(evidence),
        "evidence_digest": sha256(evidence),
        "risk": risk,
        "summary": (
            f"{vertical['name']} proposal prepared from {len(evidence)} admissible evidence item(s). "
            "The result remains advisory and no external effect was executed."
        ),
    }
    route = model_route(vertical, objective)
    receipt_body = {
        "schema": "szl.vertical-decision-receipt.v1",
        "vertical": slug,
        "state": state,
        "blocks": sorted(set(blocks)),
        "matched_prohibited_terms": matched_terms,
        "proposal": proposal,
        "route": route,
        "evidence": evidence,
        "evidence_warnings": evidence_warnings,
        "human_approved_input": human_approved,
        "authorization": "NONE",
        "execution_performed": False,
        "public_effectors_enabled": False,
        "lambda_uniqueness": "CONJECTURE_1_OPEN",
        "issued_at": utc_now(),
        "source_revision": exact_source_revision(),
    }
    return {**receipt_body, "receipt_sha256": sha256(receipt_body)}


def verify_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    receipt = payload.get("receipt")
    expected = str(payload.get("receipt_sha256", "")).strip().lower()
    if not isinstance(receipt, dict) or not SHA256_HEX.fullmatch(expected):
        raise ValueError("receipt object and 64-character receipt_sha256 are required")
    observed = sha256(receipt)
    return {
        "schema": "szl.receipt-verification.v1",
        "valid": observed == expected,
        "expected_sha256": expected,
        "observed_sha256": observed,
        "scope": "CANONICAL_JSON_INTEGRITY_ONLY",
        "does_not_prove": ["truth", "safety", "performance", "compliance", "authorization"],
        "verified_at": utc_now(),
    }


def build_info() -> dict[str, Any]:
    return {
        "schema": "szl.vertical-frontier-build.v1",
        "surface": "SZL Vertical Frontier",
        "source_repository": "szl-holdings/vertical-services",
        "source_revision": exact_source_revision(),
        "registry_sha256": sha256(REGISTRY),
        "python": platform.python_version(),
        "vertical_count": len(VERTICALS),
        "model_may_authorize": False,
        "kernel_may_authorize": False,
        "public_effectors_enabled": False,
    }


def sanitize_error(exc: Exception) -> tuple[int, str, str]:
    if isinstance(exc, ValueError):
        return HTTPStatus.BAD_REQUEST, "INVALID_REQUEST", str(exc)
    if isinstance(exc, RuntimeError):
        return HTTPStatus.SERVICE_UNAVAILABLE, "CONFIGURATION_REQUIRED", str(exc)
    if isinstance(exc, HTTPError):
        return HTTPStatus.BAD_GATEWAY, "UPSTREAM_HTTP_ERROR", f"official source returned HTTP {exc.code}"
    if isinstance(exc, URLError):
        return HTTPStatus.BAD_GATEWAY, "UPSTREAM_UNAVAILABLE", "official source is unavailable"
    return HTTPStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "request could not be completed"


class Handler(BaseHTTPRequestHandler):
    server_version = "SZLVerticalFrontier/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def do_HEAD(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in STATIC_FILES or path.startswith("/v/"):
            self._send_bytes(HTTPStatus.OK, b"", "text/html; charset=utf-8", head_only=True)
            return
        if path.startswith("/api/") or path == "/healthz":
            self._send_bytes(HTTPStatus.OK, b"", "application/json; charset=utf-8", head_only=True)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "NOT_FOUND"})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query, keep_blank_values=False)
        try:
            if path == "/healthz":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "state": "RUNNING",
                        "uptime_seconds": round(time.monotonic() - STARTED_AT, 3),
                        "build": build_info(),
                    },
                )
                return
            if path == "/api/build-info":
                self._send_json(HTTPStatus.OK, build_info())
                return
            if path == "/api/fashion":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "schema": "szl.fashion-lineage/v1",
                        "rule": REGISTRY.get("fashion_rule"),
                        "truth": "REPORTED",
                        "lanes": [
                            {"id": row["slug"], **row.get("fashion", {})}
                            for row in REGISTRY["verticals"]
                        ],
                    },
                )
                return
            if path == "/api/v1/verticals":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "schema": REGISTRY["schema"],
                        "authority": REGISTRY["authority"],
                        "shared_edge": REGISTRY["shared_edge"],
                        "verticals": REGISTRY["verticals"],
                        "registry_sha256": sha256(REGISTRY),
                    },
                )
                return
            match = re.fullmatch(r"/api/v1/verticals/([a-z0-9-]+)(?:/(snapshot|route))?", path)
            if match:
                slug, operation = match.groups()
                if slug not in VERTICALS:
                    self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "UNKNOWN_VERTICAL"})
                    return
                if operation == "snapshot":
                    snapshotter = SNAPSHOTTERS[slug]
                    self._send_json(HTTPStatus.OK, snapshotter(query).as_dict())
                    return
                if operation == "route":
                    objective = (query.get("objective") or ["inspect the current evidence boundary"])[0][:2000]
                    self._send_json(HTTPStatus.OK, model_route(VERTICALS[slug], objective))
                    return
                self._send_json(HTTPStatus.OK, VERTICALS[slug])
                return
            if path in STATIC_FILES:
                self._serve_static(STATIC_FILES[path])
                return
            if re.fullmatch(r"/v/[a-z0-9-]+", path):
                slug = path.rsplit("/", 1)[-1]
                if slug not in VERTICALS:
                    self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "UNKNOWN_VERTICAL"})
                    return
                self._serve_static("index.html")
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "NOT_FOUND"})
        except Exception as exc:  # fail closed and avoid leaking stack details
            status, code, message = sanitize_error(exc)
            self._send_json(status, {"ok": False, "error": code, "message": message})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            payload = self._read_json()
            if path == "/api/v1/decision":
                self._send_json(HTTPStatus.OK, evaluate_proposal(payload))
                return
            if path == "/api/v1/verify":
                self._send_json(HTTPStatus.OK, verify_receipt(payload))
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "NOT_FOUND"})
        except Exception as exc:
            status, code, message = sanitize_error(exc)
            self._send_json(status, {"ok": False, "error": code, "message": message})

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("valid Content-Length is required") from exc
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("request body is empty or exceeds 128 KiB")
        content_type = self.headers.get("Content-Type", "")
        if "application/json" not in content_type.lower():
            raise ValueError("Content-Type must be application/json")
        raw = self.rfile.read(length)
        document = json.loads(raw.decode("utf-8"))
        if not isinstance(document, dict):
            raise ValueError("request body must be a JSON object")
        return document

    def _serve_static(self, name: str) -> None:
        if name not in set(STATIC_FILES.values()):
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "NOT_FOUND"})
            return
        path = (STATIC_ROOT / name).resolve()
        if path.parent != STATIC_ROOT.resolve() or not path.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "STATIC_NOT_FOUND"})
            return
        self._send_bytes(HTTPStatus.OK, path.read_bytes(), CONTENT_TYPES.get(path.suffix, "application/octet-stream"))

    def _security_headers(self, *, content_type: str) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cache-Control", "no-store" if "json" in content_type else "public, max-age=300")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: https://huggingface.co; "
            "style-src 'self'; script-src 'self'; connect-src 'self'; "
            "font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_bytes(self, status: int, body: bytes, content_type: str, *, head_only: bool = False) -> None:
        self.send_response(status)
        self._security_headers(content_type=content_type)
        self.send_header("Content-Length", "0" if head_only else str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)


def serve(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(
        f"SZL Vertical Frontier listening on http://{host}:{port} · "
        f"{len(VERTICALS)} verticals · models propose · humans bind"
    )
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "7860")))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        assert len(VERTICALS) == 8
        assert build_info()["model_may_authorize"] is False
        held = evaluate_proposal({"vertical": "a11oy", "objective": "inspect evidence", "evidence": []})
        assert held["state"] == "HOLD"
        assert held["authorization"] == "NONE"
        assert held["execution_performed"] is False
        print(json.dumps({"ok": True, "verticals": sorted(VERTICALS), "registry_sha256": sha256(REGISTRY)}, indent=2))
        return 0
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
