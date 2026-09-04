from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

ZERO_HASH = "0" * 64


class CanonicalizationError(ValueError):
    pass


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalizationError("non-finite floats are not valid receipt data")
        return value
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    raise CanonicalizationError(f"unsupported receipt value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _normalize(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_hex(value: Any) -> str:
    if not isinstance(value, str):
        value = canonical_json(value)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class ReceiptChain:
    """Append-only integrity chain.

    This establishes deterministic scoped integrity. It is not a signature and
    does not prove factual accuracy, safety, performance, compliance, or
    authorization.
    """

    vertical_id: str
    entries: list[dict[str, Any]] = field(default_factory=list)

    @property
    def head(self) -> str:
        return self.entries[-1]["receipt_hash"] if self.entries else ZERO_HASH

    def append(
        self,
        *,
        operation: str,
        payload: Mapping[str, Any],
        actor_id: str,
        signal_id: str,
        issued_at: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": "szl.vertical-receipt/v1",
            "sequence": len(self.entries),
            "vertical_id": self.vertical_id,
            "operation": operation,
            "actor_id": actor_id,
            "signal_id": signal_id,
            "issued_at": issued_at or utc_now(),
            "payload_hash": sha256_hex(payload),
            "previous_hash": self.head,
            "metadata": _normalize(metadata or {}),
            "integrity_scope": "SCOPED_SHA256_CHAIN",
            "authorization_proof": False,
        }
        body["receipt_hash"] = sha256_hex(body)
        self.entries.append(body)
        return dict(body)

    def verify(self) -> dict[str, Any]:
        previous = ZERO_HASH
        errors: list[dict[str, Any]] = []
        for expected_sequence, entry in enumerate(self.entries):
            candidate = dict(entry)
            observed_hash = candidate.pop("receipt_hash", None)
            expected_hash = sha256_hex(candidate)
            if entry.get("sequence") != expected_sequence:
                errors.append({"sequence": expected_sequence, "error": "SEQUENCE_MISMATCH"})
            if entry.get("previous_hash") != previous:
                errors.append({"sequence": expected_sequence, "error": "PREVIOUS_HASH_MISMATCH"})
            if observed_hash != expected_hash:
                errors.append({"sequence": expected_sequence, "error": "RECEIPT_HASH_MISMATCH"})
            previous = str(observed_hash or "")
        return {
            "ok": not errors,
            "entries": len(self.entries),
            "head": self.head,
            "errors": errors,
            "proves": ["scoped integrity", "append order"],
            "does_not_prove": ["truth", "safety", "performance", "compliance", "authorization"],
        }
