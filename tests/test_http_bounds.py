"""Inbound HTTP bounds. Fixture results are not estate qualification."""
from __future__ import annotations

import importlib.util
import json
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_PATH = str(ROOT / "deploy")
if DEPLOY_PATH not in sys.path:
    sys.path.insert(0, DEPLOY_PATH)

from fastapi import HTTPException  # noqa: E402

from szl_verticals import http_bounds  # noqa: E402
from szl_verticals.contract import canonical_vertical  # noqa: E402
from szl_verticals.http_bounds import (  # noqa: E402
    MAX_BODY_BYTES,
    MAX_JSON_DEPTH,
    BodyBoundError,
    accumulate_sync,
    body_is_parsed_as_json,
    json_nesting_depth,
    maybe_parse_json,
    parse_declared_content_length,
    parse_strict_json,
)

# Content types FastAPI decodes as JSON (absent, empty, application/json,
# application/*+json; parameters and case ignored), and ones it hands to the
# route as raw bytes. ``None`` means the request carries no Content-Type.
JSON_CONTENT_TYPES = (
    None,
    "",
    "application/json",
    "application/json; charset=utf-8",
    "Application/JSON",
    "application/vnd.api+json",
    "application/merge-patch+json",
    "application/problem+json; charset=utf-8",
)
NON_JSON_CONTENT_TYPES = (
    "text/plain",
    "text/json",
    "application/jsonx",
    "application/json-seq",
    "application/octet-stream",
    "application/x-www-form-urlencoded",
    "multipart/form-data; boundary=bounds",
    "text/plain; note=application/json",
    "application/json, text/plain",
    "json",
)


def _headers(content_type: str | None) -> dict[str, str]:
    return {} if content_type is None else {"content-type": content_type}


def _nested_object(depth: int) -> str:
    """A JSON object whose container nesting is exactly ``depth`` (>= 1)."""
    return '{"a":' * (depth - 1) + "{}" + "}" * (depth - 1)


def _nested_array_in_object(depth: int) -> str:
    """An object holding arrays, total container nesting exactly ``depth`` (>= 2)."""
    return '{"a":' + "[" * (depth - 1) + "]" * (depth - 1) + "}"


def _true_depth(value: object) -> int:
    if isinstance(value, dict):
        return 1 + max((_true_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_true_depth(item) for item in value), default=0)
    return 0


# String content that would fool a naive bracket counter: quotes, backslashes
# (a string ending in an escaped backslash), brackets, and non-ASCII.
_TRICKY_CHARS = ('"', "\\", "[", "]", "{", "}", "a", "\u00e9", "\u2028", "\n")


def _random_json_value(rng: random.Random, depth: int) -> object:
    roll = rng.random()
    if depth >= 8 or roll < 0.3:
        return rng.choice(
            [1, 2.5, True, None, "".join(rng.choice(_TRICKY_CHARS) for _ in range(rng.randint(0, 6)))]
        )
    if roll < 0.65:
        return [_random_json_value(rng, depth + 1) for _ in range(rng.randint(0, 3))]
    return {
        "".join(rng.choice(_TRICKY_CHARS) for _ in range(rng.randint(0, 4))): _random_json_value(rng, depth + 1)
        for _ in range(rng.randint(0, 3))
    }

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


class ContentTypeGateUnitTests(unittest.TestCase):
    """The strict parser runs on exactly the bodies FastAPI decodes as JSON."""

    def test_json_content_types_are_parsed_as_json(self) -> None:
        for content_type in JSON_CONTENT_TYPES:
            with self.subTest(content_type=content_type):
                self.assertTrue(body_is_parsed_as_json(_headers(content_type)))

    def test_title_case_header_name_is_read(self) -> None:
        self.assertTrue(body_is_parsed_as_json({"Content-Type": "application/vnd.api+json"}))
        self.assertFalse(body_is_parsed_as_json({"Content-Type": "text/plain"}))

    def test_other_content_types_are_not_parsed_as_json(self) -> None:
        for content_type in NON_JSON_CONTENT_TYPES:
            with self.subTest(content_type=content_type):
                self.assertFalse(body_is_parsed_as_json(_headers(content_type)))

    def test_duplicate_keys_rejected_for_every_json_content_type(self) -> None:
        for content_type in JSON_CONTENT_TYPES:
            with self.subTest(content_type=content_type):
                with self.assertRaises(BodyBoundError) as ctx:
                    maybe_parse_json(_headers(content_type), b'{"a":1,"a":2}')
                self.assertEqual(ctx.exception.code, "DUPLICATE_JSON_KEY")
                self.assertEqual(ctx.exception.status_code, 400)

    def test_empty_body_is_not_parsed(self) -> None:
        for content_type in JSON_CONTENT_TYPES:
            with self.subTest(content_type=content_type):
                self.assertIsNone(maybe_parse_json(_headers(content_type), b""))


