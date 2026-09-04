"""SZL Vertical Frontier Fabric.

Typed product, data, model, kernel, policy, and receipt contracts shared by the
SZL vertical estate. The package is deliberately fail-closed: a declared model
or kernel that is not bound at runtime is reported as UNAVAILABLE and never
silently replaced with a fabricated result.
"""

from .catalog import CATALOG_ERRORS, CONNECTORS, VERTICALS, get_vertical, public_catalog
from .connectors import (
    ConnectorError,
    ConnectorPolicyError,
    ConnectorRegistry,
    ConnectorUnavailable,
    FetchResult,
)
from .engine import EvaluationError, VerticalFabric, request_from_mapping, result_json
from .receipts import ReceiptChain, canonical_json, sha256_hex
from .types import (
    ClaimState,
    ConnectorSpec,
    Decision,
    EffectMode,
    EvaluationRequest,
    EvaluationResult,
    KernelBinding,
    KernelResult,
    ModelBinding,
    Proposal,
    SourceRef,
    ThemeSpec,
    VerticalSpec,
    as_public_dict,
)

__all__ = [
    "CATALOG_ERRORS",
    "CONNECTORS",
    "VERTICALS",
    "ClaimState",
    "ConnectorError",
    "ConnectorPolicyError",
    "ConnectorRegistry",
    "ConnectorSpec",
    "ConnectorUnavailable",
    "Decision",
    "EffectMode",
    "EvaluationError",
    "EvaluationRequest",
    "EvaluationResult",
    "FetchResult",
    "KernelBinding",
    "KernelResult",
    "ModelBinding",
    "Proposal",
    "ReceiptChain",
    "SourceRef",
    "ThemeSpec",
    "VerticalFabric",
    "VerticalSpec",
    "as_public_dict",
    "canonical_json",
    "get_vertical",
    "public_catalog",
    "request_from_mapping",
    "result_json",
    "sha256_hex",
]
