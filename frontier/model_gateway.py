#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed model gateway for SZL vertical proposal generation.

The gateway supports an operator-configured OpenAI-compatible chat endpoint,
including a private vLLM deployment or a compatible Hugging Face endpoint. The
caller cannot choose a URL or arbitrary model: both are selected from operator
environment and the source-bound vertical registry.

No tools are sent. Tool calls are rejected. Returned text remains proposal-only
and is wrapped in request/output digests, latency, model identity, and an
explicit no-authorization/no-execution boundary.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Final, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_PROMPT_CHARS: Final = 12_000
MAX_RESPONSE_BYTES: Final = 256 * 1024
DEFAULT_TIMEOUT_SECONDS: Final = 25.0
VALID_MODES: Final = {"route_only", "openai_compatible"}
SAFE_ROLE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical_json(value)
    return hashlib.sha256(raw).hexdigest()


def _parse_hosts(value: str) -> frozenset[str]:
    hosts = {item.strip().lower() for item in value.split(",") if item.strip()}
    return frozenset(hosts or {"127.0.0.1", "localhost", "::1"})


def _safe_float(value: str, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except ValueError:
        return default
    return min(maximum, max(minimum, parsed))


def _safe_int(value: str, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError:
        return default
    return min(maximum, max(minimum, parsed))


@dataclass(frozen=True)
class InferenceConfig:
    mode: str
    base_url: str | None
    chat_path: str
    allowed_hosts: frozenset[str]
    token: str | None
    timeout_seconds: float
    max_tokens: int
    temperature: float

    @classmethod
    def from_env(cls) -> "InferenceConfig":
        mode = os.getenv("SZL_INFERENCE_MODE", "route_only").strip().lower()
        if mode not in VALID_MODES:
            mode = "route_only"
        base_url = os.getenv("SZL_INFERENCE_BASE_URL", "").strip() or None
        chat_path = os.getenv("SZL_INFERENCE_CHAT_PATH", "/v1/chat/completions").strip()
        if not chat_path.startswith("/") or "?" in chat_path or "#" in chat_path:
            chat_path = "/v1/chat/completions"
        return cls(
            mode=mode,
            base_url=base_url,
            chat_path=chat_path,
            allowed_hosts=_parse_hosts(os.getenv("SZL_INFERENCE_ALLOWED_HOSTS", "")),
            token=os.getenv("SZL_INFERENCE_TOKEN", "").strip() or None,
            timeout_seconds=_safe_float(
                os.getenv("SZL_INFERENCE_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)),
                DEFAULT_TIMEOUT_SECONDS,
                1.0,
                60.0,
            ),
            max_tokens=_safe_int(os.getenv("SZL_INFERENCE_MAX_TOKENS", "600"), 600, 64, 2048),
            temperature=_safe_float(os.getenv("SZL_INFERENCE_TEMPERATURE", "0"), 0.0, 0.0, 0.3),
        )

    def validated_endpoint(self) -> tuple[str, str]:
        if self.mode != "openai_compatible":
            raise RuntimeError("live inference mode is not enabled")
        if not self.base_url:
            raise RuntimeError("SZL_INFERENCE_BASE_URL is required for live inference")
        parsed = urlparse(self.base_url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"}:
            raise RuntimeError("inference base URL must use http or https")
        if host not in self.allowed_hosts:
            raise RuntimeError("inference host is not in SZL_INFERENCE_ALLOWED_HOSTS")
        local = host in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https" and not local:
            raise RuntimeError("non-local inference endpoints must use HTTPS")
        if not local and not self.token:
            raise RuntimeError("SZL_INFERENCE_TOKEN is required for non-local inference")
        normalized = self.base_url.rstrip("/") + "/"
        endpoint = urljoin(normalized, self.chat_path.lstrip("/"))
        endpoint_parsed = urlparse(endpoint)
        endpoint_host = (endpoint_parsed.hostname or "").lower()
        if endpoint_host != host:
            raise RuntimeError("inference chat path changed the configured host")
        return endpoint, host


class SameHostRedirects(HTTPRedirectHandler):
    def __init__(self, expected_host: str) -> None:
        super().__init__()
        self.expected_host = expected_host

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> Request | None:
        host = (urlparse(newurl).hostname or "").lower()
        if host != self.expected_host:
            raise URLError("inference redirect left the configured host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def select_model(vertical: Mapping[str, Any], preferred_role: str | None = None) -> dict[str, Any]:
    rows = vertical.get("models")
    models = [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []
    if not models:
        raise RuntimeError("vertical has no declared model route")
    role = (preferred_role or "").strip().lower()
    if role and SAFE_ROLE.fullmatch(role):
        for row in models:
            if str(row.get("role", "")).lower() == role:
                return dict(row)
    return dict(models[0])


def _evidence_lines(evidence: Any) -> list[str]:
    if not isinstance(evidence, list):
        return []
    lines: list[str] = []
    for index, row in enumerate(evidence[:12], start=1):
        if not isinstance(row, Mapping):
            continue
        source = str(row.get("source", "unknown"))[:120]
        claim = str(row.get("claim", ""))[:900]
        digest = str(row.get("sha256", ""))[:64]
        observed = str(row.get("observed_at", ""))[:64]
        lines.append(
            f"E{index} | source={source} | observed={observed or 'UNAVAILABLE'} | "
            f"sha256={digest or 'UNAVAILABLE'} | claim={claim}"
        )
    return lines


def build_messages(
    *,
    vertical: Mapping[str, Any],
    objective: str,
    requested_action: str,
    evidence: Any,
) -> list[dict[str, str]]:
    system = (
        "You are a proposal-only analyst inside the SZL governed command fabric. "
        "You may analyze evidence, identify gaps, produce alternatives, and recommend "
        "a bounded next human review step. You may not grant authorization, claim an "
        "external action occurred, call tools, invent sources, upgrade stale evidence, "
        "or conceal uncertainty. Cite supplied evidence as [E1], [E2], and so on. "
        "Separate observed facts, inferences, assumptions, counterevidence, and open "
        "questions. End with the exact sentence: AUTHORIZATION: NONE."
    )
    context = {
        "vertical": vertical.get("name"),
        "category": vertical.get("category"),
        "promise": vertical.get("promise"),
        "operating_wedge": vertical.get("unserved_wedge"),
        "prohibited": vertical.get("prohibited", []),
        "requested_action": requested_action,
        "objective": objective,
    }
    evidence_lines = _evidence_lines(evidence)
    user = (
        "SOURCE-BOUND VERTICAL CONTEXT\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
        + "\n\nADMISSIBLE EVIDENCE\n"
        + ("\n".join(evidence_lines) if evidence_lines else "NONE")
        + "\n\nReturn these sections: Observed evidence; Analysis; Counterevidence and gaps; "
        "Bounded recommendation; Required human decision; Receipt note."
    )
    if len(system) + len(user) > MAX_PROMPT_CHARS:
        overflow = len(system) + len(user) - MAX_PROMPT_CHARS
        user = user[:-overflow] if overflow < len(user) else user[:1000]
        user += "\n[INPUT TRUNCATED AT GOVERNED PROMPT BOUND]"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def route_only_result(
    *,
    vertical: Mapping[str, Any],
    model: Mapping[str, Any],
    messages: Sequence[Mapping[str, str]],
    reason: str,
) -> dict[str, Any]:
    body = {
        "schema": "szl.model-proposal.v1",
        "state": "ROUTE_ONLY",
        "vertical": vertical.get("slug"),
        "model": model.get("id"),
        "model_role": model.get("role"),
        "request_sha256": sha256(messages),
        "content": None,
        "content_sha256": None,
        "tool_calls": [],
        "authorization": "NONE",
        "execution_performed": False,
        "proposal_only": True,
        "reason": reason,
    }
    return {**body, "gateway_receipt_sha256": sha256(body)}


def propose(
    *,
    vertical: Mapping[str, Any],
    objective: str,
    requested_action: str,
    evidence: Any,
    preferred_role: str | None = None,
    config: InferenceConfig | None = None,
) -> dict[str, Any]:
    """Route or execute a bounded model proposal against operator configuration."""
    selected = select_model(vertical, preferred_role)
    messages = build_messages(
        vertical=vertical,
        objective=objective,
        requested_action=requested_action,
        evidence=evidence,
    )
    runtime = config or InferenceConfig.from_env()
    if runtime.mode != "openai_compatible":
        return route_only_result(
            vertical=vertical,
            model=selected,
            messages=messages,
            reason="Live inference is disabled; the source-bound model route is disclosed without fabricating output.",
        )

    try:
        endpoint, endpoint_host = runtime.validated_endpoint()
    except RuntimeError as exc:
        return route_only_result(
            vertical=vertical,
            model=selected,
            messages=messages,
            reason=f"Inference unavailable: {exc}",
        )

    request_payload = {
        "model": selected.get("id"),
        "messages": messages,
        "temperature": runtime.temperature,
        "max_tokens": runtime.max_tokens,
        "stream": False,
        "tools": [],
    }
    raw_request = canonical_json(request_payload)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "SZL-Vertical-Frontier/1.0",
    }
    if runtime.token:
        headers["Authorization"] = f"Bearer {runtime.token}"
    request = Request(endpoint, data=raw_request, headers=headers, method="POST")
    opener = build_opener(SameHostRedirects(endpoint_host))
    started = time.perf_counter()
    try:
        with opener.open(request, timeout=runtime.timeout_seconds) as response:
            raw_response = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw_response) > MAX_RESPONSE_BYTES:
                raise ValueError("inference response exceeded 256 KiB")
            content_type = response.headers.get("Content-Type", "")
            if "json" not in content_type.lower() and not raw_response.lstrip().startswith(b"{"):
                raise ValueError("inference endpoint did not return JSON")
            document = json.loads(raw_response.decode("utf-8"))
    except HTTPError as exc:
        return route_only_result(
            vertical=vertical,
            model=selected,
            messages=messages,
            reason=f"Inference endpoint returned HTTP {exc.code}; no output was fabricated.",
        )
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return route_only_result(
            vertical=vertical,
            model=selected,
            messages=messages,
            reason=f"Inference endpoint unavailable or invalid ({type(exc).__name__}); no output was fabricated.",
        )
    latency = time.perf_counter() - started

    choices = document.get("choices") if isinstance(document, Mapping) else None
    first = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], Mapping) else {}
    message = first.get("message") if isinstance(first, Mapping) else None
    message = message if isinstance(message, Mapping) else {}
    content = message.get("content")
    tool_calls = message.get("tool_calls")
    if not isinstance(content, str) or not content.strip():
        return route_only_result(
            vertical=vertical,
            model=selected,
            messages=messages,
            reason="Inference response contained no usable text; no output was fabricated.",
        )
    if tool_calls:
        body = route_only_result(
            vertical=vertical,
            model=selected,
            messages=messages,
            reason="Provider returned tool calls; the gateway rejected them.",
        )
        body["state"] = "MODEL_TOOL_CALLS_REFUSED"
        body["tool_calls"] = ["REDACTED_AND_REFUSED"]
        body["gateway_receipt_sha256"] = sha256({key: value for key, value in body.items() if key != "gateway_receipt_sha256"})
        return body

    usage = document.get("usage") if isinstance(document, Mapping) else None
    safe_usage = {
        "prompt_tokens": usage.get("prompt_tokens") if isinstance(usage, Mapping) else None,
        "completion_tokens": usage.get("completion_tokens") if isinstance(usage, Mapping) else None,
        "total_tokens": usage.get("total_tokens") if isinstance(usage, Mapping) else None,
    }
    body = {
        "schema": "szl.model-proposal.v1",
        "state": "INFERENCE_LIVE",
        "vertical": vertical.get("slug"),
        "model": selected.get("id"),
        "model_role": selected.get("role"),
        "endpoint_host": endpoint_host,
        "request_sha256": hashlib.sha256(raw_request).hexdigest(),
        "content": content.strip()[:65_536],
        "content_sha256": hashlib.sha256(content.strip().encode("utf-8")).hexdigest(),
        "finish_reason": first.get("finish_reason"),
        "usage": safe_usage,
        "latency_seconds": round(latency, 6),
        "tool_calls": [],
        "authorization": "NONE",
        "execution_performed": False,
        "proposal_only": True,
        "provider_response_sha256": hashlib.sha256(raw_response).hexdigest(),
    }
    return {**body, "gateway_receipt_sha256": sha256(body)}


def capabilities(config: InferenceConfig | None = None) -> dict[str, Any]:
    runtime = config or InferenceConfig.from_env()
    endpoint_state = "ROUTE_ONLY"
    host: str | None = None
    reason: str | None = None
    if runtime.mode == "openai_compatible":
        try:
            _, host = runtime.validated_endpoint()
            endpoint_state = "CONFIGURED"
        except RuntimeError as exc:
            endpoint_state = "CONFIGURATION_REQUIRED"
            reason = str(exc)
    return {
        "schema": "szl.model-gateway-capabilities.v1",
        "mode": runtime.mode,
        "state": endpoint_state,
        "endpoint_host": host,
        "allowed_hosts": sorted(runtime.allowed_hosts),
        "token_present": bool(runtime.token),
        "tools_enabled": False,
        "arbitrary_model_selection": False,
        "arbitrary_url_selection": False,
        "authorization": "NONE",
        "execution_performed": False,
        "reason": reason,
    }


def self_test() -> dict[str, Any]:
    vertical = {
        "slug": "a11oy",
        "name": "A11oy",
        "category": "Governed AI",
        "promise": "Bound proposals.",
        "unserved_wedge": "Decision receipts.",
        "prohibited": ["self authorization"],
        "models": [{"id": "SZLHOLDINGS/szl-nemo", "role": "planner", "execution": "PROPOSAL_ONLY"}],
    }
    result = propose(
        vertical=vertical,
        objective="inspect evidence",
        requested_action="prepare a recommendation",
        evidence=[{"source": "test", "claim": "bounded fact"}],
        config=InferenceConfig(
            mode="route_only",
            base_url=None,
            chat_path="/v1/chat/completions",
            allowed_hosts=frozenset({"localhost"}),
            token=None,
            timeout_seconds=1.0,
            max_tokens=64,
            temperature=0.0,
        ),
    )
    assert result["state"] == "ROUTE_ONLY"
    assert result["model"] == "SZLHOLDINGS/szl-nemo"
    assert result["authorization"] == "NONE"
    assert result["execution_performed"] is False
    assert result["content"] is None
    return {"ok": True, "gateway_receipt_sha256": result["gateway_receipt_sha256"]}


if __name__ == "__main__":
    print(json.dumps(self_test(), indent=2))
