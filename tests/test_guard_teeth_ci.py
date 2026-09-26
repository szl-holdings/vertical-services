"""tools/guard_teeth.py is re-checked by CI, not only on a laptop.

ci.yml runs the harness self-test and the manifest staleness gate on every
pull request (no path filter), and guard-teeth.yml re-runs the full mutation
receipt whenever a guarded module, a guarded test or the harness changes.  The
path filter is checked against tools/guard_teeth.json, so a guard added in a
new module or a test file added to a guard cannot fall outside it silently.
"""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
MANIFEST = json.loads((ROOT / "tools" / "guard_teeth.json").read_text(encoding="utf-8"))
SHA_PIN = re.compile(r"^\s*(?:-\s+)?uses:\s+[\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d", re.M)


def _workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _trigger_block(workflow: str) -> str:
    return workflow.split('"on":', 1)[1].split("\npermissions:", 1)[0]


def _event_paths(trigger: str) -> dict[str, list[str]]:
    """{event: [path globs]} from a two-space-indented "on:" block."""
    paths: dict[str, list[str]] = {}
    event, in_paths = None, False
    for line in trigger.splitlines():
        head = re.match(r"^  ([\w-]+):", line)
        if head:
            event, in_paths = head.group(1), False
            continue
        if re.match(r"^    [\w-]+:", line):
            in_paths = line.strip() == "paths:"
            if in_paths:
                paths[event] = []
            continue
        item = re.match(r"^      - (\S+)\s*$", line)
        if in_paths and item:
            paths[event].append(item.group(1).strip("'\""))
    return paths


def _glob_matches(pattern: str, path: str) -> bool:
    """GitHub path-filter semantics for the subset used here: '*' stays inside
    one directory level, '**' crosses directories."""
    assert not set(pattern) & set("?[]!+"), f"unsupported path-filter syntax in {pattern!r}"
    regex = "".join(
        ".*" if token == "**" else "[^/]*" if token == "*" else re.escape(token)
        for token in re.split(r"(\*\*|\*)", pattern)
        if token
    )
    return re.fullmatch(regex, path) is not None


def _guarded_paths() -> list[str]:
    files = {guard["file"] for guard in MANIFEST["guards"]}
    files |= {test.split("::", 1)[0] for guard in MANIFEST["guards"] for test in guard["tests"]}
    files |= {"tools/guard_teeth.py", "tools/guard_teeth.json"}
    return sorted(files)


def test_every_pull_request_runs_the_self_test_and_staleness_gate():
    workflow = _workflow("ci.yml")
    trigger = _trigger_block(workflow)
    assert "pull_request:" in trigger
    assert "paths" not in trigger
    assert "run: python tools/guard_teeth.py --self-test\n" in workflow
    assert "run: python tools/guard_teeth.py --dry-run\n" in workflow
    assert "continue-on-error" not in workflow


def test_full_receipt_runs_whenever_a_guarded_file_changes():
    workflow = _workflow("guard-teeth.yml")
    paths = _event_paths(_trigger_block(workflow))
    assert set(paths) == {"pull_request", "push"}
    assert paths["pull_request"] == paths["push"]
    uncovered = [
        path for path in _guarded_paths()
        if not any(_glob_matches(pattern, path) for pattern in paths["pull_request"])
    ]
    assert uncovered == [], f"guard-teeth.yml path filter misses {uncovered}"
    assert ".github/workflows/guard-teeth.yml" in paths["pull_request"]
    assert "workflow_dispatch:" in _trigger_block(workflow)


def test_full_receipt_fails_the_job_and_uploads_the_receipt():
    workflow = _workflow("guard-teeth.yml")
    assert "run: python tools/guard_teeth.py --jobs 2 --json-out guard-teeth-receipt.json\n" in workflow
    assert "path: guard-teeth-receipt.json\n" in workflow
    assert "timeout-minutes: 15\n" in workflow
    assert "continue-on-error" not in workflow
    assert "|| true" not in workflow
    assert "\npermissions:\n  contents: read\n" in workflow
    assert "persist-credentials: false" in workflow
    assert "ref: ${{ github.sha }}" in workflow
    uses = re.findall(r"^\s*(?:-\s+)?uses:.*$", workflow, re.M)
    assert uses and len(SHA_PIN.findall(workflow)) == len(uses)


def test_glob_matcher_follows_github_directory_semantics():
    assert _glob_matches("tests/*evidence*", "tests/test_evidence_replay.py")
    assert not _glob_matches("tests/*evidence*", "tests/sub/test_evidence_replay.py")
    assert _glob_matches("tests/**", "tests/sub/test_evidence_replay.py")
    assert _glob_matches("tools/guard_teeth.*", "tools/guard_teeth.json")
    assert not _glob_matches("deploy/szl_verticals/store.py", "deploy/szl_verticals/replay_store.py")
