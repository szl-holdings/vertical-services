"""A corrupt stored assessment row is a store fault on every entry point.

JSON columns were already classified as StoredAssessmentInvalid (503). These
tests corrupt each scalar column and require registration and status to agree
on 503, never a 500 on one path and a 503 or a CURRENT answer on the other.
Real SQLite ledger and mounted Hatun routes; no live feeds.
"""
from __future__ import annotations

import sqlite3

import pytest

from test_hatun_evidence_admission import URL, context, post, request_body, seed  # noqa: F401

UNAVAILABLE = {"detail": "evidence replay unavailable"}
LATCH = '[{"payload_sha256":null,"reason":"EVIDENCE_WITHDRAWN"}]'


def status(client, assessment_id):
    return client.get(f"/api/verticals/puriq/evidence/assessments/{assessment_id}")


@pytest.mark.parametrize("assignments", [
    {"last_checked_at": "corrupt"},
    {"last_checked_at": -1.0},
    {"last_checked_at": float("inf")},
    {"assessed_at": "corrupt"},
    {"invalidated": "x"},
    {"invalidated": 2},
    {"kind": "bogus"},
    {"snapshot_sha256": "zz"},
    {"snapshot_sha256": "D" * 64},
    # Every write keeps invalidated == bool(reasons); a row that breaks it must
    # neither clear a latched invalidation nor hide recorded reasons.
    {"invalidated": 1, "reasons_json": "[]"},
    {"invalidated": 0, "reasons_json": LATCH},
], ids=lambda value: ",".join(f"{key}={value[key]!r}" for key in value))
def test_corrupt_scalar_column_is_unavailable_on_registration_and_status(context, assignments):
    db, client = context
    seed(db)
    first = post(context)
    assessment_id = first["receipt"]["basis_sha256"]
    assert first["receipt"]["evidence_replay"]["state"] == "CURRENT"
    columns = ", ".join(f"{key}=?" for key in assignments)
    with sqlite3.connect(db.path) as connection:
        changed = connection.execute(
            f"UPDATE evidence_assessments SET {columns} WHERE assessment_id=?",
            (*assignments.values(), assessment_id),
        ).rowcount
    assert changed == 1
    # The fixture pins the clock, so the same request re-registers the same id.
    registered = client.post(URL, json=request_body())
    read = status(client, assessment_id)
    assert (registered.status_code, registered.json()) == (503, UNAVAILABLE)
    assert (read.status_code, read.json()) == (503, UNAVAILABLE)


def test_well_formed_rows_still_register_and_read_current(context):
    db, client = context
    seed(db)
    first = post(context)
    again = post(context)
    assert again["receipt"]["basis_sha256"] == first["receipt"]["basis_sha256"]
    assert again["receipt"]["evidence_replay"]["state"] == "CURRENT"
    body = status(client, first["receipt"]["basis_sha256"]).json()
    assert body["state"] == "CURRENT" and body["original_decision"] == "REVIEW"


def test_latched_row_keeps_reading_as_revalidation_required(context):
    # A legitimately invalidated row (invalidated=1 with its reasons) is valid.
    db, client = context
    seed(db)
    assessment_id = post(context)["receipt"]["basis_sha256"]
    assert client.post("/api/verticals/puriq/evidence/withdraw",
                       json={"evidence_sha256": ["d" * 64]}).status_code == 200
    with sqlite3.connect(db.path) as connection:
        row = connection.execute("SELECT invalidated, reasons_json FROM evidence_assessments").fetchone()
    assert row[0] == 1 and "EVIDENCE_WITHDRAWN" in row[1]
    body = status(client, assessment_id).json()
    assert body["state"] == "REVALIDATION_REQUIRED"
    assert body["changed_dependencies"][0]["reason"] == "EVIDENCE_WITHDRAWN"
