from __future__ import annotations

import json
import math
import os
import threading
from collections.abc import Callable, Mapping
from typing import Any

from .catalog import get_vertical, public_catalog
from .receipts import ReceiptChain, canonical_json, sha256_hex
from .types import (
    ClaimState,
    Decision,
    EffectMode,
    EvaluationRequest,
    EvaluationResult,
    KernelResult,
    Proposal,
    SourceRef,
    VerticalSpec,
    as_public_dict,
)

ModelAdapter = Callable[[EvaluationRequest, VerticalSpec], Proposal]
KernelAdapter = Callable[[EvaluationRequest, Proposal, VerticalSpec], KernelResult]


class EvaluationError(ValueError):
    pass


def _payload_size(payload: Mapping[str, Any]) -> int:
    return len(canonical_json(payload).encode("utf-8"))


def _valid_human_bind(bind: Mapping[str, Any] | None) -> tuple[bool, str]:
    if bind is None:
        return False, "human binding is absent"
    required = {"approver_id", "approved_at", "scope", "decision", "policy_revision"}
    missing = sorted(required - set(bind))
    if missing:
        return False, f"human binding is missing fields: {', '.join(missing)}"
    if str(bind.get("decision")).upper() not in {"ALLOW", "DENY"}:
        return False, "human binding decision must be ALLOW or DENY"
    if not all(str(bind.get(key, "")).strip() for key in required):
        return False, "human binding fields must be non-empty"
    return True, "human binding structure is complete"


def _core_kernel_results(
    request: EvaluationRequest,
    proposal: Proposal,
    vertical: VerticalSpec,
) -> tuple[KernelResult, ...]:
    results: list[KernelResult] = []

    payload_size = _payload_size(request.payload)
    max_payload = 1_000_000
    results.append(
        KernelResult(
            kernel_id="szl-core/payload-boundary",
            passed=payload_size <= max_payload,
            blocking=True,
            state=ClaimState.MEASURED,
            reason=(
                f"canonical payload is {payload_size} bytes"
                if payload_size <= max_payload
                else f"canonical payload exceeds {max_payload} bytes"
            ),
            evidence={"payload_bytes": payload_size, "maximum_bytes": max_payload},
        )
    )

    source_ids = {source.connector_id for source in request.sources}
    permitted_ids = {connector.id for connector in vertical.connectors}
    unknown_sources = sorted(source_ids - permitted_ids)
    results.append(
        KernelResult(
            kernel_id="SZLHOLDINGS/szl-invariants/source-boundary",
            passed=not unknown_sources,
            blocking=True,
            state=ClaimState.MEASURED,
            reason=(
                "all source references are declared for this vertical"
                if not unknown_sources
                else f"undeclared source connectors: {', '.join(unknown_sources)}"
            ),
            evidence={
                "declared_connectors": sorted(permitted_ids),
                "observed_connectors": sorted(source_ids),
            },
        )
    )

    citation_ids = {citation.connector_id for citation in proposal.citations}
    citation_gaps = sorted(citation_ids - permitted_ids)
    results.append(
        KernelResult(
            kernel_id="SZLHOLDINGS/szl-invariants/citation-boundary",
            passed=not citation_gaps,
            blocking=True,
            state=ClaimState.MEASURED,
            reason=(
                "proposal citations remain within the vertical source contract"
                if not citation_gaps
                else f"proposal cites undeclared connectors: {', '.join(citation_gaps)}"
            ),
            evidence={"proposal_connector_ids": sorted(citation_ids)},
        )
    )

    requested = (request.requested_effect or "").strip().lower()
    prohibited_tokens = {
        "weapon",
        "fire",
        "launch",
        "strike",
        "target",
        "credential",
        "exfiltrate",
        "bypass",
        "disable-control",
    }
    prohibited = sorted(token for token in prohibited_tokens if token in requested)
    if vertical.id == "killinchu" and requested not in {"", "simulate", "compare-simulation", "export-report"}:
        prohibited.append("non-simulated-killinchu-effect")
    if vertical.effect_mode is EffectMode.READ_ONLY and requested:
        prohibited.append("read-only-surface-effect")
    results.append(
        KernelResult(
            kernel_id="SZLHOLDINGS/szl-blocked/effect-boundary",
            passed=not prohibited,
            blocking=True,
            state=ClaimState.MEASURED,
            reason=(
                "requested effect remains inside the declared public boundary"
                if not prohibited
                else f"requested effect violates policy: {', '.join(sorted(set(prohibited)))}"
            ),
            evidence={"effect_mode": vertical.effect_mode.value, "requested_effect": requested or None},
        )
    )

    axes = request.payload.get("lambda_axes")
    weights = request.payload.get("lambda_weights")
    if isinstance(axes, list) and axes:
        try:
            numeric_axes = [float(item) for item in axes]
            numeric_weights = (
                [float(item) for item in weights]
                if isinstance(weights, list)
                else [1.0 / len(numeric_axes)] * len(numeric_axes)
            )
            valid = (
                len(numeric_axes) == len(numeric_weights)
                and all(math.isfinite(item) and item > 0 for item in numeric_axes)
                and all(math.isfinite(item) and item >= 0 for item in numeric_weights)
                and abs(sum(numeric_weights) - 1.0) < 1e-9
            )
            score = (
                math.exp(sum(weight * math.log(axis) for axis, weight in zip(numeric_axes, numeric_weights)))
                if valid
                else None
            )
        except (TypeError, ValueError, OverflowError):
            valid, score = False, None
        results.append(
            KernelResult(
                kernel_id="SZLHOLDINGS/szl-lambda-gate/advisory",
                passed=bool(valid),
                blocking=False,
                state=ClaimState.ADVISORY if valid else ClaimState.BLOCKED,
                reason=(
                    "weighted-geometric advisory score computed; it grants no authority"
                    if valid
                    else "lambda axes or weights are invalid"
                ),
                evidence={
                    "score": score,
                    "conjecture_1": "OPEN",
                    "decision_authority": False,
                },
            )
        )
    else:
        results.append(
            KernelResult(
                kernel_id="SZLHOLDINGS/szl-lambda-gate/advisory",
                passed=True,
                blocking=False,
                state=ClaimState.UNAVAILABLE,
                reason="no lambda axes were supplied; no score was fabricated",
                evidence={"score": None, "conjecture_1": "OPEN", "decision_authority": False},
            )
        )

    bind_ok, bind_reason = _valid_human_bind(request.human_bind)
    bind_required_now = bool(request.requested_effect) and vertical.requires_human_bind
    results.append(
        KernelResult(
            kernel_id="szl-core/human-bind",
            passed=(bind_ok or not bind_required_now),
            blocking=bind_required_now,
            state=ClaimState.MEASURED if bind_ok else ClaimState.UNAVAILABLE,
            reason=bind_reason if bind_required_now or bind_ok else "human binding is not required for an advisory read",
            evidence={"required": bind_required_now, "present": request.human_bind is not None},
        )
    )

    return tuple(results)


