"""Parameter and destination validation for authoritative connectors."""
from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import HTTPException


def _scalar(parameters: Mapping[str, Any], key: str, default: Any = None) -> Any:
    value = parameters.get(key, default)
    if isinstance(value, (list, dict)):
        raise HTTPException(422, f"{key} must be a scalar")
    return value


def _bounded_int(
    parameters: Mapping[str, Any],
    key: str,
    default: int,
    low: int,
    high: int,
) -> int:
    value = _scalar(parameters, key, default)
    try:
        numeric = int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, f"{key} must be an integer") from exc
    if numeric < low or numeric > high:
        raise HTTPException(422, f"{key} must be between {low} and {high}")
    return numeric


def _safe_text(
    parameters: Mapping[str, Any],
    key: str,
    default: str = "",
    max_length: int = 128,
) -> str:
    value = str(_scalar(parameters, key, default)).strip()
    if len(value) > max_length or any(ord(char) < 32 for char in value):
        raise HTTPException(422, f"{key} is invalid")
    return value


def _reject_unknown(parameters: Mapping[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(parameters) - allowed)
    if unknown:
        raise HTTPException(422, f"unsupported connector parameters: {', '.join(unknown)}")


def _redacted_url(url: str, query: Mapping[str, str]) -> str:
    sensitive = {
        "api_key", "apikey", "token", "key", "authorization",
        "x-api-key", "access_token",
    }
    safe_query = {
        key: ("<redacted>" if key.casefold() in sensitive else value)
        for key, value in query.items()
    }
    parts = urlsplit(url)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(safe_query, doseq=False), "")
    )


_ALLOWED_HOSTS = {
    "www.cisa.gov",
    "services.nvd.nist.gov",
    "api.first.org",
    "api.github.com",
    "api.weather.gov",
    "api.tidesandcurrents.noaa.gov",
    "www.fisheries.noaa.gov",
    "sanctionslistservice.ofac.treas.gov",
    "scsanctions.un.org",
    "data.sec.gov",
    "api.fiscaldata.treasury.gov",
    "api.stlouisfed.org",
    "api.census.gov",
    "www.fema.gov",
    "www.fhfa.gov",
    "data.cityofnewyork.us",
    "www.federalregister.gov",
    "www.courtlistener.com",
    "api.congress.gov",
}


def _assert_allowed_destination(url: str) -> None:
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.hostname not in _ALLOWED_HOSTS
        or parts.username
        or parts.password
    ):
        raise HTTPException(500, "connector destination failed the fixed allowlist")


def _assert_allowed_redirect(
    url: str,
    allowed_hosts: tuple[str, ...],
    allowed_path_prefixes: tuple[str, ...],
) -> None:
    parts = urlsplit(url)
    path_allowed = bool(allowed_path_prefixes) and any(
        parts.path.startswith(prefix) for prefix in allowed_path_prefixes
    )
    if (
        parts.scheme != "https"
        or parts.hostname not in set(allowed_hosts)
        or not path_allowed
        or parts.username
        or parts.password
        or parts.fragment
    ):
        raise HTTPException(502, "upstream redirect failed the connector redirect allowlist")
