"""Direct evidence dependencies in the existing observation database.

These are session-scoped historical assessments, not durable matters or a
complete decision graph. Invalidation is monotonic; CURRENT means only that
the recorded evidence basis still matches at the time of this read.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from contextlib import closing
from typing import Any

REPLAY_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_withdrawals (
    vertical TEXT NOT NULL, session_scope TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL, withdrawn_at REAL NOT NULL,
    PRIMARY KEY (vertical, session_scope, payload_sha256)
);
CREATE TABLE IF NOT EXISTS evidence_assessments (
    vertical TEXT NOT NULL, session_scope TEXT NOT NULL,
    assessment_id TEXT NOT NULL, kind TEXT NOT NULL,
    snapshot_sha256 TEXT NOT NULL, dependencies_json TEXT NOT NULL,
    assessed_at REAL NOT NULL, last_checked_at REAL NOT NULL,
    invalidated INTEGER NOT NULL DEFAULT 0, reasons_json TEXT NOT NULL,
    PRIMARY KEY (vertical, session_scope, assessment_id)
);
"""
MAX_ASSESSMENTS_PER_SCOPE = 10_000

def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)

class EvidenceNotFound(LookupError):
    """Requested evidence is absent from, or foreign to, the caller's session scope."""

def _valid_clock_value(now: Any) -> bool:
    return type(now) in (int, float) and math.isfinite(now) and now >= 0

def _validate_scope(vertical: str, session_scope: str, now: Any) -> None:
    if (not isinstance(vertical, str) or not 1 <= len(vertical) <= 64
            or not isinstance(session_scope, str) or not 1 <= len(session_scope) <= 256
            or not (callable(now) or _valid_clock_value(now))):
        raise ValueError("invalid assessment scope or clock")

def _sample_clock(now: Any) -> float:
    """Read the clock inside the write transaction.

    Callers pass a zero-argument clock such as ``time.time`` so the value is
    taken after the process lock and BEGIN IMMEDIATE. A value read before the
    lock can be older than a concurrent reader's ``last_checked_at`` and would
    permanently latch ASSESSMENT_CLOCK_REGRESSED on unchanged evidence. A plain
    number is still accepted for fixed or replayed clocks. A clock that fails
    makes the store unavailable; it is never a server error.
    """
    try:
        value = now() if callable(now) else now
    except Exception as exc:
        raise RuntimeError("assessment clock unavailable") from exc
    if not _valid_clock_value(value):
        raise RuntimeError("assessment clock unavailable")
    return value

class StoredAssessmentInvalid(RuntimeError):
    """A stored assessment row is malformed, so replay is unavailable for it."""

_DEPENDENCY_KEYS = frozenset(("payload_sha256", "receipt_id", "summary_sha256", "observed_at", "expires_at"))

def _stored_json(text: Any) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_unique_object)
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise StoredAssessmentInvalid("malformed stored assessment") from exc

def _stored_dependencies(text: Any) -> list[dict[str, Any]]:
    """Parse and shape-check stored dependencies; a malformed row is unavailable, not a crash."""
    dependencies = _stored_json(text)
    if not isinstance(dependencies, list) or not dependencies:
        raise StoredAssessmentInvalid("malformed stored assessment")
    for dep in dependencies:
        if (not isinstance(dep, dict) or set(dep) != _DEPENDENCY_KEYS
                or any(not isinstance(dep[key], str) or re.fullmatch(r"[0-9a-f]{64}", dep[key]) is None
                       for key in ("payload_sha256", "receipt_id", "summary_sha256"))
                or not _valid_clock_value(dep["observed_at"]) or not _valid_clock_value(dep["expires_at"])):
            raise StoredAssessmentInvalid("malformed stored assessment")
    return dependencies

def _stored_reasons(text: Any) -> list[dict[str, Any]]:
    reasons = _stored_json(text)
    if not isinstance(reasons, list) or any(not isinstance(item, dict) for item in reasons):
        raise StoredAssessmentInvalid("malformed stored assessment")
    return reasons

