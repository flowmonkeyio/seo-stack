"""Slack Web API HTTP transport."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from stackos.actions.connectors import ActionConnectorRequest
from stackos.actions.provider_utils import credential_config, credential_value
from stackos.artifacts import redact_secret_text
from stackos.repositories.base import ValidationError

from .constants import _BASE_URL, _SLACK_TOKEN_RE


async def _slack_api(
    request: ActionConnectorRequest,
    method: str,
    api_method: str,
    *,
    json_body: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
) -> tuple[int, Any, httpx.Headers]:
    url = f"{_api_base_url(request)}/{api_method}"
    token = credential_value(request, "bot_token", "access_token", "token")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as http:
        response = await http.request(
            method,
            url,
            headers=headers,
            json=dict(json_body or {}) if json_body is not None else None,
            params=dict(params or {}),
        )
    if response.status_code >= 400:
        raise ValidationError(
            _redact_slack_text(
                f"Slack {api_method} returned status {response.status_code}: {response.text[:500]}"
            )
        )
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text
    if isinstance(body, Mapping) and body.get("ok") is False:
        error = _redact_slack_text(str(body.get("error") or "unknown_error"))
        raise ValidationError(f"Slack {api_method} returned error {error}")
    return response.status_code, body, response.headers


def _api_base_url(request: ActionConnectorRequest) -> str:
    config = credential_config(request)
    return str(config.get("api_base_url") or _BASE_URL).rstrip("/")


def _redact_slack_text(value: str) -> str:
    return _SLACK_TOKEN_RE.sub("[redacted]", redact_secret_text(value))
