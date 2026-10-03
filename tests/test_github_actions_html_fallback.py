"""A public GitHub Actions page may rescue an unauthenticated REST quota failure."""
import hashlib
import os
import sys
import tempfile
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))

_STATE = tempfile.TemporaryDirectory()
os.environ.setdefault("SENTRA_SIGNING_KEY", "test-key-only")
os.environ.setdefault("SZL_SOURCE_REVISION", "3" * 40)
os.environ.setdefault("SZL_STATE_PATH", str(Path(_STATE.name) / "observations.sqlite3"))

from szl_verticals.connector_parameters import _assert_allowed_destination  # noqa: E402
from szl_verticals.official_connectors import fetch_connector  # noqa: E402
from szl_verticals.connector_specs import ConnectorFetchRequest  # noqa: E402


REPO = "vertical-services"
URL = f"https://github.com/szl-holdings/{REPO}/actions"
HTML = f"""<!doctype html><html><body>
<a href="/szl-holdings/{REPO}/actions/runs/123" aria-label="completed successfully:  Run 7 of CI. Commit one">CI</a>
<a href="/szl-holdings/{REPO}/commit/{'a' * 40}">commit</a>
<relative-time datetime="2026-10-02T23:13:12Z"></relative-time>
<a href="/szl-holdings/{REPO}/actions/runs/122" aria-label="failed:  Run 6 of CI. Commit two">CI</a>
<a href="/szl-holdings/{REPO}/commit/{'b' * 40}">commit</a>
<relative-time datetime="2026-10-02T22:13:12Z"></relative-time>
</body></html>""".encode()


def _request(**parameters):
    return ConnectorFetchRequest(parameters={"repository": REPO, "limit": 10, **parameters},
                                 force_refresh=True)


def test_unauthenticated_quota_fallback_records_actual_html_source(monkeypatch):
    monkeypatch.delenv("GITHUB_READ_TOKEN", raising=False)
    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        if request.url.host == "api.github.com":
            assert "authorization" not in request.headers
            return httpx.Response(403)
        assert str(request.url) == URL
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"},
                              content=HTML)

    result = fetch_connector(vertical="lyte", connector_id="github-actions",
                             request=_request(), session_scope="f" * 64,
                             transport=httpx.MockTransport(handler))
    assert hosts == ["api.github.com", "github.com"]
    assert result["receipt"]["source_url"] == URL
    assert result["receipt"]["payload_sha256"] == hashlib.sha256(HTML).hexdigest()
    assert result["receipt"]["truth_label"] == "REPORTED"
    assert result["observation"]["source_representation"] == "PUBLIC_GITHUB_ACTIONS_HTML"
    assert result["observation"]["coverage"] == "PAGE_FIRST_N"
    assert result["observation"]["success_rate"] == 0.5
    assert [run["head_sha"] for run in result["observation"]["runs"]] == ["a" * 40, "b" * 40]
    assert result["signal"]["severity"] == "HIGH"


def test_rest_success_keeps_authoritative_api_source(monkeypatch):
    monkeypatch.delenv("GITHUB_READ_TOKEN", raising=False)
    payload = {"total_count": 1, "workflow_runs": [
        {"id": 123, "status": "completed", "conclusion": "success"}]}
    result = fetch_connector(vertical="lyte", connector_id="github-actions",
                             request=_request(), session_scope="e" * 64,
                             transport=httpx.MockTransport(
                                 lambda _: httpx.Response(200, json=payload)))
    assert result["receipt"]["source_url"].startswith("https://api.github.com/")
    assert "source_representation" not in result["observation"]


@pytest.mark.parametrize("status", [403, 429])
def test_unknown_page_does_not_become_observed(monkeypatch, status):
    monkeypatch.delenv("GITHUB_READ_TOKEN", raising=False)

    def handler(request):
        if request.url.host == "api.github.com":
            return httpx.Response(status)
        return httpx.Response(200, headers={"content-type": "text/html"},
                              content=b"<html>Sign in to GitHub</html>")

    with pytest.raises(HTTPException) as error:
        fetch_connector(vertical="lyte", connector_id="github-actions",
                        request=_request(), session_scope="d" * 64,
                        transport=httpx.MockTransport(handler))
    assert error.value.status_code == 502
    assert error.value.detail == "public Actions page schema is not recognized"


@pytest.mark.parametrize("parameters", [{"branch": "main"}, {"status": "completed"}])
def test_filtered_rest_failure_never_changes_query_semantics(monkeypatch, parameters):
    monkeypatch.delenv("GITHUB_READ_TOKEN", raising=False)
    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        return httpx.Response(403)

    with pytest.raises(HTTPException) as error:
        fetch_connector(vertical="lyte", connector_id="github-actions",
                        request=_request(**parameters), session_scope="c" * 64,
                        transport=httpx.MockTransport(handler))
    assert error.value.detail == "upstream returned HTTP 403"
    assert hosts == ["api.github.com"]


