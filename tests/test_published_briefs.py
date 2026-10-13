"""Published research survives artifact restarts without entering private state."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))

from szl_verticals import operational, published_briefs as archive
from szl_verticals.briefs import WeeklyBriefRequest, _canonical
from szl_verticals.connector_specs import CONNECTORS
from szl_verticals.contract import ALIASES, VERTICALS
from szl_verticals.evidence import resolve_evidence
from szl_verticals.store import ObservationStore

PACKAGED = archive.ARCHIVE_DIRECTORY
FILENAME = "2026-10-13.json"
REVISION = "a" * 40
TOKEN = "published-brief-private-test-session-000001"


@pytest.fixture
def api(tmp_path, monkeypatch):
    directory = tmp_path / "research_data"
    directory.mkdir()
    shutil.copyfile(PACKAGED / FILENAME, directory / FILENAME)
    monkeypatch.setattr(archive, "ARCHIVE_DIRECTORY", directory)
    monkeypatch.setenv("SZL_SOURCE_REVISION", REVISION)
    monkeypatch.setenv("SZL_STATE_PATH", str(tmp_path / "private.sqlite3"))
    store = ObservationStore()
    monkeypatch.setattr(operational, "STORE", store)
    app = FastAPI()
    app.include_router(operational.operational)
    with TestClient(app) as client:
        yield client, store, directory


@pytest.mark.parametrize("vertical", list(VERTICALS) + list(ALIASES))
def test_public_reads_all_engines_and_aliases_without_session(api, vertical):
    client, _, _ = api
    response = client.get(f"/api/verticals/{vertical}/published-briefs")
    assert response.status_code == 200
    result = response.json()
    assert result["vertical"] == ALIASES.get(vertical, vertical)
    assert result["scope"] == "SOURCE_CONTROLLED_PUBLIC_ARCHIVE"
    assert result["status"] == "AVAILABLE"
    assert len(result["items"]) == 1
    assert result["truth_label"] == "CALLER_REPORTED"
    assert result["review_status"] == "REVIEW_REQUIRED"
    assert result["counts_as_connector_evidence"] is False


def test_digests_bind_artifact_and_content_with_separate_source_revisions(api):
    client, _, directory = api
    item = client.get("/api/verticals/terra/published-briefs").json()["items"][0]
    raw = (directory / FILENAME).read_bytes()
    assert item["artifact_sha256"] == hashlib.sha256(raw).hexdigest()
    assert item["content_sha256"] == hashlib.sha256(
        _canonical({"vertical": "terra", "brief": item["brief"]}).encode("utf-8")
    ).hexdigest()
    assert item["research_source_revision"] == json.loads(raw)["source_revision"]
    assert item["runtime_source_revision"] == REVISION
    assert item["source_url"] == f"https://github.com/szl-holdings/vertical-services/blob/{REVISION}/{archive.ARCHIVE_REPOSITORY_PATH}/{FILENAME}"
    assert item["receipt"]["signature_claimed"] is False
    assert item["verification_claims"] == "CALLER_REPORTED_NOT_INDEPENDENTLY_VERIFIED"


def test_public_read_has_no_store_or_network_dependency(api, monkeypatch):
    client, _, _ = api

    class UnusableStore:
        def __getattr__(self, name):
            raise AssertionError(f"public archive accessed private store: {name}")

    def forbidden(*args, **kwargs):
        raise AssertionError("public archive must not fetch URLs")

    monkeypatch.setattr(operational, "STORE", UnusableStore())
    monkeypatch.setattr("szl_verticals.official_connectors._bounded_get", forbidden)
    assert client.get("/api/verticals/terra/published-briefs").status_code == 200


def test_private_briefs_stay_private_and_published_digests_are_not_evidence(api):
    client, store, directory = api
    request = copy.deepcopy(json.loads((directory / FILENAME).read_text())["briefs"]["terra"])
    request["title"] = "PRIVATE SESSION CONTENT"
    saved = client.post("/api/verticals/terra/briefs", headers={"X-SZL-Session": TOKEN}, json=request)
    assert saved.status_code == 200
    response = client.get("/api/verticals/terra/published-briefs")
    assert "PRIVATE SESSION CONTENT" not in response.text
    assert TOKEN not in response.text
    digest = response.json()["items"][0]["content_sha256"]
    scope = hashlib.sha256(TOKEN.encode()).hexdigest()
    evidence = resolve_evidence(store, vertical="terra", session_scope=scope,
                                digests=[digest], connectors=CONNECTORS)
    assert "EVIDENCE_REFERENCE_UNRESOLVED" in evidence.blockers
    assert store.counts(vertical="terra", session_scope=scope)["observations"] == 0
    brain = client.get("/api/verticals/terra/second-brain", headers={"X-SZL-Session": TOKEN}).json()
    assert brain["published_briefs"]["items"][0]["content_sha256"] == digest
    assert "brief" not in brain["published_briefs"]["items"][0]
    assert brain["weekly_briefs"]["items"][0]["title"] == "PRIVATE SESSION CONTENT"
    assert brain["memory"]["observations"] == []
    assert client.get("/api/verticals/terra/briefs").status_code == 422
    assert client.post("/api/verticals/terra/published-briefs", json=request).status_code == 405


@pytest.mark.parametrize("fault", ["missing", "empty", "malformed", "duplicate", "invalid_model", "filename", "file_bytes", "total_bytes", "file_count"])
def test_archive_failure_is_explicit_and_does_not_break_second_brain(api, monkeypatch, fault):
    client, _, directory = api
    path = directory / FILENAME
    if fault == "missing":
        shutil.rmtree(directory)
    elif fault == "empty":
        path.unlink()
    elif fault == "malformed":
        path.write_text("{broken")
    elif fault == "duplicate":
        path.write_text('{"schema":"a","schema":"b"}')
    elif fault == "invalid_model":
        bundle = json.loads(path.read_text())
        bundle["briefs"]["terra"]["truth_label"] = "VERIFIED"
        path.write_text(json.dumps(bundle))
    elif fault == "filename":
        path.rename(directory / "2026-10-12.json")
    elif fault == "file_bytes":
        monkeypatch.setattr(archive, "MAX_ARCHIVE_FILE_BYTES", 8)
    elif fault == "total_bytes":
        monkeypatch.setattr(archive, "MAX_ARCHIVE_TOTAL_BYTES", 8)
    else:
        monkeypatch.setattr(archive, "MAX_ARCHIVE_FILES", 0)
    response = client.get("/api/verticals/terra/published-briefs")
    assert response.status_code == 503
    assert response.json() == {"detail": "published brief archive unavailable"}
    assert str(directory) not in response.text
    brain = client.get("/api/verticals/terra/second-brain", headers={"X-SZL-Session": TOKEN})
    assert brain.status_code == 200
    assert brain.json()["published_briefs"]["status"] == "UNAVAILABLE"
    assert brain.json()["published_briefs"]["error_code"] == "PUBLISHED_BRIEFS_UNAVAILABLE"
    assert brain.json()["memory"]["observations"] == []
    assert client.get("/api/verticals/terra/connectors").status_code == 200


def test_result_limit_unknown_vertical_and_unbound_identity(api, monkeypatch):
    client, _, _ = api
    for limit in (0, 26):
        assert client.get(f"/api/verticals/terra/published-briefs?limit={limit}").status_code == 422
    assert client.get("/api/verticals/unknown/published-briefs").status_code == 404
    monkeypatch.setattr(archive, "runtime_source_identity", lambda: {"runtime_source_revision": "UNAVAILABLE"})
    item = client.get("/api/verticals/terra/published-briefs").json()["items"][0]
    assert item["runtime_source_revision"] == "UNAVAILABLE"
    assert item["source_url"] is None


def test_packaged_archive_survives_fresh_processes_without_state(tmp_path):
    """Model Docker's package COPY, not a checkout-relative fallback."""
    application = tmp_path / "app"
    application.mkdir()
    shutil.copytree(DEPLOY / "szl_verticals", application / "szl_verticals", ignore=shutil.ignore_patterns("__pycache__"))
    (application / "source_revision.txt").write_text(REVISION)
    assert "COPY deploy/szl_verticals/ ./szl_verticals/" in (DEPLOY / "Dockerfile").read_text()
    assert not (ROOT / "docs" / "briefings" / FILENAME).exists()
    command = [sys.executable, "-c", "import json; from szl_verticals.published_briefs import published_briefs; print(json.dumps(published_briefs('terra')))"]
    env = {**os.environ, "PYTHONPATH": str(application), "SZL_SOURCE_REVISION": REVISION,
           "SZL_STATE_PATH": str(tmp_path / "never-created.sqlite3")}
    first = json.loads(subprocess.check_output(command, cwd=application, env=env, text=True))
    second = json.loads(subprocess.check_output(command, cwd=application, env=env, text=True))
    assert first == second
    assert first["runtime_source_revision"] == REVISION
    assert not (tmp_path / "never-created.sqlite3").exists()
    assert first["items"][0]["artifact_sha256"] == hashlib.sha256((PACKAGED / FILENAME).read_bytes()).hexdigest()
