"""Shared runtime contract for the SZL vertical engines."""
from __future__ import annotations

import hashlib
import os
import re
import threading
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict

VERSION = "1.1.0"
SOURCE_REPOSITORY = "szl-holdings/vertical-services"
HF_REPOSITORY = "SZLHOLDINGS/vertical-services"
ENGINES = ("sentra", "lyte", "vessels", "finance", "terra", "counsel")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
STATE_LOCK = threading.RLock()


def _revision_observation() -> dict[str, Any]:
    """Observe all supported source bindings and fail closed on disagreement."""
    candidates: list[tuple[str, str]] = []
    env_revision = os.environ.get("SZL_SOURCE_REVISION", "").strip().lower()
    if SHA40.fullmatch(env_revision):
        candidates.append(("env", env_revision))

    for label, path in (
        ("adjacent-file", Path(__file__).resolve().parents[1] / "source_revision.txt"),
        ("container-file", Path("/app/source_revision.txt")),
    ):
        try:
            revision = path.read_text(encoding="ascii").strip().lower()
        except OSError:
            continue
        if SHA40.fullmatch(revision):
            candidates.append((label, revision))

    revisions = sorted({revision for _, revision in candidates})
    if not revisions:
        state, revision = "UNBOUND", "UNAVAILABLE"
    elif len(revisions) == 1:
        state, revision = "OBSERVED", revisions[0]
    else:
        state, revision = "MISMATCH", revisions[0]
    return {
        "state": state,
        "revision": revision,
        "evidence_sources": sorted({label for label, _ in candidates}),
        "bindings_agree": len(revisions) <= 1,
    }


def build_info() -> dict[str, Any]:
    observation = _revision_observation()
    return {
        "schema": "szl.build-info/v1",
        "service": "szl-vertical-services",
        "version": VERSION,
        "source_repository": SOURCE_REPOSITORY,
        "hf_repository": HF_REPOSITORY,
        "build": {
            "state": observation["state"],
            "revision": observation["revision"],
        },
        "source_binding": {
            "evidence_sources": observation["evidence_sources"],
            "bindings_agree": observation["bindings_agree"],
        },
        "receipt_minted": False,
        "truth_label": "MEASURED",
    }


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


SESSION_TOKEN = re.compile(r"^[A-Za-z0-9._~-]{32,128}$")


def session_scope(x_szl_session: str = Header(..., alias="X-SZL-Session")) -> str:
    """Map a caller-held high-entropy token to a non-reversible state scope."""
    token = x_szl_session.strip()
    if SESSION_TOKEN.fullmatch(token) is None:
        raise HTTPException(
            400,
            "X-SZL-Session must be a 32-128 character high-entropy token using A-Z, a-z, 0-9, . _ ~ or -",
        )
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


SessionScope = Annotated[str, Depends(session_scope)]
