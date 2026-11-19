from __future__ import annotations

from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from frontier_fabric.catalog import CATALOG_ERRORS, VERTICALS, get_vertical, public_catalog
from frontier_fabric.connectors import (
    ConnectorError,
    ConnectorPolicyError,
    ConnectorRegistry,
    ConnectorUnavailable,
)
from frontier_fabric.engine import VerticalFabric, request_from_mapping
from frontier_fabric.receipts import ReceiptChain, canonical_json, sha256_hex
from frontier_fabric.types import (
    ClaimState,
    Decision,
    EffectMode,
    EvaluationRequest,
    KernelResult,
    Proposal,
    SourceRef,
)


def _reviewed_proposal(vertical_id: str) -> Proposal:
    vertical = get_vertical(vertical_id)
    model_id = vertical.models[0].repo_id if vertical.models else None
    return Proposal(
        summary="Reviewed proposal derived from the declared evidence set.",
        model_id=model_id,
        model_revision="a" * 40 if model_id else None,
        confidence=0.71,
        citations=(),
        state=ClaimState.ADVISORY,
        payload={"reviewed": True},
    )


def _human_bind(decision: str = "ALLOW") -> dict[str, str]:
    return {
        "approver_id": "operator-01",
        "approved_at": "2026-09-04T00:00:00Z",
        "scope": "publish evidence-linked report",
        "decision": decision,
        "policy_revision": "policy-v1",
    }


def _pass_kernel(repo_id: str):
    def adapter(request, proposal, vertical):  # noqa: ANN001
        return KernelResult(
            kernel_id=repo_id,
            passed=True,
            blocking=True,
            state=ClaimState.MEASURED,
            reason="deterministic test adapter passed",
            evidence={
                "signal_id": request.signal_id,
                "proposal_state": proposal.state.value,
                "vertical_id": vertical.id,
            },
        )

    return adapter


def test_catalog_is_valid_and_complete() -> None:
    assert CATALOG_ERRORS == []
    assert len(VERTICALS) == 10
    assert {item.id for item in VERTICALS} == {
        "a11oy",
        "hatun",
        "killinchu",
        "sentra",
        "lyte",
        "puriq-finance",
        "terra",
        "prism-counsel",
        "living-anatomy",
        "szl-atlas",
    }


def test_every_vertical_has_a_unique_lane_and_visual_identity() -> None:
    assert len({item.lane for item in VERTICALS}) == len(VERTICALS)
    assert len({item.unmet_need for item in VERTICALS}) == len(VERTICALS)
    assert len({item.differentiator for item in VERTICALS}) == len(VERTICALS)
    assert len({item.theme.id for item in VERTICALS}) == len(VERTICALS)
    assert len({item.theme.signature_modules for item in VERTICALS}) == len(VERTICALS)

    for vertical in VERTICALS:
        assert len(vertical.experience_modules) >= 6
        assert len(vertical.evidence_contract) >= 5
        assert vertical.theme.tokens["focus"]
        assert vertical.public_actuation is not ClaimState.LIVE


def test_killinchu_is_simulation_only_in_public_contract() -> None:
    killinchu = get_vertical("killinchu")
    assert killinchu.effect_mode is EffectMode.SIMULATED_ONLY
    assert killinchu.requires_human_bind is True
    assert killinchu.public_actuation is ClaimState.SIMULATED
    assert any("Historical" in item.notes for item in killinchu.connectors)


def test_public_catalog_preserves_the_authority_boundary() -> None:
    catalog = public_catalog()
    assert catalog["truth_boundary"] == {
        "model_proposes": True,
        "policy_decides": True,
        "human_binds_consequential_action": True,
        "lambda_uniqueness": "CONJECTURE_1_OPEN",
        "public_effectors_enabled": False,
    }
    assert len(catalog["verticals"]) == len(VERTICALS)


