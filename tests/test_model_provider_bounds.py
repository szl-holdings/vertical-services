"""Provider admission through real httpx streams and the actual invoke path.

MockTransport is the only substituted transport; response iteration, response
cleanup, JSON admission, evidence checks, and output extraction stay real.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException

from test_evidence_resolution import DIGESTS, SCOPE, ledger, put
from test_intelligence_evidence_admission import request as intelligence_request, runtime
from test_public_khipu_integration import (
    public_runtime,
    reply as public_reply,
    request as public_request,
)
from szl_verticals.provider_response import MAX_PROVIDER_BYTES, MAX_PROVIDER_JSON_DEPTH


PRIVATE_BODY = "provider-private-body-must-stay-out-of-errors"
OUTPUT = "Synthetic provider output: caf\u00e9 \u2615"
WIRE_CHUNK_BYTES = 64 * 1024


class TrackedStream(httpx.AsyncByteStream):
    """Record what httpx actually pulls from an unbuffered transport response."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.chunks_read = 0
        self.bytes_read = 0
        self.exhausted = False
        self.close_calls = 0

    async def __aiter__(self):
        for chunk in self.chunks:
            self.chunks_read += 1
            self.bytes_read += len(chunk)
            yield chunk
        self.exhausted = True

    async def aclose(self):
        self.close_calls += 1


@pytest.fixture
def bound_runtime(runtime, ledger):
    for digest in DIGESTS[:2]:
        put(ledger, digest)
    return runtime


