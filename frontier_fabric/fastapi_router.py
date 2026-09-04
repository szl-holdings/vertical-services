from __future__ import annotations

from typing import Any, Mapping

from .catalog import get_vertical
from .engine import EvaluationError, VerticalFabric, request_from_mapping
from .types import as_public_dict


def create_router(fabric: VerticalFabric | None = None):
    """Create an optional FastAPI router without making FastAPI a core dependency."""

    try:
        from fastapi import APIRouter, Body, HTTPException
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("FastAPI is required to create the vertical frontier router") from exc

    runtime = fabric or VerticalFabric()
    router = APIRouter(prefix="/api/vertical-fabric/v1", tags=["vertical-fabric"])

    @router.get("/healthz")
    def healthz() -> dict[str, Any]:
        capabilities = runtime.capabilities()
        return {
            "ok": True,
            "surface": "SZL Vertical Frontier Fabric",
            "schema": "szl.vertical-fabric-health/v1",
            "verticals": len(capabilities["verticals"]),
            "bound_models": len(capabilities["runtime"]["bound_models"]),
            "bound_kernels": len(capabilities["runtime"]["bound_kernels"]),
            "strict_effect_gate": capabilities["runtime"]["strict_effect_gate"],
            "public_effectors_enabled": False,
            "lambda_uniqueness": "CONJECTURE_1_OPEN",
        }

    @router.get("/verticals")
    def verticals() -> dict[str, Any]:
        return runtime.capabilities()

    @router.get("/verticals/{vertical_id}")
    def vertical(vertical_id: str) -> dict[str, Any]:
        try:
            return runtime.capabilities(vertical_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/verticals/{vertical_id}/experience")
    def experience(vertical_id: str) -> dict[str, Any]:
        try:
            spec = get_vertical(vertical_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "schema": "szl.vertical-experience/v1",
            "vertical_id": vertical_id,
            "display_name": spec.display_name,
            "lane": spec.lane,
            "operator_outcome": spec.operator_outcome,
            "unmet_need": spec.unmet_need,
            "differentiator": spec.differentiator,
            "theme": as_public_dict(spec.theme),
            "modules": list(spec.experience_modules),
            "evidence_contract": list(spec.evidence_contract),
            "effect_mode": spec.effect_mode.value,
            "public_actuation": spec.public_actuation.value,
        }

    @router.post("/evaluate")
    def evaluate(payload: Mapping[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            request = request_from_mapping(payload)
            result = runtime.evaluate(request)
            return as_public_dict(result)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (EvaluationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/receipts/verify")
    def verify_receipts(payload: Mapping[str, Any] = Body(...)) -> dict[str, Any]:
        vertical_id = str(payload.get("vertical_id", "")).strip()
        session_id = str(payload.get("session_id", "")).strip()
        if not vertical_id or not session_id:
            raise HTTPException(status_code=422, detail="vertical_id and session_id are required")
        try:
            get_vertical(vertical_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return runtime.verify_session(vertical_id, session_id)

    return router
