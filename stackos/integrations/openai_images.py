"""OpenAI Images integration wrapper (PLAN.md L1050).

Authentication: Bearer ``Authorization: Bearer <api_key>``. This is a
daemon-side vendor key for image generation only; prose generation uses
the current operator agent's runtime credentials outside StackOS.

Operations:

- ``generate(prompt, size, quality, n)`` — GPT Image generation.
- ``edit(prompt, input_image_paths, ...)`` — GPT Image edits with input
  reference images, used for product-faithful marketing shots. Input
  images are uploaded as multipart ``image`` files on ``/images/edits``.
  The JSON edit shape uses ``images`` only for public URL or file-id
  references, not daemon-local generated-asset files.

The current OpenAI Image API returns base64 for GPT Image models. This
wrapper persists those bytes into the daemon's generated-assets directory
and returns local artifact URLs.

Cost: the table below is a rough budget guardrail derived from the
published GPT Image pricing table. The operator should reconcile actual
invoices against OpenAI's current pricing page.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from pathlib import Path
from typing import Any, ClassVar

from stackos.integrations._base import BaseIntegration, IntegrationCallResult
from stackos.mcp.errors import IntegrationDownError


class OpenAIImagesIntegration(BaseIntegration):
    """Wrapper for ``https://api.openai.com/v1/images/generations``."""

    kind = "openai-images"
    vendor = "openai-images"
    default_qps = 10.0

    BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-image-2"

    # Official refs:
    # https://developers.openai.com/api/docs/guides/image-generation
    # https://developers.openai.com/api/reference/resources/images
    #
    # Values are output image-cost guardrails for the StackOS budget pre-check.
    # Text/image input tokens and invoices remain OpenAI's source of truth.
    _IMAGE_COSTS: ClassVar[dict[tuple[str, str, str], float]] = {
        ("gpt-image-2", "1024x1024", "low"): 0.006,
        ("gpt-image-2", "1024x1024", "medium"): 0.053,
        ("gpt-image-2", "1024x1024", "high"): 0.211,
        ("gpt-image-2", "1536x1024", "low"): 0.005,
        ("gpt-image-2", "1536x1024", "medium"): 0.041,
        ("gpt-image-2", "1536x1024", "high"): 0.165,
        ("gpt-image-2", "1024x1536", "low"): 0.005,
        ("gpt-image-2", "1024x1536", "medium"): 0.041,
        ("gpt-image-2", "1024x1536", "high"): 0.165,
        ("gpt-image-1.5", "1024x1024", "low"): 0.009,
        ("gpt-image-1.5", "1024x1024", "medium"): 0.034,
        ("gpt-image-1.5", "1024x1024", "high"): 0.133,
        ("gpt-image-1.5", "1536x1024", "low"): 0.013,
        ("gpt-image-1.5", "1536x1024", "medium"): 0.050,
        ("gpt-image-1.5", "1536x1024", "high"): 0.200,
        ("gpt-image-1.5", "1024x1536", "low"): 0.013,
        ("gpt-image-1.5", "1024x1536", "medium"): 0.050,
        ("gpt-image-1.5", "1024x1536", "high"): 0.200,
        ("gpt-image-1", "1024x1024", "low"): 0.011,
        ("gpt-image-1", "1024x1024", "medium"): 0.042,
        ("gpt-image-1", "1024x1024", "high"): 0.167,
        ("gpt-image-1", "1536x1024", "low"): 0.016,
        ("gpt-image-1", "1536x1024", "medium"): 0.063,
        ("gpt-image-1", "1536x1024", "high"): 0.250,
        ("gpt-image-1", "1024x1536", "low"): 0.016,
        ("gpt-image-1", "1024x1536", "medium"): 0.063,
        ("gpt-image-1", "1024x1536", "high"): 0.250,
        ("gpt-image-1-mini", "1024x1024", "low"): 0.005,
        ("gpt-image-1-mini", "1024x1024", "medium"): 0.011,
        ("gpt-image-1-mini", "1024x1024", "high"): 0.036,
        ("gpt-image-1-mini", "1536x1024", "low"): 0.006,
        ("gpt-image-1-mini", "1536x1024", "medium"): 0.015,
        ("gpt-image-1-mini", "1536x1024", "high"): 0.052,
        ("gpt-image-1-mini", "1024x1536", "low"): 0.006,
        ("gpt-image-1-mini", "1024x1536", "medium"): 0.015,
        ("gpt-image-1-mini", "1024x1536", "high"): 0.052,
    }
    _GPT_IMAGE_MODELS: ClassVar[frozenset[str]] = frozenset(
        {"gpt-image-2", "gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"}
    )
    _DALL_E_MODELS: ClassVar[frozenset[str]] = frozenset({"dall-e-2", "dall-e-3"})
    # gpt-image-2 always processes input images at high fidelity; the API
    # rejects an explicit input_fidelity parameter for it.
    _INPUT_FIDELITY_MODELS: ClassVar[frozenset[str]] = frozenset({"gpt-image-1.5", "gpt-image-1"})
    MAX_EDIT_INPUT_IMAGES: ClassVar[int] = 16
    _OUTPUT_EXTENSIONS: ClassVar[dict[str, str]] = {
        "jpeg": "jpg",
        "png": "png",
        "webp": "webp",
    }
    _INPUT_IMAGE_MIME: ClassVar[dict[str, str]] = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }

    def __init__(
        self,
        *,
        asset_dir: Path | None = None,
        asset_url_prefix: str = "/generated-assets",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._api_key = self.payload.decode("utf-8")
        self._asset_dir = asset_dir
        self._asset_url_prefix = asset_url_prefix.rstrip("/")

    def _auth_headers(self, *, content_type: str | None = "application/json") -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if content_type is not None:
            headers["Content-Type"] = content_type
        return headers

    def _estimate_cost_usd(self, op: str, **kwargs: Any) -> float:
        """Estimate cost from ``size`` + ``quality`` keyword args."""
        del op
        body = kwargs.get("json", {}) or {}
        model = str(body.get("model", self.DEFAULT_MODEL))
        size = body.get("size", "1024x1024")
        quality = body.get("quality", "medium")
        n = int(body.get("n", 1))
        return self.estimate_image_cost_usd(model=model, size=str(size), quality=str(quality), n=n)

    @classmethod
    def estimate_image_cost_usd(cls, *, model: str, size: str, quality: str, n: int = 1) -> float:
        """Estimate output-image cost for the current StackOS-supported sizes."""
        if model not in cls._GPT_IMAGE_MODELS:
            return 0.04 * n
        normalized_size = size if size != "auto" else "1024x1024"
        normalized_quality = quality if quality != "auto" else "high"
        per_image = cls._IMAGE_COSTS.get((model, normalized_size, normalized_quality))
        if per_image is None:
            model_costs = [
                cost
                for (cost_model, _size, cost_quality), cost in cls._IMAGE_COSTS.items()
                if cost_model == model and cost_quality == normalized_quality
            ]
            per_image = max(model_costs) if model_costs else 0.04
        return per_image * n

    async def generate(
        self,
        *,
        prompt: str,
        size: str = "1536x1024",
        quality: str = "medium",
        n: int = 1,
        model: str = DEFAULT_MODEL,
        output_format: str = "webp",
    ) -> IntegrationCallResult:
        """Generate ``n`` images from ``prompt``.

        GPT Image models return base64 image bytes. When ``asset_dir`` is
        configured, the wrapper writes those bytes to disk and returns a
        response with local ``url`` fields and no ``b64_json`` payloads.
        """
        body = {
            "prompt": prompt,
            "n": n,
            "model": model,
        }
        # DALL-E keeps legacy size/quality names while GPT Image models use
        # low/medium/high quality and output_format.
        if model in self._DALL_E_MODELS:
            body["size"] = _dalle_size(size)
            body["quality"] = _dalle_quality(quality)
            body["response_format"] = "url"
        else:
            body["size"] = size
            body["quality"] = quality
            body["output_format"] = output_format
        result = await self.call(
            op="generate",
            method="POST",
            url=f"{self.BASE_URL}/images/generations",
            json_body=body,
            headers=self._auth_headers(),
        )
        return IntegrationCallResult(
            data=self._persist_base64_images(
                result.data,
                output_format=output_format,
                model=model,
            ),
            cost_usd=result.cost_usd,
            duration_ms=result.duration_ms,
            cached=result.cached,
        )

    async def edit(
        self,
        *,
        prompt: str,
        input_image_paths: list[Path],
        size: str = "auto",
        quality: str = "medium",
        n: int = 1,
        model: str = DEFAULT_MODEL,
        output_format: str = "webp",
        input_fidelity: str | None = None,
    ) -> IntegrationCallResult:
        """Edit/compose images from ``prompt`` plus input reference images.

        GPT Image edits keep the referenced subject (product, logo, label)
        faithful while changing scene, style, or composition. Input images
        are submitted as multipart file uploads. ``input_fidelity`` is
        forwarded only for models that accept it; gpt-image-2 always runs
        at high input fidelity.
        """
        if not input_image_paths:
            raise IntegrationDownError(
                "OpenAI Images edit requires at least one input image",
                data={"vendor": "openai-images", "model": model},
            )
        if len(input_image_paths) > self.MAX_EDIT_INPUT_IMAGES:
            raise IntegrationDownError(
                f"OpenAI Images edit accepts at most {self.MAX_EDIT_INPUT_IMAGES} input images",
                data={"vendor": "openai-images", "model": model},
            )
        form_body: dict[str, Any] = {
            "prompt": prompt,
            "n": str(n),
            "model": model,
            "size": size,
            "quality": quality,
            "output_format": output_format,
        }
        if input_fidelity is not None and model in self._INPUT_FIDELITY_MODELS:
            form_body["input_fidelity"] = input_fidelity

        files: list[tuple[str, tuple[str, bytes, str]]] = []
        image_log: list[dict[str, Any]] = []
        for path in input_image_paths:
            filename, raw, mime = self._read_input_image(path)
            files.append(("image", (filename, raw, mime)))
            image_log.append({"filename": filename, "mime_type": mime, "bytes": len(raw)})
        request_log = dict(form_body)
        request_log["image_files"] = image_log
        result = await self.call(
            op="edit",
            method="POST",
            url=f"{self.BASE_URL}/images/edits",
            data_body=form_body,
            files=files,
            headers=self._auth_headers(content_type=None),
            request_log_body=request_log,
        )
        return IntegrationCallResult(
            data=self._persist_base64_images(
                result.data,
                output_format=output_format,
                model=model,
            ),
            cost_usd=result.cost_usd,
            duration_ms=result.duration_ms,
            cached=result.cached,
        )

    def _read_input_image(self, path: Path) -> tuple[str, bytes, str]:
        """Read one local input image for multipart upload."""
        mime = self._INPUT_IMAGE_MIME.get(path.suffix.lower())
        if mime is None:
            raise IntegrationDownError(
                "OpenAI Images edit input images must be png, jpg, or webp",
                data={"vendor": "openai-images", "file": path.name},
            )
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise IntegrationDownError(
                "OpenAI Images edit input image could not be read",
                data={"vendor": "openai-images", "file": path.name},
            ) from exc
        return path.name, raw, mime

    def _persist_base64_images(
        self,
        data: Any,
        *,
        output_format: str,
        model: str,
    ) -> Any:
        """Replace OpenAI ``b64_json`` entries with daemon-local URLs."""
        if self._asset_dir is None or not isinstance(data, dict):
            return data
        items = data.get("data")
        if not isinstance(items, list):
            return data

        out = dict(data)
        persisted: list[Any] = []
        for item in items:
            if not isinstance(item, dict):
                persisted.append(item)
                continue
            b64 = item.get("b64_json")
            if not isinstance(b64, str):
                persisted.append(item)
                continue
            try:
                raw = base64.b64decode(b64, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise IntegrationDownError(
                    "OpenAI Images returned invalid base64 image data",
                    data={"vendor": "openai-images", "model": model},
                ) from exc
            ext = self._OUTPUT_EXTENSIONS.get(output_format, "webp")
            digest = hashlib.sha256(raw).hexdigest()
            filename = f"openai-{digest[:32]}.{ext}"
            subdir = self._asset_dir / "openai-images"
            subdir.mkdir(parents=True, exist_ok=True)
            path = subdir / filename
            if not path.exists():
                path.write_bytes(raw)
            clean = {k: v for k, v in item.items() if k != "b64_json"}
            clean["url"] = f"{self._asset_url_prefix}/openai-images/{filename}"
            clean["file_format"] = ext
            clean["source_model"] = model
            persisted.append(clean)
        out["data"] = persisted
        return out

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


def _dalle_quality(quality: str) -> str:
    if quality in {"standard", "hd"}:
        return quality
    return "hd" if quality == "high" else "standard"


def _dalle_size(size: str) -> str:
    if size == "1536x1024":
        return "1792x1024"
    if size == "1024x1536":
        return "1024x1792"
    return size
