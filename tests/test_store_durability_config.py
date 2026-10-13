"""A persistence flag alone must not relabel the default ephemeral ledger."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))

from szl_verticals.briefs import WeeklyBriefRequest
from szl_verticals.store import ObservationStore


def assert_writable_brief_ledger(store: ObservationStore) -> None:
    """Changing the label must preserve ordinary ledger writes and reads."""
    assert store.status()["writable"] is True
    assert store.status()["error"] is None
    brief = WeeklyBriefRequest(
        week_start="2026-10-12", title="Weekly review",
        coverage_state="NO_MATERIAL_CHANGE",
        coverage_note="No material developments met the inclusion threshold.",
    )
    saved = store.put_brief("terra", "test-durability-scope", brief)
    assert saved["inserted"] is True
    assert store.recent_briefs("terra", "test-durability-scope")[0]["content_sha256"] == saved["content_sha256"]


@pytest.mark.parametrize("path_value", [None, "   "])
def test_persistent_flag_without_explicit_path_remains_ephemeral(tmp_path, monkeypatch, path_value):
    if path_value is None:
        monkeypatch.delenv("SZL_STATE_PATH", raising=False)
    else:
        monkeypatch.setenv("SZL_STATE_PATH", path_value)
    monkeypatch.setenv("SZL_STATE_DURABILITY", "persistent")

    # Exercise real SQLite without touching the shared default test database.
    class IsolatedDefaultStore(ObservationStore):
        def _connect(self):
            connection = sqlite3.connect(tmp_path / "isolated-default.sqlite3")
            connection.row_factory = sqlite3.Row
            return connection

    store = IsolatedDefaultStore()
    assert store.path == Path("/tmp/szl-vertical-services.sqlite3")
    status = store.status()
    assert status["durability"] == "EPHEMERAL_FILE"
    assert status["configured_path"] is False
    assert status["persistent_claim_explicit"] is False
    assert_writable_brief_ledger(store)


def test_explicit_path_and_persistent_flag_report_configuration(tmp_path, monkeypatch):
    state_path = tmp_path / "explicit.sqlite3"
    monkeypatch.setenv("SZL_STATE_PATH", str(state_path))
    monkeypatch.setenv("SZL_STATE_DURABILITY", " PeRsIsTeNt ")
    store = ObservationStore()
    assert store.path == state_path
    status = store.status()
    assert status["durability"] == "PERSISTENT_CONFIGURED"
    assert status["configured_path"] is True
    assert status["persistent_claim_explicit"] is True
    assert_writable_brief_ledger(store)


@pytest.mark.parametrize("durability", [None, "", "ephemeral"])
def test_explicit_path_without_persistent_flag_remains_ephemeral(tmp_path, monkeypatch, durability):
    monkeypatch.setenv("SZL_STATE_PATH", str(tmp_path / "configured.sqlite3"))
    if durability is None:
        monkeypatch.delenv("SZL_STATE_DURABILITY", raising=False)
    else:
        monkeypatch.setenv("SZL_STATE_DURABILITY", durability)
    store = ObservationStore()
    status = store.status()
    assert status["durability"] == "EPHEMERAL_FILE"
    assert status["configured_path"] is True
    assert status["persistent_claim_explicit"] is False
    assert_writable_brief_ledger(store)
