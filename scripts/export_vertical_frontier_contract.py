#!/usr/bin/env python3
"""Export the machine-readable SZL vertical experience and runtime contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from frontier_fabric.catalog import CATALOG_ERRORS, public_catalog
from frontier_fabric.receipts import canonical_json, sha256_hex


def build_export() -> dict[str, object]:
    if CATALOG_ERRORS:
        raise RuntimeError("catalog validation failed: " + "; ".join(CATALOG_ERRORS))
    catalog = public_catalog()
    return {
        "schema": "szl.vertical-frontier-export/v1",
        "catalog": catalog,
        "catalog_sha256": sha256_hex(catalog),
        "integrity_scope": "CANONICAL_JSON_SHA256",
        "authorization_proof": False,
        "truth_boundary": (
            "The export proves deterministic serialization of the declared contract. "
            "It does not prove provider availability, model quality, compliance, or authorization."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the export to this path. Omit to print canonical JSON to stdout.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Use indented JSON rather than the canonical compact representation.",
    )
    args = parser.parse_args()

    payload = build_export()
    if args.pretty:
        rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    else:
        rendered = canonical_json(payload) + "\n"

    if args.output is None:
        print(rendered, end="")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output} · sha256={sha256_hex(rendered)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
