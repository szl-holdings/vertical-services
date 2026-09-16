"""Deterministic claim-to-passage integrity, not legal or semantic validation.

Documents and relationship labels are caller reports. Matching their bytes proves
only internal textual consistency. This module performs no I/O, inference,
signature generation, source authentication, or consequential action.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_DOCUMENT_BYTES = 64_000
MAX_CORPUS_BYTES = 256_000
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def canonical_json(value: Any) -> str:
    """Stable UTF-8 JSON; non-finite numbers cannot enter a receipt."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Document(ReviewModel):
    document_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=MAX_DOCUMENT_BYTES)
    expected_sha256: str = Field(min_length=64, max_length=64)

    @field_validator("document_id")
    @classmethod
    def identifier(cls, value: str) -> str:
        if ID.fullmatch(value) is None:
            raise ValueError("document_id must be a bounded identifier")
        return value

    @field_validator("text")
    @classmethod
    def bounded_utf8(cls, value: str) -> str:
        try:
            size = len(value.encode("utf-8"))
        except UnicodeError as exc:
            raise ValueError("document must be valid UTF-8") from exc
        if not value.strip() or size > MAX_DOCUMENT_BYTES:
            raise ValueError("document must be nonblank and at most 64000 UTF-8 bytes")
        return value

    @field_validator("expected_sha256")
    @classmethod
    def exact_digest(cls, value: str) -> str:
        if SHA256.fullmatch(value) is None:
            raise ValueError("expected_sha256 must be lowercase SHA-256")
        return value


class Anchor(ReviewModel):
    document_id: str = Field(min_length=1, max_length=64)
    start: int = Field(ge=0, le=MAX_DOCUMENT_BYTES)
    end: int = Field(gt=0, le=MAX_DOCUMENT_BYTES)
    quote: str = Field(min_length=1, max_length=4000)
    relationship: Literal["SUPPORT", "ADVERSE", "CONTEXT"]

    @field_validator("document_id")
    @classmethod
    def identifier(cls, value: str) -> str:
        if ID.fullmatch(value) is None:
            raise ValueError("document_id must be a bounded identifier")
        return value

    @model_validator(mode="after")
    def ordered_span(self) -> Anchor:
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        try:
            self.quote.encode("utf-8")
        except UnicodeError as exc:
            raise ValueError("quote must be valid UTF-8") from exc
        return self


