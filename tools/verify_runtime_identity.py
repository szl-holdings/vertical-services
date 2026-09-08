#!/usr/bin/env python3
"""Verify source/runtime identity parity without exercising effectful routes."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any

IDENTITY_PATHS = (
    "/healthz",
    "/api/build-info",
    "/api/source",
    "/.well-known/szl-source.json",
)
IDENTITY_FIELDS = (
    "source_repository",
    "source_revision",
    "runtime_repository",
    "runtime_source_revision",
    "effectors_enabled",
    "human_approval_required",
)
SOURCE_REPOSITORY = "szl-holdings/vertical-services"
RUNTIME_REPOSITORY = SOURCE_REPOSITORY
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _get_json(url: str, *, timeout: float, attempts: int) -> dict[str, Any]:
    last_error = "request was not attempted"
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "SZL-Runtime-Identity-Verifier/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = response.status
                raw = response.read()
            if status != 200:
                last_error = f"HTTP {status}"
            else:
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("response JSON was not an object")
                return payload
        except (
            OSError,
            UnicodeDecodeError,
            ValueError,
            json.JSONDecodeError,
            urllib.error.HTTPError,
            urllib.error.URLError,
        ) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < attempts:
            time.sleep(min(2 ** (attempt - 1), 4))
    raise RuntimeError(f"{url}: {last_error}")


def validate_identity_documents(
    documents: dict[str, dict[str, Any]],
    *,
    expected_revision: str,
) -> list[str]:
    """Return all tuple, safety, and nested-build validation failures."""
    failures: list[str] = []
    expected = {
        "source_repository": SOURCE_REPOSITORY,
        "source_revision": expected_revision,
        "runtime_repository": RUNTIME_REPOSITORY,
        "runtime_source_revision": expected_revision,
        "effectors_enabled": False,
        "human_approval_required": True,
    }
    baseline: dict[str, Any] | None = None
    for path in IDENTITY_PATHS:
        body = documents.get(path)
        if body is None:
            failures.append(f"{path}: document missing")
            continue
        identity = {field: body.get(field) for field in IDENTITY_FIELDS}
        if baseline is None:
            baseline = identity
        elif identity != baseline:
            failures.append(f"{path}: identity tuple differs from /healthz")
        for field, value in expected.items():
            actual = identity[field]
            matches = actual is value if isinstance(value, bool) else actual == value
            if not matches:
                failures.append(f"{path}: {field} mismatch")
        build = body.get("build")
        if not isinstance(build, dict):
            failures.append(f"{path}: nested build object missing")
        elif build.get("state") != "OBSERVED" or build.get("revision") != expected_revision:
            failures.append(f"{path}: nested build observation mismatch")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()

    expected_revision = args.expected_revision.strip().lower()
    if SHA40.fullmatch(expected_revision) is None:
        parser.error("--expected-revision must be an exact 40-character Git SHA")
    if args.timeout <= 0 or args.attempts <= 0:
        parser.error("--timeout and --attempts must be positive")

    base_url = args.base_url.rstrip("/")
    documents: dict[str, dict[str, Any]] = {}
    request_failures: list[str] = []
    for path in IDENTITY_PATHS:
        try:
            documents[path] = _get_json(
                f"{base_url}{path}",
                timeout=args.timeout,
                attempts=args.attempts,
            )
        except RuntimeError as exc:
            request_failures.append(str(exc))

    failures = request_failures + validate_identity_documents(
        documents,
        expected_revision=expected_revision,
    )
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    identity = {
        field: documents["/api/build-info"][field]
        for field in IDENTITY_FIELDS
    }
    print(
        json.dumps(
            {
                "schema": "szl.runtime-identity-verification/v1",
                "base_url": base_url,
                "required_paths": list(IDENTITY_PATHS),
                "identity": identity,
                "complete": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