class VerticalFabric:
    """Shared governed backend for every SZL vertical.

    The fabric is useful with no model loaded: it validates boundaries and emits
    explicit UNAVAILABLE/HOLD results. Registered model and kernel adapters can
    be added at runtime without changing the authority model.
    """

    def __init__(self, *, require_bound_kernels_for_effects: bool | None = None) -> None:
        if require_bound_kernels_for_effects is None:
            require_bound_kernels_for_effects = os.getenv(
                "SZL_REQUIRE_BOUND_KERNELS_FOR_EFFECTS", "true"
            ).strip().lower() not in {"0", "false", "no"}
        self.require_bound_kernels_for_effects = require_bound_kernels_for_effects
        self._model_adapters: dict[str, ModelAdapter] = {}
        self._kernel_adapters: dict[str, KernelAdapter] = {}
        self._chains: dict[tuple[str, str], ReceiptChain] = {}
        self._lock = threading.RLock()

    def register_model(self, repo_id: str, adapter: ModelAdapter) -> None:
        if not repo_id.startswith("SZLHOLDINGS/"):
            raise EvaluationError("model adapters must use an SZLHOLDINGS repository id")
        self._model_adapters[repo_id] = adapter

    def register_kernel(self, repo_id: str, adapter: KernelAdapter) -> None:
        if not repo_id.startswith("SZLHOLDINGS/"):
            raise EvaluationError("kernel adapters must use an SZLHOLDINGS repository id")
        self._kernel_adapters[repo_id] = adapter

    def capabilities(self, vertical_id: str | None = None) -> dict[str, Any]:
        if vertical_id is None:
            catalog = public_catalog()
            catalog["runtime"] = {
                "bound_models": sorted(self._model_adapters),
                "bound_kernels": sorted(self._kernel_adapters),
                "strict_effect_gate": self.require_bound_kernels_for_effects,
            }
            return catalog
        vertical = get_vertical(vertical_id)
        payload = as_public_dict(vertical)
        payload["runtime"] = {
            "models": {
                binding.repo_id: (
                    ClaimState.LIVE.value if binding.repo_id in self._model_adapters else ClaimState.UNAVAILABLE.value
                )
                for binding in vertical.models
            },
            "kernels": {
                binding.repo_id: (
                    ClaimState.LIVE.value if binding.repo_id in self._kernel_adapters else ClaimState.UNAVAILABLE.value
                )
                for binding in vertical.kernels
            },
            "strict_effect_gate": self.require_bound_kernels_for_effects,
        }
        return payload

    def _proposal(self, request: EvaluationRequest, vertical: VerticalSpec) -> Proposal:
        if request.proposal is not None:
            return request.proposal
        for binding in vertical.models:
            adapter = self._model_adapters.get(binding.repo_id)
            if adapter is None:
                continue
            proposal = adapter(request, vertical)
            if proposal.model_id != binding.repo_id:
                raise EvaluationError(
                    f"model adapter identity mismatch: expected {binding.repo_id}, observed {proposal.model_id}"
                )
            return proposal
        return Proposal(
            summary="No approved model adapter is bound for this vertical runtime.",
            model_id=None,
            model_revision=None,
            confidence=None,
            citations=tuple(request.sources),
            state=ClaimState.UNAVAILABLE,
            payload={"proposal_generated": False},
        )

    def _external_kernel_results(
        self,
        request: EvaluationRequest,
        proposal: Proposal,
        vertical: VerticalSpec,
    ) -> tuple[KernelResult, ...]:
        results: list[KernelResult] = []
        for binding in vertical.kernels:
            adapter = self._kernel_adapters.get(binding.repo_id)
            if adapter is None:
                results.append(
                    KernelResult(
                        kernel_id=binding.repo_id,
                        passed=False,
                        blocking=False,
                        state=ClaimState.UNAVAILABLE,
                        reason="declared SZL kernel is not bound in this runtime; no result was fabricated",
                        evidence={"enforcement": binding.enforcement},
                    )
                )
                continue
            result = adapter(request, proposal, vertical)
            if result.kernel_id != binding.repo_id:
                raise EvaluationError(
                    f"kernel adapter identity mismatch: expected {binding.repo_id}, observed {result.kernel_id}"
                )
            results.append(result)
        return tuple(results)

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        vertical = get_vertical(request.vertical_id)
        if not request.signal_id.strip() or not request.session_id.strip() or not request.actor_id.strip():
            raise EvaluationError("signal_id, session_id, and actor_id are required")
        if _payload_size(request.payload) > 1_100_000:
            raise EvaluationError("request payload is too large to evaluate")

        proposal = self._proposal(request, vertical)
        core = _core_kernel_results(request, proposal, vertical)
        external = self._external_kernel_results(request, proposal, vertical)
        kernel_results = core + external

        blocking_failures = [result for result in kernel_results if result.blocking and not result.passed]
        unavailable_bound_kernels = [
            result for result in external if result.state is ClaimState.UNAVAILABLE
        ]

        bind_ok, _ = _valid_human_bind(request.human_bind)
        bind_decision = (
            str(request.human_bind.get("decision", "")).upper()
            if bind_ok and request.human_bind is not None
            else None
        )

        if blocking_failures:
            decision = Decision.DENY
            state = ClaimState.BLOCKED
            reason = "; ".join(result.reason for result in blocking_failures)
        elif bind_decision == "DENY":
            decision = Decision.DENY
            state = ClaimState.BLOCKED
            reason = "human binding denied the requested scope"
        elif request.requested_effect and proposal.state is ClaimState.UNAVAILABLE:
            decision = Decision.HOLD
            state = ClaimState.UNAVAILABLE
            reason = "an effect cannot proceed without a bound model proposal or reviewed caller proposal"
        elif (
            request.requested_effect
            and self.require_bound_kernels_for_effects
            and unavailable_bound_kernels
        ):
            decision = Decision.HOLD
            state = ClaimState.UNAVAILABLE
            reason = "declared SZL kernels are not bound; consequential effect remains on hold"
        elif request.requested_effect and vertical.requires_human_bind and not bind_ok:
            decision = Decision.HOLD
            state = ClaimState.UNAVAILABLE
            reason = "consequential effect requires a complete human binding"
        elif request.requested_effect and bind_decision == "ALLOW":
            decision = Decision.ALLOW
            state = ClaimState.MEASURED
            reason = "policy boundaries passed and an explicit human binding allows the declared scope"
        else:
            decision = Decision.HOLD
            state = ClaimState.ADVISORY if proposal.state is not ClaimState.UNAVAILABLE else ClaimState.UNAVAILABLE
            reason = "proposal is advisory; no effect is authorized"

        receipt_payload = {
            "request": {
                "vertical_id": request.vertical_id,
                "signal_id": request.signal_id,
                "session_id_hash": sha256_hex(request.session_id),
                "actor_id_hash": sha256_hex(request.actor_id),
                "payload_hash": sha256_hex(request.payload),
                "source_refs": [as_public_dict(source) for source in request.sources],
                "requested_effect": request.requested_effect,
            },
            "proposal": as_public_dict(proposal),
            "kernel_results": [as_public_dict(result) for result in kernel_results],
            "decision": decision.value,
            "state": state.value,
            "reason": reason,
            "human_bind_hash": sha256_hex(request.human_bind) if request.human_bind else None,
        }
        key = (request.vertical_id, sha256_hex(request.session_id))
        with self._lock:
            chain = self._chains.setdefault(key, ReceiptChain(request.vertical_id))
            receipt = chain.append(
                operation="vertical.evaluate",
                payload=receipt_payload,
                actor_id=sha256_hex(request.actor_id),
                signal_id=request.signal_id,
                metadata={
                    "decision": decision.value,
                    "state": state.value,
                    "effect_mode": vertical.effect_mode.value,
                    "human_bind_required": vertical.requires_human_bind,
                },
            )

        return EvaluationResult(
            vertical_id=request.vertical_id,
            signal_id=request.signal_id,
            decision=decision,
            state=state,
            reason=reason,
            proposal=proposal,
            kernel_results=kernel_results,
            effect_mode=vertical.effect_mode,
            human_bind_required=vertical.requires_human_bind,
            receipt=receipt,
        )

    def verify_session(self, vertical_id: str, session_id: str) -> dict[str, Any]:
        key = (vertical_id, sha256_hex(session_id))
        with self._lock:
            chain = self._chains.get(key)
            if chain is None:
                return {
                    "ok": False,
                    "state": ClaimState.UNAVAILABLE.value,
                    "reason": "no receipt chain exists for this session",
                    "entries": 0,
                }
            return chain.verify()