def _reply_bytes(protocol="openai-chat", text=PRIVATE_BODY, **extra):
    if protocol == "hf-text-generation":
        value = [{"generated_text": text, **extra}]
    else:
        value = {"choices": [{"message": {"content": text}}], **extra}
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _serve(runtime, monkeypatch, stream, *, headers=None, status=200, on_request=None):
    """Use httpx's real client/stream manager, including exceptional cleanup."""
    real_client = httpx.AsyncClient
    response = httpx.Response(
        status,
        headers={"content-type": "application/json"} if headers is None else headers,
        stream=stream,
    )
    seen = []

    def handle(req):
        seen.append(req)
        assert req.method == "POST"
        assert req.headers["accept-encoding"] == "identity"
        if on_request is not None:
            on_request(req)
        return response

    monkeypatch.setattr(
        runtime.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    return response, seen


def _invoke(runtime, payload=None):
    if payload is None:
        payload = intelligence_request(runtime)
    return asyncio.run(runtime.vertical_intelligence_invoke("finance", payload, SCOPE))


def _rejected(runtime, payload=None):
    with pytest.raises(HTTPException) as error:
        _invoke(runtime, payload)
    assert error.value.status_code == 502
    assert PRIVATE_BODY not in str(error.value.detail)
    assert PRIVATE_BODY not in str(error.value)
    return error.value


@pytest.mark.parametrize("length", [None, "1", "oversized"], ids=[
    "no-content-length", "understated-content-length", "oversized-content-length",
])
def test_size_rejection_stops_transport_before_unread_tail(bound_runtime, monkeypatch, length):
    # Valid JSON followed by whitespace would be accepted by an eager JSON
    # decoder. The transport supplies considerably more than the byte budget.
    first = _reply_bytes()
    chunks = [first + b" " * (WIRE_CHUNK_BYTES - len(first))]
    chunks += [b" " * WIRE_CHUNK_BYTES] * (MAX_PROVIDER_BYTES // WIRE_CHUNK_BYTES + 8)
    chunks.append(b"unread-private-tail-" + PRIVATE_BODY.encode())
    stream = TrackedStream(chunks)
    headers = {"content-type": "application/json"}
    if length is not None:
        headers["content-length"] = str(MAX_PROVIDER_BYTES + 1) if length == "oversized" else length
    response, seen = _serve(bound_runtime, monkeypatch, stream, headers=headers)

    error = _rejected(bound_runtime)

    assert "size" in error.detail
    assert len(seen) == 1
    assert response.is_closed and stream.close_calls == 1
    assert not stream.exhausted
    assert stream.chunks_read < len(chunks) - 1
    if length == "oversized":
        assert stream.bytes_read == 0
    else:
        # One transport chunk may cross the limit; no subsequent chunk may be
        # requested. This fails if client.post()/aread() first drains the body.
        assert MAX_PROVIDER_BYTES < stream.bytes_read <= MAX_PROVIDER_BYTES + WIRE_CHUNK_BYTES


@pytest.mark.parametrize("extra_byte", [0, 1], ids=["exact-budget", "one-byte-over-budget"])
def test_byte_budget_boundary_for_valid_json(bound_runtime, monkeypatch, extra_byte):
    body = _reply_bytes(text=OUTPUT)
    body += b" " * (MAX_PROVIDER_BYTES + extra_byte - len(body))
    stream = TrackedStream([body[n:n + 32768] for n in range(0, len(body), 32768)])
    response, seen = _serve(bound_runtime, monkeypatch, stream)

    if extra_byte:
        assert "size" in _rejected(bound_runtime).detail
    else:
        assert _invoke(bound_runtime)["output"] == OUTPUT

    assert len(seen) == 1
    assert response.is_closed and stream.close_calls == 1


@pytest.mark.parametrize("declared_delta", [-1, 1], ids=["understated", "overstated"])
def test_in_budget_content_length_mismatch_is_rejected(bound_runtime, monkeypatch, declared_delta):
    body = _reply_bytes()
    stream = TrackedStream([body[:9], body[9:]])
    response, _ = _serve(bound_runtime, monkeypatch, stream, headers={
        "content-type": "application/json", "content-length": str(len(body) + declared_delta),
    })

    assert "Content-Length" in _rejected(bound_runtime).detail
    assert stream.exhausted
    assert response.is_closed and stream.close_calls == 1


@pytest.mark.parametrize("protocol", ["hf-text-generation", "openai-chat"])
@pytest.mark.parametrize("mime", [
    "application/json", "application/vnd.szl.model+json",
    "Application/Vnd.SZL.Model+JSON; charset=UTF-8",
])
def test_valid_provider_shapes_and_json_media_types_are_accepted(
    bound_runtime, monkeypatch, protocol, mime,
):
    monkeypatch.setenv("SZL_MODEL_PROTOCOL_RECEIPT_AGENT", protocol)
    body = _reply_bytes(protocol, OUTPUT, metadata={"finite": .25, "brackets": "[[[{}]]]"})
    # Split a multibyte code point at the transport boundary. UTF-8 is decoded
    # only after bounded accumulation, rather than separately per raw chunk.
    split = body.index("\u00e9".encode("utf-8")) + 1
    stream = TrackedStream([body[:split], body[split:split + 1], body[split + 1:]])
    response, seen = _serve(bound_runtime, monkeypatch, stream, headers={
        "content-type": mime, "content-length": str(len(body)),
    })

    result = _invoke(bound_runtime)

    assert result["output"] == OUTPUT
    assert result["protocol"] == protocol
    assert result["provider_verification"]["state"] == "NOT_VERIFIED"
    assert len(seen) == 1 and stream.exhausted
    assert stream.bytes_read == len(body)
    assert response.is_closed and stream.close_calls == 1


@pytest.mark.parametrize("protocol", ["hf-text-generation", "openai-chat"])
@pytest.mark.parametrize("extra_char", [0, 1], ids=["exact-text-limit", "oversized-text"])
def test_generated_text_limit_withholds_whole_oversized_output(
    bound_runtime, monkeypatch, protocol, extra_char,
):
    monkeypatch.setenv("SZL_MODEL_PROTOCOL_RECEIPT_AGENT", protocol)
    text = PRIVATE_BODY + "x" * (bound_runtime.MAX_GENERATED_CHARS + extra_char - len(PRIVATE_BODY))
    body = _reply_bytes(protocol, text)
    stream = TrackedStream([body[:37], body[37:]])
    response, seen = _serve(bound_runtime, monkeypatch, stream)

    if extra_char:
        assert _rejected(bound_runtime).detail == "model provider generated text exceeded the bounded size"
    else:
        assert _invoke(bound_runtime)["output"] == text

    assert len(seen) == 1 and stream.exhausted
    assert response.is_closed and stream.close_calls == 1


@pytest.mark.parametrize("mime", [
    None, "", "text/json", "text/plain", "text/vnd.szl.model+json",
    "application/jsonish", "application/json-seq", "application/jsonp",
    'text/plain; note="application/json"', 'application/octet-stream; profile="application/json"',
], ids=[
    "absent", "empty", "text-json", "text-plain", "text-vendor-json",
    "jsonish", "json-seq", "jsonp", "misleading-text-parameter", "misleading-application-parameter",
])
def test_misleading_mime_is_rejected_before_reading(bound_runtime, monkeypatch, mime):
    stream = TrackedStream([_reply_bytes(), b"unread-tail"])
    headers = {} if mime is None else {"content-type": mime}
    response, seen = _serve(bound_runtime, monkeypatch, stream, headers=headers)

    assert "JSON" in _rejected(bound_runtime).detail
    assert len(seen) == 1 and stream.chunks_read == 0
    assert response.is_closed and stream.close_calls == 1


@pytest.mark.parametrize("protocol, body", [
    pytest.param("openai-chat", (
        '{"choices":[{"message":{"content":"' + PRIVATE_BODY + '","content":"accepted"}}]}'
    ).encode(), id="duplicate-nested-key"),
    pytest.param("openai-chat", (
        '{"choices":[{"message":{"content":"' + PRIVATE_BODY + '","\\u0063ontent":"accepted"}}]}'
    ).encode(), id="escaped-equivalent-nested-key"),
    pytest.param("openai-chat", (
        '{"choices":[{"message":{"content":"' + PRIVATE_BODY + '"}}],"metadata":{"x":1,"x":2}}'
    ).encode(), id="duplicate-ignored-metadata-key"),
    pytest.param("hf-text-generation", (
        '[{"generated_text":"' + PRIVATE_BODY + '","\\u0067enerated_text":"accepted"}]'
    ).encode(), id="escaped-equivalent-hf-key"),
])
def test_duplicate_keys_cannot_choose_which_provider_value_is_admitted(
    bound_runtime, monkeypatch, protocol, body,
):
    monkeypatch.setenv("SZL_MODEL_PROTOCOL_RECEIPT_AGENT", protocol)
    stream = TrackedStream([body[:13], body[13:]])
    response, _ = _serve(bound_runtime, monkeypatch, stream)

    assert "invalid bounded JSON" in _rejected(bound_runtime).detail
    assert response.is_closed and stream.close_calls == 1


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e400", "-1e400"])
def test_nonfinite_numbers_in_otherwise_valid_reply_are_rejected(bound_runtime, monkeypatch, number):
    # This field is ignored by generated-text extraction. A permissive decoder
    # would therefore return the valid text while silently admitting infinity.
    body = _reply_bytes()[:-1] + b',"provider_score":' + number.encode() + b"}"
    stream = TrackedStream([body])
    response, _ = _serve(bound_runtime, monkeypatch, stream)

    assert "invalid bounded JSON" in _rejected(bound_runtime).detail
    assert response.is_closed and stream.close_calls == 1


@pytest.mark.parametrize("depth_delta", [0, 1], ids=["maximum-depth", "too-deep"])
def test_depth_limit_applies_even_to_ignored_metadata(bound_runtime, monkeypatch, depth_delta):
    depth = MAX_PROVIDER_JSON_DEPTH + depth_delta - 1  # The outer object adds one.
    body = _reply_bytes()[:-1] + b',"metadata":' + b"[" * depth + b"0" + b"]" * depth + b"}"
    stream = TrackedStream([body])
    response, _ = _serve(bound_runtime, monkeypatch, stream)

    if depth_delta:
        assert "invalid bounded JSON" in _rejected(bound_runtime).detail
    else:
        assert _invoke(bound_runtime)["output"] == PRIVATE_BODY
    assert response.is_closed and stream.close_calls == 1


@pytest.mark.parametrize("body", [
    pytest.param(_reply_bytes().replace(PRIVATE_BODY.encode(), PRIVATE_BODY.encode() + b"\xff"),
                 id="invalid-utf8"),
    pytest.param(_reply_bytes()[:-1], id="truncated-json"),
    pytest.param(json.dumps(PRIVATE_BODY).encode(), id="string"),
    pytest.param(b"null", id="null"),
    pytest.param(b"true", id="boolean"),
    pytest.param(b"42", id="integer"),
    pytest.param(b"0.5", id="float"),
])
def test_invalid_utf8_malformed_or_primitive_json_is_withheld(bound_runtime, monkeypatch, body):
    stream = TrackedStream([body])
    response, _ = _serve(bound_runtime, monkeypatch, stream)

    # Distinguish reader rejection from later "unsupported generated text"
    # extraction, which used to let primitive JSON through the admission gate.
    assert "invalid bounded JSON" in _rejected(bound_runtime).detail
    assert response.is_closed and stream.close_calls == 1


@pytest.mark.parametrize("status", [302, 400, 503])
def test_unsuccessful_status_never_reads_or_reflects_provider_body(bound_runtime, monkeypatch, status):
    stream = TrackedStream([_reply_bytes(), b"unread-tail"])
    response, seen = _serve(bound_runtime, monkeypatch, stream, status=status)

    _rejected(bound_runtime)

    assert len(seen) == 1 and stream.chunks_read == 0
    assert response.is_closed and stream.close_calls == 1


@pytest.mark.parametrize("encoding", ["gzip", "deflate", "br"])
def test_encoded_response_is_refused_before_a_decoder_can_expand_it(bound_runtime, monkeypatch, encoding):
    stream = TrackedStream([_reply_bytes(), b"unread-tail"])
    response, _ = _serve(bound_runtime, monkeypatch, stream, headers={
        "content-type": "application/json", "content-encoding": encoding,
    })

    assert "encoding" in _rejected(bound_runtime).detail
    assert stream.chunks_read == 0
    assert response.is_closed and stream.close_calls == 1


def test_streamed_public_reply_still_passes_request_and_provenance_checks(public_runtime, monkeypatch):
    stream = TrackedStream([])

    def make_reply(req):
        assert "authorization" not in req.headers
        body = json.dumps(public_reply(public_runtime.public_khipu, json.loads(req.content))).encode()
        stream.chunks = [body[:31], body[31:]]

    response, seen = _serve(public_runtime, monkeypatch, stream, on_request=make_reply)

    result = _invoke(public_runtime, public_request(public_runtime))

    assert result["output"] == json.loads(seen[0].content)["messages"][1]["content"]
    assert result["output_sha256"] == result["inference_input_sha256"]
    assert result["provider_verification"]["request_hash_verified"] is True
    assert result["provider_verification"]["authenticity_established"] is False
    assert len(seen) == 1 and stream.exhausted
    assert response.is_closed and stream.close_calls == 1


@pytest.mark.parametrize("public_demo", [False, True], ids=["private-provider", "public-demo"])
def test_total_deadline_cancels_a_stalled_stream_and_closes_response(request, monkeypatch, public_demo):
    runtime = request.getfixturevalue("public_runtime" if public_demo else "bound_runtime")
    payload = public_request(runtime) if public_demo else intelligence_request(runtime)
    real_timeout = asyncio.timeout
    deadlines, durations = [], []

    def controlled_timeout(delay):
        durations.append(delay)
        deadline = real_timeout(None)
        deadlines.append(deadline)
        return deadline

    class StalledStream(TrackedStream):
        cancelled = False

        async def __aiter__(self):
            self.chunks_read += 1
            first = b'{"private":"' + PRIVATE_BODY.encode() + b'","choices":['
            self.bytes_read += len(first)
            yield first
            # Advance the real timeout's deadline when a read stalls. No wall
            # clock sleeps or HTTP read-timeout mock is needed: cancellation
            # goes through asyncio.timeout and httpx's response manager.
            assert len(deadlines) == 1, "provider read must have a total deadline"
            deadlines[0].reschedule(asyncio.get_running_loop().time() - 1)
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise
            raise AssertionError("stalled read must not resume or drain a tail")

    monkeypatch.setattr(runtime.asyncio, "timeout", controlled_timeout)
    stream = StalledStream([])
    response, seen = _serve(runtime, monkeypatch, stream)

    error = _rejected(runtime, payload)

    assert "deadline" in error.detail
    assert durations == [60.0 if public_demo else 30.0]
    assert deadlines[0].expired() and stream.cancelled
    assert len(seen) == 1 and stream.chunks_read == 1
    assert not stream.exhausted
    assert response.is_closed and stream.close_calls == 1
