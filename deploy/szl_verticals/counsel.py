"""PRISM Counsel matter, obligation, docket, and receipt-chain engine."""
from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import Field

from .core import STATE_LOCK, SessionScope, StrictModel

# ----------------------------- counsel ------------------------------------
counsel = APIRouter(prefix="/counsel", tags=["counsel"])
MATTERS: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
RECEIPT_CHAIN: Dict[str, Deque[Dict[str, Any]]] = defaultdict(lambda: deque(maxlen=500))
PREVIOUS_HASH: Dict[str, str] = defaultdict(lambda: "GENESIS")


class MatterIn(StrictModel):
    title: str = Field(..., min_length=1, max_length=256)
    client: str = Field(..., min_length=1, max_length=256)
    domain: str = Field("general", min_length=1, max_length=128)
    counterparty: str = Field("", max_length=256)
    exposure_usd: float = Field(0.0, ge=0, allow_inf_nan=False)
    deadline_ts: Optional[float] = Field(None, gt=0, allow_inf_nan=False)


class ObligationIn(StrictModel):
    clause: str = Field(..., min_length=1, max_length=512)
    obligation: str = Field(..., min_length=1, max_length=1024)
    party: str = Field("client", min_length=1, max_length=128)
    due_days: int = Field(30, ge=0, le=36500)
    severity: Literal["critical", "high", "medium", "low"] = "medium"


def _chain(session: str, step: str, payload: str) -> dict[str, Any]:
    with STATE_LOCK:
        previous = PREVIOUS_HASH[session]
        digest = hashlib.sha256(f"{previous}|{step}|{payload}".encode("utf-8")).hexdigest()
        receipt = {
            "step": step,
            "hash": digest,
            "prev": previous,
            "ts": time.time(),
            "truth_label": "MEASURED",
        }
        PREVIOUS_HASH[session] = digest
        RECEIPT_CHAIN[session].append(receipt)
        return dict(receipt)


@counsel.get("/healthz")
def counsel_health() -> dict[str, Any]:
    with STATE_LOCK:
        sessions = len(MATTERS)
        matters = sum(len(items) for items in MATTERS.values())
        receipts = sum(len(items) for items in RECEIPT_CHAIN.values())
    return {
        "status": "ok",
        "service": "counsel",
        "matters": matters,
        "receipt_chain": receipts,
        "state": "SESSION_ISOLATED_PROCESS_MEMORY",
        "active_sessions": sessions,
    }


@counsel.post("/v1/matters")
def counsel_open(matter: MatterIn, session: SessionScope) -> dict[str, Any]:
    matter_id = hashlib.sha256(
        f"{matter.title}|{matter.client}|{time.time_ns()}".encode("utf-8")
    ).hexdigest()[:12]
    record = matter.model_dump()
    record.update({"id": matter_id, "ts": time.time(), "status": "open", "obligations": []})
    with STATE_LOCK:
        MATTERS[session][matter_id] = record
    receipt = _chain(session, "matter.open", f"{matter_id}|{matter.title}")
    return {**record, "receipt": receipt, "truth_label": "REPORTED"}


@counsel.post("/v1/matters/{matter_id}/obligations")
def counsel_obligation(matter_id: str, obligation: ObligationIn, session: SessionScope) -> dict[str, Any]:
    with STATE_LOCK:
        if matter_id not in MATTERS.get(session, {}):
            raise HTTPException(404, "unknown matter")
        item = obligation.model_dump()
        item["id"] = f"ob-{len(MATTERS[session][matter_id]['obligations']) + 1:03d}"
        item["truth_label"] = "REPORTED"
        MATTERS[session][matter_id]["obligations"].append(item)
    receipt = _chain(session, "obligation.map", f"{matter_id}|{item['id']}|{obligation.obligation}")
    return {"matter_id": matter_id, "obligation": item, "receipt": receipt}


@counsel.get("/v1/matters/{matter_id}")
def counsel_get(matter_id: str, session: SessionScope) -> dict[str, Any]:
    with STATE_LOCK:
        if matter_id not in MATTERS.get(session, {}):
            raise HTTPException(404, "unknown matter")
        matter = json.loads(json.dumps(MATTERS[session][matter_id]))
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    ranked = sorted(matter["obligations"], key=lambda item: severity_order[item["severity"]])
    return {**matter, "obligations_by_severity": ranked, "truth_label": "REPORTED"}


@counsel.get("/v1/docket")
def counsel_docket(session: SessionScope) -> dict[str, Any]:
    with STATE_LOCK:
        snapshot = json.loads(json.dumps(MATTERS.get(session, {})))
    rows = []
    for matter_id, matter in snapshot.items():
        high_severity = sum(
            1 for item in matter["obligations"] if item["severity"] in {"critical", "high"}
        )
        rows.append(
            {
                "id": matter_id,
                "title": matter["title"],
                "client": matter["client"],
                "domain": matter["domain"],
                "open_obligations": len(matter["obligations"]),
                "high_severity": high_severity,
                "exposure_usd": matter["exposure_usd"],
                "status": matter["status"],
            }
        )
    rows.sort(key=lambda row: (-row["high_severity"], -row["exposure_usd"]))
    return {"matters": len(rows), "docket": rows, "truth_label": "MODELED"}
