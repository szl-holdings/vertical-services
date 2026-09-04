from __future__ import annotations

import json
import re
import ssl
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from .catalog import CONNECTORS
from .types import ConnectorSpec


class ConnectorError(RuntimeError):
    pass


class ConnectorUnavailable(ConnectorError):
    pass


class ConnectorPolicyError(ConnectorError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


@dataclass(frozen=True, slots=True)
class FetchResult:
    connector_id: str
    url: str
    status: int
    content_type: str
    body: bytes

    def json(self) -> Any:
        if "json" not in self.content_type.lower():
            raise ConnectorError(f"{self.connector_id}: response is not JSON")
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectorError(f"{self.connector_id}: invalid JSON response") from exc


class ConnectorRegistry:
    """Fetch only named, pre-declared official endpoints.

    Callers cannot supply a URL. Redirects are refused, path parameters are
    regular-expression constrained, query keys are allowlisted, and response
    bodies are bounded before they enter any model or kernel.
    """

    def __init__(self, specs: Mapping[str, ConnectorSpec] | None = None) -> None:
        self._specs = dict(specs or CONNECTORS)
        context = ssl.create_default_context()
        self._opener = build_opener(_NoRedirect(), HTTPSHandler(context=context))

    def get(self, connector_id: str) -> ConnectorSpec:
        try:
            return self._specs[connector_id]
        except KeyError as exc:
            raise ConnectorPolicyError(f"unknown connector id: {connector_id}") from exc

    def build_url(
        self,
        connector_id: str,
        *,
        path_params: Mapping[str, str] | None = None,
        query: Mapping[str, str | int | bool] | None = None,
    ) -> str:
        spec = self.get(connector_id)
        if spec.endpoint_template is None:
            raise ConnectorUnavailable(
                f"{connector_id}: endpoint is operator-bound or local-only and is unavailable by default"
            )

        params = {str(key): str(value) for key, value in (path_params or {}).items()}
        expected = set(spec.path_params)
        observed = set(params)
        if expected != observed:
            missing = sorted(expected - observed)
            extra = sorted(observed - expected)
            raise ConnectorPolicyError(
                f"{connector_id}: path parameters mismatch; missing={missing}, extra={extra}"
            )
        for name, pattern in spec.path_params.items():
            value = params[name]
            if not re.fullmatch(pattern, value):
                raise ConnectorPolicyError(f"{connector_id}: invalid path parameter {name!r}")

        try:
            endpoint = spec.endpoint_template.format(**params)
        except (KeyError, ValueError) as exc:
            raise ConnectorPolicyError(f"{connector_id}: invalid endpoint template") from exc

        query_values = query or {}
        unknown_query = sorted(set(query_values) - set(spec.query_params))
        if unknown_query:
            raise ConnectorPolicyError(
                f"{connector_id}: query parameters are not allowed: {unknown_query}"
            )
        normalized_query: dict[str, str] = {}
        for key, raw in query_values.items():
            value = str(raw)
            if len(value) > 512:
                raise ConnectorPolicyError(f"{connector_id}: query value for {key!r} is too long")
            if any(char in value for char in ("\r", "\n", "\x00")):
                raise ConnectorPolicyError(f"{connector_id}: control characters are forbidden")
            normalized_query[key] = value

        parts = urlsplit(endpoint)
        if parts.scheme != "https":
            raise ConnectorPolicyError(f"{connector_id}: HTTPS is required")
        host = (parts.hostname or "").lower().rstrip(".")
        if host not in {item.lower().rstrip(".") for item in spec.allowed_hosts}:
            raise ConnectorPolicyError(f"{connector_id}: host is outside the fixed allowlist")
        if parts.username or parts.password or parts.port not in (None, 443):
            raise ConnectorPolicyError(f"{connector_id}: userinfo and non-standard ports are forbidden")
        if not any(parts.path.startswith(prefix) for prefix in spec.allowed_path_prefixes):
            raise ConnectorPolicyError(f"{connector_id}: path is outside the fixed allowlist")
        if parts.fragment:
            raise ConnectorPolicyError(f"{connector_id}: URL fragments are forbidden")

        encoded = urlencode(normalized_query, doseq=False, safe="[],$:")
        return urlunsplit(("https", host, parts.path, encoded, ""))

    def fetch(
        self,
        connector_id: str,
        *,
        path_params: Mapping[str, str] | None = None,
        query: Mapping[str, str | int | bool] | None = None,
        timeout: float = 10.0,
        extra_headers: Mapping[str, str] | None = None,
    ) -> FetchResult:
        spec = self.get(connector_id)
        url = self.build_url(connector_id, path_params=path_params, query=query)
        if not 0.1 <= timeout <= 30.0:
            raise ConnectorPolicyError("timeout must be between 0.1 and 30 seconds")

        headers = {
            "Accept": ", ".join(spec.media_types),
            "Accept-Encoding": "identity",
            "User-Agent": "SZL-Vertical-Fabric/1.0 (+https://a-11-oy.com)",
        }
        headers.update(spec.required_headers)
        for key, value in (extra_headers or {}).items():
            normalized_key = key.strip()
            if normalized_key.lower() not in {"authorization", "x-api-key"}:
                raise ConnectorPolicyError(
                    f"{connector_id}: only explicit credential headers may be added at runtime"
                )
            if not value or any(char in value for char in ("\r", "\n", "\x00")):
                raise ConnectorPolicyError(f"{connector_id}: invalid credential header")
            headers[normalized_key] = value

        request = Request(url, method="GET", headers=headers)
        try:
            with self._opener.open(request, timeout=timeout) as response:
                status = int(response.status)
                if not 200 <= status < 300:
                    raise ConnectorError(f"{connector_id}: unexpected HTTP status {status}")
                content_type = response.headers.get_content_type().lower()
                permitted = {item.split(";", 1)[0].strip().lower() for item in spec.media_types}
                if content_type not in permitted:
                    raise ConnectorPolicyError(
                        f"{connector_id}: content type {content_type!r} is not permitted"
                    )
                declared = response.headers.get("Content-Length")
                if declared is not None:
                    try:
                        if int(declared) > spec.max_bytes:
                            raise ConnectorPolicyError(
                                f"{connector_id}: declared response exceeds {spec.max_bytes} bytes"
                            )
                    except ValueError:
                        raise ConnectorPolicyError(
                            f"{connector_id}: invalid Content-Length header"
                        ) from None
                body = response.read(spec.max_bytes + 1)
                if len(body) > spec.max_bytes:
                    raise ConnectorPolicyError(
                        f"{connector_id}: response exceeds {spec.max_bytes} bytes"
                    )
                return FetchResult(
                    connector_id=connector_id,
                    url=url,
                    status=status,
                    content_type=content_type,
                    body=body,
                )
        except HTTPError as exc:
            if 300 <= exc.code < 400:
                raise ConnectorPolicyError(f"{connector_id}: redirects are forbidden") from exc
            raise ConnectorError(f"{connector_id}: HTTP {exc.code}") from exc
        except URLError as exc:
            raise ConnectorUnavailable(f"{connector_id}: provider request failed") from exc
