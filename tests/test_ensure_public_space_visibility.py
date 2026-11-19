"""Offline contracts for public Space visibility enforcement."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import tools.ensure_public_space_visibility as subject


class FakeApi:
    def __init__(self, private: bool):
        self.private = private
        self.updates = []

    def space_info(self, repo_id: str):
        return SimpleNamespace(private=self.private, id=repo_id)

    def update_repo_settings(self, **kwargs):
        self.updates.append(kwargs)
        self.private = bool(kwargs.get("private", self.private))


def test_ensure_public_mutates_private_space(tmp_path: Path, monkeypatch):
    api = FakeApi(private=True)
    visibility = subject.ensure_public(api, "SZLHOLDINGS/vertical-services")
    assert visibility["private_before"] is True
    assert visibility["private_after"] is False
    assert visibility["visibility_mutated"] is True
    assert api.updates == [
        {"repo_id": "SZLHOLDINGS/vertical-services", "repo_type": "space", "private": False}
    ]


def test_ensure_public_is_noop_when_already_public():
    api = FakeApi(private=False)
    visibility = subject.ensure_public(api, "SZLHOLDINGS/vertical-services")
    assert visibility["visibility_mutated"] is False
    assert visibility["public"] is True
    assert api.updates == []


def test_probe_unauthenticated_records_http_error(monkeypatch):
    class _FP:
        def read(self):
            return b"y" * 3020

        def close(self):
            return None

    def fake_urlopen(request, timeout=0):
        raise subject.urllib.error.HTTPError(
            request.full_url, 404, "Not Found", hdrs=None, fp=_FP()
        )

    monkeypatch.setattr(subject.urllib.request, "urlopen", fake_urlopen)
    probe = subject.probe_unauthenticated("https://szlholdings-vertical-services.hf.space")
    assert probe["status"] == 404
    assert probe["bytes"] == 3020
    assert probe["authorization_sent"] is False
    assert probe["ok"] is False


def test_workflow_invokes_ensure_public_before_publish():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "hf-space.yml").read_text(encoding="utf-8")
    assert "tools/ensure_public_space_visibility.py" in workflow
    assert "Ensure public Space visibility for public smoke" in workflow
    assert "Checkout exact source for local writer helpers" in workflow
    assert workflow.index("Checkout exact source for local writer helpers") < workflow.index(
        "Resolve writer without exposing token material"
    )
    # Must run in the local writer path before reusable publish consumes the Space.
    assert workflow.index("Ensure public Space visibility for public smoke") < workflow.index(
        "reusable-hf-deploy.yml"
    )


def _step(workflow: str, name: str) -> str:
    marker = f"- name: {name}\n"
    start = workflow.index(marker)
    rest = workflow[start + len(marker):]
    nxt = rest.find("\n      - name:")
    return rest[:nxt] if nxt != -1 else rest


def test_publisher_exposes_pinned_governed_provider_before_witness():
    """Anonymous reads of a private Space are the Hub marketing HTTP 404.

    The Lyte witness then records invoke HTTP 502 and never reaches a protocol
    hash check. The publisher must force the pinned provider Space public and
    probe its contract URL before that witness, without softening the witness.
    """
    root = Path(__file__).resolve().parents[1]
    pin = (root / "deploy" / "szl_verticals" / "public_governed_khipu.py").read_text(
        encoding="utf-8"
    )
    assert 'ORIGIN = "https://szlholdings-szl-model-inference-lab.hf.space"' in pin
    assert 'CONTRACT_URL = ORIGIN + "/.well-known/szl-governed-inference-contract.json"' in pin
    workflow = (root / ".github" / "workflows" / "hf-space.yml").read_text(encoding="utf-8")
    provider = _step(workflow, "Ensure pinned governed provider Space is public")
    witness = _step(workflow, "Witness the pinned public governed proposal protocol")
    assert "tools/ensure_public_space_visibility.py" in provider
    assert "--repo-id SZLHOLDINGS/szl-model-inference-lab" in provider
    assert "--probe-path /.well-known/szl-governed-inference-contract.json" in provider
    assert "continue-on-error" not in provider
    assert "tools/probe_public_governed_khipu.py" in witness
    assert "--expected-revision" in witness
    assert "continue-on-error" not in witness
    assert workflow.index("Ensure pinned governed provider Space is public") < workflow.index(
        "Witness the pinned public governed proposal protocol"
    )
