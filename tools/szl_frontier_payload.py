#!/usr/bin/env python3
"""Verify or restart the governed SZL vertical runtime without destructive actions.

This replaces the original one-shot payload's direct overwrites and Space-deletion
path. Production publication is handled by GitHub Actions from protected `main`.
The operator tool is intentionally limited to public verification and an optional,
explicit restart of only SZLHOLDINGS/vertical-services.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ORG = "SZLHOLDINGS"
COMBINED = "vertical-services"
FLAGSHIPS = ("a11oy", "killinchu", "terra", "sentra", "counsel", "finance", "vessels", "lyte", "david-leads")
RECEIPT_SCHEMA = "szl.frontier-verification/v2"
USER_AGENT = "SZL-Frontier-Operator/2.0"


def origin(slug: str) -> str:
    return f"https://{ORG.lower()}-{slug}.hf.space"


def get_json(url: str, timeout: float = 20.0) -> tuple[int | None, Any, str | None]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Cache-Control": "no-cache", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("content-type", "")
            body = response.read()
            if "json" not in content_type.lower():
                return response.status, None, f"non-JSON content-type: {content_type}"
            return response.status, json.loads(body), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, f"HTTP {exc.code}"
    except Exception as exc:  # bounded evidence capture
        return None, None, f"{type(exc).__name__}: {exc}"


def probe(slug: str, path: str = "/healthz") -> dict[str, Any]:
    url = origin(slug) + path
    started = time.monotonic()
    status, payload, error = get_json(url)
    ok = status == 200 and isinstance(payload, dict)
    return {
        "slug": slug,
        "url": url,
        "http_status": status,
        "latency_ms": round((time.monotonic() - started) * 1000, 1),
        "ok": ok,
        "payload": payload,
        "error": error,
    }


def verify(receipt_path: Path) -> bool:
    targets = [(COMBINED, "/healthz"), (COMBINED, "/readyz"), (COMBINED, "/api/build-info")]
    targets.extend((slug, "/healthz") for slug in FLAGSHIPS)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(12, len(targets))) as pool:
        rows = list(pool.map(lambda item: probe(*item), targets))
    complete = all(row["ok"] for row in rows)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "complete": complete,
        "targets": len(rows),
        "healthy": sum(1 for row in rows if row["ok"]),
        "boundaries": [
            "No Hugging Face repository content was changed.",
            "No Space was deleted, paused, made private, or reconfigured.",
            "Vessels is retained as a historical Space; Killinchu is its public product home.",
        ],
        "rows": rows,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return complete


def restart_combined() -> None:
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise SystemExit("HF_TOKEN with write access is required for --restart-combined")
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.auth_check(repo_id=f"{ORG}/{COMBINED}", repo_type="space", write=True)
    api.restart_space(repo_id=f"{ORG}/{COMBINED}")
    print(f"Restart requested for {ORG}/{COMBINED}; no other Space was changed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restart-combined", action="store_true")
    parser.add_argument("--receipt", type=Path, default=Path("szl-frontier-verification.json"))
    args = parser.parse_args()
    if args.restart_combined:
        restart_combined()
    return 0 if verify(args.receipt) else 1


if __name__ == "__main__":
    raise SystemExit(main())
