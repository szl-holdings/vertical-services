"""Lyte metric summary and drift engine."""
from __future__ import annotations

import statistics
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field

from .core import STATE_LOCK, SessionScope, StrictModel

# ----------------------------- lyte ---------------------------------------
lyte = APIRouter(prefix="/lyte", tags=["lyte"])
STREAMS: Dict[str, Dict[str, Deque[Dict[str, float]]]] = defaultdict(
    lambda: defaultdict(lambda: deque(maxlen=2000))
)


class Metric(StrictModel):
    stream: str = Field(..., min_length=1, max_length=128)
    value: float = Field(..., allow_inf_nan=False)
    ts: Optional[float] = Field(None, gt=0, allow_inf_nan=False)


@lyte.get("/healthz")
def lyte_health() -> dict[str, Any]:
    with STATE_LOCK:
        sessions = len(STREAMS)
        count = sum(len(streams) for streams in STREAMS.values())
    return {"status": "ok", "service": "lyte", "streams": count, "active_sessions": sessions, "state": "SESSION_ISOLATED_PROCESS_MEMORY"}


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
