#!/usr/bin/env python3
"""Resolve the newest first-parent main revision covered by deployment triggers."""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

DEPLOY_TRIGGER_PATHS = (
    ".github/workflows/hf-space.yml",
    "deploy",
    "requirements.txt",
    "requirements-test.txt",
    "README.md",
    "tests",
    "tools",
)
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def resolve_deployable_revision(repo_root: Path) -> str:
    """Return the latest first-parent revision changing a deploy-trigger path."""
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "log",
            "--first-parent",
            "-1",
            "--format=%H",
            "--",
            *DEPLOY_TRIGGER_PATHS,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    revision = completed.stdout.strip().lower()
    if SHA40.fullmatch(revision) is None:
        raise RuntimeError("no exact deploy-trigger revision was found on main history")
    return revision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    print(resolve_deployable_revision(args.repo_root.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
