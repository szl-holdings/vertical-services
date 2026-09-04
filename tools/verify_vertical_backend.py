#!/usr/bin/env python3
"""Verify one canonical vertical backend without external network access."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))

os.environ.setdefault("SENTRA_SIGNING_KEY", "ci-contract-key-not-used-in-production")
os.environ.setdefault("SZL_SOURCE_REVISION", "f" * 40)
os.environ.setdefault("SZL_STATE_PATH", "/tmp/szl-vertical-services-ci.sqlite3")

from app import app  # noqa: E402
from szl_verticals.core import ENGINES  # noqa: E402


def require(response, expected: int = 200):
    if response.status_code != expected:
        raise RuntimeError(
            f"{response.request.method} {response.request.url.path}: "
            f"expected {expected}, got {response.status_code}: {response.text[:500]}"
        )
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", required=True, choices=ENGINES)
    args = parser.parse_args()

    token = secrets.token_urlsafe(32)
    client = TestClient(app, headers={"X-SZL-Session": token})
    vertical = args.vertical

    health = require(client.get(f"/{vertical}/healthz"))
    anatomy = require(client.get(f"/api/verticals/{vertical}/anatomy"))
    formulas = require(client.get(f"/api/verticals/{vertical}/formulas"))
    connectors = require(client.get(f"/api/verticals/{vertical}/connectors"))
    readiness = require(client.get(f"/api/verticals/{vertical}/readyz"))
    brain = require(client.get(f"/api/verticals/{vertical}/second-brain"))

    if health["service"] != vertical:
        raise RuntimeError("health service identity mismatch")
    if len(anatomy["organs"]) != 9:
        raise RuntimeError("Living Anatomy must expose exactly nine ordered organs")
    if formulas["count"] < 1:
        raise RuntimeError("formula binding is empty")
    if connectors["count"] < 1:
        raise RuntimeError("official-source connector binding is empty")
    if connectors["caller_supplied_urls_allowed"]:
        raise RuntimeError("caller-supplied connector URLs must remain disabled")
    if not readiness["requirements"]["source_bound"]:
        raise RuntimeError("source binding is not observed")
    if not readiness["requirements"]["observation_store_writable"]:
        raise RuntimeError("observation store is not writable")
    if brain["effectors_enabled"]:
        raise RuntimeError("public effectors must remain disabled")
    if vertical == "killinchu":
        if anatomy["consolidation"]["vessels_status"] != "CONSOLIDATED":
            raise RuntimeError("Vessels is not consolidated into Killinchu")
        if health["vessels"]["independent_vertical"]:
            raise RuntimeError("Vessels must not remain an independent vertical")

    print(
        json.dumps(
            {
                "vertical": vertical,
                "status": "PASS",
                "health": health["status"],
                "organs": len(anatomy["organs"]),
                "formulas": formulas["count"],
                "connectors": connectors["count"],
                "source_bound": readiness["requirements"]["source_bound"],
                "store": readiness["store"]["durability"],
                "effectors_enabled": brain["effectors_enabled"],
                "truth_label": "MEASURED",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