def _digest(value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("invalid digest")

def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate member")
        result[key] = value
    return result

class ReplayStoreMixin:
    """Uses ObservationStore's connection and process lock; no second ledger."""

    def _invalidate_changed_payload(self, connection, vertical, session_scope, digest):
        rows = connection.execute(
            """SELECT assessment_id, dependencies_json FROM evidence_assessments
            WHERE vertical=? AND session_scope=? AND invalidated=0
              AND instr(dependencies_json, ?) > 0""",
            (vertical, session_scope, '"payload_sha256":"' + digest + '"'),
        ).fetchall()
        for row in rows:
            dependencies = [d for d in _stored_dependencies(row["dependencies_json"])
                            if d["payload_sha256"] == digest]
            if not dependencies:
                raise StoredAssessmentInvalid("malformed stored assessment")
            changes = self._dependency_changes(connection, vertical, session_scope,
                                               dependencies, dependencies[0]["observed_at"])
            if changes:
                connection.execute(
                    """UPDATE evidence_assessments SET invalidated=1, reasons_json=?
                    WHERE vertical=? AND session_scope=? AND assessment_id=? AND invalidated=0""",
                    (_json(changes), vertical, session_scope, row["assessment_id"]),
                )

    @staticmethod
    def _dependency_changes(connection, vertical, session_scope, dependencies, now):
        changes = []
        for dep in dependencies:
            digest = dep["payload_sha256"]
            reason = None
            withdrawn = connection.execute(
                "SELECT 1 FROM evidence_withdrawals WHERE vertical=? AND session_scope=? AND payload_sha256=?",
                (vertical, session_scope, digest),
            ).fetchone()
            row = connection.execute(
                """SELECT * FROM connector_observations
                WHERE vertical=? AND session_scope=? AND payload_sha256=?
                ORDER BY observed_at DESC, receipt_id ASC LIMIT 1""",
                (vertical, session_scope, digest),
            ).fetchone()
            if withdrawn:
                reason = "EVIDENCE_WITHDRAWN"
            elif row is None:
                reason = "EVIDENCE_MISSING"
            elif not dep["observed_at"] <= now < dep["expires_at"]:
                reason = "EVIDENCE_NOT_FRESH"
            elif row["receipt_id"] != dep["receipt_id"]:
                reason = "EVIDENCE_RECORD_CHANGED"
            elif row["state"] != "OBSERVED":
                reason = "EVIDENCE_NOT_OBSERVED"
            else:
                try:
                    receipt_basis = {"schema": "szl.connector-observation/v2", **{
                        key: row[key] for key in (
                            "vertical", "connector_id", "session_scope", "query_hash", "source_url",
                            "http_status", "payload_sha256", "observed_at", "expires_at", "state", "truth_label")}}
                    if hashlib.sha256(_json(receipt_basis).encode("utf-8")).hexdigest() != row["receipt_id"]:
                        raise ValueError("invalid receipt")
                    summary = json.loads(row["summary_json"], object_pairs_hook=_unique_object)
                    if hashlib.sha256(_json(summary).encode("utf-8")).hexdigest() != dep["summary_sha256"]:
                        reason = "EVIDENCE_SUMMARY_CHANGED"
                    elif (row["observed_at"] != dep["observed_at"] or row["expires_at"] != dep["expires_at"]):
                        reason = "EVIDENCE_RECORD_CHANGED"
                except (TypeError, ValueError, UnicodeError, RecursionError):
                    reason = "EVIDENCE_RECORD_INVALID"
            if reason:
                changes.append({"payload_sha256": digest, "reason": reason})
        return changes

    @staticmethod
    def _assessment_result(row, changes, now):
        return {
            "schema": "szl.evidence-replay-status/v1",
            "assessment_id": row["assessment_id"], "kind": row["kind"],
            "original_decision": "REVIEW" if row["kind"] == "hatun-review" else "READY_FOR_INFERENCE",
            "original_snapshot_sha256": row["snapshot_sha256"],
            "state": "REVALIDATION_REQUIRED" if changes else "CURRENT",
            "changed_dependencies": changes, "checked_at": now,
            "basis_scope": "DIRECT_RECORDED_CONNECTOR_EVIDENCE_ONLY",
            "source_authority_verified": False, "can_execute": False,
            "automatic_replay": False,
        }

    def register_assessment(self, *, vertical, session_scope, assessment_id, kind, snapshot, now):
        _validate_scope(vertical, session_scope, now)
        _digest(assessment_id)
        if (kind not in {"intelligence-plan", "hatun-review"}
                or not snapshot.matches_scope(vertical, session_scope, snapshot.requested_digests)
                or snapshot.state != "COMPLETE" or not snapshot.requested_digests):
            raise ValueError("only resolved scoped assessments can be registered")
        deps = [{key: record[key] for key in (
            "payload_sha256", "receipt_id", "summary_sha256", "observed_at", "expires_at")}
            for record in json.loads(snapshot.records_json)]
        if self.error:
            raise RuntimeError("assessment store unavailable")
        try:
            with self._lock, closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                now = _sample_clock(now)
                existing = connection.execute(
                    "SELECT * FROM evidence_assessments WHERE vertical=? AND session_scope=? AND assessment_id=?",
                    (vertical, session_scope, assessment_id),
                ).fetchone()
                if existing:
                    if existing["snapshot_sha256"] != snapshot.snapshot_sha256 or existing["kind"] != kind:
                        raise RuntimeError("assessment identity conflict")
                else:
                    count = connection.execute(
                        "SELECT COUNT(*) FROM evidence_assessments WHERE vertical=? AND session_scope=?",
                        (vertical, session_scope),
                    ).fetchone()[0]
                    if count >= MAX_ASSESSMENTS_PER_SCOPE:
                        raise RuntimeError("assessment capacity reached")
                    connection.execute(
                        "INSERT INTO evidence_assessments VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, '[]')",
                        (vertical, session_scope, assessment_id, kind,
                         snapshot.snapshot_sha256, _json(deps), now, now),
                    )
                result = self._check_assessment(connection, vertical, session_scope, assessment_id, now)
                connection.commit()
                return result
        except (OSError, sqlite3.Error) as exc:
            raise RuntimeError("assessment store unavailable") from exc

    def _check_assessment(self, connection, vertical, session_scope, assessment_id, now, connectors=None):
        row = connection.execute(
            "SELECT * FROM evidence_assessments WHERE vertical=? AND session_scope=? AND assessment_id=?",
            (vertical, session_scope, assessment_id),
        ).fetchone()
        if row is None:
            return None
        changes = _stored_reasons(row["reasons_json"])
        if not row["invalidated"]:
            changes = self._dependency_changes(connection, vertical, session_scope,
                                               _stored_dependencies(row["dependencies_json"]), now)
            if now < row["last_checked_at"]:
                changes.append({"payload_sha256": None, "reason": "ASSESSMENT_CLOCK_REGRESSED"})
            if not changes and connectors is not None:
                from .evidence import resolve_evidence
                dependencies = _stored_dependencies(row["dependencies_json"])
                current = resolve_evidence(
                    self, vertical=vertical, session_scope=session_scope,
                    digests=[dep["payload_sha256"] for dep in dependencies],
                    connectors=connectors, now=now)
                if current.state == "UNAVAILABLE":
                    raise RuntimeError("assessment evidence unavailable")
                if current.snapshot_sha256 != row["snapshot_sha256"]:
                    changes.append({"payload_sha256": None, "reason": "EVIDENCE_ADMISSION_CHANGED"})
        connection.execute(
            """UPDATE evidence_assessments SET invalidated=?, reasons_json=?, last_checked_at=?
            WHERE vertical=? AND session_scope=? AND assessment_id=?""",
            (int(bool(changes)), _json(changes), max(now, row["last_checked_at"]),
             vertical, session_scope, assessment_id),
        )
        return self._assessment_result(row, changes, now)

    def assessment_status(self, *, vertical, session_scope, assessment_id, now, connectors):
        _validate_scope(vertical, session_scope, now)
        _digest(assessment_id)
        if self.error:
            raise RuntimeError("assessment store unavailable")
        try:
            with self._lock, closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                now = _sample_clock(now)
                result = self._check_assessment(connection, vertical, session_scope, assessment_id, now, connectors)
                connection.commit()
                return result
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError) as exc:
            raise RuntimeError("assessment store unavailable") from exc

    def withdraw_payloads(self, *, vertical, session_scope, payload_digests, now):
        _validate_scope(vertical, session_scope, now)
        if not isinstance(payload_digests, (list, tuple)) or not 1 <= len(payload_digests) <= 64:
            raise ValueError("withdrawal requires 1 to 64 digests")
        for digest in payload_digests:
            _digest(digest)
        if self.error:
            raise RuntimeError("assessment store unavailable")
        try:
            with self._lock, closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                now = _sample_clock(now)
                for digest in sorted(set(payload_digests)):
                    if connection.execute(
                        "SELECT 1 FROM connector_observations WHERE vertical=? AND session_scope=? AND payload_sha256=? LIMIT 1",
                        (vertical, session_scope, digest),
                    ).fetchone() is None:
                        raise EvidenceNotFound("evidence not found in this session")
                for digest in sorted(set(payload_digests)):
                    connection.execute(
                        "INSERT OR IGNORE INTO evidence_withdrawals VALUES (?, ?, ?, ?)",
                        (vertical, session_scope, digest, now),
                    )
                    self._invalidate_changed_payload(connection, vertical, session_scope, digest)
                connection.commit()
                return {"state": "WITHDRAWN", "distinct_payloads": len(set(payload_digests)),
                        "scope": "CALLER_SESSION_AND_CANONICAL_VERTICAL",
                        "source_retracted_globally": False, "automatic_replay": False}
        except (OSError, sqlite3.Error) as exc:
            raise RuntimeError("assessment store unavailable") from exc
