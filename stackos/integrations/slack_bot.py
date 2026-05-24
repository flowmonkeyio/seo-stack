"""Slack bot auth wrapper for credential tests.

Official docs verified:
- auth.test: https://docs.slack.dev/reference/methods/auth.test/
- Web API bearer auth: https://docs.slack.dev/apis/web-api/
"""

from __future__ import annotations

import json
from typing import Any

from stackos.integrations._base import BaseIntegration, IntegrationCallResult
from stackos.mcp.errors import IntegrationDownError


class SlackBotIntegration(BaseIntegration):
    """Wrapper for Slack Web API credential health checks."""

    kind = "slack-bot"
    vendor = "slack-bot"
    default_qps = 1.0

    def __init__(self, *, api_base_url: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._api_base_url = (api_base_url or "https://slack.com/api").rstrip("/")
        self._bot_token = self._parse_payload(self.payload)

    @staticmethod
    def _parse_payload(payload: bytes) -> str:
        text = payload.decode("utf-8").strip()
        if not text:
            raise IntegrationDownError(
                "Slack credential payload is empty",
                data={"vendor": "slack-bot"},
            )
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            token = text
        else:
            if not isinstance(parsed, dict):
                raise IntegrationDownError(
                    "Slack credential JSON must be an object",
                    data={"vendor": "slack-bot"},
                )
            token = str(parsed.get("bot_token") or parsed.get("access_token") or "")
        if not token:
            raise IntegrationDownError(
                "Slack credential missing bot_token",
                data={"vendor": "slack-bot"},
            )
        return token

    def _method_url(self, method: str) -> str:
        return f"{self._api_base_url}/{method}"

    async def auth_test(self) -> IntegrationCallResult:
        # Slack auth.test: https://docs.slack.dev/reference/methods/auth.test/
        return await self.call(
            op="auth.test",
            method="POST",
            url=self._method_url("auth.test"),
            headers={
                "Authorization": f"Bearer {self._bot_token}",
                "Content-Type": "application/json",
            },
        )

    async def test_credentials(self) -> dict[str, Any]:
        result = await self.auth_test()
        body: dict[str, Any] = result.data if isinstance(result.data, dict) else {}
        ok = bool(body.get("ok"))
        return {
            "ok": ok,
            "vendor": "slack-bot",
            "team_id": body.get("team_id"),
            "team": body.get("team"),
            "user_id": body.get("user_id"),
            "user": body.get("user"),
            "bot_id": body.get("bot_id"),
            "url": body.get("url"),
            "status": "ok" if ok else str(body.get("error") or "failed"),
        }


__all__ = ["SlackBotIntegration"]
