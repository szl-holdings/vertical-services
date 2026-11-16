"""Bounded public dataset catalog metadata; no content or training admission."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping, NoReturn

from fastapi import HTTPException

from .connector_parameters import _reject_unknown
from .connector_specs import HF_DATASET_OWNER, HF_DATASET_PAGE_LIMIT

_DATASET_ID = re.compile(r"^SZLHOLDINGS/[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_REVISION = re.compile(r"^[a-fA-F0-9]{40}$")
# Keep the summary inside Hatun's existing 128KB evidence budget, including
# its enclosing receipt. A larger page fails explicitly instead of dropping rows.
_SUMMARY_BYTE_LIMIT = 120_000


def _invalid(field: str) -> NoReturn:
    raise HTTPException(502, f"Hugging Face dataset metadata has invalid {field}")


def _optional_text(value: Any, field: str, limit: int) -> str | None:
    if value is None:
        return None
    if (not isinstance(value, str) or not value or len(value) > limit
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        _invalid(field)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        _invalid(field)
    return value


def _last_modified(value: Any) -> str | None:
    value = _optional_text(value, "lastModified", 64)
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            _invalid("lastModified")
        return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    except (ValueError, OverflowError):
        _invalid("lastModified")


def _license_tags(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > 256:
        _invalid("tags")
    licenses = set()
    for tag in value:
        tag = _optional_text(tag, "tag", 512)
        if tag is None:
            _invalid("tag")
        if tag.startswith("license:"):
            license_id = _optional_text(tag[len("license:"):], "license tag", 128)
            licenses.add(license_id)
    if len(licenses) > 16:
        _invalid("license tag count")
    return sorted(licenses)


def _normalize_dataset(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        _invalid("dataset row")
    dataset_id = row.get("id")
    if not isinstance(dataset_id, str) or _DATASET_ID.fullmatch(dataset_id) is None:
        _invalid("dataset id or owner")
    revision = row.get("sha")
    if revision is not None:
        if not isinstance(revision, str) or _REVISION.fullmatch(revision) is None:
            _invalid("revision")
        revision = revision.lower()
    private = row.get("private")
    if private is not None and not isinstance(private, bool):
        _invalid("private flag")
    gated = row.get("gated")
    if gated is not None and not isinstance(gated, bool):
        # Preserve unknown provider gating states as reported text; never coerce
        # missing or unfamiliar values to False or infer access permission.
        gated = _optional_text(gated, "gated state", 64)
    return {
        "id": dataset_id,
        "revision": revision,
        "source_url": f"https://huggingface.co/datasets/{dataset_id}",
        "license_tags": _license_tags(row.get("tags")),
        "gated": gated,
        "private": private,
        "last_modified": _last_modified(row.get("lastModified")),
    }


def _parse_hf_datasets(payload: Any, parameters: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one public catalog page without asserting estate completeness."""
    _reject_unknown(parameters, set())
    if not isinstance(payload, list) or len(payload) > HF_DATASET_PAGE_LIMIT:
        _invalid("catalog page")
    unique: dict[str, dict[str, Any]] = {}
    for raw in payload:
        row = _normalize_dataset(raw)
        prior = unique.get(row["id"])
        if prior is not None and prior != row:
            _invalid("conflicting duplicate dataset")
        unique[row["id"]] = row
    at_limit = len(payload) == HF_DATASET_PAGE_LIMIT
    summary = {
        "schema": "szl.public-dataset-inventory/v1",
        "owner": HF_DATASET_OWNER,
        "coverage": "PUBLIC_CATALOG_PAGE",
        "returned_count": len(payload),
        "unique_count": len(unique),
        "duplicate_count": len(payload) - len(unique),
        "requested_limit": HF_DATASET_PAGE_LIMIT,
        "at_limit": at_limit,
        "completeness": "AT_LIMIT" if at_limit else "UNKNOWN",
        "private_estate_covered": False,
        "training_admission": "NOT_ADMITTED",
        "quality_evidence": "UNAVAILABLE",
        "items": [unique[key] for key in sorted(unique)],
    }
    encoded = json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(encoded.encode("utf-8")) > _SUMMARY_BYTE_LIMIT:
        raise HTTPException(502, "dataset inventory exceeds the bounded evidence summary budget")
    return summary
