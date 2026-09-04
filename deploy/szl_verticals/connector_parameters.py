"""Parameter and destination validation for official connectors."""
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
    safe_query = {
        key: (
            "<redacted>"
            if key.casefold() in {"api_key", "apikey", "token", "key"}
            else value
        )
        for key, value in query.items()
    }
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(safe_query, doseq=False),
            "",
        )
    )


def _assert_allowed_destination(url: str) -> None:
    parts = urlsplit(url)
    allowed_hosts = {
        "www.cisa.gov",
        "services.nvd.nist.gov",
        "api.github.com",
        "www.fisheries.noaa.gov",
        "data.sec.gov",
        "gamma-api.polymarket.com",
        "api.coinbase.com",
        "api.fiscaldata.treasury.gov",
        "data.cityofnewyork.us",
        "www.federalregister.gov",
        "api.congress.gov",
    }
    if (
        parts.scheme != "https"
        or parts.hostname not in allowed_hosts
        or parts.username
        or parts.password
    ):
        raise HTTPException(500, "connector destination failed the fixed allowlist")
