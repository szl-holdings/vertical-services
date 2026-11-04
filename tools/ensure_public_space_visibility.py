#!/usr/bin/env python3
"""Ensure the vertical-services Space stays public for the public smoke contract.

Public application probes in the shared Dockerfile publisher never attach Hub
authentication. A private Space therefore returns provider marketing HTTP 404
HTML and fails attest even when the container is RUNNING. This helper measures
visibility, sets private=False when needed, and records a receipt.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_REPO = "SZLHOLDINGS/vertical-services"
DEFAULT_ORIGIN = "https://szlholdings-vertical-services.hf.space"
SCHEMA = "szl.hf-space-public-visibility/v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _origin_for(repo_id: str) -> str:
    owner, _, name = repo_id.partition("/")
    if not owner or not name:
        raise ValueError(f"HF Space id must be owner/name: {repo_id!r}")
    slug = f"{owner}-{name}".lower().replace("_", "-")
    return f"https://{slug}.hf.space"


def measure_private(api: Any, repo_id: str) -> bool | None:
    info = api.space_info(repo_id)
    return getattr(info, "private", None)


def ensure_public(api: Any, repo_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    before = measure_private(api, repo_id)
    mutated = False
    if before is True:
        if dry_run:
            after = True
        else:
            api.update_repo_settings(repo_id=repo_id, repo_type="space", private=False)
            after = measure_private(api, repo_id)
            mutated = True
    else:
        after = before
    return {
        "repo_id": repo_id,
        "private_before": before,
        "private_after": after,
        "visibility_mutated": mutated,
        "public": after is False,
    }


def probe_unauthenticated(origin: str, path: str = "/healthz", timeout: float = 30.0) -> dict[str, Any]:
    url = origin.rstrip("/") + path
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return {
                "url": url,
                "status": int(response.status),
                "bytes": len(body),
                "authorization_sent": False,
                "ok": int(response.status) == 200 and len(body) > 0,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else b""
        try:
            payload = body if isinstance(body, (bytes, bytearray)) else b""
        except Exception:
            payload = b""
        return {
            "url": url,
            "status": int(exc.code),
            "bytes": len(payload),
            "authorization_sent": False,
            "ok": False,
        }
    except Exception as exc:  # noqa: BLE001 - receipt must name transport failure
        return {
            "url": url,
            "status": None,
            "bytes": 0,
            "authorization_sent": False,
            "ok": False,
            "error_kind": type(exc).__name__,
        }


def build_receipt(
    *,
    repo_id: str,
    visibility: dict[str, Any],
    probe: dict[str, Any],
    source_revision: str,
) -> dict[str, Any]:
    public_ok = bool(visibility.get("public")) and bool(probe.get("ok"))
    return {
        "schema": SCHEMA,
        "observed_at": _utc_now(),
        "source_repository": "szl-holdings/vertical-services",
        "source_revision": source_revision,
        "hf_repository": repo_id,
        "visibility": visibility,
        "public_probe": probe,
        "public_smoke_ready": public_ok,
        "truth_label": "MEASURED",
        "credential_value_recorded": False,
        "known_limits": [
            "Public smoke never attaches Hub Authorization; private Spaces fail that contract.",
            "This helper does not attest application semantics beyond unauthenticated HTTP 200.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default=DEFAULT_REPO)
    parser.add_argument("--origin", default="")
    parser.add_argument("--probe-path", default="/healthz")
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-revision", default=os.environ.get("GITHUB_SHA", "REVISION_UNAVAILABLE"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--require-public-probe", action="store_true", default=True)
    parser.add_argument("--allow-failed-probe", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    token = os.environ.get("HF_TOKEN", "")
    if not token and not args.dry_run:
        print("::error::HF_TOKEN is required to measure and enforce Space visibility", file=sys.stderr)
        return 2

    from huggingface_hub import HfApi

    api = HfApi(token=token or None)
    visibility = ensure_public(api, args.repo_id, dry_run=args.dry_run)
    origin = args.origin or _origin_for(args.repo_id)
    probe = probe_unauthenticated(origin, args.probe_path)
    receipt = build_receipt(
        repo_id=args.repo_id,
        visibility=visibility,
        probe=probe,
        source_revision=args.source_revision,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"public": visibility.get("public"), "probe_ok": probe.get("ok"), "output": str(out)}))

    if visibility.get("private_after") is not False:
        print("::error::Space remains private after ensure-public; public smoke cannot pass", file=sys.stderr)
        return 1
    if args.require_public_probe and not args.allow_failed_probe and not probe.get("ok"):
        # Visibility is enforced even when the app is still booting; publish will wait for RUNNING.
        print(
            "::warning::Unauthenticated probe is not ready yet; visibility is public and attest will wait for RUNNING",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
