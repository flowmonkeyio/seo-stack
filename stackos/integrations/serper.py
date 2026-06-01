"""Serper.dev integration wrapper.

Serper's public site documents the provider as a Google SERP API; its
dashboard/playground contract uses the Google endpoint family under
``https://google.serper.dev``.
"""

from __future__ import annotations

from typing import Any

from stackos.integrations._base import BaseIntegration, IntegrationCallResult


class SerperIntegration(BaseIntegration):
    """Wrapper for Serper.dev Google Search API calls."""

    kind = "serper"
    vendor = "serper"
    default_qps = 10.0

    # Official product/docs entrypoint: https://serper.dev/
    # Endpoint contract used by Serper examples and dashboard playgrounds.
    BASE_URL = "https://google.serper.dev"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._api_key = self.payload.decode("utf-8").strip()

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-API-KEY": self._api_key,
        }

    async def search(
        self,
        *,
        query: str,
        num: int = 10,
        country: str | None = None,
        language: str | None = None,
        page: int | None = None,
        tbs: str | None = None,
    ) -> IntegrationCallResult:
        """Return structured Google Search result evidence for ``query``."""
        body: dict[str, Any] = {"q": query, "num": num}
        if country:
            body["gl"] = country
        if language:
            body["hl"] = language
        if page is not None:
            body["page"] = page
        if tbs:
            body["tbs"] = tbs
        return await self.call(
            op="search",
            method="POST",
            url=f"{self.BASE_URL}/search",
            json_body=body,
            headers=self._headers(),
        )

    async def test_credentials(self) -> dict[str, Any]:
        """Credential probe.

        Serper does not expose a separate public account probe, so the auth
        test performs a minimal search and records returned credit metadata if
        the provider includes it.
        """
        result = await self.search(query="stackos", num=1)
        data = result.data if isinstance(result.data, dict) else {}
        return {
            "ok": True,
            "vendor": "serper",
            "credits": data.get("credits"),
            "result_count": (
                len(data.get("organic", [])) if isinstance(data.get("organic"), list) else 0
            ),
        }


__all__ = ["SerperIntegration"]
