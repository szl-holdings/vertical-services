#!/usr/bin/env python3
"""Exercise the complete public-source and command-surface frontier.

The generated X-SZL-Session token is kept in process memory and never printed.
The report contains source-safe receipts, normalized signals, readiness,
source identity, alias resolution, and public-experience status. No connector
in this probe places an order, holds custody, or triggers an effector.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit, urlunsplit

import httpx

PROBES = (
    ("sentra", "cisa-kev", {"limit": 3}),
    ("lyte", "github-actions", {"repository": "vertical-services", "limit": 10}),
    ("killinchu", "noaa-ais-2025", {}),
    ("finance", "sec-submissions", {"cik": "320193", "limit": 3}),
    ("finance", "polymarket-markets", {"limit": 5}),
    ("finance", "coinbase-spot", {"base": "BTC", "currency": "USD"}),
    ("finance", "treasury-average-rates", {"limit": 5}),
    ("terra", "nyc-pluto", {"borough": "MN", "limit": 1}),
    ("terra", "nyc-hpd-violations", {"limit": 5}),
    ("terra", "nyc-dob-violations", {"limit": 5}),
    ("counsel", "federal-register", {"limit": 3}),
)

EXPERIENCES = {
    "defend": ("sentra", "Killinchu Defend Plane", "threat-shield"),
    "lyte": ("lyte", "Lyte Signal Lattice", "service-lattice"),
    "killinchu": ("killinchu", "Killinchu Voyage Radar", "voyage-radar"),
    "puriq": ("finance", "PURIQ Market Chamber", "probability-orbit"),
    "terra": ("terra", "Terra Parcel Loom", "parcel-grid"),
    "prism": ("counsel", "PRISM Authority Chain", "authority-chain"),
}


def _safe_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", ""))


def _response_evidence(response: httpx.Response) -> dict[str, Any]:
    prefix = response.content[:4096]
    return {
        "http_status": response.status_code,
        "body_bytes": len(response.content),
        "body_prefix_bytes": len(prefix),
        "body_prefix_sha256": hashlib.sha256(prefix).hexdigest(),
        "body_prefix_truncated": len(response.content) > len(prefix),
        "body_recorded": False,
    }


class ProbeResponseFailure(RuntimeError):
    def __init__(
        self, response: httpx.Response, stage: str, classification: str,
    ) -> None:
        super().__init__("response did not satisfy the JSON contract")
        self.record = {
            "state": "INVALID_RESPONSE",
            "stage": stage,
            "method": response.request.method,
            "url": _safe_url(str(response.request.url)),
            "attempts": [{
                "attempt": 1,
                "classification": classification,
                **_response_evidence(response),
            }],
            "headers_recorded": False,
            "request_body_recorded": False,
        }


def _json_object(response: httpx.Response, stage: str) -> dict[str, Any]:
    media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise ProbeResponseFailure(response, stage, "UNEXPECTED_CONTENT_TYPE")
    try:
        body = response.json()
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ProbeResponseFailure(response, stage, "MALFORMED_JSON") from None
    if not isinstance(body, dict):
        raise ProbeResponseFailure(response, stage, "NON_OBJECT_JSON")
    return body


def _object_field(
    body: dict[str, Any], field: str, response: httpx.Response, stage: str,
) -> dict[str, Any]:
    value = body.get(field, {})
    if not isinstance(value, dict):
        raise ProbeResponseFailure(response, stage, "INVALID_JSON_FIELD")
    return value


class ProbeRequestFailure(RuntimeError):
    def __init__(self, method: str, url: str, attempts: list[dict[str, Any]]) -> None:
        super().__init__("request did not converge after three attempts")
        self.record = {
            "state": "UNAVAILABLE",
            "method": method,
            "url": _safe_url(url),
            "attempts": attempts,
            "headers_recorded": False,
            "request_body_recorded": False,
        }


@contextmanager
def _capture_probe_failure(
    report: dict[str, Any], failures: list[str],
) -> Iterator[None]:
    try:
        yield
    except ProbeRequestFailure as exc:
        report["request_failure"] = exc.record
        report["stopped_before_remaining_requests"] = True
        failures.append("request convergence unavailable")
    except ProbeResponseFailure as exc:
        report["response_failure"] = exc.record
        report["stopped_before_remaining_requests"] = True
        failures.append("JSON response contract invalid")


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, 4):
        try:
            response = client.request(method, url, **kwargs)
            if response.status_code < 500:
                return response
            attempts.append({
                "attempt": attempt,
                "classification": "UPSTREAM_5XX",
                **_response_evidence(response),
            })
        except httpx.HTTPError as exc:
            attempts.append({
                "attempt": attempt,
                "classification": "TRANSPORT_ERROR",
                "error_type": type(exc).__name__,
                "http_status": None,
                "exception_message_recorded": False,
            })
        if attempt < 3:
            time.sleep(2 ** (attempt - 1))
    raise ProbeRequestFailure(method, url, attempts)


def _receipt_valid(item: dict[str, Any]) -> bool:
    return (
        item.get("state") == "OBSERVED"
        and isinstance(item.get("receipt_id"), str)
        and len(item["receipt_id"]) == 64
        and isinstance(item.get("payload_sha256"), str)
        and len(item["payload_sha256"]) == 64
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="https://szlholdings-vertical-services.hf.space",
    )
    parser.add_argument(
        "--output",
        default="artifacts/live-connector-probe.json",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    session = secrets.token_urlsafe(32)
    report: dict[str, Any] = {
        "schema": "szl.live-frontier-probe/v3",
        "base_url": _safe_url(base),
        "observed_at": time.time(),
        "probes": [],
        "experiences": [],
        "frontier_contracts": [],
        "session_token_recorded": False,
        "trading_enabled": False,
        "custody_enabled": False,
        "effectors_enabled": False,
        "truth_label": "MEASURED",
    }
    failures: list[str] = []

    with _capture_probe_failure(report, failures), httpx.Client(
        timeout=httpx.Timeout(75.0, connect=15.0),
        follow_redirects=False,
        headers={
            "X-SZL-Session": session,
            "User-Agent": "SZL-Live-Frontier-Probe/3.0",
        },
    ) as client:
        for vertical, connector, parameters in PROBES:
            path = f"/api/verticals/{vertical}/connectors/{connector}/fetch"
            response = request_with_retry(
                client,
                "POST",
                f"{base}{path}",
                json={"parameters": parameters, "force_refresh": True},
            )
            item: dict[str, Any] = {
                "vertical": vertical,
                "connector": connector,
                "path": path,
                "http_status": response.status_code,
            }
            if response.status_code != 200:
                item["state"] = "FAILED"
                item["response_evidence"] = _response_evidence(response)
                failures.append(f"{vertical}/{connector}: HTTP {response.status_code}")
            else:
                body = _json_object(response, "connector_fetch")
                receipt = _object_field(body, "receipt", response, "connector_fetch")
                item.update(
                    {
                        "state": receipt.get("state"),
                        "receipt_id": receipt.get("receipt_id"),
                        "payload_sha256": receipt.get("payload_sha256"),
                        "source_url": receipt.get("source_url"),
                        "signal": body.get("signal"),
                        "cache": body.get("cache"),
                    }
                )
                if not _receipt_valid(item):
                    failures.append(
                        f"{vertical}/{connector}: invalid observation receipt"
                    )
                if connector in {"polymarket-markets", "coinbase-spot"}:
                    observation = _object_field(
                        body, "observation", response, "connector_fetch"
                    )
                    if observation.get("trading_enabled") is not False:
                        failures.append(f"{connector}: trading boundary missing")
                    if observation.get("custody_enabled") is not False:
                        failures.append(f"{connector}: custody boundary missing")
                if connector in {"nyc-hpd-violations", "nyc-dob-violations"}:
                    observation = _object_field(
                        body, "observation", response, "connector_fetch"
                    )
                    if observation.get("person_level_prospecting") is not False:
                        failures.append(
                            f"{connector}: person-level prospecting boundary missing"
                        )
            report["probes"].append(item)

        canonical_verticals = tuple(
            dict.fromkeys(vertical for vertical, _, _ in PROBES)
        )
        vertical_readiness: dict[str, Any] = {}
        report["vertical_readiness"] = vertical_readiness
        for vertical in canonical_verticals:
            response = request_with_retry(
                client,
                "GET",
                f"{base}/api/verticals/{vertical}/readyz",
            )
            if response.status_code != 200:
                failures.append(f"{vertical}: readiness HTTP {response.status_code}")
                vertical_readiness[vertical] = {
                    "http_status": response.status_code,
                    "response_evidence": _response_evidence(response),
                }
                continue
            body = _json_object(response, "vertical_readiness")
            live_data = _object_field(
                body, "live_data", response, "vertical_readiness"
            )
            vertical_readiness[vertical] = {
                "http_status": response.status_code,
                "ready": body.get("ready"),
                "status": body.get("status"),
                "live_data": body.get("live_data"),
                "build": body.get("build"),
                "lambda_advisory": body.get("lambda_advisory"),
            }
            if body.get("ready") is not True:
                failures.append(f"{vertical}: readiness is not true")
            if not live_data.get("observed_in_scope"):
                failures.append(f"{vertical}: live observation not visible")

        for alias, (canonical, title, motif) in EXPERIENCES.items():
            path = f"/experience/{alias}"
            response = request_with_retry(client, "GET", f"{base}{path}")
            item = {
                "alias": alias,
                "canonical": canonical,
                "path": path,
                "http_status": response.status_code,
                "title_observed": title in response.text,
                "motif_observed": f'data-motif="{motif}"' in response.text,
                "viewport_observed": "viewport-fit=cover" in response.text,
                "reduced_motion_observed": (
                    "@media(prefers-reduced-motion:reduce)" in response.text
                ),
            }
            if response.status_code != 200 or not all(
                item[key]
                for key in (
                    "title_observed",
                    "motif_observed",
                    "viewport_observed",
                    "reduced_motion_observed",
                )
            ):
                failures.append(f"experience/{alias}: contract mismatch")
            report["experiences"].append(item)

            contract_path = f"/api/verticals/{alias}/frontier"
            contract_response = request_with_retry(
                client,
                "GET",
                f"{base}{contract_path}",
            )
            contract: dict[str, Any] = {
                "alias": alias,
                "path": contract_path,
                "http_status": contract_response.status_code,
            }
            if contract_response.status_code == 200:
                body = _json_object(contract_response, "frontier_contract")
                source = _object_field(
                    body, "source", contract_response, "frontier_contract"
                )
                build = _object_field(
                    source, "build", contract_response, "frontier_contract"
                )
                hatun = _object_field(
                    body, "hatun", contract_response, "frontier_contract"
                )
                contract.update(
                    {
                        "canonical": body.get("vertical"),
                        "source_revision": build.get("revision"),
                        "hatun_can_authorize": hatun.get("can_authorize"),
                        "effectors_enabled": hatun.get("effectors_enabled"),
                    }
                )
                if (
                    contract["canonical"] != canonical
                    or contract["hatun_can_authorize"] is not False
                    or contract["effectors_enabled"] is not False
                ):
                    failures.append(f"frontier/{alias}: authority boundary mismatch")
            else:
                contract["response_evidence"] = _response_evidence(contract_response)
                failures.append(
                    f"frontier/{alias}: HTTP {contract_response.status_code}"
                )
            report["frontier_contracts"].append(contract)

        root = request_with_retry(client, "GET", f"{base}/readyz")
        root_body = _json_object(root, "root_readiness") if root.status_code == 200 else {}
        report["root_readiness"] = {
            "http_status": root.status_code,
            "body": root_body,
        }
        if root.status_code != 200:
            report["root_readiness"]["response_evidence"] = _response_evidence(root)
        build_info = request_with_retry(client, "GET", f"{base}/api/build-info")
        build_body = (
            _json_object(build_info, "build_info")
            if build_info.status_code == 200 else {}
        )
        build: dict[str, Any] = {}
        source_binding: dict[str, Any] = {}
        if build_info.status_code == 200:
            build = _object_field(build_body, "build", build_info, "build_info")
            source_binding = _object_field(
                build_body, "source_binding", build_info, "build_info"
            )
        report["build_info"] = {
            "http_status": build_info.status_code,
            "body": build_body,
        }
        if build_info.status_code != 200:
            report["build_info"]["response_evidence"] = _response_evidence(build_info)
        if root.status_code != 200 or root_body.get("ready") is not True:
            failures.append("root readiness is not closed")
        if (
            build_info.status_code != 200
            or build.get("state") != "OBSERVED"
            or source_binding.get("bindings_agree") is not True
        ):
            failures.append("build source identity is not closed")

    report["status"] = "PASS" if not failures else "FAIL"
    report["complete"] = not failures
    report["failures"] = failures
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "probes": len(report["probes"]),
                "experiences": len(report["experiences"]),
                "report": str(output),
            }
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
