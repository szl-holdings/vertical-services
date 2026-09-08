#!/usr/bin/env python3
"""Resolve and validate the exact checked-out default-branch deployment tip."""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
MAIN_REF = "refs/heads/main"


def resolve_deployable_revision(repo_root: Path) -> str:
    """Return the exact checked-out commit; every main tip is deployable."""
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "rev-parse",
            "--verify",
            "HEAD^{commit}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    revision = completed.stdout.strip().lower()
    if SHA40.fullmatch(revision) is None:
        raise RuntimeError("the checked-out deployment source is not an exact Git SHA")
    return revision


def require_deployable_revision(repo_root: Path, requested_revision: str) -> str:
    """Require the event revision to equal the exact checked-out deployment source."""
    requested = requested_revision.strip().lower()
    if SHA40.fullmatch(requested) is None:
        raise RuntimeError("required revision is not an exact Git SHA")
    selected = resolve_deployable_revision(repo_root)
    if requested != selected:
        raise RuntimeError(
            "manual dispatch revision does not match the checked-out main tip: "
            f"requested={requested} expected={selected}"
        )
    return selected


def require_main_ref(github_ref: str) -> None:
    """Reject provider-bound manual dispatch from any non-main ref."""
    if github_ref != MAIN_REF:
        raise RuntimeError(
            f"manual dispatch is restricted to {MAIN_REF}; observed={github_ref}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--require-revision")
    parser.add_argument("--require-ref")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    try:
        if args.require_ref is not None:
            require_main_ref(args.require_ref)
        if args.require_revision is None:
            revision = resolve_deployable_revision(repo_root)
        else:
            revision = require_deployable_revision(repo_root, args.require_revision)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(revision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