class NestingDepthUnitTests(unittest.TestCase):
    def test_depth_of_simple_documents(self) -> None:
        self.assertEqual(json_nesting_depth("1"), 0)
        self.assertEqual(json_nesting_depth('"x"'), 0)
        self.assertEqual(json_nesting_depth("{}"), 1)
        self.assertEqual(json_nesting_depth('{"a":[1,{"b":[]}]}'), 4)
        self.assertEqual(json_nesting_depth(_nested_object(7)), 7)
        self.assertEqual(json_nesting_depth(_nested_array_in_object(7)), 7)

    def test_brackets_inside_strings_are_not_counted(self) -> None:
        text = json.dumps({"a": "[" * 500 + "{" * 500, "b": '\\"[[[', "c": "\\"})
        self.assertEqual(json_nesting_depth(text), 1)
        # A string ending in an escaped backslash must still close the string.
        text = json.dumps({"a": "\\", "b": [[[]]]})
        self.assertEqual(json_nesting_depth(text), 4)

    def test_depth_matches_parsed_structure_for_random_documents(self) -> None:
        rng = random.Random(20260926)
        for _ in range(3000):
            value = _random_json_value(rng, 0)
            text = json.dumps(value, ensure_ascii=rng.random() < 0.5, indent=rng.choice([None, 1]))
            self.assertEqual(json_nesting_depth(text), _true_depth(value), text)

    def test_object_at_depth_limit_is_accepted(self) -> None:
        self.assertEqual(MAX_JSON_DEPTH, 64)
        for build in (_nested_object, _nested_array_in_object):
            with self.subTest(shape=build.__name__):
                value = parse_strict_json(build(MAX_JSON_DEPTH).encode("utf-8"))
                self.assertIsInstance(value, dict)

    def test_object_one_past_depth_limit_is_rejected(self) -> None:
        for build in (_nested_object, _nested_array_in_object):
            with self.subTest(shape=build.__name__):
                with self.assertRaises(BodyBoundError) as ctx:
                    parse_strict_json(build(MAX_JSON_DEPTH + 1).encode("utf-8"))
                self.assertEqual(ctx.exception.code, "JSON_TOO_DEEP")
                self.assertEqual(ctx.exception.status_code, 400)

    def test_audit_payloads_under_byte_budget_are_client_errors(self) -> None:
        # The byte budget does not bound depth; each of these raised
        # RecursionError (HTTP 500) before the explicit depth bound.
        payloads = (
            b"[" * 30000 + b"]" * 30000,
            b'{"a":' * 20000 + b"1" + b"}" * 20000,
            b"[" * 60000,
            b"{" * MAX_BODY_BYTES,
        )
        for raw in payloads:
            self.assertLessEqual(len(raw), MAX_BODY_BYTES)
            with self.subTest(size=len(raw), head=raw[:8]):
                with self.assertRaises(BodyBoundError) as ctx:
                    parse_strict_json(raw)
                self.assertEqual(ctx.exception.code, "JSON_TOO_DEEP")
                self.assertEqual(ctx.exception.status_code, 400)

    def test_recursion_error_maps_to_client_error_if_bound_is_raised(self) -> None:
        with mock.patch.object(http_bounds, "MAX_JSON_DEPTH", 10**9):
            with self.assertRaises(BodyBoundError) as ctx:
                parse_strict_json(b"[" * 100_000)
        self.assertEqual(ctx.exception.code, "JSON_TOO_DEEP")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIsInstance(ctx.exception.__cause__, RecursionError)