class Claim(ReviewModel):
    claim_id: str = Field(min_length=1, max_length=64)
    statement: str = Field(min_length=1, max_length=2000)
    anchors: list[Anchor] = Field(default_factory=list, max_length=16)

    @field_validator("claim_id")
    @classmethod
    def identifier(cls, value: str) -> str:
        if ID.fullmatch(value) is None:
            raise ValueError("claim_id must be a bounded identifier")
        return value

    @field_validator("statement")
    @classmethod
    def nonblank_utf8(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("statement must not be blank")
        try:
            value.encode("utf-8")
        except UnicodeError as exc:
            raise ValueError("statement must be valid UTF-8") from exc
        return value

    @model_validator(mode="after")
    def unique_anchors(self) -> Claim:
        keys = [(a.document_id, a.start, a.end, a.relationship) for a in self.anchors]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate anchor in claim")
        return self


class ClaimReviewRequest(ReviewModel):
    documents: list[Document] = Field(min_length=1, max_length=16)
    claims: list[Claim] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def bounded_unique_corpus(self) -> ClaimReviewRequest:
        for values in (
            [d.document_id for d in self.documents],
            [c.claim_id for c in self.claims],
        ):
            if len(values) != len(set(values)):
                raise ValueError("document and claim identifiers must be unique")
        if sum(len(d.text.encode("utf-8")) for d in self.documents) > MAX_CORPUS_BYTES:
            raise ValueError("corpus exceeds 256000 UTF-8 bytes")
        return self


def review_claims(request: ClaimReviewRequest, *, source_revision: str) -> dict[str, Any]:
    """Audit exact code-point spans with source-digest binding and honest bounds.

    Hash-identical document aliases do not become independent evidence. Relative
    anchor offsets refer to Python/Unicode code points, not UTF-16 or UTF-8 bytes.
    No normalization silently changes the text or claimed quotation.
    """
    documents = {d.document_id: d for d in request.documents}
    actual = {key: digest(doc.text) for key, doc in documents.items()}
    document_results = [
        {
            "document_id": key,
            "actual_sha256": actual[key],
            "expected_sha256": documents[key].expected_sha256,
            "integrity": "MATCH" if actual[key] == documents[key].expected_sha256 else "MISMATCH",
            "provenance": "CALLER_SUPPLIED_NOT_AUTHENTICATED",
        }
        for key in sorted(documents)
    ]
    rows: list[dict[str, Any]] = []
    matched_claims = 0
    all_errors = 0
    for claim in sorted(request.claims, key=lambda item: item.claim_id):
        anchors: list[dict[str, Any]] = []
        supporting: set[tuple[str, int, int]] = set()
        adverse: set[tuple[str, int, int]] = set()
        seen: set[tuple[str, int, int, str]] = set()
        for anchor in sorted(claim.anchors, key=lambda a: (a.document_id, a.start, a.end, a.relationship)):
            doc = documents.get(anchor.document_id)
            status = "MATCHED"
            if doc is None:
                status = "DOCUMENT_UNAVAILABLE"
            elif actual[anchor.document_id] != doc.expected_sha256:
                status = "DOCUMENT_DIGEST_MISMATCH"
            elif anchor.end > len(doc.text):
                status = "SPAN_OUT_OF_RANGE"
            elif doc.text[anchor.start:anchor.end] != anchor.quote:
                status = "QUOTE_MISMATCH"
            content_key = (actual.get(anchor.document_id, "UNAVAILABLE"), anchor.start, anchor.end)
            relationship_key = (*content_key, anchor.relationship)
            duplicate_content = status == "MATCHED" and relationship_key in seen
            if status == "MATCHED":
                seen.add(relationship_key)
                if anchor.relationship == "SUPPORT":
                    supporting.add(content_key)
                elif anchor.relationship == "ADVERSE":
                    adverse.add(content_key)
            else:
                all_errors += 1
            anchors.append({
                "document_id": anchor.document_id,
                "document_sha256": content_key[0],
                "start": anchor.start,
                "end": anchor.end,
                "quote_sha256": digest(anchor.quote),
                "relationship_reported": anchor.relationship,
                "integrity": status,
                "duplicate_content_anchor": duplicate_content,
                "entailment": "NOT_EVALUATED",
            })
        if supporting:
            matched_claims += 1
        rows.append({
            "claim_id": claim.claim_id,
            "statement_sha256": digest(claim.statement),
            "supporting_text_anchors": len(supporting),
            "adverse_text_anchors": len(adverse),
            "reported_support_and_adverse_present": bool(supporting and adverse),
            "textual_support_state": "ANCHORED" if supporting else "UNANCHORED",
            "anchors": anchors,
            "legal_validity": "NOT_EVALUATED",
        })
    bound = SHA40.fullmatch(source_revision) is not None
    blockers = []
    if not bound:
        blockers.append("SOURCE_UNBOUND")
    if any(d["integrity"] != "MATCH" for d in document_results):
        blockers.append("DOCUMENT_INTEGRITY_FAILURE")
    if all_errors:
        blockers.append("ANCHOR_INTEGRITY_FAILURE")
    if matched_claims != len(rows):
        blockers.append("UNANCHORED_CLAIMS")
    basis = {
        "schema": "szl.claim-integrity-review/v1",
        "source_repository": "szl-holdings/vertical-services",
        "source_revision": source_revision if bound else "UNAVAILABLE",
        "input_sha256": digest(canonical_json(request.model_dump(mode="json"))),
        "documents": document_results,
        "claims": rows,
        "metrics": {
            "claims_total": len(rows),
            "claims_with_matching_support_text": matched_claims,
            "textual_anchor_coverage": matched_claims / len(rows),
            "unique_document_contents": len(set(actual.values())),
            "failed_anchors": all_errors,
            "independent_authorities": "NOT_ESTABLISHED",
            "metric_is_legal_accuracy": False,
        },
        "decision": "REVIEW_INTEGRITY_FAILURES" if blockers else "READY_FOR_TEXT_REVIEW",
        "blockers": blockers,
        "bounds": {
            "source_authentication": "NOT_PERFORMED",
            "relationship_classification": "CALLER_REPORTED",
            "citation_existence": "NOT_VERIFIED",
            "citation_treatment": "NOT_VERIFIED",
            "jurisdiction_applicability": "NOT_VERIFIED",
            "semantic_entailment": "NOT_EVALUATED",
            "deadlines": "NOT_COMPUTED",
            "retrieval_performed": False,
            "model_invoked": False,
            "good_law_claimed": False,
            "legal_advice": False,
            "raw_documents_stored": False,
            "raw_documents_returned": False,
            "session_token_recorded": False,
            "effectors_enabled": False,
            "human_approval_required": True,
            "offset_unit": "UNICODE_CODE_POINT",
        },
        "truth_label": "MEASURED_TEXT_INTEGRITY_ONLY",
    }
    return {
        **basis,
        "receipt": {
            "schema": "szl.claim-integrity-receipt/v1",
            "algorithm": "SHA-256",
            "basis_sha256": digest(canonical_json(basis)),
            "signature_claimed": False,
            "durable_storage_claimed": False,
        },
    }
