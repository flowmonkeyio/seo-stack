"""Google Gemini image generation integration wrapper.

Official docs:

- https://ai.google.dev/gemini-api/docs/image-generation
- https://ai.google.dev/gemini-api/docs/image-understanding
- https://ai.google.dev/api/generate-content
- https://ai.google.dev/gemini-api/docs/pricing

Gemini image generation returns generated images as inline base64 parts from
``models.generateContent``. The wrapper persists image bytes immediately and
returns generated-assets URLs instead of raw image data.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from pathlib import Path
from typing import Any, ClassVar

import httpx

from stackos.integrations._base import BaseIntegration, IntegrationCallResult
from stackos.mcp.errors import IntegrationDownError


class GoogleGeminiImageIntegration(BaseIntegration):
    """Wrapper for Gemini Developer API image models."""

    kind = "google-gemini-image"
    vendor = "google-gemini-image"
    default_qps = 2.0

    BASE_URL = "https://generativelanguage.googleapis.com/v1"
    DEFAULT_MODEL = "gemini-3.1-flash-image"
    MODELS: ClassVar[frozenset[str]] = frozenset(
        {
            "gemini-3.1-flash-image",
            "gemini-3-pro-image",
            "gemini-2.5-flash-image",
        }
    )
    GEMINI_3_MODELS: ClassVar[frozenset[str]] = frozenset(
        {"gemini-3.1-flash-image", "gemini-3-pro-image"}
    )
    ASPECT_RATIOS_3_1_FLASH: ClassVar[frozenset[str]] = frozenset(
        {
            "1:1",
            "1:4",
            "1:8",
            "2:3",
            "3:2",
            "3:4",
            "4:1",
            "4:3",
            "4:5",
            "5:4",
            "8:1",
            "9:16",
            "16:9",
            "21:9",
        }
    )
    ASPECT_RATIOS_PRO_AND_25: ClassVar[frozenset[str]] = frozenset(
        {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}
    )
    IMAGE_SIZES_3_1_FLASH: ClassVar[frozenset[str]] = frozenset({"512", "1K", "2K", "4K"})
    IMAGE_SIZES_3_PRO: ClassVar[frozenset[str]] = frozenset({"1K", "2K", "4K"})
    INPUT_IMAGE_FORMATS: ClassVar[frozenset[str]] = frozenset({"jpg", "jpeg", "png", "webp"})
    MAX_INLINE_REQUEST_BYTES = 20_000_000
    INLINE_REQUEST_ENVELOPE_MARGIN_BYTES = 8_192

    _OUTPUT_EXTENSIONS: ClassVar[dict[str, str]] = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    _OUTPUT_COSTS_USD: ClassVar[dict[str, dict[str, float]]] = {
        "gemini-3.1-flash-image": {
            "512": 0.045,
            "1K": 0.067,
            "2K": 0.101,
            "4K": 0.151,
        },
        "gemini-3-pro-image": {
            "1K": 0.134,
            "2K": 0.134,
            "4K": 0.24,
        },
        "gemini-2.5-flash-image": {
            "": 0.039,
        },
    }
    _INPUT_IMAGE_COSTS_USD: ClassVar[dict[str, float]] = {
        "gemini-3-pro-image": 0.0011,
    }

    def __init__(
        self,
        *,
        payload: bytes,
        project_id: int,
        http: httpx.AsyncClient,
        asset_dir: Path | None = None,
        asset_url_prefix: str = "/generated-assets",
        **kwargs: Any,
    ) -> None:
        super().__init__(payload=payload, project_id=project_id, http=http, **kwargs)
        self._asset_dir = asset_dir
        self._asset_url_prefix = asset_url_prefix.rstrip("/")
        self._pending_cost_context: dict[str, Any] | None = None

    def _auth_headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": self.payload.decode("utf-8"),
            "Content-Type": "application/json",
        }

    def _estimate_cost_usd(self, op: str, **kwargs: Any) -> float:
        del op, kwargs
        context = getattr(self, "_pending_cost_context", None)
        if not isinstance(context, dict):
            return 0.0
        model = str(context.get("model") or self.DEFAULT_MODEL)
        image_size = str(context.get("image_size") or "")
        input_images = context.get("input_images")
        return self.estimate_image_cost_usd(
            model=model,
            image_size=image_size,
            input_images=input_images if isinstance(input_images, int) else 0,
        )

    @classmethod
    def aspect_ratios_for_model(cls, model: str) -> frozenset[str]:
        if model == "gemini-3.1-flash-image":
            return cls.ASPECT_RATIOS_3_1_FLASH
        return cls.ASPECT_RATIOS_PRO_AND_25

    @classmethod
    def max_input_images_for_model(cls, model: str) -> int:
        if model == "gemini-2.5-flash-image":
            return 3
        return 14

    @classmethod
    def image_sizes_for_model(cls, model: str) -> frozenset[str]:
        if model == "gemini-3.1-flash-image":
            return cls.IMAGE_SIZES_3_1_FLASH
        if model == "gemini-3-pro-image":
            return cls.IMAGE_SIZES_3_PRO
        return frozenset()

    @classmethod
    def estimate_image_cost_usd(
        cls,
        *,
        model: str = DEFAULT_MODEL,
        image_size: str = "1K",
        input_images: int = 0,
    ) -> float:
        output_costs = cls._OUTPUT_COSTS_USD.get(model, cls._OUTPUT_COSTS_USD[cls.DEFAULT_MODEL])
        output_cost = (
            output_costs.get(image_size) or output_costs.get("1K") or output_costs.get("", 0)
        )
        input_cost = max(0, input_images) * cls._INPUT_IMAGE_COSTS_USD.get(model, 0.0)
        return output_cost + input_cost

    async def generate_image(
        self,
        *,
        prompt: str,
        model: str = DEFAULT_MODEL,
        aspect_ratio: str | None = "1:1",
        image_size: str | None = None,
    ) -> IntegrationCallResult:
        return await self._generate_content(
            prompt=prompt,
            model=model,
            input_image_paths=[],
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )

    async def edit_image(
        self,
        *,
        prompt: str,
        input_image_paths: list[Path],
        model: str = DEFAULT_MODEL,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
    ) -> IntegrationCallResult:
        if not input_image_paths:
            raise IntegrationDownError(
                "Google Gemini image edit requires at least one input image",
                data={"vendor": self.vendor},
            )
        return await self._generate_content(
            prompt=prompt,
            model=model,
            input_image_paths=input_image_paths,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )

    async def _generate_content(
        self,
        *,
        prompt: str,
        model: str,
        input_image_paths: list[Path],
        aspect_ratio: str | None,
        image_size: str | None,
    ) -> IntegrationCallResult:
        image_parts = self._image_parts(prompt=prompt, paths=input_image_paths)
        parts: list[dict[str, Any]] = [{"text": prompt}, *image_parts]
        generation_config = self._generation_config(
            model=model,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation_config,
        }
        self._pending_cost_context = {
            "model": model,
            "image_size": image_size,
            "input_images": len(input_image_paths),
        }
        result = await self.call(
            op="image.edit" if input_image_paths else "image.generate",
            method="POST",
            url=f"{self.BASE_URL}/models/{model}:generateContent",
            json_body=body,
            headers=self._auth_headers(),
            request_log_body={
                "model": model,
                "prompt": prompt,
                "input_image_count": len(input_image_paths),
                "input_image_names": [path.name for path in input_image_paths],
                "generationConfig": generation_config,
            },
        )
        data = self._persist_response_images(result.data, model=model)
        return IntegrationCallResult(
            data=data,
            cost_usd=result.cost_usd,
            duration_ms=result.duration_ms,
        )

    @classmethod
    def _generation_config(
        cls,
        *,
        model: str,
        aspect_ratio: str | None,
        image_size: str | None,
    ) -> dict[str, Any]:
        config: dict[str, Any] = {"responseModalities": ["Image"]}
        image_config: dict[str, str] = {}
        if aspect_ratio is not None:
            image_config["aspectRatio"] = aspect_ratio
        if model in cls.GEMINI_3_MODELS and image_size is not None:
            image_config["imageSize"] = image_size
        if image_config:
            config["responseFormat"] = {"image": image_config}
        return config

    def _image_parts(self, *, prompt: str, paths: list[Path]) -> list[dict[str, Any]]:
        if not paths:
            return []
        images = self.ensure_inline_image_preflight(prompt=prompt, paths=paths)
        return [
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64.b64encode(raw).decode("ascii"),
                }
            }
            for raw, mime_type in images
        ]

    @classmethod
    def ensure_inline_image_preflight(
        cls,
        *,
        prompt: str,
        paths: list[Path],
    ) -> list[tuple[bytes, str]]:
        total_request_bytes = len(prompt.encode("utf-8")) + cls.INLINE_REQUEST_ENVELOPE_MARGIN_BYTES
        images: list[tuple[bytes, str]] = []
        for path in paths:
            suffix = path.suffix.lower().lstrip(".")
            if suffix not in cls.INPUT_IMAGE_FORMATS:
                raise IntegrationDownError(
                    "Google Gemini inline image inputs must be JPEG, PNG, or WEBP",
                    data={"vendor": cls.vendor, "file": path.name},
                )
            try:
                raw = path.read_bytes()
            except OSError as exc:
                raise IntegrationDownError(
                    "Google Gemini input image could not be read",
                    data={"vendor": cls.vendor, "file": path.name},
                ) from exc
            total_request_bytes += _base64_encoded_length(len(raw))
            if total_request_bytes >= cls.MAX_INLINE_REQUEST_BYTES:
                raise IntegrationDownError(
                    "Google Gemini inline image requests must stay under 20 MB",
                    data={
                        "vendor": cls.vendor,
                        "bytes": total_request_bytes,
                        "max_bytes": cls.MAX_INLINE_REQUEST_BYTES,
                    },
                )
            images.append((raw, _mime_type_for_suffix(suffix)))
        return images

    def _persist_response_images(self, data: Any, *, model: str) -> Any:
        if self._asset_dir is None or not isinstance(data, dict):
            return data
        persisted: list[dict[str, Any]] = []
        text_parts: list[str] = []
        candidates = data.get("candidates")
        if isinstance(candidates, list):
            for candidate_index, candidate in enumerate(candidates):
                if not isinstance(candidate, dict):
                    continue
                content = candidate.get("content")
                if not isinstance(content, dict):
                    continue
                parts = content.get("parts")
                if not isinstance(parts, list):
                    continue
                for part_index, part in enumerate(parts):
                    if not isinstance(part, dict):
                        continue
                    if isinstance(part.get("text"), str):
                        text_parts.append(part["text"])
                    inline_data = part.get("inlineData") or part.get("inline_data")
                    if isinstance(inline_data, dict):
                        persisted.append(
                            self._persist_inline_image(
                                inline_data,
                                model=model,
                                candidate_index=candidate_index,
                                part_index=part_index,
                            )
                        )
        clean = {
            key: value for key, value in data.items() if key not in {"candidates", "usageMetadata"}
        }
        clean["data"] = persisted
        if text_parts:
            clean["text"] = text_parts
        if isinstance(data.get("usageMetadata"), dict):
            clean["usage"] = _safe_usage_metadata(data["usageMetadata"])
        return clean

    def _persist_inline_image(
        self,
        inline_data: dict[str, Any],
        *,
        model: str,
        candidate_index: int,
        part_index: int,
    ) -> dict[str, Any]:
        raw_b64 = inline_data.get("data")
        if not isinstance(raw_b64, str) or not raw_b64:
            raise IntegrationDownError(
                "Google Gemini returned an image part without base64 data",
                data={"vendor": self.vendor},
            )
        try:
            raw = base64.b64decode(raw_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise IntegrationDownError(
                "Google Gemini returned invalid base64 image data",
                data={"vendor": self.vendor},
            ) from exc
        raw_mime_type = inline_data.get("mimeType") or inline_data.get("mime_type")
        mime_type = raw_mime_type if isinstance(raw_mime_type, str) else "image/png"
        return {
            **self._write_image(raw, mime_type=mime_type),
            "source_model": model,
            "candidate_index": candidate_index,
            "part_index": part_index,
        }

    def _write_image(self, raw: bytes, *, mime_type: str) -> dict[str, str]:
        digest = hashlib.sha256(raw).hexdigest()
        file_format = self._OUTPUT_EXTENSIONS.get(mime_type.lower(), "png")
        filename = f"google-gemini-image-{digest[:32]}.{file_format}"
        assert self._asset_dir is not None
        target_dir = self._asset_dir / "google-gemini-image"
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / filename
        if not path.exists():
            path.write_bytes(raw)
        return {
            "url": f"{self._asset_url_prefix}/google-gemini-image/{filename}",
            "file_format": file_format,
        }

    async def test_credentials(self) -> dict[str, Any]:
        return {
            "ok": True,
            "vendor": self.vendor,
            "status": "format-only",
            "summary": (
                "Gemini image generation does not document a free credential probe; "
                "StackOS verified credential storage format without making a billable "
                "generateContent request."
            ),
            "probe_mode": "non_billable_format_only",
            "next_action": "Run a Google Gemini image action to verify the live API key.",
        }


def _base64_encoded_length(raw_length: int) -> int:
    return ((raw_length + 2) // 3) * 4


def _mime_type_for_suffix(suffix: str) -> str:
    if suffix in {"jpg", "jpeg"}:
        return "image/jpeg"
    if suffix == "webp":
        return "image/webp"
    return "image/png"


def _safe_usage_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        _safe_usage_key(raw_key): _safe_usage_value(value) for raw_key, value in metadata.items()
    }


def _safe_usage_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            _safe_usage_key(raw_key): _safe_usage_value(nested) for raw_key, nested in value.items()
        }
    if isinstance(value, list):
        return [_safe_usage_value(item) for item in value]
    return value


def _safe_usage_key(raw_key: Any) -> str:
    snake = _camel_to_snake(str(raw_key))
    if snake == "token_count":
        return "count"
    if snake.endswith("_token_count"):
        return snake.removesuffix("_token_count") + "_count"
    return snake.replace("token", "unit")


def _camel_to_snake(value: str) -> str:
    out: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            out.append("_")
        out.append(char.lower())
    return "".join(out)


__all__ = ["GoogleGeminiImageIntegration"]
