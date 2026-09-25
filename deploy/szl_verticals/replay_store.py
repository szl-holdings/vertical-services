"""Direct evidence dependencies in the existing observation database."""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from contextlib import closing
from typing import Any

REPLAY_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_withdrawals (
    vertical TEXT NOT NULL, session_scope TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL, withdrawn_at REAL NOT NULL,
    PRIMARY KEY (vertical, session_scope, payload_sha256)
);
CREATE TABLE IF NOT EXISTS evidence_assessments (
    vertical TEXT NOT NULL, session_scope TEXT NOT NULL,
    assessment_id TEXT NOT NULL, kind TEXT NOT NULL,
    snapshot_sha256 TEXT NOT NULL, dependencies_json TEXT NOT NULL,
    assessed_at REAL NOT NULL, last_checked_at REAL NOT NULL,
    invalidated INTEGER NOT NULL DEFAULT 0, reasons_json TEXT NOT NULL,
    PRIMARY KEY (vertical, session_scope, assessment_id)
);
"""
MAX_ASSESSMENTS_PER_SCOPE = 10_000