def test_connector_registry_builds_only_declared_official_urls() -> None:
    registry = ConnectorRegistry()
    sec = registry.build_url(
        "sec-submissions",
        path_params={"cik": "0000320193"},
    )
    assert sec == "https://data.sec.gov/submissions/CIK0000320193.json"

    actions = registry.build_url(
        "github-actions",
        path_params={"owner": "szl-holdings", "repo": "a11oy"},
        query={"branch": "main", "per_page": 25},
    )
    parts = urlsplit(actions)
    assert parts.scheme == "https"
    assert parts.hostname == "api.github.com"
    assert parts.path == "/repos/szl-holdings/a11oy/actions/runs"
    assert parse_qs(parts.query) == {"branch": ["main"], "per_page": ["25"]}


def test_connector_registry_rejects_path_and_query_injection() -> None:
    registry = ConnectorRegistry()

    with pytest.raises(ConnectorPolicyError):
        registry.build_url(
            "github-actions",
            path_params={"owner": "szl-holdings/../root", "repo": "a11oy"},
        )

    with pytest.raises(ConnectorPolicyError):
        registry.build_url(
            "sec-submissions",
            path_params={"cik": "1"},
        )

    with pytest.raises(ConnectorPolicyError):
        registry.build_url(
            "cisa-kev",
            query={"url": "https://example.invalid"},
        )

    with pytest.raises(ConnectorPolicyError):
        registry.get("https://example.invalid/data.json")


def test_operator_bound_connectors_fail_closed_without_network_configuration() -> None:
    registry = ConnectorRegistry()
    with pytest.raises(ConnectorUnavailable):
        registry.build_url("operator-evidence")
    with pytest.raises(ConnectorUnavailable):
        registry.build_url("otel")
    with pytest.raises(ConnectorUnavailable):
        registry.build_url("local-anatomy")


def test_canonical_json_and_hash_are_deterministic() -> None:
    left = {"b": [2, 3], "a": {"enabled": True}}
    right = {"a": {"enabled": True}, "b": [2, 3]}
    assert canonical_json(left) == canonical_json(right)
    assert sha256_hex(left) == sha256_hex(right)


def test_receipt_chain_detects_tampering() -> None:
    chain = ReceiptChain("lyte")
    first = chain.append(
        operation="signal.observe",
        payload={"service": "checkout", "state": "DEGRADED"},
        actor_id="actor-hash",
        signal_id="signal-1",
        issued_at="2026-09-04T00:00:00Z",
    )
    second = chain.append(
        operation="decision.review",
        payload={"decision": "HOLD"},
        actor_id="actor-hash",
        signal_id="signal-1",
        issued_at="2026-09-04T00:01:00Z",
    )
    assert first["previous_hash"] == "0" * 64
    assert second["previous_hash"] == first["receipt_hash"]
    assert chain.verify()["ok"] is True

    chain.entries[0]["actor_id"] = "tampered"
    result = chain.verify()
    assert result["ok"] is False
    assert result["errors"][0]["error"] == "RECEIPT_HASH_MISMATCH"


def test_unbound_model_is_explicitly_unavailable_and_never_authorizes() -> None:
    fabric = VerticalFabric()
    result = fabric.evaluate(
        EvaluationRequest(
            vertical_id="lyte",
            signal_id="sig-1",
            session_id="session-secret",
            actor_id="actor-secret",
            payload={"service": "checkout"},
        )
    )
    assert result.decision is Decision.HOLD
    assert result.state is ClaimState.UNAVAILABLE
    assert result.proposal.model_id is None
    assert result.proposal.state is ClaimState.UNAVAILABLE
    assert result.receipt["authorization_proof"] is False


def test_undeclared_source_is_blocked_before_any_effect() -> None:
    fabric = VerticalFabric()
    result = fabric.evaluate(
        EvaluationRequest(
            vertical_id="terra",
            signal_id="parcel-1",
            session_id="session-1",
            actor_id="actor-1",
            payload={"bbl": "1000010001"},
            sources=(
                SourceRef(
                    connector_id="cisa-kev",
                    locator="CVE-2026-0001",
                ),
            ),
            proposal=_reviewed_proposal("terra"),
        )
    )
    assert result.decision is Decision.DENY
    assert result.state is ClaimState.BLOCKED
    assert "undeclared source connectors" in result.reason


