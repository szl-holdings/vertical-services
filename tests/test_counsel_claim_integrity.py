"""Network-free regressions against the actual mounted Counsel router."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = str(ROOT / "deploy")
if DEPLOY not in sys.path:
    sys.path.insert(0, DEPLOY)

from szl_verticals.claim_integrity import ClaimReviewRequest, canonical_json, digest, review_claims
from szl_verticals.counsel import counsel
from szl_verticals.counsel_review_ui import REVIEW_CSP, REVIEW_HTML

SOURCE = "1" * 40
SESSION = "test-session-claim-integrity-0123456789"


def request_payload():
    text = "SYNTHETIC. Notice must be written. Exceptions may apply."
    quote = "Notice must be written."
    start = text.index(quote)
    return {
        "documents": [{"document_id": "doc-1", "text": text, "expected_sha256": digest(text)}],
        "claims": [{"claim_id": "claim-1", "statement": "The example contains written notice.",
                    "anchors": [{"document_id": "doc-1", "start": start, "end": start + len(quote),
                                 "quote": quote, "relationship": "SUPPORT"}]}],
    }


def evaluate(payload=None, source=SOURCE):
    return review_claims(ClaimReviewRequest.model_validate(payload or request_payload()), source_revision=source)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SZL_SOURCE_REVISION", SOURCE)
    app = FastAPI()
    app.include_router(counsel)
    with TestClient(app) as value:
        value.headers.update({"X-SZL-Session": SESSION})
        yield value


def test_exact_match_and_honest_bounds():
    result = evaluate()
    assert result["decision"] == "READY_FOR_TEXT_REVIEW"
    assert result["claims"][0]["textual_support_state"] == "ANCHORED"
    assert result["metrics"]["textual_anchor_coverage"] == 1
    assert result["bounds"]["semantic_entailment"] == "NOT_EVALUATED"
    assert result["bounds"]["citation_treatment"] == "NOT_VERIFIED"
    assert result["bounds"]["source_authentication"] == "NOT_PERFORMED"
    assert result["bounds"]["human_approval_required"] is True
    for key in ["good_law_claimed", "effectors_enabled", "model_invoked", "legal_advice"]:
        assert result["bounds"][key] is False


def test_receipt_recomputes_and_input_is_bound():
    payload = request_payload()
    result = evaluate(payload)
    receipt = result.pop("receipt")
    assert receipt["basis_sha256"] == digest(canonical_json(result))
    assert result["input_sha256"] == digest(canonical_json(payload))
    assert receipt["signature_claimed"] is False
    assert receipt["durable_storage_claimed"] is False


def test_deterministic_and_no_input_mutation():
    payload = request_payload()
    before = copy.deepcopy(payload)
    assert evaluate(payload) == evaluate(payload)
    assert payload == before


@pytest.mark.parametrize("source", ["", "UNAVAILABLE", "main", "1" * 39, "G" * 40])
def test_source_unbound_never_ready(source):
    result = evaluate(source=source)
    assert result["source_revision"] == "UNAVAILABLE"
    assert "SOURCE_UNBOUND" in result["blockers"]
    assert result["decision"] != "READY_FOR_TEXT_REVIEW"


@pytest.mark.parametrize("mutation,status", [
    ("digest", "DOCUMENT_DIGEST_MISMATCH"),
    ("missing", "DOCUMENT_UNAVAILABLE"),
    ("span", "SPAN_OUT_OF_RANGE"),
    ("quote", "QUOTE_MISMATCH"),
])
def test_integrity_failures(mutation, status):
    payload = request_payload()
    anchor = payload["claims"][0]["anchors"][0]
    if mutation == "digest": payload["documents"][0]["expected_sha256"] = "0" * 64
    if mutation == "missing": anchor["document_id"] = "missing"
    if mutation == "span": anchor["end"] = 900
    if mutation == "quote": anchor["quote"] = "Notice need not be written."
    result = evaluate(payload)
    assert result["claims"][0]["anchors"][0]["integrity"] == status
    assert result["decision"] == "REVIEW_INTEGRITY_FAILURES"
    assert result["metrics"]["claims_with_matching_support_text"] == 0


def test_unanchored_claim_is_not_hidden():
    payload = request_payload()
    payload["claims"].append({"claim_id": "unanchored", "statement": "Unknown proposition.", "anchors": []})
    result = evaluate(payload)
    assert result["metrics"]["textual_anchor_coverage"] == .5
    assert "UNANCHORED_CLAIMS" in result["blockers"]


def test_adverse_and_support_preserved_without_deciding_truth():
    payload = request_payload()
    anchor = copy.deepcopy(payload["claims"][0]["anchors"][0])
    anchor["relationship"] = "ADVERSE"
    payload["claims"][0]["anchors"].append(anchor)
    result = evaluate(payload)
    claim = result["claims"][0]
    assert claim["reported_support_and_adverse_present"] is True
    assert claim["supporting_text_anchors"] == claim["adverse_text_anchors"] == 1
    assert claim["legal_validity"] == "NOT_EVALUATED"


@pytest.mark.parametrize("relationship", ["ADVERSE", "CONTEXT"])
def test_non_support_does_not_inflate_support(relationship):
    payload = request_payload()
    payload["claims"][0]["anchors"][0]["relationship"] = relationship
    assert evaluate(payload)["metrics"]["textual_anchor_coverage"] == 0


def test_document_alias_cannot_inflate_evidence():
    payload = request_payload()
    alias = copy.deepcopy(payload["documents"][0]); alias["document_id"] = "alias"
    payload["documents"].append(alias)
    anchor = copy.deepcopy(payload["claims"][0]["anchors"][0]); anchor["document_id"] = "alias"
    payload["claims"][0]["anchors"].append(anchor)
    result = evaluate(payload)
    assert result["metrics"]["unique_document_contents"] == 1
    assert result["claims"][0]["supporting_text_anchors"] == 1
    assert sum(a["duplicate_content_anchor"] for a in result["claims"][0]["anchors"]) == 1
    assert result["metrics"]["independent_authorities"] == "NOT_ESTABLISHED"


def test_unicode_offsets_are_code_points_and_no_normalization():
    payload = request_payload()
    text = "⚖️ 🧭 Notice café."
    quote = "Notice café."
    payload["documents"][0].update(text=text, expected_sha256=digest(text))
    payload["claims"][0]["anchors"][0].update(start=text.index(quote), end=len(text), quote=quote)
    assert evaluate(payload)["decision"] == "READY_FOR_TEXT_REVIEW"
    payload["claims"][0]["anchors"][0]["quote"] = "Notice cafe\u0301."
    assert evaluate(payload)["claims"][0]["anchors"][0]["integrity"] == "QUOTE_MISMATCH"


def test_receipt_changes_with_source_statement_and_relationship():
    first = evaluate()["receipt"]["basis_sha256"]
    assert evaluate(source="2" * 40)["receipt"]["basis_sha256"] != first
    for key, value in [("statement", "A different statement."), ("relationship", "CONTEXT")]:
        payload = request_payload()
        if key == "statement": payload["claims"][0][key] = value
        else: payload["claims"][0]["anchors"][0][key] = value
        assert evaluate(payload)["receipt"]["basis_sha256"] != first


@pytest.mark.parametrize("case", ["document_id", "claim_id", "anchor", "float_offset", "bool_offset", "extra", "empty", "blank", "surrogate", "corpus_budget", "document_budget"])
def test_invalid_requests_fail_closed(case):
    payload = request_payload()
    if case == "document_id": payload["documents"].append(copy.deepcopy(payload["documents"][0]))
    if case == "claim_id": payload["claims"].append(copy.deepcopy(payload["claims"][0]))
    if case == "anchor": payload["claims"][0]["anchors"] *= 2
    if case == "float_offset": payload["claims"][0]["anchors"][0]["start"] = 1.0
    if case == "bool_offset": payload["claims"][0]["anchors"][0]["start"] = True
    if case == "extra": payload["verified"] = True
    if case == "empty": payload["claims"] = []
    if case == "blank": payload["claims"][0]["statement"] = " "
    if case == "surrogate": payload["documents"][0]["text"] = "\ud800"
    if case == "document_budget": payload["documents"][0]["text"] = "é" * 32_001
    if case == "corpus_budget": payload["documents"] = [{"document_id": f"d-{i}", "text": "x" * 64_000, "expected_sha256": "0" * 64} for i in range(5)]
    with pytest.raises(ValidationError): ClaimReviewRequest.model_validate(payload)


def test_http_route_is_mounted_on_existing_counsel_router(client):
    response = client.post("/counsel/v1/claim-integrity", json=request_payload())
    assert response.status_code == 200
    assert response.json()["source_revision"] == SOURCE
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/counsel/healthz").status_code == 200


def test_session_boundary_preserved(client):
    del client.headers["X-SZL-Session"]
    assert client.post("/counsel/v1/claim-integrity", json=request_payload()).status_code == 422
    client.headers["X-SZL-Session"] = "short"
    assert client.post("/counsel/v1/claim-integrity", json=request_payload()).status_code == 400


@pytest.mark.parametrize("body", [b'{"documents":[],"documents":[]}', b'{"value":NaN}', b'\xff', b'{}'])
def test_bad_json_is_redacted(client, body):
    response = client.post("/counsel/v1/claim-integrity", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json() == {"detail": "INVALID_REVIEW_REQUEST"}


def test_private_invalid_input_not_echoed(client):
    payload = request_payload(); payload["secret"] = "PRIVATE-CONTENT-SENTINEL"
    response = client.post("/counsel/v1/claim-integrity", json=payload)
    assert response.status_code == 422
    assert "PRIVATE-CONTENT-SENTINEL" not in response.text


def test_body_budget_and_content_type(client):
    assert client.post("/counsel/v1/claim-integrity", content=b"x" * 512_001,
                       headers={"Content-Type": "application/json"}).status_code == 413
    assert client.post("/counsel/v1/claim-integrity", content=b"{}").status_code == 415


def test_output_omits_raw_text_and_session(client):
    payload = request_payload()
    response = client.post("/counsel/v1/claim-integrity", json=payload)
    assert response.status_code == 200
    for value in [payload["documents"][0]["text"], payload["claims"][0]["statement"], SESSION]:
        assert value not in response.text


def test_ui_is_static_no_external_scripts_and_hashed_csp(client):
    response = client.get("/counsel/review")
    assert response.status_code == 200
    assert "PRISM COUNSEL" in response.text
    assert response.headers["content-security-policy"] == REVIEW_CSP
    assert "unsafe-inline" not in REVIEW_CSP
    for forbidden in ["innerHTML", "localStorage", "sessionStorage", "<script src", "eval("]:
        assert forbidden not in REVIEW_HTML
    assert "textContent" in REVIEW_HTML
    assert "UNICODE_CODE_POINT" == evaluate()["bounds"]["offset_unit"]
    assert "Array.from(text.slice(0,position)).length" in REVIEW_HTML
