"""Exercise the public inference probe's capacity retry without network or sleep."""

import hashlib
import json
import sys

import httpx
import pytest

from tools import probe_public_khipu as probe


REVISION = "f" * 40
PRIMARY_SESSION = "private-session-fixture-one-123456"
OTHER_SESSION = "private-session-fixture-two-123456"
CAPACITY = {"detail": "model provider returned HTTP 429"}


def valid_invocation(plan_hash):
    output = "Public observations require human review."
    result = {
        "output": output,
        "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
        "plan_receipt_sha256": plan_hash,
        "provider_verification": {
            "model_identity_verified": True,
            "request_hash_verified": True,
            "output_hash_verified": True,
        },
        "effectors_enabled": False,
    }
    basis = {key: value for key, value in result.items() if key != "output"}
    result["receipt"] = {"basis_sha256": probe.sha(basis)}
    return result


def run_probe(monkeypatch, tmp_path, invoke_replies, *, failure_stage=None,
              second_plan_decision="READY_FOR_INFERENCE"):
    events = []
    requests = []
    plans = []
    invocations = []
    fetch_round = 0

    def handler(request):
        nonlocal fetch_round
        requests.append(request)
        path = request.url.path
        payload = json.loads(request.content) if request.content else None
        if path == "/api/build-info":
            return httpx.Response(200, json={"build": {"revision": REVISION}})
        if path.endswith("/fetch"):
            connector = path.split("/")[-2]
            if connector == "coinbase-spot":
                fetch_round += 1
            events.append(("fetch", connector, fetch_round))
            assert payload["force_refresh"] is True
            if failure_stage == "fetch" and fetch_round == 1:
                return httpx.Response(502, json=CAPACITY)
            digit = str(2 * fetch_round - (connector == "coinbase-spot"))
            return httpx.Response(200, json={"receipt": {
                "state": "OBSERVED", "payload_sha256": digit * 64,
            }})
        if path.endswith("/plan"):
            if request.headers["X-SZL-Session"] == OTHER_SESSION:
                events.append(("cross-session-plan",))
                return httpx.Response(200, json={"decision": "ABSTAIN"})
            if failure_stage == "plan" and not plans:
                events.append(("plan-failed",))
                return httpx.Response(502, json=CAPACITY)
            plans.append(payload)
            events.append(("plan", len(plans)))
            decision = second_plan_decision if len(plans) == 2 else "READY_FOR_INFERENCE"
            return httpx.Response(200, json={
                "decision": decision,
                "receipt": {"basis_sha256": ("a" if len(plans) == 1 else "b") * 64},
            })
        if path.endswith("/invoke"):
            invocations.append(payload)
            events.append(("invoke", len(invocations)))
            reply = invoke_replies[len(invocations) - 1]
            if reply is None:
                return httpx.Response(200, json=valid_invocation(
                    ("a" if len(invocations) == 1 else "b") * 64))
            status, body = reply
            if isinstance(body, str):
                return httpx.Response(status, text=body)
            return httpx.Response(status, json=body)
        raise AssertionError(f"unexpected path: {path}")

    real_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(probe.httpx, "Client", lambda **kw: real_client(transport=transport, **kw))
    tokens = iter((PRIMARY_SESSION, OTHER_SESSION))
    monkeypatch.setattr(probe.secrets, "token_urlsafe", lambda _: next(tokens))
    monkeypatch.setattr(probe.time, "sleep", lambda seconds: events.append(("sleep", seconds)))
    output = tmp_path / "public-khipu-report.json"
    monkeypatch.setattr(sys, "argv", ["probe_public_khipu", "--base-url", "https://local.test",
                                      "--expected-revision", REVISION, "--output", str(output)])
    exit_code = probe.main()
    report_text = output.read_text(encoding="utf-8")
    assert PRIMARY_SESSION not in report_text and OTHER_SESSION not in report_text
    return exit_code, json.loads(report_text), events, requests, plans, invocations


