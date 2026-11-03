#!/usr/bin/env python3
"""Attest the public intelligence rooms of one exact deployed commit.

The judged commit is VERIFIED only when the Space serves exactly that revision
before and after the capture and every room and profile contract holds.

The judged commit is SUPERSEDED, never VERIFIED, only when Git proves that the
Space serves a strict descendant of it that is on main. The publisher deploys
only the main tip, so a superseded commit can never be served again, and the
descendant's own deploy run attests the descendant.

Every other outcome fails closed with a nonzero exit. A receipt is written for
every terminal state, so the evidence upload never has to tolerate a missing
file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCHEMA = "szl.vertical-intelligence-live-evidence/v1"
USER_AGENT = "szl-vertical-intelligence-live-evidence/1.0"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
VERTICALS = {
    "sentra": "threat-shield",
    "lyte": "service-lattice",
    "killinchu": "voyage-radar",
    "finance": "probability-orbit",
    "terra": "parcel-grid",
    "counsel": "authority-chain",
}
ROOM_MARKERS = (
    "Skip to intelligence room",
    "Learn broadly. Copy nothing proprietary.",
    "@media(prefers-reduced-motion:reduce)",
)
EXACT = "EXACT"
SUPERSEDED = "SUPERSEDED"
UNPROVEN = "UNPROVEN"
PASSING_STATES = frozenset({"VERIFIED", SUPERSEDED})
NETWORK_ERRORS = (HTTPError, URLError, TimeoutError, OSError)


class AttestationFailure(RuntimeError):
    """A live contract did not hold for the judged commit."""


def http_get(url: str, timeout: float = 15.0) -> tuple[int, bytes, str]:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return (
            int(response.status),
            response.read(2_000_000),
            response.headers.get("content-type", ""),
        )


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _is_ancestor(repo_root: Path, ancestor: str, descendant: str) -> bool:
    # Exit status 1 means "not an ancestor"; any other failure proves nothing.
    return _git(repo_root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def classify_observed(
    repo_root: Path,
    expected: str,
    observed: str,
    *,
    main_branch: str = "main",
    refresh: bool = True,
) -> str:
    """Return EXACT, SUPERSEDED (proven by Git), or UNPROVEN."""
    if observed == expected:
        return EXACT
    if SHA40.fullmatch(observed) is None or SHA40.fullmatch(expected) is None:
        return UNPROVEN
    main_ref = f"refs/remotes/origin/{main_branch}"
    if refresh:
        # Main may have moved after checkout; a failed fetch leaves the old view,
        # which can only make the proof below fail, never pass.
        _git(
            repo_root,
            "fetch",
            "--no-tags",
            "--quiet",
            "origin",
            f"+refs/heads/{main_branch}:{main_ref}",
        )
    if _is_ancestor(repo_root, expected, observed) and _is_ancestor(
        repo_root, observed, main_ref
    ):
        return SUPERSEDED
    return UNPROVEN


def observe_revision(get: Callable[[str], tuple[int, bytes, str]]) -> str:
    status, raw, _ = get("/api/build-info")
    if status != 200:
        raise ValueError(f"build-info returned HTTP {status}")
    payload = json.loads(raw)
    build = payload.get("build") if isinstance(payload, dict) else None
    if not isinstance(build, dict):
        raise ValueError("build-info did not carry a build object")
    return str(build.get("revision", "UNAVAILABLE")).lower()


def await_revision(
    get: Callable[[str], tuple[int, bytes, str]],
    classify: Callable[[str], str],
    expected: str,
    *,
    timeout: float,
    interval: float = 15.0,
) -> tuple[str, str, str]:
    """Poll until the Space serves the judged commit or a proven descendant."""
    deadline = time.monotonic() + timeout
    observed = "UNAVAILABLE"
    last_error = ""
    verdicts: dict[str, str] = {}  # one Git proof per distinct served revision
    while True:
        try:
            observed = observe_revision(get)
            if observed not in verdicts:
                verdicts[observed] = classify(observed)
            if verdicts[observed] != UNPROVEN:
                return verdicts[observed], observed, ""
            last_error = f"build revision {observed} != {expected}"
        except (*NETWORK_ERRORS, ValueError) as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
        if time.monotonic() >= deadline:
            return UNPROVEN, observed, last_error
        time.sleep(interval)


def capture_rooms(
    get: Callable[[str], tuple[int, bytes, str]], report: dict[str, Any]
) -> None:
    status, raw, content_type = get("/api/intelligence")
    if status != 200 or "json" not in content_type.lower():
        raise AttestationFailure("intelligence catalog did not return JSON 200")
    catalog = json.loads(raw)
    if set(catalog.get("verticals", {})) != set(VERTICALS):
        raise AttestationFailure("intelligence catalog vertical set drifted")
    if catalog.get("caller_supplied_endpoints_allowed") is not False:
        raise AttestationFailure("caller-supplied endpoint boundary drifted")
    if catalog.get("effectors_enabled") is not False:
        raise AttestationFailure("effector boundary drifted")
    report["routes"]["/api/intelligence"] = {
        "http": status,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }

    page_hashes = set()
    for vertical, motif in VERTICALS.items():
        p_status, p_raw, p_type = get(f"/intelligence/{vertical}")
        if p_status != 200 or "html" not in p_type.lower():
            raise AttestationFailure(f"{vertical} intelligence room did not return HTML 200")
        text = p_raw.decode("utf-8")
        required = (f'data-vertical="{vertical}"', f'data-motif="{motif}"', *ROOM_MARKERS)
        missing = [item for item in required if item not in text]
        if missing:
            raise AttestationFailure(f"{vertical} intelligence room missing {missing!r}")
        page_sha = hashlib.sha256(p_raw).hexdigest()
        page_hashes.add(page_sha)

        j_status, j_raw, j_type = get(f"/api/verticals/{vertical}/intelligence")
        if j_status != 200 or "json" not in j_type.lower():
            raise AttestationFailure(f"{vertical} intelligence profile did not return JSON 200")
        profile = json.loads(j_raw)
        if profile.get("vertical") != vertical:
            raise AttestationFailure(f"{vertical} profile identity mismatch")
        if len(profile.get("tasks", {})) != 4:
            raise AttestationFailure(f"{vertical} task contract drifted")
        if len(profile.get("novel_capabilities", [])) != 3:
            raise AttestationFailure(f"{vertical} frontier delta drifted")
        if profile.get("policy", {}).get("effectors_enabled") is not False:
            raise AttestationFailure(f"{vertical} effector boundary drifted")
        report["verticals"][vertical] = {
            "room_http": p_status,
            "room_sha256": page_sha,
            "profile_http": j_status,
            "profile_sha256": hashlib.sha256(j_raw).hexdigest(),
            "motif": motif,
            "models": len(profile.get("models", [])),
            "kernels": len(profile.get("kernels", [])),
            "tasks": len(profile.get("tasks", {})),
        }

    if len(page_hashes) != len(VERTICALS):
        raise AttestationFailure("vertical intelligence rooms are not byte-distinct")


def _superseded(report: dict[str, Any], observed: str, when: str) -> None:
    report["state"] = SUPERSEDED
    report["superseded_by"] = observed
    report["reason"] = (
        f"the Space serves {observed}, a strict descendant on main of the judged "
        f"commit, {when}; the judged commit is not verified and is no longer deployable"
    )


def attest(
    base: str,
    expected: str,
    *,
    repo_root: Path,
    main_branch: str,
    timeout: float,
    interval: float,
) -> dict[str, Any]:
    def get(path: str) -> tuple[int, bytes, str]:
        return http_get(base + path)

    def classify(observed: str) -> str:
        return classify_observed(repo_root, expected, observed, main_branch=main_branch)

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "captured_at": None,
        "base_url": base,
        "expected_source_revision": expected,
        "observed_source_revision": "UNAVAILABLE",
        "observed_source_revision_after_capture": None,
        "superseded_by": None,
        "routes": {},
        "verticals": {},
        "state": "UNKNOWN",
        "reason": None,
    }
    verdict, observed, last_error = await_revision(
        get, classify, expected, timeout=timeout, interval=interval
    )
    report["captured_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    report["observed_source_revision"] = observed
    if verdict == SUPERSEDED:
        _superseded(report, observed, "before capture")
        return report
    if verdict != EXACT:
        report["state"] = "NOT_CONVERGED"
        report["reason"] = f"exact deployment did not converge: {last_error}"
        return report

    try:
        capture_rooms(get, report)
        # Bracket the capture: the rooms belong to the judged commit only if the
        # same exact revision is still served after the last room was read.
        after = observe_revision(get)
        report["observed_source_revision_after_capture"] = after
        if after == expected:
            report["state"] = "VERIFIED"
        elif classify(after) == SUPERSEDED:
            _superseded(report, after, "during capture")
            # Hashes read across a redeploy belong to neither commit.
            report["routes"], report["verticals"] = {}, {}
        else:
            report["state"] = "FAILED"
            report["reason"] = (
                f"build revision changed during capture: {after} != {expected}"
            )
    except Exception as exc:  # any unexpected live shape fails closed, with a receipt
        report["state"] = "FAILED"
        report["reason"] = f"{exc.__class__.__name__}: {exc}"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--main-branch", default="main")
    parser.add_argument("--timeout-seconds", type=float, default=1_200.0)
    parser.add_argument("--interval-seconds", type=float, default=15.0)
    args = parser.parse_args(argv)

    expected = args.expected_revision.strip().lower()
    if SHA40.fullmatch(expected) is None:
        parser.error("--expected-revision must be an exact 40-character Git SHA")
    report = attest(
        args.base_url.rstrip("/"),
        expected,
        repo_root=args.repo_root.resolve(),
        main_branch=args.main_branch,
        timeout=args.timeout_seconds,
        interval=args.interval_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["state"] == SUPERSEDED:
        print(f"::notice title=Live intelligence evidence superseded::{report['reason']}")
    elif report["state"] not in PASSING_STATES:
        print(f"::error title=Live intelligence evidence {report['state']}::{report['reason']}")
    return 0 if report["state"] in PASSING_STATES else 1


if __name__ == "__main__":
    sys.exit(main())
