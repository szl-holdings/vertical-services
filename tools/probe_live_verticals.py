#!/usr/bin/env python3
"""Exercise every required official-source connector through the deployed runtime.

The generated X-SZL-Session token is kept in process memory and never printed.
The report contains only source-safe receipts, normalized signals, readiness,
and endpoint status.
"""
from __future__ import annotations

import argparse
import json
import secrets
import time
from pathlib import Path
from typing import Any

import httpx

PROBES = (
    ("sentra", "cisa-kev", {"limit": 3}),
    ("lyte", "github-actions", {"repository": "vertical-services", "limit": 10}),
    ("killinchu", "noaa-ais-2025", {}),
    ("finance", "sec-submissions", {"cik": "320193", "limit": 3}),
    ("terra", "nyc-pluto", {"borough": "MN", "limit": 1}),
    ("counsel", "federal-register", {"limit": 3}),
)


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = client.request(method, url, **kwargs)
            if response.status_code < 500:
                return response
            last = RuntimeError(f"upstream returned {response.status_code}")
        except httpx.HTTPError as exc:
            last = exc
        if attempt < 3:
            time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"request did not converge after three attempts: {type(last).__name__}")


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
        "schema": "szl.live-connector-probe/v2",
        "base_url": base,
        "observed_at": time.time(),
        "probes": [],
        "session_token_recorded": False,
        "truth_label": "MEASURED",
    }
    failures: list[str] = []

    with httpx.Client(
        timeout=httpx.Timeout(75.0, connect=15.0),
        follow_redirects=False,
        headers={"X-SZL-Session": session, "User-Agent": "SZL-Live-Probe/2.0"},
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
                item["body_excerpt"] = response.text[:500]
                failures.append(f"{vertical}/{connector}: HTTP {response.status_code}")
            else:
                body = response.json()
                receipt = body.get("receipt", {})
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
                if (
                    item["state"] != "OBSERVED"
                    or not isinstance(item["receipt_id"], str)
                    or len(item["receipt_id"]) != 64
                    or not isinstance(item["payload_sha256"], str)
                    or len(item["payload_sha256"]) != 64
                ):
                    failures.append(f"{vertical}/{connector}: invalid observation receipt")
            report["probes"].append(item)

        vertical_readiness: dict[str, Any] = {}
        for vertical, _, _ in PROBES:
            response = request_with_retry(
                client,
                "GET",
                f"{base}/api/verticals/{vertical}/readyz",
            )
            if response.status_code != 200:
                failures.append(f"{vertical}: readiness HTTP {response.status_code}")
                vertical_readiness[vertical] = {
                    "http_status": response.status_code,
                    "body_excerpt": response.text[:500],
                }
                continue
            body = response.json()
            vertical_readiness[vertical] = {
                "http_status": response.status_code,
                "ready": body.get("ready"),
                "status": body.get("status"),
                "live_data": body.get("live_data"),
                "build": body.get("build"),
                "lambda_advisory": body.get("lambda_advisory"),
            }
            if not body.get("live_data", {}).get("observed_in_scope"):
                failures.append(f"{vertical}: required live observation not visible")

        root = request_with_retry(client, "GET", f"{base}/readyz")
        report["vertical_readiness"] = vertical_readiness
        report["root_readiness"] = {
            "http_status": root.status_code,
            "body": root.json() if root.headers.get("content-type", "").startswith("application/json") else root.text[:500],
        }

    report["status"] = "PASS" if not failures else "FAIL"
    report["failures"] = failures
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "probes": len(PROBES), "report": str(output)}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
