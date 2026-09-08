from pathlib import Path

from tools.verify_runtime_identity import IDENTITY_PATHS, discover_deployed_revision


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
    assert "--expected-revision" not in workflow
    assert "persist-credentials: false" in workflow


def test_scheduled_monitor_discovers_only_an_exact_deployed_revision():
    revision = "abcdef0123456789abcdef0123456789abcdef01"
    discovered, failures = discover_deployed_revision(
        {"/api/build-info": {"source_revision": revision.upper()}}
    )
    assert discovered == revision
    assert failures == []

    unavailable, failures = discover_deployed_revision(
        {"/api/build-info": {"source_revision": "UNAVAILABLE"}}
    )
    assert unavailable == "UNAVAILABLE"
    assert failures == [
        "/api/build-info: deployed source_revision is not an exact Git SHA"
    ]
