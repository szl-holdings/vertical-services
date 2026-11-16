"""Lyte metric summary, drift, and receipt-backed telemetry projection."""
from __future__ import annotations

import hashlib
import json
import statistics
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field

from .core import STATE_LOCK, RedactedValidationRoute, SessionScope, StrictModel

# ----------------------------- lyte ---------------------------------------
lyte = APIRouter(prefix="/lyte", tags=["lyte"], route_class=RedactedValidationRoute)
STREAMS: Dict[str, Dict[str, Deque[Dict[str, float]]]] = defaultdict(
    lambda: defaultdict(lambda: deque(maxlen=2000))
)
TELEMETRY_LIMIT = 512
TELEMETRY_CLOCK_SKEW_SECONDS = 5
TELEMETRY: Dict[str, Deque[Dict[str, Any]]] = defaultdict(lambda: deque(maxlen=TELEMETRY_LIMIT))
TELEMETRY_SCHEMA = "szl.lyte-telemetry/v1"
TELEMETRY_FIELDS = (
    "trace_id", "span_id", "source_revision", "dataset_id", "model_id",
    "provider", "observed_at", "freshness_seconds", "sampling_rate",
    "freshness_state", "age_seconds", "rights", "license", "outcome", "latency_ms",
    "deployment_revision", "cohort", "action", "approval_id", "approval_required",
    "source_state", "effective_state", "receipt_id", "receipt_url",
)


class Metric(StrictModel):
    stream: str = Field(..., min_length=1, max_length=128)
    value: float = Field(..., allow_inf_nan=False)
    ts: Optional[float] = Field(None, gt=0, allow_inf_nan=False)


class TelemetryEvent(StrictModel):
    """A bounded, caller-provided observation envelope.

    This route records metadata and a deterministic receipt only. It does not
    fetch a provider, accept arbitrary URLs, or authorize an action.
    """

    trace_id: str = Field(..., min_length=1, max_length=128)
    span_id: str = Field(..., min_length=1, max_length=128)
    source_revision: str = Field(..., min_length=1, max_length=256)
    dataset_id: Optional[str] = Field(None, max_length=256)
    model_id: Optional[str] = Field(None, max_length=256)
    provider: str = Field("UNSPECIFIED", min_length=1, max_length=128)
    observed_at: Optional[str] = Field(None, max_length=64)
    freshness_seconds: int = Field(300, ge=1, le=31_536_000)
    sampling_rate: float = Field(1.0, ge=0.0, le=1.0, allow_inf_nan=False)
    rights: str = Field("UNSPECIFIED", min_length=1, max_length=256)
    license: Optional[str] = Field(None, max_length=256)
    outcome: str = Field("UNKNOWN", min_length=1, max_length=128)
    latency_ms: Optional[float] = Field(None, ge=0.0, le=86_400_000, allow_inf_nan=False)
    deployment_revision: Optional[str] = Field(None, max_length=256)
    cohort: Optional[str] = Field(None, max_length=256)
    action: Optional[str] = Field(None, max_length=256)
    approval_id: Optional[str] = Field(None, max_length=256)
    approval_required: bool = True
    source_state: Literal["OBSERVED", "STALE", "UNAVAILABLE", "NOT_ATTEMPTED"] = "OBSERVED"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _admit_observed_at(value: str) -> tuple[str, float]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise HTTPException(422, "observed_at must include a UTC offset")
        normalized = parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise HTTPException(422, "observed_at must be an ISO-8601 timestamp with a UTC offset") from None
    age_seconds = (datetime.now(timezone.utc) - normalized).total_seconds()
    if age_seconds < -TELEMETRY_CLOCK_SKEW_SECONDS:
        raise HTTPException(422, "observed_at exceeds the allowed five-second clock skew")
    return normalized.isoformat(timespec="milliseconds").replace("+00:00", "Z"), max(0.0, age_seconds)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _telemetry_receipt_id(basis: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(basis).encode("utf-8")).hexdigest()


