"""Session-scoped connector evidence resolution, not legal/source authentication.

The ledger records a connector's normalized observation. A raw payload hash is
not a passage, a signature, or proof that a model consumed that payload. This
module binds the actual normalized input into an immutable local snapshot.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlsplit

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_EVIDENCE_BYTES = 128_000
MAX_SUMMARY_BYTES = 128_000


class EvidenceStore(Protocol):
    def resolve_payloads(
        self, *, vertical: str, session_scope: str, payload_digests: Sequence[str],
        max_summary_bytes: int,
    ) -> list[dict[str, Any]]: ...


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _scope(vertical: str, session_scope: str) -> str:
    return sha256(canonical_json(["szl.evidence-scope/v1", vertical, session_scope]))


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object member")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("non-finite JSON constant")


def _finite_number(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


@dataclass(frozen=True)
class EvidenceSnapshot:
    """Only immutable serialized bytes are retained; no live DB row alias."""

    vertical: str
    scope_binding_sha256: str
    requested_digests: tuple[str, ...]
    records_json: str
    state: str
    blockers: tuple[str, ...]

    @property
    def snapshot_sha256(self) -> str:
        return sha256(canonical_json({
            "schema": "szl.connector-evidence-snapshot/v1",
            "vertical": self.vertical,
            "scope_binding_sha256": self.scope_binding_sha256,
            "requested_digests": self.requested_digests,
            "records": json.loads(self.records_json),
            "state": self.state,
            "blockers": self.blockers,
        }))

    def matches_scope(self, vertical: str, session_scope: str, digests: Sequence[str]) -> bool:
        return (self.vertical == vertical
                and self.scope_binding_sha256 == _scope(vertical, session_scope)
                and self.requested_digests == tuple(sorted(set(digests))))

    def fresh_at(self, now: float) -> bool:
        if self.state != "COMPLETE" or not _finite_number(now):
            return False
        records = json.loads(self.records_json)
        return bool(records) and all(row["observed_at"] <= now < row["expires_at"]
                                     for row in records)

    def metadata(self) -> dict[str, Any]:
        records = json.loads(self.records_json)
        resolved = {row["payload_sha256"] for row in records}
        return {
            "schema": "szl.connector-evidence-resolution/v1",
            "state": self.state,
            "requested_count": len(self.requested_digests),
            "resolved_count": None if self.state == "UNAVAILABLE" else len(resolved),
            "unresolved_digests": sorted(set(self.requested_digests) - resolved),
            "snapshot_sha256": self.snapshot_sha256,
            "records": [{key: value for key, value in row.items() if key != "summary"}
                        for row in records],
            "blockers": list(self.blockers),
            "count_unit": "DISTINCT_REQUESTED_CONNECTOR_PAYLOAD",
            "independent_authorities": "NOT_ESTABLISHED",
            "payload_bytes_reverified": False,
            "historical_parser_revision": "NOT_STORED",
            "source_signature_verified": False,
            "semantic_validity": "NOT_VERIFIED",
            "raw_summary_returned": False,
        }


def resolve_evidence(
    store: EvidenceStore, *, vertical: str, session_scope: str,
    digests: Sequence[str], connectors: Mapping[str, Any],
    now: float | None = None, budget_bytes: int = MAX_EVIDENCE_BYTES,
) -> EvidenceSnapshot:
    """Resolve only exact requested records in one bounded ledger snapshot.

    A missing, wrong-scope, future, expired, or invalid reference has the same
    public unresolved result. No lookup in another tenant or vertical occurs.
    Repeated observations of one payload never count as independent evidence.
    """
    if (isinstance(digests, (str, bytes)) or len(digests) > 64
            or any(not isinstance(item, str) or HEX64.fullmatch(item) is None for item in digests)):
        raise ValueError("evidence references must be at most 64 exact SHA-256 digests")
    if not isinstance(session_scope, str) or not session_scope or not isinstance(vertical, str) or not vertical:
        raise ValueError("an explicit vertical and session scope are required")
    if type(budget_bytes) is not int or not 1 <= budget_bytes <= MAX_EVIDENCE_BYTES:
        raise ValueError("invalid evidence byte budget")
    clock = time.time() if now is None else now
    if not _finite_number(clock) or clock < 0:
        raise ValueError("invalid assessment time")
    requested = tuple(sorted(set(digests)))
    scope_digest = _scope(vertical, session_scope)
    try:
        rows = store.resolve_payloads(vertical=vertical, session_scope=session_scope,
                                      payload_digests=requested,
                                      max_summary_bytes=min(budget_bytes, MAX_SUMMARY_BYTES))
    except (OSError, RuntimeError):
        return EvidenceSnapshot(vertical, scope_digest, requested, "[]", "UNAVAILABLE",
                                ("EVIDENCE_STORE_UNAVAILABLE",))
    if not isinstance(rows, list) or len(rows) > len(requested):
        return EvidenceSnapshot(vertical, scope_digest, requested, "[]", "UNAVAILABLE",
                                ("EVIDENCE_STORE_RESULT_INVALID",))
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    blockers: set[str] = set()
    for row in rows:
        try:
            payload_digest = row["payload_sha256"]
            spec = connectors.get(row["connector_id"])
            if (payload_digest not in requested or payload_digest in seen
                    or row["vertical"] != vertical or row["session_scope"] != session_scope):
                raise ValueError("unexpected or duplicate scoped row")
            seen.add(payload_digest)
            if (spec is None or spec.vertical != vertical or row["state"] != "OBSERVED"
                    or row["truth_label"] != "REPORTED" or type(row["http_status"]) is not int
                    or not 200 <= row["http_status"] < 300):
                raise ValueError("unqualified connector record")
            observed, expires = row["observed_at"], row["expires_at"]
            if (not _finite_number(observed) or not _finite_number(expires)
                    or not 0 <= observed <= clock < expires
                    or expires > observed + spec.freshness_seconds):
                raise ValueError("record is not fresh")
            if any(not isinstance(row[key], str) or HEX64.fullmatch(row[key]) is None
                   for key in ("receipt_id", "query_hash", "payload_sha256")):
                raise ValueError("invalid receipt identity")
            source_url = row["source_url"]
            if not isinstance(source_url, str) or len(source_url) > 4096:
                raise ValueError("invalid source URL")
            parsed = urlsplit(source_url)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                    or parsed.password or parsed.fragment):
                raise ValueError("invalid recorded source origin")
            receipt_basis = {"schema": "szl.connector-observation/v2", **{
                key: row[key] for key in (
                    "vertical", "connector_id", "session_scope", "query_hash", "source_url",
                    "http_status", "payload_sha256", "observed_at", "expires_at", "state", "truth_label")}}
            if sha256(canonical_json(receipt_basis)) != row["receipt_id"]:
                raise ValueError("stored receipt basis does not match its identifier")
            serialized = row["summary_json"]
            if (not isinstance(serialized, str)
                    or len(serialized.encode("utf-8")) > min(budget_bytes, MAX_SUMMARY_BYTES)):
                raise ValueError("summary is unavailable or exceeds byte budget")
            summary = json.loads(serialized, object_pairs_hook=_unique_object,
                                 parse_constant=_reject_constant)
            if not isinstance(summary, dict):
                raise ValueError("normalized connector summary must be an object")
            normalized = canonical_json(summary)
            record = {
                "receipt_id": row["receipt_id"], "connector_id": row["connector_id"],
                "payload_sha256": payload_digest, "summary_sha256": sha256(normalized),
                "observed_at": observed, "expires_at": expires,
                "source_url_sha256": sha256(source_url), "source_origin": parsed.hostname,
                "http_status": row["http_status"], "truth_label": row["truth_label"],
                "state": row["state"], "summary": summary,
            }
            if len(canonical_json([*records, record]).encode("utf-8")) > budget_bytes:
                blockers.add("EVIDENCE_CONTEXT_BUDGET_EXCEEDED")
                continue
            records.append(record)
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError, RecursionError):
            blockers.add("EVIDENCE_REFERENCE_UNRESOLVED")
    records.sort(key=lambda item: item["payload_sha256"])
    if len(records) != len(requested):
        blockers.add("EVIDENCE_REFERENCE_UNRESOLVED")
    state = "PARTIAL" if blockers else "COMPLETE" if requested else "EMPTY"
    return EvidenceSnapshot(vertical, scope_digest, requested, canonical_json(records),
                            state, tuple(sorted(blockers)))
