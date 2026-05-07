"""OpenAI Images integration wrapper (PLAN.md L1050).

Authentication: Bearer ``Authorization: Bearer <api_key>`` — separate
row from the procedure-runner LLM key (PLAN.md L1057-L1063), so the
operator can budget images independently from prose generation.

Operation:

- ``generate(prompt, size, quality, n)`` — DALL-E 3 / gpt-image-1
  generation.

Cost: per OpenAI's published pricing the standard ``1024x1024 hd``
generation runs ~$0.04/image; we estimate the cost upfront and
reconcile against ``response.usage`` if the API surface returns it
(image-1 does; DALL-E 3 does not — we use the estimate).
"""

from __future__ import annotations

from typing import Any, ClassVar

from content_stack.integrations._base import BaseIntegration, IntegrationCallResult


class OpenAIImagesIntegration(BaseIntegration):
    """Wrapper for ``https://api.openai.com/v1/images/generations``."""

    kind = "openai-images"
    vendor = "openai-images"
    default_qps = 10.0

    BASE_URL = "https://api.openai.com/v1"

    # Per-image USD cost (rough, tracks OpenAI pricing as of 2025-Q1).
    _IMAGE_COSTS: ClassVar[dict[tuple[str, str], float]] = {
        ("1024x1024", "standard"): 0.04,
        ("1024x1024", "hd"): 0.08,
        ("1024x1792", "standard"): 0.08,
        ("1024x1792", "hd"): 0.12,
        ("1792x1024", "standard"): 0.08,
        ("1792x1024", "hd"): 0.12,
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._api_key = self.payload.decode("utf-8")

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _estimate_cost_usd(self, op: str, **kwargs: Any) -> float:
        """Estimate cost from ``size`` + ``quality`` keyword args."""
        del op
        body = kwargs.get("json", {}) or {}
        size = body.get("size", "1024x1024")
        quality = body.get("quality", "standard")
        n = int(body.get("n", 1))
        per_image = self._IMAGE_COSTS.get((size, quality), 0.04)
        return per_image * n

    async def generate(
        self,
        *,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        n: int = 1,
        model: str = "dall-e-3",
    ) -> IntegrationCallResult:
        """Generate ``n`` images from ``prompt``.

        Returns the raw OpenAI response; the caller persists the URLs +
        cost via ``run_step_calls`` (which BaseIntegration already does).
        """
        body = {
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": n,
            "model": model,
        }
        return await self.call(
            op="generate",
            method="POST",
            url=f"{self.BASE_URL}/images/generations",
            json_body=body,
            headers=self._auth_headers(),
        )

    async def test_credentials(self) -> dict[str, Any]:
        """Cheap auth probe — list models (free, validates auth)."""
        result = await self.call(
            op="test",
            method="GET",
            url=f"{self.BASE_URL}/models",
            headers=self._auth_headers(),
        )
        models_count = len(result.data.get("data", [])) if isinstance(result.data, dict) else 0
        return {"ok": True, "vendor": "openai-images", "models_count": models_count}


__all__ = ["OpenAIImagesIntegration"]