def _telemetry_public(record: dict[str, Any], *, session: str) -> dict[str, Any] | None:
    """Return a verified copy, dropping a record if its receipt was altered."""
    basis = record.get("_receipt_basis")
    receipt_id = record.get("receipt_id")
    if not isinstance(basis, dict) or not isinstance(receipt_id, str):
        return None
    if basis.get("schema") != TELEMETRY_SCHEMA or basis.get("session_scope") != session:
        return None
    # Verify both the sealed basis and the displayed observation. The derived
    # read-time freshness is deliberately outside the immutable receipt basis.
    try:
        if _telemetry_receipt_id(basis) != receipt_id:
            return None
        public = {key: value for key, value in basis.items() if key != "session_scope"}
        if any(key not in record or _canonical(record[key]) != _canonical(value)
               for key, value in public.items()):
            return None
        _, age_seconds = _admit_observed_at(public["observed_at"])
    except (HTTPException, KeyError, TypeError, ValueError, OverflowError):
        return None
    source_state = public["source_state"]
    freshness_state = "FRESH" if age_seconds <= public["freshness_seconds"] else "STALE"
    effective_state = source_state
    if source_state == "OBSERVED" and freshness_state == "STALE":
        effective_state = "STALE"
    public.update({
        "receipt_id": receipt_id,
        "truth_label": "REPORTED" if source_state in {"OBSERVED", "STALE"} else "UNAVAILABLE",
        "source_provenance": "CALLER_REPORTED_NOT_AUTHENTICATED",
        "counts_as_connector_evidence": False,
        "freshness_state": freshness_state,
        "age_seconds": int(age_seconds),
        "effective_state": effective_state,
    })
    public["receipt_url"] = f"/lyte/v1/telemetry?receipt_id={receipt_id}"
    public["receipt"] = {
        "schema": TELEMETRY_SCHEMA,
        "receipt_id": receipt_id,
        "receipt_algorithm": "SHA-256",
        "signature_claimed": False,
        "receipt_url": public["receipt_url"],
        "source_revision": public["source_revision"],
        "observed_at": public["observed_at"],
        "state": public["source_state"],
        "truth_label": public["truth_label"],
    }
    public["freshness"] = {
        "observed_at": public["observed_at"],
        "seconds": public["freshness_seconds"],
        "state": public["freshness_state"],
    }
    public["sampling"] = {"rate": public["sampling_rate"]}
    public["rights_info"] = {"rights": public["rights"], "license": public["license"]}
    public["deployment"] = {"revision": public["deployment_revision"]}
    public["approval"] = {
        "id": public["approval_id"],
        "required": public["approval_required"],
    }
    return public


def _telemetry_matches(item: dict[str, Any], filters: dict[str, str | None]) -> bool:
    return all(value is None or item.get(key) == value for key, value in filters.items())


