import subprocess
from pathlib import Path

import pytest

from tools.resolve_deployable_revision import (
    require_deployable_revision,
    require_main_ref,
    resolve_deployable_revision,
)
from tools.verify_runtime_identity import (
    IDENTITY_PATHS,
    RUNTIME_REPOSITORY,
    SOURCE_REPOSITORY,
    validate_identity_documents,
)


ROOT = Path(__file__).resolve().parents[1]


def test_hf_workflow_smokes_and_verifies_every_identity_route():
    workflow = (ROOT / ".github" / "workflows" / "hf-space.yml").read_text(
        encoding="utf-8"
    )

    for path in IDENTITY_PATHS:
        assert path in workflow
    assert workflow.count("tools/verify_runtime_identity.py") == 2


def test_uptime_monitor_uses_explicit_paths_without_double_slash_root():
    workflow = (ROOT / ".github" / "workflows" / "uptime-monitor.yml").read_text(
        encoding="utf-8"
    )

    for path in IDENTITY_PATHS:
        assert path in workflow
    assert 'for engine in ""' not in workflow
    assert 'url="${BASE}/${engine}/healthz"' not in workflow
    assert 'url="${BASE}${path}"' in workflow
    assert "tools/verify_runtime_identity.py" in workflow
    assert "tools/resolve_deployable_revision.py" in workflow
    assert '--expected-revision "$EXPECTED_REVISION"' in workflow
    assert "fetch-depth: 0" in workflow
    assert "ref: main" in workflow
    assert "persist-credentials: false" in workflow


def test_publisher_runs_for_every_main_tip_and_serializes_mutations():
    workflow = (ROOT / ".github" / "workflows" / "hf-space.yml").read_text(
        encoding="utf-8"
    )
    trigger_block = workflow.split('"on":', 1)[1].split("\npermissions:", 1)[0]
    assert "push:" in trigger_block
    assert "pull_request:" in trigger_block
    assert "branches: [main]" in trigger_block
    assert "paths:" not in trigger_block
    assert "cancel-in-progress: false" in workflow
    assert "Validate manual dispatch source selection" in workflow
    assert '--require-ref "$GITHUB_REF"' in workflow
    assert '--require-revision "$GITHUB_SHA"' in workflow
    assert "github.ref == 'refs/heads/main'" in workflow


def _run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_every_main_tip_is_the_deployable_revision(tmp_path: Path):
    _run_git(tmp_path, "init", "-b", "main")
    _run_git(tmp_path, "config", "user.name", "Runtime Identity Test")
    _run_git(tmp_path, "config", "user.email", "runtime-identity@example.invalid")
    (tmp_path / "deploy").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    app_path = tmp_path / "deploy" / "app.py"
    uptime_path = tmp_path / ".github" / "workflows" / "uptime-monitor.yml"
    app_path.write_text("version = 1\n", encoding="utf-8")
    uptime_path.write_text("name: monitor-v1\n", encoding="utf-8")
    _run_git(tmp_path, "add", ".")
    _run_git(tmp_path, "commit", "-m", "initial deployable source")

    _run_git(tmp_path, "switch", "-c", "deployable-change")
    app_path.write_text("version = 2\n", encoding="utf-8")
    _run_git(tmp_path, "add", "deploy/app.py")
    _run_git(tmp_path, "commit", "-m", "deployable revision B")
    _run_git(tmp_path, "switch", "main")
    _run_git(
        tmp_path,
        "merge",
        "--no-ff",
        "deployable-change",
        "-m",
        "merge deployable revision B",
    )
    deployable_b = _run_git(tmp_path, "rev-parse", "HEAD")

    uptime_path.write_text("name: monitor-v2\n", encoding="utf-8")
    _run_git(tmp_path, "add", ".github/workflows/uptime-monitor.yml")
    _run_git(tmp_path, "commit", "-m", "monitor-only revision C")
    monitor_only_c = _run_git(tmp_path, "rev-parse", "HEAD")
    assert monitor_only_c != deployable_b
    assert resolve_deployable_revision(tmp_path) == monitor_only_c
    assert require_deployable_revision(tmp_path, monitor_only_c) == monitor_only_c
    with pytest.raises(RuntimeError, match="does not match the checked-out main tip"):
        require_deployable_revision(tmp_path, deployable_b)


def test_manual_dispatch_rejects_every_non_main_ref():
    require_main_ref("refs/heads/main")
    for ref in (
        "refs/heads/feature/runtime-identity",
        "refs/tags/v2.2.0",
        "refs/pull/33/merge",
    ):
        with pytest.raises(RuntimeError, match="restricted to refs/heads/main"):
            require_main_ref(ref)


def test_stale_live_revision_fails_independent_freshness_check():
    live_revision = "a" * 40
    expected_revision = "b" * 40
    identity = {
        "source_repository": SOURCE_REPOSITORY,
        "source_revision": live_revision,
        "runtime_repository": RUNTIME_REPOSITORY,
        "runtime_source_revision": live_revision,
        "effectors_enabled": False,
        "human_approval_required": True,
    }
    documents = {
        path: {
            **identity,
            "build": {"state": "OBSERVED", "revision": live_revision},
        }
        for path in IDENTITY_PATHS
    }
    assert validate_identity_documents(
        documents,
        expected_revision=live_revision,
    ) == []
    failures = validate_identity_documents(
        documents,
        expected_revision=expected_revision,
    )
    assert failures
    assert any("source_revision mismatch" in failure for failure in failures)