def test_capacity_once_refetches_and_replans_in_same_session(monkeypatch, tmp_path):
    code, report, events, requests, plans, invocations = run_probe(
        monkeypatch, tmp_path, [(502, CAPACITY), None])

    assert code == 0 and report["state"] == "VERIFIED_LIVE"
    assert report["capacity_retry"] == {
        "trigger": "model provider returned HTTP 429", "wait_seconds": 45,
        "first_plan_receipt_sha256": "a" * 64,
    }
    assert events == [
        ("fetch", "coinbase-spot", 1), ("fetch", "treasury-average-rates", 1),
        ("plan", 1), ("invoke", 1), ("sleep", 45),
        ("fetch", "coinbase-spot", 2), ("fetch", "treasury-average-rates", 2),
        ("plan", 2), ("invoke", 2), ("cross-session-plan",),
    ]
    assert plans[0]["evidence_sha256"] == ["1" * 64, "2" * 64]
    assert plans[1]["evidence_sha256"] == ["3" * 64, "4" * 64]
    assert invocations[0]["evidence_sha256"] == plans[0]["evidence_sha256"]
    assert invocations[1]["evidence_sha256"] == plans[1]["evidence_sha256"]
    assert [item["payload_sha256"] for item in report["observations"]] == plans[1]["evidence_sha256"]
    assert report["invocation"]["plan_receipt_sha256"] == report["plan"]["receipt"]["basis_sha256"] == "b" * 64
    assert report["cross_session_evidence_rejected"] is True
    assert all(request.headers["X-SZL-Session"] == PRIMARY_SESSION
               for request in requests[:-1])
    assert requests[-1].headers["X-SZL-Session"] == OTHER_SESSION


def test_no_capacity_keeps_the_original_single_pass(monkeypatch, tmp_path):
    code, report, events, _, plans, invocations = run_probe(
        monkeypatch, tmp_path, [None])

    assert code == 0 and report["state"] == "VERIFIED_LIVE"
    assert "capacity_retry" not in report
    assert not any(event[0] == "sleep" for event in events)
    assert len(plans) == len(invocations) == 1
    assert sum(event[0] == "fetch" for event in events) == 2


def test_second_capacity_failure_remains_failed_and_is_not_retried(monkeypatch, tmp_path):
    code, report, events, _, plans, invocations = run_probe(
        monkeypatch, tmp_path, [(502, CAPACITY), (502, CAPACITY)])

    assert code == 1 and report["state"] == "FAILED"
    assert report["error_class"] == "HTTPStatusError"
    assert report["http_status"] == 502
    assert report["path"] == "/api/verticals/finance/intelligence/invoke"
    assert report["plan"]["receipt"]["basis_sha256"] == "b" * 64
    assert "invocation" not in report and "cross_session_evidence_rejected" not in report
    assert events.count(("sleep", 45)) == 1
    assert len(plans) == len(invocations) == 2


@pytest.mark.parametrize("status, body", [
    (502, {"detail": "model provider returned HTTP 500"}),
    (503, CAPACITY),
    (429, CAPACITY),
    (502, ["model provider returned HTTP 429"]),
    (502, "not JSON"),
])
def test_unrelated_invoke_failures_do_not_retry(monkeypatch, tmp_path, status, body):
    code, report, events, _, plans, invocations = run_probe(
        monkeypatch, tmp_path, [(status, body)])

    assert code == 1 and report["state"] == "FAILED"
    assert report["http_status"] == status
    assert "capacity_retry" not in report
    assert not any(event[0] == "sleep" for event in events)
    assert len(plans) == len(invocations) == 1
    assert sum(event[0] == "fetch" for event in events) == 2


@pytest.mark.parametrize("stage", ["fetch", "plan"])
def test_capacity_mapping_outside_invoke_does_not_retry(monkeypatch, tmp_path, stage):
    code, report, events, _, plans, invocations = run_probe(
        monkeypatch, tmp_path, [], failure_stage=stage)

    assert code == 1 and report["state"] == "FAILED"
    assert report["http_status"] == 502
    assert "capacity_retry" not in report
    assert not any(event[0] == "sleep" for event in events)
    assert not plans and not invocations


def test_replan_abstention_after_capacity_withholds_second_invoke(monkeypatch, tmp_path):
    code, report, events, _, plans, invocations = run_probe(
        monkeypatch, tmp_path, [(502, CAPACITY)], second_plan_decision="ABSTAIN")

    assert code == 1 and report["state"] == "FAILED"
    assert report["error"] == "public model plan withheld"
    assert report["plan"]["decision"] == "ABSTAIN"
    assert [item["payload_sha256"] for item in report["observations"]] == ["3" * 64, "4" * 64]
    assert len(plans) == 2 and len(invocations) == 1
    assert events.count(("sleep", 45)) == 1
