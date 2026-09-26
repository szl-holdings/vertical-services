"""Local replay contract. Stdlib only. Not estate qualification."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))


class ReplayMixinContract(unittest.TestCase):
    def test_mixin_symbols(self):
        from szl_verticals.replay_store import REPLAY_SCHEMA, ReplayStoreMixin
        self.assertTrue(hasattr(ReplayStoreMixin, "withdraw_payloads"))
        self.assertIn("evidence_withdrawals", REPLAY_SCHEMA)

    def test_store_inherits(self):
        from szl_verticals.replay_store import ReplayStoreMixin
        from szl_verticals.store import ObservationStore
        self.assertTrue(issubclass(ObservationStore, ReplayStoreMixin))

    def test_withdraw_latches_cache(self):
        from szl_verticals.store import ObservationStore
        digest = "ab" * 32
        receipt = {
            "receipt_id": "c" * 64,
            "vertical": "counsel",
            "connector_id": "unit",
            "session_scope": "s1",
            "query_hash": "d" * 64,
            "observed_at": 1.0,
            "expires_at": 9.0e18,
            "source_url": "https://example.test/src",
            "http_status": 200,
            "payload_sha256": digest,
            "truth_label": "REPORTED",
            "state": "OBSERVED",
        }
        fd, path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        old = os.environ.get("SZL_STATE_PATH")
        os.environ["SZL_STATE_PATH"] = path
        try:
            store = ObservationStore()
            store.put(receipt, {"k": "v"})
            self.assertIsNotNone(store.cached(
                vertical="counsel", connector_id="unit",
                session_scope="s1", query_hash="d" * 64,
            ))
            store.withdraw_payloads(
                vertical="counsel", session_scope="s1",
                payload_digests=[digest], now=2.0,
            )
            self.assertIsNone(store.cached(
                vertical="counsel", connector_id="unit",
                session_scope="s1", query_hash="d" * 64,
            ))
            rows = store.resolve_payloads(
                vertical="counsel", session_scope="s1",
                payload_digests=[digest],
            )
            self.assertEqual(len(rows), 1)
            self.assertTrue(bool(rows[0]["withdrawn"]))
        finally:
            if old is None:
                os.environ.pop("SZL_STATE_PATH", None)
            else:
                os.environ["SZL_STATE_PATH"] = old
            try:
                os.remove(path)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