def test_effect_remains_on_hold_until_every_declared_kernel_is_bound() -> None:
    request = EvaluationRequest(
        vertical_id="a11oy",
        signal_id="decision-1",
        session_id="session-1",
        actor_id="actor-1",
        payload={"lambda_axes": [0.95, 0.92, 0.90]},
        proposal=_reviewed_proposal("a11oy"),
        requested_effect="publish-report",
        human_bind=_human_bind(),
    )
    fabric = VerticalFabric()
    held = fabric.evaluate(request)
    assert held.decision is Decision.HOLD
    assert "kernels are not bound" in held.reason

    for binding in get_vertical("a11oy").kernels:
        fabric.register_kernel(binding.repo_id, _pass_kernel(binding.repo_id))

    allowed = fabric.evaluate(request)
    assert allowed.decision is Decision.ALLOW
    assert allowed.state is ClaimState.MEASURED
    assert all(
        result.passed
        for result in allowed.kernel_results
        if result.kernel_id.startswith("SZLHOLDINGS/")
    )


def test_human_denial_overrides_passing_policy_and_kernels() -> None:
    fabric = VerticalFabric()
    for binding in get_vertical("prism-counsel").kernels:
        fabric.register_kernel(binding.repo_id, _pass_kernel(binding.repo_id))

    result = fabric.evaluate(
        EvaluationRequest(
            vertical_id="prism-counsel",
            signal_id="matter-1",
            session_id="session-1",
            actor_id="reviewer-1",
            payload={"matter": "example"},
            proposal=_reviewed_proposal("prism-counsel"),
            requested_effect="publish-report",
            human_bind=_human_bind("DENY"),
        )
    )
    assert result.decision is Decision.DENY
    assert result.state is ClaimState.BLOCKED
    assert result.reason == "human binding denied the requested scope"


def test_killinchu_non_simulated_effect_is_denied() -> None:
    fabric = VerticalFabric(require_bound_kernels_for_effects=False)
    result = fabric.evaluate(
        EvaluationRequest(
            vertical_id="killinchu",
            signal_id="track-1",
            session_id="session-1",
            actor_id="operator-1",
            payload={"track": "synthetic"},
            proposal=_reviewed_proposal("killinchu"),
            requested_effect="launch weapon at target",
            human_bind=_human_bind(),
        )
    )
    assert result.decision is Decision.DENY
    assert result.state is ClaimState.BLOCKED
    assert "violates policy" in result.reason


def test_session_receipt_scope_hashes_identifiers() -> None:
    fabric = VerticalFabric()
    request = EvaluationRequest(
        vertical_id="sentra",
        signal_id="exposure-1",
        session_id="do-not-publish-session",
        actor_id="do-not-publish-actor",
        payload={"asset": "public-test"},
    )
    result = fabric.evaluate(request)
    serialized = canonical_json(result.receipt)
    assert "do-not-publish-session" not in serialized
    assert "do-not-publish-actor" not in serialized
    assert fabric.verify_session("sentra", "do-not-publish-session")["ok"] is True


def test_mapping_parser_preserves_explicit_truth_state() -> None:
    request = request_from_mapping(
        {
            "vertical_id": "puriq-finance",
            "signal_id": "filing-1",
            "session_id": "session-1",
            "actor_id": "analyst-1",
            "payload": {"cik": "0000320193"},
            "sources": [
                {
                    "connector_id": "sec-submissions",
                    "locator": "CIK0000320193",
                    "revision": "accession-example",
                }
            ],
            "proposal": {
                "summary": "A reviewed filing observation.",
                "model_id": "SZLHOLDINGS/szl-nemo",
                "model_revision": "b" * 40,
                "confidence": 0.65,
                "state": "ADVISORY",
                "payload": {"thesis": "example"},
            },
        }
    )
    assert request.vertical_id == "puriq-finance"
    assert request.proposal is not None
    assert request.proposal.state is ClaimState.ADVISORY
    assert request.sources[0].connector_id == "sec-submissions"


