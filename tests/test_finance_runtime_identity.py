"""Source witness admission and actual Finance route regression checks."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.finance.runtime_identity import (
    RUNTIME_FILES, WITNESS_NAME, RuntimeIdentity, digest_records,
)
from tools.export_finance_artifact import export
from tools.verify_runtime_identity import IDENTITY_PATHS, validate_identity_documents

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "core.autocrlf=false",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture(scope="module")
def committed_projection(tmp_path_factory):
    base = tmp_path_factory.mktemp("finance-source")
    repo = base / "repo"
    repo.mkdir()
    for source_path in RUNTIME_FILES.values():
        target = repo / source_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / source_path).read_bytes())
    git(repo, "init")
    git(repo, "config", "user.name", "Projection Test")
    git(repo, "config", "user.email", "projection@example.invalid")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "controlled test projection")
    revision = git(repo, "rev-parse", "HEAD")
    artifact = base / "artifact"
    witness = export(repo, revision, artifact)
    return repo, revision, artifact, witness


@pytest.fixture
def artifact(committed_projection, tmp_path):
    _, revision, source, _ = committed_projection
    target = tmp_path / "artifact"
    shutil.copytree(source, target)
    return target, revision


def test_valid_projection_binds_all_controlled_bytes(artifact):
    root, revision = artifact
    document = RuntimeIdentity(root).document({})
    assert document["source_revision"] == document["runtime_source_revision"] == revision
    assert document["build"]["state"] == "OBSERVED"
    assert document["source_binding"]["controlled_file_count"] == len(RUNTIME_FILES)
    assert document["source_binding"]["signature_verified"] is False
    assert document["production_ready"] is False
    assert document["receipt_minted"] is False


@pytest.mark.parametrize("corruption", ["missing", "malformed", "scalar", "missing-file",
                                         "duplicate", "wrong-source-path", "bad-digest",
                                         "bad-revision", "altered-engine", "oversized",
                                         "duplicate-json-field"])
def test_missing_or_malformed_witness_fails_closed(artifact, corruption):
    root, _ = artifact
    witness_path = root / WITNESS_NAME
    witness = json.loads(witness_path.read_text())
    if corruption == "missing":
        witness_path.unlink()
    elif corruption == "malformed":
        witness_path.write_text("{broken")
    elif corruption == "scalar":
        witness_path.write_text("null")
    elif corruption == "altered-engine":
        (root / "engine.py").write_text("altered = True\n")
    elif corruption == "oversized":
        witness_path.write_text(" " * 32_769)
    elif corruption == "duplicate-json-field":
        witness_path.write_text('{"schema":"bad",' + json.dumps(witness)[1:])
    else:
        if corruption == "missing-file":
            witness["files"].pop()
        elif corruption == "duplicate":
            witness["files"].append(witness["files"][0])
        elif corruption == "wrong-source-path":
            witness["files"][0]["source_path"] = "unrelated/app.py"
        elif corruption == "bad-digest":
            witness["files"][0]["sha256"] = "0" * 64
        elif corruption == "bad-revision":
            witness["source_revision"] = "unknown"
        witness["artifact_set_sha256"] = digest_records(witness["files"])
        witness_path.write_text(json.dumps(witness))
    document = RuntimeIdentity(root).document({"SZL_SOURCE_REVISION": "a" * 40})
    assert document["build"]["state"] == "UNAVAILABLE"
    assert document["source_revision"] == document["runtime_source_revision"] == "UNAVAILABLE"
    assert document["source_binding"]["failure_code"]


def test_runtime_and_witness_changes_after_startup_fail_closed(artifact):
    root, _ = artifact
    identity = RuntimeIdentity(root)
    original = (root / "engine.py").read_bytes()
    (root / "engine.py").write_bytes(original + b"\n# modified after startup\n")
    assert identity.document({})["source_binding"]["failure_code"] == "RUNTIME_FILE_CHANGED_AFTER_STARTUP"
    (root / "engine.py").write_bytes(original)
    (root / WITNESS_NAME).write_bytes((root / WITNESS_NAME).read_bytes() + b"\n")
    assert identity.document({})["source_binding"]["failure_code"] == "WITNESS_CHANGED_AFTER_STARTUP"


def test_revision_settings_cannot_override_or_disagree_with_witness(artifact):
    root, revision = artifact
    identity = RuntimeIdentity(root)
    for name in ("SZL_SOURCE_REVISION", "SZL_GIT_SHA"):
        assert identity.document({name: revision})["build"]["state"] == "OBSERVED"
        assert identity.document({name: "b" * 40})["source_revision"] == "UNAVAILABLE"


def test_all_finance_identity_routes_match_and_mint_no_receipts(artifact, monkeypatch):
    from services.finance import app as finance_app
    root, revision = artifact
    monkeypatch.setattr(finance_app, "IDENTITY", RuntimeIdentity(root))
    monkeypatch.delenv("SZL_SOURCE_REVISION", raising=False)
    monkeypatch.delenv("SZL_GIT_SHA", raising=False)
    before = finance_app.CHAIN.entries()
    client = TestClient(finance_app.app)
    documents = {}
    for path in IDENTITY_PATHS:
        response = client.get(path)
        assert response.status_code == 200
        documents[path] = response.json()
        assert documents[path]["receipt_minted"] is False
    assert validate_identity_documents(documents, expected_revision=revision) == []
    assert finance_app.CHAIN.entries() == before


def test_export_ignores_working_tree_pollution_and_refuses_existing_output(committed_projection, tmp_path):
    repo, revision, _, witness = committed_projection
    dirty = repo / "services/finance/engine.py"
    original = dirty.read_bytes()
    dirty.write_bytes(b"working tree differs from committed engine\n")
    cache = repo / "services/finance/__pycache__"
    cache.mkdir()
    (cache / "polluted.pyc").write_bytes(b"untracked bytecode")
    output = tmp_path / "export"
    try:
        actual = export(repo, revision, output)
        assert actual == witness
        assert (output / "engine.py").read_bytes() == original
        assert not (output / "__pycache__").exists()
        with pytest.raises(FileExistsError):
            export(repo, revision, output)
    finally:
        dirty.write_bytes(original)


def test_export_rejects_non_exact_revision_without_creating_output(committed_projection, tmp_path):
    repo, _, _, _ = committed_projection
    output = tmp_path / "export"
    with pytest.raises(ValueError, match="exact"):
        export(repo, "HEAD", output)
    assert not output.exists()
