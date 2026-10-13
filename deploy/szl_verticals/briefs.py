"""Bounded research briefs, separate from authenticated connector evidence.

All supplied facts, verification dates and implementation statuses are caller
reports. Storing or hashing them never promotes them to connector evidence.
This module performs no network requests.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from typing import Annotated, Any, Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import AwareDatetime, Field, field_validator, model_validator

from .core import StrictModel

MAX_BRIEF_BYTES = 64_000
MAX_BRIEFS_PER_SCOPE = 104
BRIEF_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_briefs (
    vertical TEXT NOT NULL,
    session_scope TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    created_at REAL NOT NULL,
    brief_json TEXT NOT NULL,
    PRIMARY KEY (vertical, session_scope, content_sha256)
);
CREATE INDEX IF NOT EXISTS idx_research_briefs_scope
ON research_briefs(vertical, session_scope, created_at DESC);
"""
ShortText = Annotated[str, Field(min_length=1, max_length=240)]
SourceId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,47}$")]
Narrative = Annotated[str, Field(min_length=1, max_length=2400)]


class BriefSource(StrictModel):
    id: SourceId
    title: ShortText
    url: str = Field(min_length=10, max_length=2048)
    published_on: date
    event_on: date | None = None
    data_period_start: date | None = None
    data_period_end: date | None = None
    access_note: str = Field(default="", max_length=240)
    verified_at: AwareDatetime
    verification_method: ShortText

    @field_validator("url")
    @classmethod
    def public_reference(cls, value: str) -> str:
        if any(char.isspace() or ord(char) < 32 for char in value):
            raise ValueError("source URL must not contain whitespace")
        try:
            parts = urlsplit(value)
            if (parts.scheme != "https" or not parts.hostname or parts.username
                    or parts.password or parts.port not in (None, 443)):
                raise ValueError("source URL must be HTTPS without credentials")
            credential_names = {"token", "access_token", "api_key", "apikey", "key", "sig", "signature"}
            if any(key.lower() in credential_names for key, _ in parse_qsl(parts.query)):
                raise ValueError("source URL must not contain credential parameters")
        except ValueError:
            raise ValueError("source URL must be a valid HTTPS reference without credentials") from None
        return value

    @model_validator(mode="after")
    def chronology(self) -> "BriefSource":
        if self.verified_at.date() < self.published_on:
            raise ValueError("verification must not precede publication")
        if self.verified_at > datetime.now(timezone.utc):
            raise ValueError("verification must not be in the future")
        if (self.data_period_start is None) != (self.data_period_end is None):
            raise ValueError("data period requires both start and end")
        if self.data_period_start is not None and self.data_period_end < self.data_period_start:
            raise ValueError("data period end must not precede start")
        return self


class BriefDevelopment(StrictModel):
    source_fact: Narrative
    source_ids: list[SourceId] = Field(min_length=1, max_length=12)
    product_inference: Narrative
    confidence: Literal["WELL_SUPPORTED", "PRELIMINARY", "UNCERTAIN"]


class BriefOpportunity(StrictModel):
    title: ShortText
    proposal: Narrative
    source_ids: list[SourceId] = Field(min_length=1, max_length=12)
    acceptance_criteria: list[ShortText] = Field(min_length=1, max_length=8)
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    feasibility: Literal["HIGH", "MEDIUM", "LOW"]
    dependencies: list[ShortText] = Field(default_factory=list, max_length=8)
    status: Literal["PROPOSED", "PLANNED", "IN_PROGRESS", "IMPLEMENTED_REPORTED", "BLOCKED"] = "PROPOSED"