def test_bad_configured_credential_is_not_hidden(monkeypatch):
    monkeypatch.setenv("GITHUB_READ_TOKEN", "configured-token-fixture")
    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        assert request.headers["authorization"] == "Bearer configured-token-fixture"
        return httpx.Response(403)

    with pytest.raises(HTTPException) as error:
        fetch_connector(vertical="lyte", connector_id="github-actions",
                        request=_request(), session_scope="b" * 64,
                        transport=httpx.MockTransport(handler))
    assert error.value.detail == "upstream returned HTTP 403"
    assert hosts == ["api.github.com"]


@pytest.mark.parametrize("bad", [
    "https://github.com/szl-holdings/vertical-services",
    "https://github.com/szl-holdings/vertical-services/actions/runs/123",
    "https://github.com/other/vertical-services/actions",
    "https://github.com/szl-holdings/not-allowlisted/actions",
    "https://github.com/szl-holdings/vertical-services/actions?query=anything",
    "https://github.com:444/szl-holdings/vertical-services/actions",
])
def test_fallback_destination_is_one_bounded_path(bad):
    with pytest.raises(HTTPException):
        _assert_allowed_destination(bad)
    _assert_allowed_destination(URL)


def test_html_parser_rejects_missing_commit_even_with_success_label(monkeypatch):
    monkeypatch.delenv("GITHUB_READ_TOKEN", raising=False)
    forged = f'<a href="/szl-holdings/{REPO}/actions/runs/123" aria-label="completed successfully: Run 7 of CI">run</a><relative-time datetime="2026-10-02T23:13:12Z"></relative-time>'

    def handler(request):
        if request.url.host == "api.github.com":
            return httpx.Response(403)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=forged)

    with pytest.raises(HTTPException) as error:
        fetch_connector(vertical="lyte", connector_id="github-actions",
                        request=_request(), session_scope="a" * 64,
                        transport=httpx.MockTransport(handler))
    assert error.value.detail == "public Actions page schema is not recognized"


def test_pr_and_schedule_rows_preserve_unknown_head_sha():
    from szl_verticals.connector_github_html import parse_public_actions_page

    page = f"""<html><body>
    <a href="/szl-holdings/{REPO}/actions/runs/131" aria-label="completed successfully: Run 9 of CI. Pull request">run</a>
    Pull request <a href="/szl-holdings/{REPO}/pull/69">#69</a>
    <relative-time datetime="2026-10-02T23:13:12Z"></relative-time>
    <a href="/szl-holdings/{REPO}/actions/runs/130" aria-label="failed: Run 8 of Uptime Monitor.">run</a>
    Scheduled
    <relative-time datetime="2026-10-02T22:13:12Z"></relative-time>
    </body></html>""".encode()
    result = parse_public_actions_page(page, "text/html", REPO, 10)
    assert [run["event"] for run in result["runs"]] == ["pull_request", "schedule"]
    assert [run["head_sha"] for run in result["runs"]] == [None, None]
    assert result["success_rate"] == 0.5


def test_currently_running_public_row_is_observed_without_counting_as_completed(monkeypatch):
    """GitHub uses 'currently running' while this release's own probe is active."""
    monkeypatch.delenv("GITHUB_READ_TOKEN", raising=False)
    page = HTML.replace(b"failed:  Run 6", b"currently running:  Run 6")

    def handler(request):
        if request.url.host == "api.github.com":
            return httpx.Response(403)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=page)

    result = fetch_connector(vertical="lyte", connector_id="github-actions",
                             request=_request(), session_scope="9" * 64,
                             transport=httpx.MockTransport(handler))
    observation = result["observation"]
    assert observation["returned"] == 2
    assert observation["completed"] == 1
    assert observation["failed_or_cancelled"] == 0
    assert observation["success_rate"] == 1.0
    assert observation["runs"][1]["status"] == "in_progress"
    assert observation["runs"][1]["conclusion"] is None
    assert observation["runs"][1]["head_sha"] == "b" * 40
    assert result["receipt"]["payload_sha256"] == hashlib.sha256(page).hexdigest()
    assert result["receipt"]["source_url"] == URL
    assert observation["coverage"] == "PAGE_FIRST_N"


def test_all_currently_running_rows_have_no_measured_success_rate():
    from szl_verticals.connector_github_html import parse_public_actions_page

    page = HTML.replace(b"completed successfully:", b"currently running:").replace(
        b"failed:", b"currently running:")
    result = parse_public_actions_page(page, "text/html", REPO, 10)
    assert result["returned"] == 2
    assert result["completed"] == 0
    assert result["success_rate"] is None
    assert all(run["conclusion"] is None for run in result["runs"])


def test_unrecognized_running_label_still_fails_closed():
    from szl_verticals.connector_github_html import parse_public_actions_page

    page = HTML.replace(b"failed:", b"currently succeeded:")
    with pytest.raises(HTTPException) as error:
        parse_public_actions_page(page, "text/html", REPO, 10)
    assert error.value.status_code == 502
    assert error.value.detail == "public Actions page schema is not recognized"
