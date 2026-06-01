"""OpenRouter integration wrapper for setup validation.

StackOS does not expose a generic prose-generation action here. The wrapper is
registered so operators can store and test an OpenRouter connection through the
normal auth boundary while future workflow-owned model actions can be designed
explicitly.
"""

from __future__ import annotations

from typing import Any

from stackos.integrations._base import BaseIntegration, IntegrationCallResult


class OpenRouterIntegration(BaseIntegration):
    """Read-only OpenRouter setup probe wrapper."""

    kind = "openrouter"
    vendor = "openrouter"
    default_qps = 2.0

    # Official refs:
    # - https://openrouter.ai/docs/api/reference/authentication
    # - https://openrouter.ai/docs/api/api-reference/models/get-models
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        *,
        http_referer: str | None = None,
        app_title: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._api_key = self.payload.decode("utf-8").strip()
        self._http_referer = http_referer
        self._app_title = app_title

    def _headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if self._http_referer:
            headers["HTTP-Referer"] = self._http_referer
        if self._app_title:
            headers["X-OpenRouter-Title"] = self._app_title
        return headers

    async def models(self) -> IntegrationCallResult:
        """List OpenRouter model metadata without running a model."""
        return await self.call(
            op="models",
            method="GET",
            url=f"{self.BASE_URL}/models",
            headers=self._headers(),
        )

    async def test_credentials(self) -> dict[str, Any]:
        """Credential probe via the documented models endpoint."""
        result = await self.models()
        data = result.data if isinstance(result.data, dict) else {}
        models = data.get("data")
        return {
            "ok": True,
            "vendor": "openrouter",
            "models_count": len(models) if isinstance(models, list) else None,
        }


__all__ = ["OpenRouterIntegration"]