class UnknownVerticalUnitTests(unittest.TestCase):
    def test_unknown_vertical_detail_is_fixed(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            canonical_vertical("zz-echo-marker")
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "unknown vertical")

    def test_known_vertical_and_alias_still_resolve(self) -> None:
        self.assertEqual(canonical_vertical("Finance"), "finance")
        self.assertEqual(canonical_vertical(" puriq "), "finance")


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

    def assertBoundsError(self, response, status_code: int, code: str) -> None:  # noqa: N802
        self.assertEqual(response.status_code, status_code, response.text)
        self.assertEqual(
            response.json(),
            {
                "ok": False,
                "error": response.json()["error"],
                "code": code,
                "production_authorization": False,
                "effectors_enabled": False,
            },
        )

    def test_gate_matches_fastapi_json_decoding(self) -> None:
        # Pins body_is_parsed_as_json to the installed FastAPI: a valid JSON
        # object is accepted by the route exactly when FastAPI decodes it.
        raw = json.dumps({"stream": "gate-contract", "value": 1.0}).encode("utf-8")
        for content_type in JSON_CONTENT_TYPES + NON_JSON_CONTENT_TYPES:
            with self.subTest(content_type=content_type):
                headers = _headers(content_type)
                response = self.client.post("/lyte/v1/metrics", content=raw, headers=headers)
                expected = 200 if body_is_parsed_as_json(headers) else 422
                self.assertEqual(response.status_code, expected, response.text)

    def test_duplicate_keys_rejected_whatever_the_content_type(self) -> None:
        # Audit repro (Hatun): application/json 400, no Content-Type 200,
        # application/vnd.api+json 200. All JSON-decoded forms must be 400.
        hatun = b'{"intent":"first","intent":"second","axes":{"evidence":0.9,"freshness":0.9}}'
        sentra = b'{"actor":"a","actor":"b","action":"read","resource":"r"}'
        routes = (("/api/verticals/puriq/hatun/evaluate", hatun), ("/sentra/v1/evaluate", sentra))
        for path, raw in routes:
            for content_type in JSON_CONTENT_TYPES:
                with self.subTest(path=path, content_type=content_type):
                    response = self.client.post(path, content=raw, headers=_headers(content_type))
                    self.assertBoundsError(response, 400, "DUPLICATE_JSON_KEY")
            # Other content types are never decoded as JSON, so no last-wins
            # object is read. Types that mention application/json keep the
            # earlier gate's fixed-body 400; the rest reach the route's 422.
            for content_type in NON_JSON_CONTENT_TYPES:
                with self.subTest(path=path, content_type=content_type):
                    response = self.client.post(path, content=raw, headers=_headers(content_type))
                    if "application/json" in content_type.lower():
                        self.assertBoundsError(response, 400, "DUPLICATE_JSON_KEY")
                    else:
                        self.assertEqual(response.status_code, 422, response.text)

    def test_non_finite_numbers_rejected_whatever_the_content_type(self) -> None:
        # Audit repro: no Content-Type and +json answered 500, not 400.
        raw = b'{"actor":"a","action":"read","resource":"r","risk_score":NaN}'
        for content_type in JSON_CONTENT_TYPES:
            with self.subTest(content_type=content_type):
                response = self.client.post("/sentra/v1/evaluate", content=raw, headers=_headers(content_type))
                self.assertBoundsError(response, 400, "NONFINITE_JSON")

    def test_deep_nesting_is_400_not_500(self) -> None:
        payloads = (
            ("/api/verticals/puriq/hatun/evaluate", b"[" * 30000 + b"]" * 30000),
            ("/sentra/v1/evaluate", b'{"a":' * 20000 + b"1" + b"}" * 20000),
            ("/sentra/v1/evaluate", b"[" * 60000),
        )
        for path, raw in payloads:
            for content_type in (None, "application/json", "application/vnd.api+json"):
                with self.subTest(path=path, size=len(raw), content_type=content_type):
                    response = self.client.post(path, content=raw, headers=_headers(content_type))
                    self.assertBoundsError(response, 400, "JSON_TOO_DEEP")

    def test_depth_boundary_through_the_app(self) -> None:
        # At the limit the body reaches the route (which rejects the unknown
        # field with 422); one level deeper the bounds middleware answers 400.
        at_limit = '{"stream":"depth","value":1.0,"extra":' + _nested_object(MAX_JSON_DEPTH - 1) + "}"
        over_limit = '{"stream":"depth","value":1.0,"extra":' + _nested_object(MAX_JSON_DEPTH) + "}"
        self.assertEqual(json_nesting_depth(at_limit), MAX_JSON_DEPTH)
        self.assertEqual(json_nesting_depth(over_limit), MAX_JSON_DEPTH + 1)
        headers = {"content-type": "application/json"}
        response = self.client.post("/lyte/v1/metrics", content=at_limit.encode(), headers=headers)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertNotIn("JSON_TOO_DEEP", response.text)
        response = self.client.post("/lyte/v1/metrics", content=over_limit.encode(), headers=headers)
        self.assertBoundsError(response, 400, "JSON_TOO_DEEP")

    def test_unknown_vertical_is_not_echoed(self) -> None:
        marker = "zz-echo-marker-5c1e"
        requests = (
            ("GET", f"/api/verticals/{marker}/frontier"),
            ("GET", f"/api/verticals/{marker}/intelligence"),
            ("GET", f"/api/verticals/{marker}/formulas"),
            ("GET", f"/api/verticals/{marker}/anatomy"),
            ("GET", f"/api/verticals/{marker}/connectors"),
        )
        for method, path in requests:
            with self.subTest(path=path):
                response = self.client.request(method, path)
                self.assertEqual(response.status_code, 404, response.text)
                self.assertEqual(response.json(), {"detail": "unknown vertical"})
                self.assertNotIn(marker, response.text)
        response = self.client.post(
            f"/api/verticals/{marker}/hatun/evaluate",
            json={"intent": "review", "axes": {"evidence": 0.9, "freshness": 0.9}},
        )
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(response.json(), {"detail": "unknown vertical"})


if __name__ == "__main__":
    unittest.main()