def _bound_fabric(vertical_id: str) -> VerticalFabric:
    fabric = VerticalFabric()
    for binding in get_vertical(vertical_id).kernels:
        fabric.register_kernel(binding.repo_id, _pass_kernel(binding.repo_id))
    return fabric


def _effect_request(**overrides) -> EvaluationRequest:  # noqa: ANN003
    fields = {
        "vertical_id": "a11oy",
        "signal_id": "decision-contract",
        "session_id": "session-contract",
        "actor_id": "actor-contract",
        "payload": {"lambda_axes": [0.95, 0.92, 0.90]},
        "proposal": _reviewed_proposal("a11oy"),
        "requested_effect": "publish-report",
        "human_bind": _human_bind(),
    }
    fields.update(overrides)
    return EvaluationRequest(**fields)


def _contract_result(result):  # noqa: ANN001, ANN202
    return next(
        item for item in result.kernel_results if item.kernel_id == "szl-core/proposal-contract"
    )


def test_well_formed_proposal_and_bind_still_allow() -> None:
    result = _bound_fabric("a11oy").evaluate(_effect_request())
    assert result.decision is Decision.ALLOW
    contract = _contract_result(result)
    assert contract.passed is True
    assert contract.blocking is True


def test_unbound_model_proposal_satisfies_the_proposal_contract() -> None:
    result = VerticalFabric().evaluate(_effect_request(proposal=None, requested_effect=None))
    assert result.proposal.state is ClaimState.UNAVAILABLE
    assert _contract_result(result).passed is True
    assert result.decision is Decision.HOLD


@pytest.mark.parametrize("claimed", [ClaimState.LIVE, ClaimState.MEASURED])
@pytest.mark.parametrize(
    ("model_id", "model_revision"),
    [(None, None), ("SZLHOLDINGS/szl-nemo", None), (None, "a" * 40), ("  ", "a" * 40)],
)
def test_live_or_measured_proposal_without_model_identity_is_denied(
    claimed: ClaimState,
    model_id: str | None,
    model_revision: str | None,
) -> None:
    proposal = Proposal(
        summary="Unattributed claim.",
        model_id=model_id,
        model_revision=model_revision,
        confidence=0.5,
        citations=(),
        state=claimed,
        payload={},
    )
    result = _bound_fabric("a11oy").evaluate(_effect_request(proposal=proposal))
    assert result.decision is Decision.DENY
    assert result.state is ClaimState.BLOCKED
    assert "model identity and exact revision" in result.reason
    assert _contract_result(result).passed is False


@pytest.mark.parametrize("confidence", [7.5, 1.0001, -0.1])
def test_out_of_range_confidence_is_denied(confidence: float) -> None:
    proposal = Proposal(
        summary="Reviewed proposal.",
        model_id="SZLHOLDINGS/szl-nemo",
        model_revision="a" * 40,
        confidence=confidence,
        citations=(),
        state=ClaimState.ADVISORY,
        payload={},
    )
    result = _bound_fabric("a11oy").evaluate(_effect_request(proposal=proposal))
    assert result.decision is Decision.DENY
    assert result.state is ClaimState.BLOCKED
    assert "confidence must be None or within [0, 1]" in result.reason


def test_mapping_proposal_with_inflated_state_and_confidence_is_denied() -> None:
    request = request_from_mapping(
        {
            "vertical_id": "lyte",
            "signal_id": "sig-1",
            "session_id": "session-1",
            "actor_id": "actor-1",
            "payload": {},
            "proposal": {"summary": "x", "state": "LIVE", "confidence": 7.5},
            "requested_effect": "export-report",
            "human_bind": _human_bind(),
        }
    )
    result = VerticalFabric(require_bound_kernels_for_effects=False).evaluate(request)
    assert result.decision is Decision.DENY
    assert result.state is ClaimState.BLOCKED


