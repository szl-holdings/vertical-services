"""Vessels caller-supplied maritime track-risk engine."""
from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field

from .core import STATE_LOCK, SessionScope, StrictModel

# ----------------------------- vessels ------------------------------------
vessels = APIRouter(prefix="/vessels", tags=["vessels"])
TRACKS: Dict[str, Dict[str, Deque[Dict[str, float]]]] = defaultdict(
    lambda: defaultdict(lambda: deque(maxlen=1000))
)
DARK_GAP_S = 3600.0
SPEED_MAX_KN = 28.0


class Position(StrictModel):
    imo: str = Field(..., min_length=3, max_length=32)
    lat: float = Field(..., ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(..., ge=-180, le=180, allow_inf_nan=False)
    sog: float = Field(0.0, ge=0, le=100, allow_inf_nan=False)
    ts: Optional[float] = Field(None, gt=0, allow_inf_nan=False)


def _haversine_nm(a: tuple[float, float], b: tuple[float, float]) -> float:
    radius_nm = 3440.065
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius_nm * math.asin(min(1.0, math.sqrt(h)))


@vessels.get("/healthz")
def vessels_health() -> dict[str, Any]:
    with STATE_LOCK:
        sessions = len(TRACKS)
        count = sum(len(tracks) for tracks in TRACKS.values())
    return {
        "status": "ok",
        "service": "vessels",
        "tracked": count,
        "state": "SESSION_ISOLATED_PROCESS_MEMORY",
        "active_sessions": sessions,
        "public_surface": "SZLHOLDINGS/killinchu",
        "consolidated": True,
    }


@vessels.post("/v1/positions")
def vessels_ingest(position: Position, session: SessionScope) -> dict[str, Any]:
    imo = position.imo.strip().upper()
    with STATE_LOCK:
        TRACKS[session][imo].append(
            {
                "lat": position.lat,
                "lon": position.lon,
                "sog": position.sog,
                "ts": position.ts or time.time(),
            }
        )
        count = len(TRACKS[session][imo])
    return {"imo": imo, "n": count, "truth_label": "REPORTED"}


def _assess_vessel(session: str, imo: str) -> dict[str, Any]:
    with STATE_LOCK:
        track = list(TRACKS.get(session, {}).get(imo, ()))
    if not track:
        raise HTTPException(404, "unknown imo")
    flags: list[str] = []
    dark_gaps = 0
    implied_speeds: list[float] = []
    for first, second in zip(track, track[1:]):
        delta_seconds = second["ts"] - first["ts"]
        if delta_seconds > DARK_GAP_S:
            dark_gaps += 1
        if delta_seconds > 0:
            distance = _haversine_nm(
                (first["lat"], first["lon"]),
                (second["lat"], second["lon"]),
            )
            implied_speeds.append(distance / (delta_seconds / 3600.0))
    max_implied = max(implied_speeds) if implied_speeds else None
    slow_fixes = sum(1 for point in track if point["sog"] < 1.0)
    if dark_gaps:
        flags.append(f"dark_activity:{dark_gaps}_gaps")
    if max_implied is not None and max_implied > SPEED_MAX_KN:
        flags.append(f"speed_anomaly:{max_implied:.1f}kn_implied")
    if slow_fixes >= 5:
        flags.append(f"loitering:{slow_fixes}_low_sog_fixes")
    score = min(
        1.0,
        0.3 * dark_gaps
        + 0.4 * bool(max_implied is not None and max_implied > SPEED_MAX_KN)
        + 0.05 * slow_fixes,
    )
    return {
        "imo": imo,
        "fixes": len(track),
        "dark_gaps": dark_gaps,
        "max_implied_speed_kn": max_implied,
        "flags": flags,
        "risk_score": round(score, 3),
        "truth_label": "MODELED",
        "input_provenance": "CALLER_SUPPLIED",
    }


@vessels.get("/v1/vessel/risk")
def vessel_risk(session: SessionScope, imo: str = Query(..., min_length=3, max_length=32)) -> dict[str, Any]:
    return _assess_vessel(session, imo.strip().upper())


@vessels.get("/v1/fleet/risk")
def fleet_risk(session: SessionScope) -> dict[str, Any]:
    with STATE_LOCK:
        identifiers = list(TRACKS.get(session, {}))
    rows = [_assess_vessel(session, identifier) for identifier in identifiers]
    rows.sort(key=lambda row: row["risk_score"], reverse=True)
    return {"vessels": len(rows), "assessments": rows, "truth_label": "MODELED"}
