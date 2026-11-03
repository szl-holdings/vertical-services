"""Offline guards for live intelligence evidence and its deploy-bound trigger.

The attester judges one exact commit. These tests build a real Git history and
serve the Space from memory, so supersession is proven by ancestry, never
assumed, and no network is used.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from urllib.error import HTTPError

import pytest

from tools import attest_live_intelligence as attester

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
BASE = "https://space.example"


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / f"{name}.txt").write_text(name + "\n", encoding="utf-8")
    _git(repo, "add", f"{name}.txt")
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def history(tmp_path: Path) -> dict[str, object]:
    """main: a -> b (checked out with full history) -> c (pushed later); side: a -> s."""
    origin = tmp_path / "origin.git"
    author = tmp_path / "author"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(tmp_path, "clone", "-q", str(origin), str(author))
    _git(author, "config", "user.name", "Live Evidence Test")
    _git(author, "config", "user.email", "live-evidence@example.invalid")
    _git(author, "config", "commit.gpgsign", "false")
    _git(author, "symbolic-ref", "HEAD", "refs/heads/main")
    a = _commit(author, "a")
    b = _commit(author, "b")
    _git(author, "push", "-q", "origin", "main")
    _git(author, "switch", "-q", "-c", "side", a)
    s = _commit(author, "s")
    _git(author, "push", "-q", "origin", "side")
    checkout = tmp_path / "checkout"
    _git(tmp_path, "clone", "-q", str(origin), str(checkout))
    _git(author, "switch", "-q", "main")
    c = _commit(author, "c")
    _git(author, "push", "-q", "origin", "main")
    return {"repo": checkout, "a": a, "b": b, "c": c, "s": s}


def test_supersession_requires_a_proven_descendant_on_main(history):
    repo, a, b, c, s = (history[k] for k in ("repo", "a", "b", "c", "s"))
    def classify(expected, observed, refresh=False):
        return attester.classify_observed(repo, expected, observed, refresh=refresh)

    assert classify(a, a) == attester.EXACT
    assert classify(a, b) == attester.SUPERSEDED
    # An older revision is a deploy still in progress, not a supersession.
    assert classify(b, a) == attester.UNPROVEN
    # A descendant that main never received is not deployable.
    assert classify(a, s) == attester.UNPROVEN
    assert classify(a, "unavailable") == attester.UNPROVEN
    # Main moved after checkout: unprovable from the stale view, proven after a refresh.
    assert classify(a, c) == attester.UNPROVEN
    assert classify(a, c, refresh=True) == attester.SUPERSEDED
    assert classify(c, s, refresh=True) == attester.UNPROVEN


class FakeSpace:
    """Serve successive build revisions; the last one repeats."""

    def __init__(self, *revisions: str, catalog: dict | None = None) -> None:
        self.revisions = list(revisions)
        self.catalog = catalog or {
            "verticals": {name: {} for name in attester.VERTICALS},
            "caller_supplied_endpoints_allowed": False,
            "effectors_enabled": False,
        }
        self.fail_path: str | None = None

    def __call__(self, url: str, timeout: float = 15.0) -> tuple[int, bytes, str]:
        assert url.startswith(BASE)
        path = url[len(BASE):]
        if path == self.fail_path:
            raise HTTPError(url, 503, "Service Unavailable", {}, None)
        if path == "/api/build-info":
            revision = self.revisions.pop(0) if len(self.revisions) > 1 else self.revisions[0]
            return 200, json.dumps({"build": {"revision": revision}}).encode(), "application/json"
        if path == "/api/intelligence":
            return 200, json.dumps(self.catalog).encode(), "application/json"
        if path.startswith("/intelligence/"):
            vertical = path.rsplit("/", 1)[1]
            html = (
                f'<main data-vertical="{vertical}" data-motif="{attester.VERTICALS[vertical]}">'
                + " ".join(attester.ROOM_MARKERS)
                + "</main>"
            )
            return 200, html.encode(), "text/html; charset=utf-8"
        match = re.fullmatch(r"/api/verticals/([a-z]+)/intelligence", path)
        if match:
            profile = {
                "vertical": match.group(1),
                "tasks": {f"t{i}": {} for i in range(4)},
                "novel_capabilities": [1, 2, 3],
                "policy": {"effectors_enabled": False},
                "models": [],
                "kernels": [],
            }
            return 200, json.dumps(profile).encode(), "application/json"
        raise AssertionError(f"unexpected path {path}")


def _run(monkeypatch, tmp_path, repo, expected, space):
    monkeypatch.setattr(attester, "http_get", space)
    output = tmp_path / "artifacts" / "live-intelligence.json"
    code = attester.main(
        [
            "--base-url", BASE + "/",
            "--expected-revision", expected,
            "--output", str(output),
            "--repo-root", str(repo),
            "--timeout-seconds", "0.2",
            "--interval-seconds", "0",
        ]
    )
    return code, json.loads(output.read_text(encoding="utf-8"))


def test_exact_revision_is_verified_after_waiting_out_an_older_deploy(monkeypatch, tmp_path, history):
    code, report = _run(monkeypatch, tmp_path, history["repo"], history["b"], FakeSpace(history["a"], history["b"]))
    assert code == 0
    assert report["state"] == "VERIFIED" and report["reason"] is None
    assert report["schema"] == attester.SCHEMA
    assert report["observed_source_revision"] == history["b"]
    assert report["observed_source_revision_after_capture"] == history["b"]
    assert set(report["verticals"]) == set(attester.VERTICALS)


def test_proven_descendant_records_superseded_without_room_evidence(monkeypatch, tmp_path, history):
    code, report = _run(monkeypatch, tmp_path, history["repo"], history["a"], FakeSpace(history["c"]))
    assert code == 0
    assert report["state"] == "SUPERSEDED" and report["superseded_by"] == history["c"]
    assert report["routes"] == {} and report["verticals"] == {}


def test_unproven_mismatch_fails_closed_with_a_receipt(monkeypatch, tmp_path, history):
    # The Space keeps serving a branch-only descendant: never deployable, never superseding.
    code, report = _run(monkeypatch, tmp_path, history["repo"], history["a"], FakeSpace(history["s"]))
    assert code == 1
    assert report["state"] == "NOT_CONVERGED"
    assert report["reason"] == (
        f"exact deployment did not converge: build revision {history['s']} != {history['a']}"
    )
    assert report["verticals"] == {}


def test_redeploy_during_capture_never_verifies(monkeypatch, tmp_path, history):
    repo, a, b, s = (history[k] for k in ("repo", "a", "b", "s"))
    code, report = _run(monkeypatch, tmp_path, repo, a, FakeSpace(a, b))
    assert code == 0 and report["state"] == "SUPERSEDED"
    assert report["routes"] == {} and report["verticals"] == {}
    code, report = _run(monkeypatch, tmp_path, repo, a, FakeSpace(a, s))
    assert code == 1 and report["state"] == "FAILED"
    assert "changed during capture" in report["reason"]


def test_contract_drift_and_transport_failure_fail_closed(monkeypatch, tmp_path, history):
    a = history["a"]
    drifted = FakeSpace(a)
    drifted.catalog["effectors_enabled"] = True
    code, report = _run(monkeypatch, tmp_path, history["repo"], a, drifted)
    assert code == 1 and report["state"] == "FAILED"
    assert report["reason"] == "AttestationFailure: effector boundary drifted"
    broken = FakeSpace(a)
    broken.fail_path = "/intelligence/terra"
    code, report = _run(monkeypatch, tmp_path, history["repo"], a, broken)
    assert code == 1 and report["state"] == "FAILED"
    assert report["reason"].startswith("HTTPError")


def _trigger_block(workflow: str) -> str:
    return workflow.split('"on":', 1)[1].split("\npermissions:", 1)[0]


def _job(workflow: str, name: str) -> str:
    match = re.search(rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)", workflow)
    assert match is not None, name
    return match.group(1)


def test_live_evidence_is_bound_to_the_published_commit_not_a_push():
    live = (WORKFLOWS / "intelligence-live.yml").read_text(encoding="utf-8")
    triggers = _trigger_block(live)
    assert "\n  push:" not in triggers
    assert "\n  workflow_call: {}" in triggers
    job = _job(live, "live")
    assert "python tools/attest_live_intelligence.py" in job
    assert '--expected-revision "$GITHUB_SHA"' in job
    assert "fetch-depth: 0" in job and "persist-credentials: false" in job
    # The attester writes a receipt for every terminal state, so a missing file stays an error.
    assert "if-no-files-found: error" in job

    deploy = (WORKFLOWS / "hf-space.yml").read_text(encoding="utf-8")
    caller = _job(deploy, "attest-live-intelligence")
    assert "uses: ./.github/workflows/intelligence-live.yml" in caller
    assert "needs: [publish]" in caller
    assert "needs.publish.result == 'success'" in caller
    assert "github.event_name != 'pull_request'" in caller
    assert "secrets" not in caller