@pytest.mark.parametrize(
    "approved_at",
    ["whenever", "2026-09-04T00:00:00", "2026-09-04", "2026-13-40T00:00:00Z", 1788480000],
)
def test_allow_bind_without_offset_qualified_timestamp_never_allows(approved_at) -> None:  # noqa: ANN001
    bind = dict(_human_bind())
    bind["approved_at"] = approved_at
    result = _bound_fabric("a11oy").evaluate(_effect_request(human_bind=bind))
    assert result.decision is Decision.DENY
    assert result.state is ClaimState.BLOCKED
    assert "approved_at must be an ISO-8601 timestamp with a UTC offset" in result.reason
    bind_kernel = next(
        item for item in result.kernel_results if item.kernel_id == "szl-core/human-bind"
    )
    assert bind_kernel.passed is False
    assert bind_kernel.state is ClaimState.UNAVAILABLE


def test_denial_is_still_honored_when_its_timestamp_is_malformed() -> None:
    bind = dict(_human_bind("DENY"))
    bind["approved_at"] = "whenever"
    result = _bound_fabric("a11oy").evaluate(_effect_request(human_bind=bind))
    assert result.decision is Decision.DENY
    assert result.state is ClaimState.BLOCKED
    assert result.reason == "human binding denied the requested scope"


@pytest.mark.parametrize(
    "approved_at",
    ["2026-09-04T00:00:00Z", "2026-09-04T00:00:00+00:00", "2026-09-03T19:00:00-05:00"],
)
def test_bind_with_offset_qualified_timestamp_is_accepted(approved_at: str) -> None:
    bind = dict(_human_bind())
    bind["approved_at"] = approved_at
    result = _bound_fabric("a11oy").evaluate(_effect_request(human_bind=bind))
    assert result.decision is Decision.ALLOW
    assert result.state is ClaimState.MEASURED


@pytest.mark.parametrize(
    ("connector_id", "path_params"),
    [
        ("github-org", {"org": ".."}),
        ("github-org", {"org": "."}),
        ("github-actions", {"owner": "..", "repo": ".."}),
        ("github-actions", {"owner": ".", "repo": "a11oy"}),
        ("github-actions", {"owner": "szl-holdings", "repo": ".."}),
    ],
)
def test_connector_registry_rejects_dot_segment_path_parameters(
    connector_id: str,
    path_params: dict[str, str],
) -> None:
    with pytest.raises(ConnectorPolicyError):
        ConnectorRegistry().build_url(connector_id, path_params=path_params)


def test_connector_registry_keeps_dotted_names_that_are_not_dot_segments() -> None:
    url = ConnectorRegistry().build_url(
        "github-actions",
        path_params={"owner": "szl-holdings", "repo": ".github"},
    )
    assert urlsplit(url).path == "/repos/szl-holdings/.github/actions/runs"


class _StubResponse:
    def __init__(self, *, status: int = 200, content_type: str = "application/json",
                 body: bytes = b"{}", content_length: str | None = None) -> None:
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if content_length is not None:
            self.headers["Content-Length"] = content_length
        self._body = body

    def read(self, amount: int = -1) -> bytes:
        return self._body if amount < 0 else self._body[:amount]

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *exc_info) -> None:  # noqa: ANN002
        return None


class _StubOpener:
    def __init__(self, outcome) -> None:  # noqa: ANN001
        self.outcome = outcome
        self.requests: list = []

    def open(self, request, timeout=None):  # noqa: ANN001, ANN201
        self.requests.append((request, timeout))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def _stubbed_registry(outcome) -> tuple[ConnectorRegistry, _StubOpener]:  # noqa: ANN001
    registry = ConnectorRegistry()
    opener = _StubOpener(outcome)
    registry._opener = opener
    return registry, opener


