"""Killinchu canonical defense-and-maritime backend.

Vessels is retained as a compatibility route, but it is not an independent
vertical. Maritime calculations and Sentra policy evaluation are surfaced
through Killinchu so one source, one public Space, and one audit boundary own
the full defense-and-maritime product.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from .core import SessionScope
from .sentra import EvaluateRequest, sentra_evaluate
from .vessels import Position, TRACKS, fleet_risk, vessel_risk, vessels_ingest

killinchu = APIRouter(prefix="/killinchu", tags=["killinchu"])


@killinchu.get("/healthz")
def killinchu_health() -> dict[str, Any]:
    tracked = sum(len(tracks) for tracks in TRACKS.values())
    return {
        "status": "ok",
        "service": "killinchu",
        "domain": "DEFENSE_AND_MARITIME",
        "organs": {
            "defense_policy": "/killinchu/v1/defense/evaluate",
            "maritime_position_ingest": "/killinchu/v1/maritime/positions",
            "maritime_vessel_risk": "/killinchu/v1/maritime/vessel/risk",
            "maritime_fleet_risk": "/killinchu/v1/maritime/fleet/risk",
            "second_brain": "/api/verticals/killinchu/second-brain",
            "anatomy": "/api/verticals/killinchu/anatomy",
            "formulas": "/api/verticals/killinchu/formulas",
            "connectors": "/api/verticals/killinchu/connectors",
        },
        "tracked_vessels": tracked,
        "canonical_repository": "szl-holdings/killinchu",
        "public_surface": "SZLHOLDINGS/killinchu",
        "vessels": {
            "status": "CONSOLIDATED",
            "legacy_route": "/vessels",
            "canonical_route": "/killinchu",
            "independent_vertical": False,
        },
        "effectors_enabled": False,
        "truth_label": "MEASURED",
    }


@killinchu.post("/v1/defense/evaluate")
def killinchu_defense_evaluate(
    request: EvaluateRequest,
    session: SessionScope,
) -> dict[str, Any]:
    result = sentra_evaluate(request, session)
    return {
        **result,
        "vertical": "killinchu",
        "organ": "defense-policy",
        "effectors_enabled": False,
    }


@killinchu.post("/v1/maritime/positions")
def killinchu_maritime_position(
    position: Position,
    session: SessionScope,
) -> dict[str, Any]:
    result = vessels_ingest(position, session)
    return {
        **result,
        "vertical": "killinchu",
        "organ": "vessels",
        "canonical_surface": "SZLHOLDINGS/killinchu",
    }


@killinchu.get("/v1/maritime/vessel/risk")
def killinchu_maritime_vessel_risk(
    session: SessionScope,
    imo: str = Query(..., min_length=3, max_length=32),
) -> dict[str, Any]:
    result = vessel_risk(session, imo)
    return {
        **result,
        "vertical": "killinchu",
        "organ": "vessels",
        "canonical_surface": "SZLHOLDINGS/killinchu",
    }


@killinchu.get("/v1/maritime/fleet/risk")
def killinchu_maritime_fleet_risk(session: SessionScope) -> dict[str, Any]:
    result = fleet_risk(session)
    return {
        **result,
        "vertical": "killinchu",
        "organ": "vessels",
        "canonical_surface": "SZLHOLDINGS/killinchu",
    }