class WeeklyBriefRequest(StrictModel):
    week_start: date
    title: ShortText
    coverage_state: Literal["DEVELOPMENTS", "NO_MATERIAL_CHANGE"] = "DEVELOPMENTS"
    coverage_note: ShortText | None = None
    sources: list[BriefSource] = Field(default_factory=list, max_length=12)
    developments: list[BriefDevelopment] = Field(default_factory=list, max_length=16)
    opportunities: list[BriefOpportunity] = Field(default_factory=list, max_length=16)

    @field_validator("week_start")
    @classmethod
    def monday(cls, value: date) -> date:
        if value.weekday() != 0:
            raise ValueError("week_start must be a Monday")
        if value > datetime.now(timezone.utc).date():
            raise ValueError("week_start must not be in the future")
        return value

    @model_validator(mode="after")
    def source_links(self) -> "WeeklyBriefRequest":
        if self.coverage_state == "NO_MATERIAL_CHANGE":
            if not self.coverage_note or not self.coverage_note.strip():
                raise ValueError("no-material-change coverage requires a nonempty coverage note")
            if self.developments or self.opportunities:
                raise ValueError("no-material-change coverage must not contain findings or opportunities")
        elif not self.sources or not self.developments or not self.opportunities:
            raise ValueError("developments coverage requires sources, developments and opportunities")
        identifiers = [source.id for source in self.sources]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("source IDs must be unique")
        known = set(identifiers)
        for item in [*self.developments, *self.opportunities]:
            if len(set(item.source_ids)) != len(item.source_ids) or not set(item.source_ids) <= known:
                raise ValueError("source references must be distinct declared source IDs")
        return self


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def brief_record(row: sqlite3.Row, *, inserted: bool | None = None) -> dict[str, Any]:
    record = {
        "schema": "szl.weekly-brief/v1",
        "vertical": row["vertical"],
        "content_sha256": row["content_sha256"],
        "created_at": row["created_at"],
        "brief": json.loads(row["brief_json"]),
        "truth_label": "CALLER_REPORTED",
        "review_status": "REVIEW_REQUIRED",
        "verification_claims": "CALLER_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
        "implementation_status_claims": "CALLER_REPORTED_NOT_DEPLOYMENT_EVIDENCE",
        "counts_as_connector_evidence": False,
        "effectors_enabled": False,
        "human_approval_required": True,
        "receipt": {"algorithm": "SHA-256", "signature_claimed": False,
                    "scope": "CONTENT_INTEGRITY_ONLY"},
    }
    if inserted is not None:
        record["inserted"] = inserted
    return record


class BriefStoreMixin:
    """Use the existing store connection and lock without changing admission."""

    def put_brief(self, vertical: str, session_scope: str, request: WeeklyBriefRequest) -> dict[str, Any]:
        if self.error:
            raise RuntimeError("brief store unavailable")
        body = request.model_dump(mode="json")
        serialized = _canonical(body)
        if len(serialized.encode("utf-8")) > MAX_BRIEF_BYTES:
            raise ValueError("brief exceeds 64000 UTF-8 bytes")
        digest = hashlib.sha256(_canonical({"vertical": vertical, "brief": body}).encode("utf-8")).hexdigest()
        with self._lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM research_briefs WHERE vertical=? AND session_scope=? AND content_sha256=?",
                (vertical, session_scope, digest),
            ).fetchone()
            if row is not None:
                return brief_record(row, inserted=False)
            count = connection.execute(
                "SELECT count(*) FROM research_briefs WHERE vertical=? AND session_scope=?",
                (vertical, session_scope),
            ).fetchone()[0]
            if count >= MAX_BRIEFS_PER_SCOPE:
                raise ValueError("brief scope capacity reached")
            connection.execute(
                "INSERT INTO research_briefs VALUES (?, ?, ?, ?, ?)",
                (vertical, session_scope, digest, self._clock(), serialized),
            )
            row = connection.execute(
                "SELECT * FROM research_briefs WHERE vertical=? AND session_scope=? AND content_sha256=?",
                (vertical, session_scope, digest),
            ).fetchone()
            connection.commit()
        return brief_record(row, inserted=True)

    def recent_briefs(self, vertical: str, session_scope: str, limit: int = 10) -> list[dict[str, Any]]:
        if self.error:
            raise RuntimeError("brief store unavailable")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 25:
            raise ValueError("brief limit must be between 1 and 25")
        with self._lock, closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM research_briefs WHERE vertical=? AND session_scope=? ORDER BY created_at DESC, content_sha256 LIMIT ?",
                (vertical, session_scope, limit),
            ).fetchall()
        return [brief_record(row) for row in rows]
