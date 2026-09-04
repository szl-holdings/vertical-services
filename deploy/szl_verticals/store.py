"""Bounded SQLite observation ledger for the SZL vertical fabric."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Mapping

class ObservationStore:
    """Small bounded observation ledger.

    The default path is an ephemeral file. A persistent claim is emitted only
    when the operator explicitly sets SZL_STATE_DURABILITY=persistent.
    """

    def __init__(self) -> None:
        configured = os.environ.get("SZL_STATE_PATH", "").strip()
        self.path = Path(configured or "/tmp/szl-vertical-services.sqlite3")
        self.durability = (
            "PERSISTENT_CONFIGURED"
            if os.environ.get("SZL_STATE_DURABILITY", "").strip().lower() == "persistent"
            else "EPHEMERAL_FILE"
        )
        self._lock = threading.RLock()
        self.error: str | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as connection:
                connection.executescript(
                    """
                    PRAGMA journal_mode=WAL;
                    PRAGMA synchronous=NORMAL;
                    CREATE TABLE IF NOT EXISTS connector_observations (
                        receipt_id TEXT PRIMARY KEY,
                        vertical TEXT NOT NULL,
                        connector_id TEXT NOT NULL,
                        session_scope TEXT NOT NULL,
                        query_hash TEXT NOT NULL,
                        observed_at REAL NOT NULL,
                        expires_at REAL NOT NULL,
                        source_url TEXT NOT NULL,
                        http_status INTEGER NOT NULL,
                        payload_sha256 TEXT NOT NULL,
                        summary_json TEXT NOT NULL,
                        truth_label TEXT NOT NULL,
                        state TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_connector_cache
                    ON connector_observations(vertical, connector_id, session_scope, query_hash, expires_at);
                    CREATE INDEX IF NOT EXISTS idx_connector_recent
                    ON connector_observations(vertical, session_scope, observed_at DESC);
                    """
                )
                connection.commit()
        except (OSError, sqlite3.Error) as exc:
            self.error = f"{type(exc).__name__}: {exc}"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def status(self) -> dict[str, Any]:
        return {
            "writable": self.error is None,
            "durability": self.durability if self.error is None else "UNAVAILABLE",
            "configured_path": bool(os.environ.get("SZL_STATE_PATH", "").strip()),
            "persistent_claim_explicit": self.durability == "PERSISTENT_CONFIGURED",
            "error": self.error,
        }

    def put(self, receipt: Mapping[str, Any], summary: Mapping[str, Any]) -> None:
        if self.error:
            raise RuntimeError(self.error)
        serialized = json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if len(serialized.encode("utf-8")) > 512_000:
            raise RuntimeError("normalized connector summary exceeds 512000 bytes")
        with self._lock, closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO connector_observations
                (receipt_id, vertical, connector_id, session_scope, query_hash,
                 observed_at, expires_at, source_url, http_status, payload_sha256,
                 summary_json, truth_label, state)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt["receipt_id"],
                    receipt["vertical"],
                    receipt["connector_id"],
                    receipt["session_scope"],
                    receipt["query_hash"],
                    receipt["observed_at"],
                    receipt["expires_at"],
                    receipt["source_url"],
                    receipt["http_status"],
                    receipt["payload_sha256"],
                    serialized,
                    receipt["truth_label"],
                    receipt["state"],
                ),
            )
            connection.commit()

    def cached(
        self,
        *,
        vertical: str,
        connector_id: str,
        session_scope: str,
        query_hash: str,
    ) -> dict[str, Any] | None:
        if self.error:
            return None
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT * FROM connector_observations
                WHERE vertical=? AND connector_id=? AND session_scope=? AND query_hash=?
                  AND expires_at > ?
                  AND state='OBSERVED'
                ORDER BY observed_at DESC LIMIT 1
                """,
                (vertical, connector_id, session_scope, query_hash, time.time()),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["summary"] = json.loads(result.pop("summary_json"))
        return result

    def recent(self, *, vertical: str, session_scope: str, limit: int = 25) -> list[dict[str, Any]]:
        if self.error:
            return []
        with self._lock, closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT receipt_id, connector_id, observed_at, source_url, http_status,
                       payload_sha256, truth_label, state, summary_json
                FROM connector_observations
                WHERE vertical=? AND session_scope=?
                ORDER BY observed_at DESC LIMIT ?
                """,
                (vertical, session_scope, max(1, min(limit, 100))),
            ).fetchall()
        output: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["summary"] = json.loads(item.pop("summary_json"))
            output.append(item)
        return output

    def counts(self, *, vertical: str, session_scope: str | None = None) -> dict[str, int]:
        if self.error:
            return {"observations": 0, "connectors_observed": 0}
        where = "vertical=?"
        params: list[Any] = [vertical]
        if session_scope is not None:
            where += " AND session_scope=?"
            params.append(session_scope)
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS observations,
                       COUNT(DISTINCT connector_id) AS connectors_observed
                FROM connector_observations WHERE {where} AND state='OBSERVED'
                """,
                params,
            ).fetchone()
        return {
            "observations": int(row["observations"]),
            "connectors_observed": int(row["connectors_observed"]),
        }


STORE = ObservationStore()
