"""Contract tests for the source-bound vertical intelligence fabric."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))

_STATE = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "intelligence-test-key")
os.environ.setdefault("SZL_SOURCE_REVISION", "6" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_STATE.name) / "intelligence.sqlite3"))

from app import app  # noqa: E402
from szl_verticals.intelligence import (  # noqa: E402
    KERNEL_ASSETS,
    MODEL_ASSETS,
    VERTICAL_INTELLIGENCE,
)
from szl_verticals.profiles import CANONICAL_VERTICALS, VERTICALS  # noqa: E402

SESSION_TOKEN = "intelligence-session-token-01234567890123456789"
HEADERS = {"X-SZL-Session": SESSION_TOKEN}
CLIENT = TestClient(app, headers=HEADERS)
MODEL_ENV = {
    key
    for asset in MODEL_ASSETS.values()
    for key in (
        asset.get("endpoint_env"),
        asset.get("revision_env"),
        asset.get("protocol_env"),
        asset.get("token_env"),
    )
    if key
}


def clear_model_env(monkeypatch) -> None:
    for key in MODEL_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("SZL_INFERENCE_ALLOWED_HOSTS", raising=False)


def plan_payload(*, task: str, axes: dict[str, float] | None = None) -> dict:
    return {
        "task": task,
        "objective": "Produce a bounded source-linked review brief.",
        "context": "Public, licensed, or operator-authorized context only.",
        "axes": axes or {"evidence": 0.95, "freshness": 0.92, "reversibility": 0.96},
        "evidence_sha256": ["a" * 64, "b" * 64],
    }


def test_catalog_exposes_six_verticals_three_models_and_kernel_fabric():
    response = CLIENT.get("/api/intelligence")
    assert response.status_code == 200
    body = response.json()
    assert set(body["verticals"]) == set(CANONICAL_VERTICALS)
    assert {"khipu-1.5b", "receipt-agent", "a11oy-mini", "nemo-recipe"} <= set(
        body["model_assets"]
    )
    assert set(KERNEL_ASSETS) == set(body["kernel_assets"])
    assert body["caller_supplied_endpoints_allowed"] is False
    assert body["effectors_enabled"] is False


def test_each_vertical_has_distinct_jobs_tasks_and_frontend(monkeypatch):
    clear_model_env(monkeypatch)
    page_hashes = set()
    motifs = set()
    for vertical in CANONICAL_VERTICALS:
        profile = CLIENT.get(f"/api/verticals/{vertical}/intelligence")
        assert profile.status_code == 200
        data = profile.json()
        assert data["vertical"] == vertical
        assert data["primary_job"]
        assert data["unserved_job"]
        assert len(data["tasks"]) == 4
        assert len(data["novel_capabilities"]) == 3
        assert data["policy"]["effectors_enabled"] is False
        assert all(
            row["proprietary_code_copied"] is False
            for row in data["reference_patterns"]
        )
        assert all(
            row["proprietary_data_copied"] is False
            for row in data["reference_patterns"]
        )

        page = CLIENT.get(f"/intelligence/{vertical}")
        assert page.status_code == 200
        assert "viewport-fit=cover" in page.text
        assert "@media(prefers-reduced-motion:reduce)" in page.text
        assert "Skip to intelligence room" in page.text
        assert "Learn broadly. Copy nothing proprietary." in page.text
        assert VERTICALS[vertical]["product"] in page.text
        motif = VERTICALS[vertical]["experience"]["motif"]
        assert f'data-motif="{motif}"' in page.text
        motifs.add(motif)
        page_hashes.add(hashlib.sha256(page.content).hexdigest())

    assert len(motifs) == 6
    assert len(page_hashes) == 6
    assert len({row["primary_job"] for row in VERTICAL_INTELLIGENCE.values()}) == 6


def test_aliases_resolve_to_one_runtime_and_one_intelligence_room(monkeypatch):
    clear_model_env(monkeypatch)
    expected = {
        "aegis": "sentra",
        "immune": "sentra",
        "business-observability": "lyte",
        "vessels": "killinchu",
        "puriq": "finance",
        "markets": "finance",
        "real-estate": "terra",
        "prism": "counsel",
    }
    for alias, canonical in expected.items():
        profile = CLIENT.get(f"/api/verticals/{alias}/intelligence")
        assert profile.status_code == 200
        assert profile.json()["vertical"] == canonical
        page = CLIENT.get(f"/intelligence/{alias}")
        assert page.status_code == 200
        assert f'data-vertical="{canonical}"' in page.text


def test_model_routes_fail_closed_when_operator_binding_is_missing(monkeypatch):
    clear_model_env(monkeypatch)
    profile = CLIENT.get("/api/verticals/finance/intelligence").json()
    assert all(item["state"] == "UNAVAILABLE" for item in profile["models"])
    assert all(
        item["credential_value_exposed"] is False for item in profile["models"]
    )

    request = plan_payload(task="scenario-analysis")
    response = CLIENT.post(
        "/api/verticals/finance/intelligence/plan",
        json=request,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "ABSTAIN"
    assert "MODEL_ENDPOINT_NOT_BOUND" in body["blockers"]
    assert "ENDPOINT_UNAVAILABLE" in body["blockers"]
    assert body["can_execute"] is False
    assert body["effectors_enabled"] is False
    assert request["context"] not in json.dumps(body)

    invoked = CLIENT.post(
        "/api/verticals/finance/intelligence/invoke",
        json=request,
    )
    assert invoked.status_code == 503
    assert invoked.json()["detail"]["error"] == "INFERENCE_NOT_READY"


def test_non_allowlisted_endpoint_is_blocked_without_leaking_token(monkeypatch):
    clear_model_env(monkeypatch)
    monkeypatch.setenv("SZL_MODEL_ENDPOINT_KHIPU_1_5B", "https://example.com/infer")
    monkeypatch.setenv("SZL_MODEL_REVISION_KHIPU_1_5B", "c" * 40)
    monkeypatch.setenv("SZL_MODEL_PROTOCOL_KHIPU_1_5B", "hf-text-generation")
    monkeypatch.setenv("HF_TOKEN", "never-return-this-test-token")

    profile = CLIENT.get("/api/verticals/lyte/intelligence").json()
    khipu = next(
        item for item in profile["models"] if item["alias"] == "khipu-1.5b"
    )
    assert khipu["state"] == "BLOCKED"
    assert "ENDPOINT_HOST_NOT_ALLOWLISTED" in khipu["blockers"]
    assert khipu["credential_present"] is True
    assert khipu["credential_value_exposed"] is False
    assert "never-return-this-test-token" not in json.dumps(profile)


def test_exact_operator_binding_can_make_a_plan_ready_without_invoking_network(
    monkeypatch,
):
    clear_model_env(monkeypatch)
    monkeypatch.setenv(
        "SZL_MODEL_ENDPOINT_KHIPU_1_5B",
        "https://router.huggingface.co/models/SZLHOLDINGS/SZL-Khipu-1.5B",
    )
    monkeypatch.setenv("SZL_MODEL_REVISION_KHIPU_1_5B", "d" * 40)
    monkeypatch.setenv("SZL_MODEL_PROTOCOL_KHIPU_1_5B", "hf-text-generation")
    monkeypatch.setenv("HF_TOKEN", "test-token-not-returned")

    payload = plan_payload(task="scenario-analysis")
    first = CLIENT.post("/api/verticals/finance/intelligence/plan", json=payload)
    second = CLIENT.post("/api/verticals/finance/intelligence/plan", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    body = first.json()
    assert body["decision"] == "READY_FOR_INFERENCE"
    assert body["selected_model"]["alias"] == "khipu-1.5b"
    assert body["selected_model"]["revision"] == "d" * 40
    assert body["selected_model"]["revision_evidence"] == "OPERATOR_DECLARED"
    assert (
        body["receipt"]["basis_sha256"]
        == second.json()["receipt"]["basis_sha256"]
    )
    assert body["raw_context_returned"] is False
    assert body["raw_context_stored"] is False
    assert "test-token-not-returned" not in json.dumps(body)


def test_low_advisory_score_and_unapproved_preference_abstain(monkeypatch):
    clear_model_env(monkeypatch)
    low = CLIENT.post(
        "/api/verticals/counsel/intelligence/plan",
        json=plan_payload(
            task="argument-map",
            axes={"evidence": 0.4, "freshness": 0.95, "reversibility": 0.95},
        ),
    )
    assert low.status_code == 200
    assert "LAMBDA_BELOW_INFERENCE_FLOOR" in low.json()["blockers"]

    invalid = plan_payload(task="argument-map")
    invalid["preferred_model"] = "nemo-recipe"
    rejected = CLIENT.post(
        "/api/verticals/counsel/intelligence/plan",
        json=invalid,
    )
    assert rejected.status_code == 422
    assert "not approved for this vertical" in rejected.json()["detail"]


def test_invalid_evidence_digest_is_rejected_before_planning():
    payload = plan_payload(task="attack-path-review")
    payload["evidence_sha256"] = ["not-a-digest"]
    response = CLIENT.post(
        "/api/verticals/sentra/intelligence/plan",
        json=payload,
    )
    assert response.status_code == 422
