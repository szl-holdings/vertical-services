"""Read-only identity for the standalone Finance Git-blob projection.

Matching a publisher-provided witness observes local byte parity. It does not
verify a signature, GitHub approval, provider commit, or market-data readiness.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

SOURCE_REPOSITORY = "szl-holdings/vertical-services"
WITNESS_SCHEMA = "szl.finance-runtime-binding/v1"
WITNESS_NAME = "source-binding.json"
RUNTIME_FILES = {
    "app.py": "services/finance/app.py",
    "engine.py": "services/finance/engine.py",
    "feed.py": "services/finance/feed.py",
    "receipts.py": "services/finance/receipts.py",
    "runtime_identity.py": "services/finance/runtime_identity.py",
    "static/console.html": "services/finance/static/console.html",
    "static/panels.html": "services/finance/static/panels.html",
    "Dockerfile": "services/finance/Dockerfile",
    "requirements.txt": "requirements.txt",
}
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("DUPLICATE_WITNESS_FIELD")
        obj[key] = value
    return obj


def digest_records(records: list[dict]) -> str:
    raw = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def record_for(path: str, source_path: str, raw: bytes) -> dict:
    blob = b"blob " + str(len(raw)).encode() + b"\0" + raw
    return {"path": path, "source_path": source_path, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "git_blob_oid": hashlib.sha1(blob, usedforsecurity=False).hexdigest()}


class RuntimeIdentity:
    """Retain the startup witness and reject file or witness changes thereafter."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.witness = None
        self.witness_bytes = None
        self.startup_failure = None
        try:
            with (self.root / WITNESS_NAME).open("rb") as stream:
                raw = stream.read(32_769)
            if len(raw) > 32_768:
                raise ValueError("WITNESS_TOO_LARGE")
            witness = json.loads(raw, object_pairs_hook=_unique_object)
            if (not isinstance(witness, dict)
                    or witness.get("schema") != WITNESS_SCHEMA
                    or witness.get("source_repository") != SOURCE_REPOSITORY
                    or not isinstance(witness.get("source_revision"), str)
                    or SHA40.fullmatch(witness["source_revision"]) is None):
                raise ValueError("WITNESS_INVALID")
            records = witness.get("files")
            if (not isinstance(records, list)
                    or any(not isinstance(r, dict) for r in records)
                    or [r.get("path") for r in records] != sorted(RUNTIME_FILES)
                    or witness.get("artifact_set_sha256") != digest_records(records)):
                raise ValueError("WITNESS_FILE_SET_INVALID")
            for record in records:
                path = record["path"]
                local = self.root / path
                if (local.is_symlink() or type(record.get("bytes")) is not int
                        or local.stat().st_size != record["bytes"] or record != record_for(
                        path, RUNTIME_FILES[path], local.read_bytes())):
                    raise ValueError("RUNTIME_FILE_MISMATCH")
            self.witness, self.witness_bytes = witness, raw
        except FileNotFoundError:
            self.startup_failure = "WITNESS_OR_RUNTIME_FILE_MISSING"
        except (OSError, ValueError, TypeError, KeyError):
            self.startup_failure = "WITNESS_OR_RUNTIME_FILE_INVALID"

    def document(self, env: dict | None = None) -> dict:
        env = os.environ if env is None else env
        failure = self.startup_failure
        if self.witness is not None:
            try:
                if (self.root / WITNESS_NAME).read_bytes() != self.witness_bytes:
                    failure = "WITNESS_CHANGED_AFTER_STARTUP"
                for record in self.witness["files"]:
                    path = record["path"]
                    local = self.root / path
                    if (local.is_symlink() or local.stat().st_size != record["bytes"]
                            or record != record_for(
                            path, RUNTIME_FILES[path], local.read_bytes())):
                        failure = "RUNTIME_FILE_CHANGED_AFTER_STARTUP"
                for name in ("SZL_SOURCE_REVISION", "SZL_GIT_SHA"):
                    supplied = env.get(name)
                    if supplied is not None and supplied != self.witness["source_revision"]:
                        failure = "REVISION_SETTING_MISMATCH"
            except OSError:
                failure = "RUNTIME_FILE_UNAVAILABLE"
        observed = self.witness is not None and failure is None
        revision = self.witness["source_revision"] if observed else "UNAVAILABLE"
        return {
            "schema": "szl.finance-runtime-identity/v1",
            "service": "puriq-finance",
            "source_repository": SOURCE_REPOSITORY,
            "source_revision": revision,
            "runtime_repository": SOURCE_REPOSITORY,
            "runtime_source_revision": revision,
            "build": {"state": "OBSERVED" if observed else "UNAVAILABLE",
                      "revision": revision, "revision_source": WITNESS_NAME},
            "source_binding": {
                "state": "LOCAL_BYTES_MATCH_WITNESS" if observed else "UNAVAILABLE",
                "artifact_set_sha256": self.witness["artifact_set_sha256"] if observed else None,
                "controlled_file_count": len(RUNTIME_FILES) if observed else 0,
                "failure_code": failure,
                "scope": "publisher-provided Git-blob witness and local file parity",
                "signature_verified": False,
                "provider_commit_verified": False,
            },
            "effectors_enabled": False,
            "human_approval_required": True,
            "advisory_only": True,
            "paper_only": True,
            "not_financial_advice": True,
            "market_data_ready": "UNAVAILABLE",
            "production_ready": False,
            "receipt_minted": False,
        }
