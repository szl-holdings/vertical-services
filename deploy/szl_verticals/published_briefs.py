"""Read-only research published in the application artifact, never evidence."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from .briefs import MAX_BRIEF_BYTES, BriefSource, Narrative, ShortText, WeeklyBriefRequest, _canonical
from .contract import VERTICALS, canonical_vertical
from .core import SOURCE_REPOSITORY, StrictModel, runtime_source_identity

ARCHIVE_DIRECTORY = Path(__file__).resolve().parent / "research_data"
ARCHIVE_REPOSITORY_PATH = "deploy/szl_verticals/research_data"
MAX_ARCHIVE_FILES = 104
MAX_ARCHIVE_FILE_BYTES = 512_000
MAX_ARCHIVE_TOTAL_BYTES = 8_000_000
ISSUE_FILENAME = re.compile(r"\d{4}-\d{2}-\d{2}\.json\Z")
CLAIMS = {
    "truth_label": "CALLER_REPORTED",
    "review_status": "REVIEW_REQUIRED",
    "verification_claims": "CALLER_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
    "implementation_status_claims": "CALLER_REPORTED_NOT_DEPLOYMENT_EVIDENCE",
    "counts_as_connector_evidence": False,
    "effectors_enabled": False,
    "human_approval_required": True,
}


class ArchiveUnavailable(RuntimeError):
    """Missing or invalid packaged data; callers must not claim an empty week."""


class ResearchWindow(StrictModel):
    start: date
    end: date

    @model_validator(mode="after")
    def chronology(self) -> "ResearchWindow":
        if self.end < self.start or self.end > datetime.now(timezone.utc).date():
            raise ValueError("invalid research window")
        return self


class AdditionalCoverage(StrictModel):
    area: ShortText
    state: ShortText
    note: Narrative
    source: str | None = Field(default=None, max_length=2048)

    @field_validator("source")
    @classmethod
    def public_reference(cls, value: str | None) -> str | None:
        return BriefSource.public_reference(value) if value is not None else None


class ResearchBundle(StrictModel):
    schema_version: Literal["szl.weekly-research-bundle/v1"] = Field(alias="schema")
    research_window: ResearchWindow
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    notice: Narrative
    briefs: dict[str, WeeklyBriefRequest] = Field(min_length=1, max_length=6)
    additional_coverage: list[AdditionalCoverage] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def canonical_coverage(self) -> "ResearchBundle":
        if set(self.briefs) != set(VERTICALS):
            raise ValueError("published bundles must cover every canonical vertical")
        for brief in self.briefs.values():
            if brief.week_start > self.research_window.end:
                raise ValueError("brief week must not follow research window")
            if len(_canonical(brief.model_dump(mode="json")).encode("utf-8")) > MAX_BRIEF_BYTES:
                raise ValueError("brief exceeds byte limit")
        return self


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _archive() -> list[tuple[str, str, ResearchBundle]]:
    """Read a fixed, bounded package directory without network or store access."""
    try:
        paths = []
        for path in ARCHIVE_DIRECTORY.iterdir():
            if not ISSUE_FILENAME.fullmatch(path.name) or path.is_symlink() or not path.is_file():
                raise ValueError("invalid archive entry")
            paths.append(path)
            if len(paths) > MAX_ARCHIVE_FILES:
                raise ValueError("archive file capacity exceeded")
        if not paths:
            raise ValueError("archive is empty")
        records = []
        total_bytes = 0
        for path in sorted(paths, reverse=True):
            with path.open("rb") as source:
                raw = source.read(MAX_ARCHIVE_FILE_BYTES + 1)
            total_bytes += len(raw)
            if len(raw) > MAX_ARCHIVE_FILE_BYTES or total_bytes > MAX_ARCHIVE_TOTAL_BYTES:
                raise ValueError("archive byte capacity exceeded")
            bundle = ResearchBundle.model_validate(json.loads(raw, object_pairs_hook=_unique_object))
            if path.stem != bundle.research_window.end.isoformat():
                raise ValueError("issue filename must match research window end")
            records.append((path.name, hashlib.sha256(raw).hexdigest(), bundle))
        return records
    except (OSError, UnicodeError, ValueError, ValidationError, RecursionError):
        raise ArchiveUnavailable("published brief archive unavailable") from None


def published_briefs(vertical: str, limit: int = 10, *, summary: bool = False) -> dict[str, Any]:
    canonical = canonical_vertical(vertical)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 25:
        raise ValueError("published brief limit must be between 1 and 25")
    identity = runtime_source_identity()
    revision = identity["runtime_source_revision"]
    items = []
    for filename, artifact_digest, bundle in _archive()[:limit]:
        body = bundle.briefs[canonical].model_dump(mode="json")
        path = f"{ARCHIVE_REPOSITORY_PATH}/{filename}"
        item = {
            "issue_date": bundle.research_window.end.isoformat(),
            "vertical": canonical,
            "research_window": bundle.research_window.model_dump(mode="json"),
            "research_source_revision": bundle.source_revision,
            "runtime_source_revision": revision,
            "source_repository": SOURCE_REPOSITORY,
            "source_path": path,
            "source_url": (f"https://github.com/{SOURCE_REPOSITORY}/blob/{revision}/{path}"
                           if revision != "UNAVAILABLE" else None),
            "artifact_sha256": artifact_digest,
            "content_sha256": hashlib.sha256(
                _canonical({"vertical": canonical, "brief": body}).encode("utf-8")
            ).hexdigest(),
            "receipt": {"algorithm": "SHA-256", "signature_claimed": False,
                        "scope": "CONTENT_INTEGRITY_ONLY"},
            **CLAIMS,
        }
        if summary:
            item.update({key: body[key] for key in ("title", "week_start", "coverage_state")})
        else:
            item.update(brief=body, notice=bundle.notice,
                        additional_coverage=[entry.model_dump(mode="json") for entry in bundle.additional_coverage])
        items.append(item)
    return {
        "schema": "szl.published-brief-list/v1",
        "vertical": canonical,
        "scope": "SOURCE_CONTROLLED_PUBLIC_ARCHIVE",
        "status": "AVAILABLE",
        "runtime_source_revision": revision,
        "items": items,
        **CLAIMS,
    }


def published_brief_summary(vertical: str, limit: int = 10) -> dict[str, Any]:
    try:
        return published_briefs(vertical, limit, summary=True)
    except ArchiveUnavailable:
        return {
            "schema": "szl.published-brief-list/v1", "vertical": canonical_vertical(vertical),
            "scope": "SOURCE_CONTROLLED_PUBLIC_ARCHIVE", "status": "UNAVAILABLE",
            "error_code": "PUBLISHED_BRIEFS_UNAVAILABLE", "items": [], **CLAIMS,
        }