def test_fetch_returns_bounded_body_and_sends_only_declared_headers() -> None:
    registry, opener = _stubbed_registry(_StubResponse(body=b'{"ok": true}'))
    result = registry.fetch("cisa-kev", extra_headers={"Authorization": "Bearer test-token"})
    assert result.status == 200
    assert result.json() == {"ok": True}
    request, timeout = opener.requests[0]
    assert request.full_url == registry.build_url("cisa-kev")
    assert request.get_method() == "GET"
    assert timeout == 10.0
    assert request.get_header("Authorization") == "Bearer test-token"
    assert request.get_header("Accept-encoding") == "identity"


@pytest.mark.parametrize("code", [301, 302, 307, 308])
def test_fetch_refuses_redirects(code: int) -> None:
    error = HTTPError("https://www.cisa.gov/", code, "redirect", Message(), None)
    registry, _ = _stubbed_registry(error)
    with pytest.raises(ConnectorPolicyError, match="redirects are forbidden"):
        registry.fetch("cisa-kev")


def test_fetch_reports_provider_http_errors_without_policy_or_unavailable_labels() -> None:
    error = HTTPError("https://www.cisa.gov/", 503, "unavailable", Message(), None)
    registry, _ = _stubbed_registry(error)
    with pytest.raises(ConnectorError) as excinfo:
        registry.fetch("cisa-kev")
    assert type(excinfo.value) is ConnectorError


def test_fetch_rejects_undeclared_content_type() -> None:
    registry, _ = _stubbed_registry(_StubResponse(content_type="text/html"))
    with pytest.raises(ConnectorPolicyError, match="content type"):
        registry.fetch("cisa-kev")


def test_fetch_rejects_oversize_declared_and_actual_bodies() -> None:
    limit = ConnectorRegistry().get("cisa-kev").max_bytes
    registry, _ = _stubbed_registry(_StubResponse(content_length=str(limit + 1)))
    with pytest.raises(ConnectorPolicyError, match="declared response exceeds"):
        registry.fetch("cisa-kev")

    registry, _ = _stubbed_registry(_StubResponse(body=b"x" * (limit + 1)))
    with pytest.raises(ConnectorPolicyError, match="response exceeds"):
        registry.fetch("cisa-kev")

    registry, _ = _stubbed_registry(_StubResponse(content_length="not-a-number"))
    with pytest.raises(ConnectorPolicyError, match="invalid Content-Length"):
        registry.fetch("cisa-kev")


@pytest.mark.parametrize(
    "extra_headers",
    [{"Host": "example.invalid"}, {"X-Forwarded-For": "127.0.0.1"}, {"Authorization": "a\r\nb"}, {"Authorization": ""}],
)
def test_fetch_rejects_non_credential_or_malformed_runtime_headers(
    extra_headers: dict[str, str],
) -> None:
    registry, opener = _stubbed_registry(_StubResponse())
    with pytest.raises(ConnectorPolicyError):
        registry.fetch("cisa-kev", extra_headers=extra_headers)
    assert opener.requests == []


@pytest.mark.parametrize("timeout", [0.0, 30.5])
def test_fetch_rejects_out_of_bounds_timeouts(timeout: float) -> None:
    registry, opener = _stubbed_registry(_StubResponse())
    with pytest.raises(ConnectorPolicyError, match="timeout"):
        registry.fetch("cisa-kev", timeout=timeout)
    assert opener.requests == []


def test_fetch_maps_transport_failure_to_unavailable() -> None:
    registry, _ = _stubbed_registry(URLError("offline"))
    with pytest.raises(ConnectorUnavailable):
        registry.fetch("cisa-kev")


def test_fetch_of_operator_bound_connector_fails_before_any_network_call() -> None:
    registry, opener = _stubbed_registry(_StubResponse())
    with pytest.raises(ConnectorUnavailable):
        registry.fetch("operator-evidence")
    assert opener.requests == []


def test_fetch_of_dot_segment_path_fails_before_any_network_call() -> None:
    registry, opener = _stubbed_registry(_StubResponse())
    with pytest.raises(ConnectorPolicyError):
        registry.fetch("github-actions", path_params={"owner": "..", "repo": ".."})
    assert opener.requests == []
