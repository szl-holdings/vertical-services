"""Shared runtime contract for the SZL vertical engines."""
from __future__ import annotations

import hashlib
import os
import re
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict

VERSION = "2.2.0"
SOURCE_REPOSITORY = "szl-holdings/vertical-services"
HF_REPOSITORY = "SZLHOLDINGS/vertical-services"
RUNTIME_REPOSITORY = SOURCE_REPOSITORY
ENGINES = ("sentra", "lyte", "killinchu", "finance", "terra", "counsel")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
STATE_LOCK = threading.RLock()
RUNTIME_SOURCE_IDENTITY_FIELDS = (
    "source_repository",
    "source_revision",
    "runtime_repository",
    "runtime_source_revision",
    "effectors_enabled",
    "human_approval_required",
)


def _revision_observation() -> dict[str, Any]:
    """Observe all supported source bindings and fail closed on disagreement."""
    candidates: list[tuple[str, str]] = []
    invalid_sources: set[str] = set()
    if "SZL_SOURCE_REVISION" in os.environ:
        env_revision = os.environ["SZL_SOURCE_REVISION"].strip().lower()
        if SHA40.fullmatch(env_revision):
            candidates.append(("env", env_revision))
        else:
            invalid_sources.add("env")

    for label, path in (
        (
            "adjacent-file",
            Path(__file__).resolve().parents[1] / "source_revision.txt",
        ),
        ("container-file", Path("/app/source_revision.txt")),
    ):
        try:
            revision = path.read_text(encoding="ascii").strip().lower()
        except FileNotFoundError:
            continue
        except (OSError, UnicodeError):
            invalid_sources.add(label)
            continue
        if SHA40.fullmatch(revision):
            candidates.append((label, revision))
        else:
            invalid_sources.add(label)

    revisions = sorted({revision for _, revision in candidates})
    if invalid_sources:
        state, revision = "INVALID", "UNAVAILABLE"
    elif not revisions:
        state, revision = "UNBOUND", "UNAVAILABLE"
    elif len(revisions) == 1:
        state, revision = "OBSERVED", revisions[0]
    else:
        state, revision = "MISMATCH", "UNAVAILABLE"
    return {
        "state": state,
        "revision": revision,
        "evidence_sources": sorted(
            {label for label, _ in candidates} | invalid_sources
        ),
        "invalid_sources": sorted(invalid_sources),
        "bindings_agree": not invalid_sources and len(revisions) <= 1,
    }


def runtime_source_identity(
    observation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return this runtime's source tuple without guessing through ambiguity."""
    observed = _revision_observation() if observation is None else observation
    candidate = str(observed.get("revision", "")).strip().lower()
    revision = (
        candidate
        if observed.get("state") == "OBSERVED"
        and observed.get("bindings_agree") is True
        and SHA40.fullmatch(candidate)
        else "UNAVAILABLE"
    )
    return {
        "source_repository": SOURCE_REPOSITORY,
        "source_revision": revision,
        "runtime_repository": RUNTIME_REPOSITORY,
        "runtime_source_revision": revision,
        "effectors_enabled": False,
        "human_approval_required": True,
    }


def build_info() -> dict[str, Any]:
    observation = _revision_observation()
    identity = runtime_source_identity(observation)
    return {
        "schema": "szl.build-info/v1",
        "service": "szl-vertical-services",
        "version": VERSION,
        **identity,
        "hf_repository": HF_REPOSITORY,
        "build": {
            "state": observation["state"],
            "revision": identity["source_revision"],
        },
        "source_binding": {
            "evidence_sources": observation["evidence_sources"],
            "invalid_sources": observation["invalid_sources"],
            "bindings_agree": observation["bindings_agree"],
        },
        "receipt_minted": False,
        "truth_label": "MEASURED",
    }


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


SESSION_TOKEN = re.compile(r"^[A-Za-z0-9._~-]{32,128}$")


def session_scope(
    x_szl_session: str = Header(..., alias="X-SZL-Session"),
) -> str:
    """Map a caller-held high-entropy token to a non-reversible state scope."""
    token = x_szl_session.strip()
    if SESSION_TOKEN.fullmatch(token) is None:
        raise HTTPException(
            400,
            "X-SZL-Session must be a 32-128 character high-entropy token "
            "using A-Z, a-z, 0-9, . _ ~ or -",
        )
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


SessionScope = Annotated[str, Depends(session_scope)]