def telemetry_projection(
    session: str,
    *,
    limit: int = 50,
    filters: dict[str, str | None] | None = None,
    receipt_id: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """Read the caller's bounded, receipt-verified telemetry projection."""
    with STATE_LOCK:
        raw = list(TELEMETRY.get(session, ()))
    selected: list[dict[str, Any]] = []
    active_filters = filters or {}
    needle = query.casefold() if query is not None else None
    for record in reversed(raw):
        public = _telemetry_public(record, session=session)
        if public is None:
            continue
        if receipt_id is not None and public.get("receipt_id") != receipt_id:
            continue
        if not _telemetry_matches(public, active_filters):
            continue
        if needle is not None and not any(
            needle in str(public.get(key, "")).casefold() for key in TELEMETRY_FIELDS
        ):
            continue
        selected.append(public)
        if len(selected) >= limit:
            break
    return {
        "schema": TELEMETRY_SCHEMA,
        "count": len(selected),
        "limit": limit,
        "items": selected,
        "filters": {key: value for key, value in active_filters.items() if value is not None},
        "state": "SESSION_ISOLATED_PROCESS_MEMORY",
        "receipt_backed": True,
        "truth_label": "REPORTED" if selected else "UNAVAILABLE",
        "source_provenance": "CALLER_REPORTED_NOT_AUTHENTICATED",
        "counts_as_connector_evidence": False,
    }


@lyte.get("/healthz")
def lyte_health() -> dict[str, Any]:
    with STATE_LOCK:
        sessions = len(set(STREAMS) | set(TELEMETRY))
        count = sum(len(streams) for streams in STREAMS.values())
        telemetry_count = sum(len(items) for items in TELEMETRY.values())
    return {"status": "ok", "service": "lyte", "streams": count, "telemetry_events": telemetry_count,
            "active_sessions": sessions, "state": "SESSION_ISOLATED_PROCESS_MEMORY"}


@lyte.post("/v1/metrics")
def lyte_ingest(metric: Metric, session: SessionScope) -> dict[str, Any]:
    stream = metric.stream.strip()
    with STATE_LOCK:
        STREAMS[session][stream].append({"value": metric.value, "ts": metric.ts or time.time()})
        count = len(STREAMS[session][stream])
    return {"stream": stream, "n": count, "truth_label": "MEASURED"}


def _stream_values(session: str, stream: str) -> list[float]:
    with STATE_LOCK:
        points = list(STREAMS.get(session, {}).get(stream, ()))
    if not points:
        raise HTTPException(404, "unknown stream")
    return [point["value"] for point in points]


def _percentile(sorted_values: list[float], proportion: float) -> float:
    index = round((len(sorted_values) - 1) * proportion)
    return sorted_values[index]


@lyte.get("/v1/summary")
def lyte_summary(session: SessionScope, stream: str = Query(..., min_length=1, max_length=128)) -> dict[str, Any]:
    values = _stream_values(session, stream)
    ordered = sorted(values)
    return {
        "stream": stream,
        "n": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "min": ordered[0],
        "max": ordered[-1],
        "p50": _percentile(ordered, 0.50),
        "p95": _percentile(ordered, 0.95),
        "p99": _percentile(ordered, 0.99),
        "truth_label": "MEASURED",
    }


@lyte.get("/v1/drift")
def lyte_drift(
    session: SessionScope,
    stream: str = Query(..., min_length=1, max_length=128),
    split: float = Query(0.5, gt=0.05, lt=0.95),
) -> dict[str, Any]:
    values = _stream_values(session, stream)
    if len(values) < 20:
        raise HTTPException(400, "need >=20 points")
    pivot = min(len(values) - 1, max(1, int(len(values) * split)))
    baseline, recent = values[:pivot], values[pivot:]
    baseline_mean = statistics.fmean(baseline)
    recent_mean = statistics.fmean(recent)
    baseline_stdev = statistics.pstdev(baseline) or 1e-9
    z_shift = (recent_mean - baseline_mean) / baseline_stdev
    return {
        "stream": stream,
        "baseline_n": len(baseline),
        "recent_n": len(recent),
        "baseline_mean": baseline_mean,
        "recent_mean": recent_mean,
        "z_shift": z_shift,
        "drift_detected": abs(z_shift) > 2.0,
        "truth_label": "MODELED",
    }


@lyte.post("/v1/telemetry")
def lyte_telemetry_ingest(event: TelemetryEvent, session: SessionScope) -> dict[str, Any]:
    # Escaped lone surrogates are legal JSON syntax but cannot be represented
    # in the UTF-8 receipt basis. Reject them without reflecting request bytes.
    for value in event.model_dump().values():
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                raise HTTPException(422, "invalid request") from None
    observed_at, _ = _admit_observed_at(event.observed_at or _utc_now())
    for field_name in ("trace_id", "span_id", "source_revision", "provider", "rights", "outcome"):
        if not getattr(event, field_name).strip():
            raise HTTPException(422, f"{field_name} must not be blank")
    # A caller cannot make an unavailable source look observed by omitting its
    # revision. The revision itself is caller-reported and remains explicit.
    if event.source_state == "OBSERVED" and event.source_revision.strip().upper() == "UNAVAILABLE":
        raise HTTPException(422, "observed telemetry requires a source revision")
    basis = {
        "schema": TELEMETRY_SCHEMA,
        "session_scope": session,
        **event.model_dump(mode="json"),
        "observed_at": observed_at,
    }
    receipt_id = _telemetry_receipt_id(basis)
    record = {
        **{key: basis[key] for key in basis if key != "schema" and key != "session_scope"},
        "schema": TELEMETRY_SCHEMA,
        "receipt_id": receipt_id,
        "_receipt_basis": basis,
    }
    with STATE_LOCK:
        stream = TELEMETRY[session]
        if not any(existing.get("receipt_id") == receipt_id for existing in stream):
            stream.append(record)
    public = _telemetry_public(record, session=session)
    assert public is not None
    return public


@lyte.get("/v1/telemetry")
def lyte_telemetry(
    session: SessionScope,
    limit: int = Query(50, ge=1, le=200),
    receipt_id: Optional[str] = Query(None, min_length=64, max_length=64),
    trace_id: Optional[str] = Query(None, min_length=1, max_length=128),
    span_id: Optional[str] = Query(None, min_length=1, max_length=128),
    dataset_id: Optional[str] = Query(None, min_length=1, max_length=256),
    model_id: Optional[str] = Query(None, min_length=1, max_length=256),
    provider: Optional[str] = Query(None, min_length=1, max_length=128),
    cohort: Optional[str] = Query(None, min_length=1, max_length=256),
    outcome: Optional[str] = Query(None, min_length=1, max_length=128),
    deployment_revision: Optional[str] = Query(None, min_length=1, max_length=256),
    source_state: Optional[str] = Query(None, min_length=1, max_length=32),
) -> dict[str, Any]:
    projection = telemetry_projection(
        session,
        limit=limit,
        receipt_id=receipt_id,
        filters={
            "trace_id": trace_id, "span_id": span_id, "dataset_id": dataset_id,
            "model_id": model_id, "provider": provider, "cohort": cohort,
            "outcome": outcome, "deployment_revision": deployment_revision,
            "source_state": source_state,
        },
    )
    if receipt_id is not None and not projection["items"]:
        raise HTTPException(404, "telemetry receipt not found")
    return projection


@lyte.get("/v1/telemetry/search")
def lyte_telemetry_search(
    session: SessionScope,
    q: Optional[str] = Query(None, min_length=1, max_length=256),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Search indexed identifiers and outcomes without exposing raw payloads."""
    return telemetry_search_projection(session, q=q, limit=limit)


def telemetry_search_projection(
    session: str,
    *,
    q: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Filter the full bounded session history before limiting search results."""
    projection = telemetry_projection(session, limit=limit, query=q)
    projection["filters"] = {"q": q}
    return projection
