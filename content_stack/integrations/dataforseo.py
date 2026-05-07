"""DataForSEO integration wrapper (PLAN.md L1046).

Authentication: HTTP Basic with the ``login + password`` pair stored in
the ``dataforseo`` credential row's ``config_json`` (login) +
``encrypted_payload`` (password as bytes).

Operations:

- ``serp(keyword, location, language, depth)`` — SERP results for a
  query.
- ``keyword_volume(keywords, location, language)`` — search volume +
  CPC.
- ``intersection(domains, location, language)`` — competitor keyword
  intersection.
- ``keywords_for_site(target, location, language)`` — keyword
  inventory for a domain.
- ``paa(keyword, location, language)`` — People-Also-Ask boxes.

DataForSEO's response body reports the actual task cost in
``tasks[0].cost`` (USD); we override ``_extract_actual_cost_usd`` so
the budget reconciliation uses the vendor's number rather than our
estimate.
"""

from __future__ import annotations

from typing import Any, ClassVar

import httpx

from content_stack.integrations._base import BaseIntegration, IntegrationCallResult


class DataForSeoIntegration(BaseIntegration):
    """Wrapper for ``https://api.dataforseo.com/v3``."""

    kind = "dataforseo"
    vendor = "dataforseo"
    default_qps = 5.0

    BASE_URL = "https://api.dataforseo.com/v3"

    # Rough per-op cost in USD used for pre-emption when the vendor
    # response is unavailable (e.g. on retry exhaustion). DataForSEO
    # actually returns ``tasks[i].cost`` so the post-call reconciliation
    # corrects to the real number; the estimates below are
    # conservative-low so callers don't get spurious budget breaches on
    # cheap calls.
    _PRE_EMPT_COSTS: ClassVar[dict[str, float]] = {
        "serp": 0.001,
        "keyword_volume": 0.0001,
        "intersection": 0.001,
        "keywords_for_site": 0.001,
        "paa": 0.001,
    }

    def __init__(self, *, login: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # ``login`` from config_json + the encrypted payload as the
        # password. The raw plaintext bytes never leave the wrapper.
        self._login = login
        self._password = self.payload.decode("utf-8")

    # ------------------------------------------------------------------
    # Cost hooks.
    # ------------------------------------------------------------------

    def _estimate_cost_usd(self, op: str, **kwargs: Any) -> float:
        del kwargs
        return self._PRE_EMPT_COSTS.get(op, 0.001)

    def _extract_actual_cost_usd(
        self,
        op: str,
        *,
        request: dict[str, Any] | None,
        response: Any,
        estimated: float,
    ) -> float:
        """Pull ``tasks[i].cost`` from the response body."""
        del op, request
        if not isinstance(response, dict):
            return estimated
        # DataForSEO wraps tasks in a top-level ``tasks`` array.
        try:
            tasks = response.get("tasks", [])
            return float(sum(t.get("cost", 0.0) for t in tasks))
        except (AttributeError, TypeError, ValueError):
            return estimated

    # ------------------------------------------------------------------
    # Public ops.
    # ------------------------------------------------------------------

    async def serp(
        self,
        *,
        keyword: str,
        location: str = "United States",
        language: str = "en",
        depth: int = 100,
    ) -> IntegrationCallResult:
        """SERP organic results for ``keyword``.

        Returns the raw DataForSEO ``tasks_post`` response body.
        """
        payload = [
            {
                "keyword": keyword,
                "location_name": location,
                "language_code": language,
                "depth": depth,
            }
        ]
        return await self.call(
            op="serp",
            method="POST",
            url=f"{self.BASE_URL}/serp/google/organic/live/advanced",
            json_body={"data": payload},
            auth=httpx.BasicAuth(self._login, self._password),
        )

    async def keyword_volume(
        self,
        *,
        keywords: list[str],
        location: str = "United States",
        language: str = "en",
    ) -> IntegrationCallResult:
        """Monthly search volume + CPC for a keyword list."""
        payload = [
            {
                "keywords": keywords,
                "location_name": location,
                "language_code": language,
            }
        ]
        return await self.call(
            op="keyword_volume",
            method="POST",
            url=f"{self.BASE_URL}/keywords_data/google_ads/search_volume/live",
            json_body={"data": payload},
            auth=httpx.BasicAuth(self._login, self._password),
        )

    async def intersection(
        self,
        *,
        domains: list[str],
        location: str = "United States",
        language: str = "en",
    ) -> IntegrationCallResult:
        """Keyword intersection across competitor domains."""
        payload = [
            {
                "targets": domains,
                "location_name": location,
                "language_code": language,
            }
        ]
        return await self.call(
            op="intersection",
            method="POST",
            url=f"{self.BASE_URL}/dataforseo_labs/google/domain_intersection/live",
            json_body={"data": payload},
            auth=httpx.BasicAuth(self._login, self._password),
        )

    async def keywords_for_site(
        self,
        *,
        target: str,
        location: str = "United States",
        language: str = "en",
    ) -> IntegrationCallResult:
        """All keywords ranking for ``target`` domain."""
        payload = [
            {
                "target": target,
                "location_name": location,
                "language_code": language,
            }
        ]
        return await self.call(
            op="keywords_for_site",
            method="POST",
            url=f"{self.BASE_URL}/dataforseo_labs/google/keywords_for_site/live",
            json_body={"data": payload},
            auth=httpx.BasicAuth(self._login, self._password),
        )

    async def paa(
        self,
        *,
        keyword: str,
        location: str = "United States",
        language: str = "en",
    ) -> IntegrationCallResult:
        """People-Also-Ask boxes for ``keyword``."""
        payload = [
            {
                "keyword": keyword,
                "location_name": location,
                "language_code": language,
            }
        ]
        return await self.call(
            op="paa",
            method="POST",
            url=f"{self.BASE_URL}/serp/google/people_also_ask/live/advanced",
            json_body={"data": payload},
            auth=httpx.BasicAuth(self._login, self._password),
        )

    # ------------------------------------------------------------------
    # Health check.
    # ------------------------------------------------------------------

    async def test_credentials(self) -> dict[str, Any]:
        """Cheap auth probe — hits the user-info endpoint.

        Returns ``{"ok": True, "vendor": "dataforseo"}`` on success;
        raises the typed integration error on failure (the dispatcher
        formats it).
        """
        result = await self.call(
            op="test",
            method="GET",
            url=f"{self.BASE_URL}/appendix/user_data",
            auth=httpx.BasicAuth(self._login, self._password),
        )
        return {"ok": True, "vendor": "dataforseo", "data": result.data}


__all__ = ["DataForSeoIntegration"]
