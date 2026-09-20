"""Inbound HTTP bounds. Fixture results are not estate qualification."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_PATH = str(ROOT / "deploy")
if DEPLOY_PATH not in sys.path:
    sys.path.insert(0, DEPLOY_PATH)

from szl_verticals.http_bounds import (  # noqa: E402
    MAX_BODY_BYTES,
    BodyBoundError,
    accumulate_sync,
    parse_declared_content_length,
    parse_strict_json,
)

_TEST_STATE_DIR = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "unit-test-key-do-not-use-in-production")
os.environ.setdefault("SZL_SOURCE_REVISION", "1" * 40)
os.environ.setdefault(
    "SZL_STATE_PATH",
    str(Path(_TEST_STATE_DIR.name) / "vertical-services.sqlite3"),
)


class InboundLimitUnitTests(unittest.TestCase):
    def test_missing_content_length_is_allowed(self) -> None:
        self.assertIsNone(parse_declared_content_length({}))

    def test_non_numeric_content_length(self) -> None:
        with self.assertRaises(BodyBoundError) as ctx:
            parse_declared_content_length({"content-length": "not-a-number"})
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.code, "INVALID_CONTENT_LENGTH")

    def test_declared_oversize_rejected_before_read(self) -> None:
        with self.assertRaises(BodyBoundError) as ctx:
            parse_declared_content_length({"content-length": str(MAX_BODY_BYTES + 1)})
        self.assertEqual(ctx.exception.status_code, 413)

    def test_false_content_length_mismatch(self) -> None:
        with self.assertRaises(BodyBoundError) as ctx:
            accumulate_sync([b"abcd"], declared_length=2)
        self.assertEqual(ctx.exception.code, "CONTENT_LENGTH_MISMATCH")

    def test_incremental_oversize_stops_before_full_buffer(self) -> None:
        chunks = [b"x" * 16_384 for _ in range((MAX_BODY_BYTES // 16_384) + 2)]
        with self.assertRaises(BodyBoundError) as ctx:
            accumulate_sync(iter(chunks))
        self.assertEqual(ctx.exception.status_code, 413)

    def test_deadline_is_monotonic(self) -> None:
        clock = {"t": 0.0}

        def now() -> float:
            clock["t"] += 9.0
            return clock["t"]

        with self.assertRaises(BodyBoundError) as ctx:
            accumulate_sync([b"{}"], started_at=0.0, now=now)
        self.assertEqual(ctx.exception.status_code, 408)
        self.assertEqual(ctx.exception.code, "READ_DEADLINE")

    def test_duplicate_json_keys(self) -> None:
        with self.assertRaises(BodyBoundError) as ctx:
            parse_strict_json(b'{"a":1,"a":2}')
        self.assertEqual(ctx.exception.code, "DUPLICATE_JSON_KEY")

    def test_nan_rejected(self) -> None:
        with self.assertRaises(BodyBoundError) as ctx:
            parse_strict_json(b'{"a":NaN}')
        self.assertEqual(ctx.exception.code, "NONFINITE_JSON")

    def test_invalid_unicode(self) -> None:
        with self.assertRaises(BodyBoundError) as ctx:
            parse_strict_json(b"\xff\xfe")
        self.assertEqual(ctx.exception.code, "INVALID_UNICODE")

    def test_array_rejected(self) -> None:
        with self.assertRaises(BodyBoundError) as ctx:
            parse_strict_json(b"[1]")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_legitimate_small_body_passes(self) -> None:
        raw = json.dumps({"stream": "latency", "value": 1.0}).encode("utf-8")
        body = accumulate_sync([raw], declared_length=len(raw))
        self.assertEqual(parse_strict_json(body)["stream"], "latency")


class InboundLimitAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app_path = ROOT / "deploy" / "app.py"
        spec = importlib.util.spec_from_file_location("vertical_services_app_bounds", app_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        from fastapi.testclient import TestClient

        cls.module = module
        cls.client = TestClient(module.app)
        cls.client.headers.update({"X-SZL-Session": "unit-test-session-token-0123456789"})

    def test_existing_small_post_still_works(self) -> None:
        response = self.client.post(
            "/lyte/v1/metrics",
            json={"stream": "bounds-ok", "value": 1.0},
        )
        self.assertEqual(response.status_code, 200)

    def test_actual_oversize_is_413(self) -> None:
        response = self.client.post(
            "/lyte/v1/metrics",
            content=b"{" + (b"x" * (MAX_BODY_BYTES + 1)) + b"}",
            headers={"content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 413)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["code"], "BODY_TOO_LARGE")
        self.assertFalse(body["production_authorization"])

    def test_duplicate_keys_are_400(self) -> None:
        raw = b'{"stream":"latency","stream":"other","value":1}'
        response = self.client.post(
            "/lyte/v1/metrics",
            content=raw,
            headers={"content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "DUPLICATE_JSON_KEY")


if __name__ == "__main__":
    unittest.main()
