"""Fail-closed reader for GitHub's public Actions run list.

This is a degraded, unauthenticated source used only when the REST API's
shared-IP quota refuses a request.  It never turns a page into an API receipt:
the connector retains the HTML URL and SHA-256 of the exact page bytes.
"""
from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any

from fastapi import HTTPException

from .connector_parsers_security import _parse_github


_RUN_STATES = {
    "completed successfully": ("completed", "success"),
    "failed": ("completed", "failure"),
    "cancelled": ("completed", "cancelled"),
    "timed out": ("completed", "timed_out"),
    "skipped": ("completed", "skipped"),
    "in progress": ("in_progress", None),
    "currently running": ("in_progress", None),
    "queued": ("queued", None),
    "waiting": ("waiting", None),
    "requested": ("requested", None),
    "pending": ("pending", None),
}
_RUN_NUMBER = re.compile(r"\bRun ([1-9][0-9]*) of\b")
_SHA = re.compile(r"[0-9a-f]{40}")


class _ActionsPage(HTMLParser):
    def __init__(self, repository: str, limit: int) -> None:
        super().__init__(convert_charrefs=True)
        self.repository = repository
        self.limit = limit
        self.rows: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.run_prefix = f"/szl-holdings/{repository}/actions/runs/"
        self.commit_prefix = f"/szl-holdings/{repository}/commit/"

    def _finish(self) -> None:
        if self.current is None or len(self.rows) >= self.limit:
            return
        if (self.current["created_at"] is None
                or (self.current["head_sha"] is None
                    and self.current["event"] not in {"pull_request", "schedule"})):
            raise ValueError("public Actions run lacks a source or timestamp")
        self.rows.append(self.current)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a":
            href = values.get("href") or ""
            label = values.get("aria-label") or ""
            if href.startswith(self.run_prefix) and label:
                if len(self.rows) >= self.limit:
                    self.current = None
                    return
                if len(label) > 512 or any(ord(char) < 32 for char in label):
                    raise ValueError("public Actions run label is unbounded")
                suffix = href[len(self.run_prefix):]
                if not suffix.isascii() or not suffix.isdecimal() or suffix.startswith("0"):
                    raise ValueError("public Actions run id is invalid")
                self._finish()
                state_label = label.partition(":")[0].strip().lower()
                state = _RUN_STATES.get(state_label)
                number = _RUN_NUMBER.search(label)
                if state is None or number is None:
                    raise ValueError("public Actions run state is unknown")
                self.current = {
                    "id": int(suffix),
                    "name": None,
                    "display_title": label,
                    "event": None,
                    "status": state[0],
                    "conclusion": state[1],
                    "head_branch": None,
                    "head_sha": None,
                    "run_number": int(number.group(1)),
                    "created_at": None,
                    "updated_at": None,
                    "html_url": f"https://github.com{href}",
                }
            elif self.current is not None and href.startswith(self.commit_prefix):
                sha = href[len(self.commit_prefix):]
                if _SHA.fullmatch(sha) is not None:
                    self.current["head_sha"] = sha
            elif (self.current is not None
                  and re.fullmatch(rf"/szl-holdings/{re.escape(self.repository)}/pull/[1-9][0-9]*", href)):
                self.current["event"] = "pull_request"
        elif tag == "relative-time" and self.current is not None:
            stamp = values.get("datetime") or ""
            try:
                parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                return
            if parsed.tzinfo is not None and self.current["created_at"] is None:
                self.current["created_at"] = stamp

    def finish(self) -> list[dict[str, Any]]:
        self._finish()
        if not self.rows:
            raise ValueError("public Actions page has no attributable runs")
        ids = [item["id"] for item in self.rows]
        if len(ids) != len(set(ids)):
            raise ValueError("public Actions page repeats a run id")
        return self.rows

    def handle_data(self, data: str) -> None:
        if (self.current is not None and self.current["created_at"] is None
                and data.strip() == "Scheduled"):
            self.current["event"] = "schedule"


def parse_public_actions_page(raw: bytes, content_type: str, repository: str,
                              limit: int) -> dict[str, Any]:
    if content_type.split(";", 1)[0].strip().lower() != "text/html":
        raise HTTPException(502, "public Actions page was not HTML")
    try:
        page = raw.decode("utf-8", "strict")
        parser = _ActionsPage(repository, limit)
        parser.feed(page)
        parser.close()
        rows = parser.finish()
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(502, "public Actions page schema is not recognized") from exc
    summary = _parse_github({"total_count": None, "workflow_runs": rows}, {})
    summary["source_representation"] = "PUBLIC_GITHUB_ACTIONS_HTML"
    summary["coverage"] = "PAGE_FIRST_N"
    return summary
