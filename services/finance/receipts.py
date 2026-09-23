"""
SZL Finance Engine v2 — hash-chained receipt primitive.

Receipts are UNSIGNED_HONEST under Doctrine v11: hash-chained, replayable,
offline-verifiable; the unsigned fallback is declared, never hidden.
Entry i covers canonical(prev_hash + payload), so any mutation, reorder,
or injection breaks the chain detectably. Chain state lives for the process
lifetime by design — persistence/export is the deployment plane's job
(szl-lake), and /receipts/verify attests to what this process has emitted.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

GENESIS = "SZL-FINANCE-ENGINE/v2:genesis"
SIGNING_SCHEME = "UNSIGNED_HONEST"


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


class ReceiptChain:
    def __init__(self) -> None:
        self._entries: list[dict] = []

    def _head(self) -> str:
        if not self._entries:
            return hashlib.sha256(_canon(GENESIS)).hexdigest()
        return self._entries[-1]["receipt_sha256"]

    def append(self, kind: str, payload: dict) -> dict:
        prev = self._head()
        body = {
            "seq": len(self._entries),
            "kind": kind,
            "ts_unix": time.time(),
            "payload": payload,
            "prev_receipt": prev,
        }
        digest = hashlib.sha256(_canon(body)).hexdigest()
        entry = dict(body)
        entry["receipt_sha256"] = digest
        entry["signature"] = {"scheme": SIGNING_SCHEME}
        self._entries.append(entry)
        return entry

    def entries(self) -> list[dict]:
        return list(self._entries)

    @staticmethod
    def verify(entries: list[dict]) -> dict:
        """Offline verification: CONSISTENT / DIVERGENT on tampered chain."""
        prev = hashlib.sha256(_canon(GENESIS)).hexdigest()
        for i, e in enumerate(entries):
            body = {k: e[k] for k in ("seq", "kind", "ts_unix", "payload", "prev_receipt")}
            if e.get("seq") != i or e.get("prev_receipt") != prev:
                return {"state": "DIVERGENT", "at_seq": i, "reason": "link_mismatch"}
            digest = hashlib.sha256(_canon(body)).hexdigest()
            if digest != e.get("receipt_sha256"):
                return {"state": "DIVERGENT", "at_seq": i, "reason": "payload_tamper"}
            prev = digest
        return {"state": "CONSISTENT", "length": len(entries)}
