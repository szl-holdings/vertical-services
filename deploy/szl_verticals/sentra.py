"""Sentra deny-by-default policy engine and signed verdict receipts."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Literal

from fastapi import APIRouter, Query
from pydantic import Field

from .core import STATE_LOCK, SessionScope, StrictModel

# ----------------------------- sentra -------------------------------------
sentra = APIRouter(prefix="/sentra", tags=["sentra"])
_SENTRA_SECRET = os.environ.get("SENTRA_SIGNING_KEY", "").strip()
SENTRA_KEY_SOURCE = "env" if _SENTRA_SECRET else "ephemeral-dev"
SENTRA_KEY = (_SENTRA_SECRET or secrets.token_hex(32)).encode("utf-8")
VERDICTS: Dict[str, Deque[Dict[str, Any]]] = defaultdict(lambda: deque(maxlen=500))
RATE: Dict[tuple[str, str], Deque[float]] = defaultdict(lambda: deque(maxlen=120))


class EvaluateRequest(StrictModel):
    actor: str = Field(..., min_length=1, max_length=128)
    action: str = Field(..., min_length=1, max_length=128)
    resource: str = Field(..., min_length=1, max_length=512)
    risk_score: float = Field(0.0, ge=0.0, le=1.0, allow_inf_nan=False)
    authenticated: bool = False
    tier: Literal["untrusted", "operator", "admin", "service"] = "untrusted"
    evidence: List[str] = Field(default_factory=list, max_length=32)


GATES = (
    ("g1_actor_present", lambda r: bool(r.actor.strip())),
    ("g2_action_present", lambda r: bool(r.action.strip())),
    ("g3_resource_scoped", lambda r: "/" in r.resource or ":" in r.resource),
    ("g4_authenticated", lambda r: r.authenticated),
    ("g5_tier_allowed", lambda r: r.tier in {"operator", "admin", "service"}),
    ("g6_risk_threshold", lambda r: r.risk_score < 0.75),
    ("g7_evidence_cited", lambda r: bool(r.evidence)),
    (
        "g8_not_destructive_unattended",
        lambda r: not (
            r.action.strip().lower() in {"delete", "purge", "drop"}
            and r.tier != "admin"
        ),
    ),
)


def _rate_ok(session: str, actor: str, limit: int = 60, window: float = 60.0) -> bool:
    now = time.time()
    with STATE_LOCK:
        hits = RATE[(session, actor)]
        while hits and now - hits[0] >= window:
            hits.popleft()
        allowed = len(hits) < limit
        hits.append(now)
        return allowed


def _sentra_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(SENTRA_KEY, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        **payload,
        "receipt_id": hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24],
        "signature": signature,
        "signature_alg": "HMAC-SHA256",
        "key_source": SENTRA_KEY_SOURCE,
    }


@sentra.get("/healthz")
def sentra_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "sentra",
        "signing_key_source": SENTRA_KEY_SOURCE,
        "gates": len(GATES) + 1,
        "state": "SESSION_ISOLATED_PROCESS_MEMORY",
        "active_sessions": len(VERDICTS),
    }


@sentra.post("/v1/evaluate")
def sentra_evaluate(req: EvaluateRequest, session: SessionScope) -> dict[str, Any]:
    traversed = [{"gate": name, "passed": bool(rule(req))} for name, rule in GATES]
    traversed.append({"gate": "g9_rate_limit", "passed": _rate_ok(session, req.actor)})
    failed = [item["gate"] for item in traversed if not item["passed"]]
    payload = {
        "decision": "ALLOW" if not failed else "DENY",
        "actor": req.actor,
        "action": req.action,
        "resource": req.resource,
        "failed_gates": failed,
        "gates_traversed": traversed,
        "timestamp_ns": time.time_ns(),
        "truth_label": "MEASURED",
    }
    receipt = _sentra_receipt(payload)
    with STATE_LOCK:
        VERDICTS[session].append(receipt)
    return receipt


@sentra.get("/v1/verdicts")
def sentra_verdicts(session: SessionScope, limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    with STATE_LOCK:
        items = list(VERDICTS.get(session, ()))[-limit:]
    return {"count": len(items), "verdicts": items, "truth_label": "MEASURED"}