def request_from_mapping(raw: Mapping[str, Any]) -> EvaluationRequest:
    try:
        sources = tuple(
            SourceRef(
                connector_id=str(item["connector_id"]),
                locator=str(item["locator"]),
                revision=str(item["revision"]) if item.get("revision") is not None else None,
                digest=str(item["digest"]) if item.get("digest") is not None else None,
            )
            for item in raw.get("sources", [])
        )
    except (KeyError, TypeError) as exc:
        raise EvaluationError("sources must contain connector_id and locator") from exc

    proposal_raw = raw.get("proposal")
    proposal = None
    if proposal_raw is not None:
        if not isinstance(proposal_raw, Mapping):
            raise EvaluationError("proposal must be an object")
        try:
            proposal_state = ClaimState(str(proposal_raw.get("state", ClaimState.ADVISORY.value)))
            proposal = Proposal(
                summary=str(proposal_raw["summary"]),
                model_id=(str(proposal_raw["model_id"]) if proposal_raw.get("model_id") else None),
                model_revision=(
                    str(proposal_raw["model_revision"])
                    if proposal_raw.get("model_revision")
                    else None
                ),
                confidence=(
                    float(proposal_raw["confidence"])
                    if proposal_raw.get("confidence") is not None
                    else None
                ),
                citations=sources,
                state=proposal_state,
                payload=(
                    dict(proposal_raw.get("payload", {}))
                    if isinstance(proposal_raw.get("payload", {}), Mapping)
                    else {}
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise EvaluationError("proposal is invalid") from exc

    payload = raw.get("payload", {})
    if not isinstance(payload, Mapping):
        raise EvaluationError("payload must be an object")
    human_bind = raw.get("human_bind")
    if human_bind is not None and not isinstance(human_bind, Mapping):
        raise EvaluationError("human_bind must be an object")

    try:
        return EvaluationRequest(
            vertical_id=str(raw["vertical_id"]),
            signal_id=str(raw["signal_id"]),
            session_id=str(raw["session_id"]),
            actor_id=str(raw["actor_id"]),
            payload=dict(payload),
            sources=sources,
            proposal=proposal,
            requested_effect=(str(raw["requested_effect"]) if raw.get("requested_effect") else None),
            human_bind=dict(human_bind) if human_bind is not None else None,
        )
    except KeyError as exc:
        raise EvaluationError(f"missing required field: {exc.args[0]}") from exc


def result_json(result: EvaluationResult) -> str:
    return json.dumps(as_public_dict(result), indent=2, sort_keys=True)
