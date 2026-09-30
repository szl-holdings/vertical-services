"""Export a Finance deployment projection solely from immutable Git objects.

This prepares reviewable files and a local-byte witness; it never contacts the
Hub, publishes, merges, or claims external attestation.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "finance"))
from runtime_identity import (
    RUNTIME_FILES, SOURCE_REPOSITORY, WITNESS_NAME, WITNESS_SCHEMA,
    digest_records, record_for,
)


def export(repo: Path, revision: str, output: Path) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("revision must be an exact lowercase 40-character Git SHA")
    resolved = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", revision + "^{commit}"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if resolved != revision:
        raise ValueError("revision did not resolve exactly")
    # Read and validate the full projection before creating any output.
    blobs = {}
    records = []
    for path, source_path in sorted(RUNTIME_FILES.items()):
        tree = subprocess.run(
            ["git", "-C", str(repo), "ls-tree", revision, "--", source_path],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        if not tree.startswith("100644 blob "):
            raise ValueError(f"missing or non-regular source object: {source_path}")
        raw = subprocess.run(
            ["git", "-C", str(repo), "show", revision + ":" + source_path],
            check=True, capture_output=True,
        ).stdout
        blobs[path] = raw
        records.append(record_for(path, source_path, raw))
    witness = {"schema": WITNESS_SCHEMA, "source_repository": SOURCE_REPOSITORY,
               "source_revision": revision, "files": records,
               "artifact_set_sha256": digest_records(records)}
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for path, raw in blobs.items():
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (output / WITNESS_NAME).write_text(
        json.dumps(witness, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return witness


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    witness = export(ROOT, args.revision, args.output)
    print(json.dumps({"source_revision": witness["source_revision"],
                      "artifact_set_sha256": witness["artifact_set_sha256"],
                      "files": len(witness["files"]), "published": False}, indent=2))


if __name__ == "__main__":
    main()
