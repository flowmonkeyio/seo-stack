"""OpenAI Images connector for generic StackOS actions."""

from __future__ import annotations

from pathlib import Path

import httpx

from stackos.actions.connectors import (
    ActionConnectorRequest,
    ActionConnectorResult,
    ActionValidationIssue,
)
from stackos.config import Settings
from stackos.integrations.openai_images import OpenAIImagesIntegration
from stackos.repositories.base import ValidationError

# gpt-image-2 free-form size constraints from the official image guide:
# https://developers.openai.com/api/docs/guides/image-generation
# both edges <= 3840px, both edges divisible by 16, long:short ratio <=
# 3:1, and total pixels inside the documented bounds.
_FREEFORM_SIZE_MODELS = frozenset({"gpt-image-2"})
_FREEFORM_EDGE_DIVISOR = 16
_FREEFORM_MAX_EDGE = 3840
_FREEFORM_MAX_RATIO = 3.0
_FREEFORM_MIN_PIXELS = 655_360
_FREEFORM_MAX_PIXELS = 8_294_400


class OpenAIImagesActionConnector:
    """Decision-free adapter from utils image actions to the vendor wrapper."""

    key = "openai-images"
    _SUPPORTED_MODELS = OpenAIImagesIntegration._GPT_IMAGE_MODELS
    _FIDELITY_MODELS = OpenAIImagesIntegration._INPUT_FIDELITY_MODELS
    _MAX_INPUT_IMAGES = OpenAIImagesIntegration.MAX_EDIT_INPUT_IMAGES
    _SUPPORTED_SIZES = frozenset({"auto", "1024x1024", "1536x1024", "1024x1536"})
    _SUPPORTED_QUALITIES = frozenset({"auto", "low", "medium", "high"})
    _SUPPORTED_FORMATS = frozenset({"webp", "png", "jpeg"})
    _SUPPORTED_FIDELITY = frozenset({"high", "low"})

    def validate(self, request: ActionConnectorRequest) -> list[ActionValidationIssue]:
        issues = self._validate_common(request)
        if request.operation == "image.edit":
            issues.extend(self._validate_edit(request))
        return issues

    def _validate_common(self, request: ActionConnectorRequest) -> list[ActionValidationIssue]:
        issues: list[ActionValidationIssue] = []
        payload = request.input_json
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            issues.append(
                ActionValidationIssue(
                    path="$.prompt",
                    message="prompt is required",
                    code="required",
                )
            )
        model = payload.get("model", OpenAIImagesIntegration.DEFAULT_MODEL)
        if not isinstance(model, str) or model not in self._SUPPORTED_MODELS:
            issues.append(
                ActionValidationIssue(
                    path="$.model",
                    message="model must be one of the supported GPT Image model profiles",
                    code="enum_mismatch",
                )
            )
            model = OpenAIImagesIntegration.DEFAULT_MODEL
        n = payload.get("n", 1)
        if not isinstance(n, int) or isinstance(n, bool) or n < 1 or n > 10:
            issues.append(
                ActionValidationIssue(
                    path="$.n",
                    message="n must be an integer between 1 and 10",
                    code="range",
                )
            )
        size = payload.get("size", self._default_size(request.operation))
        if not isinstance(size, str) or not self._size_supported(model=str(model), size=size):
            issues.append(
                ActionValidationIssue(
                    path="$.size",
                    message=(
                        "size must be a supported GPT Image size profile; gpt-image-2 "
                        "also accepts WxH with both edges <= 3840 and divisible by 16, "
                        "ratio at most 3:1, and total pixels between 655360 and 8294400"
                    ),
                    code="enum_mismatch",
                )
            )
        quality = payload.get("quality", "medium")
        if not isinstance(quality, str) or quality not in self._SUPPORTED_QUALITIES:
            issues.append(
                ActionValidationIssue(
                    path="$.quality",
                    message="quality must be one of the supported GPT Image quality profiles",
                    code="enum_mismatch",
                )
            )
        output_format = payload.get("output_format", "webp")
        if not isinstance(output_format, str) or output_format not in self._SUPPORTED_FORMATS:
            issues.append(
                ActionValidationIssue(
                    path="$.output_format",
                    message="output_format is not supported",
                    code="enum_mismatch",
                )
            )
        return issues

    def _validate_edit(self, request: ActionConnectorRequest) -> list[ActionValidationIssue]:
        issues: list[ActionValidationIssue] = []
        payload = request.input_json
        refs = payload.get("input_image_refs")
        if (
            not isinstance(refs, list)
            or not refs
            or not all(isinstance(ref, str) and ref.strip() for ref in refs)
        ):
            issues.append(
                ActionValidationIssue(
                    path="$.input_image_refs",
                    message="input_image_refs must be a non-empty list of artifact refs",
                    code="required",
                )
            )
        elif len(refs) > self._MAX_INPUT_IMAGES:
            issues.append(
                ActionValidationIssue(
                    path="$.input_image_refs",
                    message=f"input_image_refs accepts at most {self._MAX_INPUT_IMAGES} images",
                    code="range",
                )
            )
        fidelity = payload.get("input_fidelity")
        model = payload.get("model", OpenAIImagesIntegration.DEFAULT_MODEL)
        if fidelity is not None:
            if not isinstance(fidelity, str) or fidelity not in self._SUPPORTED_FIDELITY:
                issues.append(
                    ActionValidationIssue(
                        path="$.input_fidelity",
                        message="input_fidelity must be 'high' or 'low'",
                        code="enum_mismatch",
                    )
                )
            elif model not in self._FIDELITY_MODELS:
                issues.append(
                    ActionValidationIssue(
                        path="$.input_fidelity",
                        message=(
                            "input_fidelity is only configurable for gpt-image-1.5 and "
                            "gpt-image-1; gpt-image-2 always uses high input fidelity"
                        ),
                        code="model_mismatch",
                    )
                )
        return issues

    @classmethod
    def _default_size(cls, operation: str) -> str:
        return "auto" if operation == "image.edit" else "1536x1024"

    @classmethod
    def _size_supported(cls, *, model: str, size: str) -> bool:
        if size in cls._SUPPORTED_SIZES:
            return True
        if model not in _FREEFORM_SIZE_MODELS:
            return False
        width_text, separator, height_text = size.partition("x")
        if not separator or not width_text.isdigit() or not height_text.isdigit():
            return False
        width = int(width_text)
        height = int(height_text)
        if width <= 0 or height <= 0:
            return False
        if width % _FREEFORM_EDGE_DIVISOR or height % _FREEFORM_EDGE_DIVISOR:
            return False
        if max(width, height) > _FREEFORM_MAX_EDGE:
            return False
        if max(width, height) / min(width, height) > _FREEFORM_MAX_RATIO:
            return False
        return _FREEFORM_MIN_PIXELS <= width * height <= _FREEFORM_MAX_PIXELS

    def estimate_cost_cents(self, request: ActionConnectorRequest) -> int:
        payload = request.input_json
        model = str(payload.get("model", OpenAIImagesIntegration.DEFAULT_MODEL))
        size = str(payload.get("size", self._default_size(request.operation)))
        quality = str(payload.get("quality", "medium"))
        raw_n = payload.get("n", 1)
        n = raw_n if isinstance(raw_n, int) and not isinstance(raw_n, bool) else 1
        estimated = OpenAIImagesIntegration.estimate_image_cost_usd(
            model=model,
            size=size,
            quality=quality,
            n=n,
        )
        return max(0, round(estimated * 100))

    async def execute(self, request: ActionConnectorRequest) -> ActionConnectorResult:
        if request.credential is None:
            raise ValidationError("openai-images action requires a resolved credential")
        payload = request.input_json
        asset_dir = request.asset_dir or Settings().generated_assets_dir
        async with httpx.AsyncClient(timeout=120.0) as http:
            client = OpenAIImagesIntegration(
                payload=request.credential.secret_payload,
                project_id=request.project_id,
                http=http,
                asset_dir=asset_dir,
            )
            match request.operation:
                case "image.edit":
                    fidelity = payload.get("input_fidelity")
                    result = await client.edit(
                        prompt=str(payload["prompt"]),
                        input_image_paths=[
                            _artifact_path(asset_dir, str(ref))
                            for ref in payload["input_image_refs"]
                        ],
                        size=str(payload.get("size", "auto")),
                        quality=str(payload.get("quality", "medium")),
                        n=int(payload.get("n", 1)),
                        model=str(payload.get("model", OpenAIImagesIntegration.DEFAULT_MODEL)),
                        output_format=str(payload.get("output_format", "webp")),
                        input_fidelity=str(fidelity) if isinstance(fidelity, str) else None,
                    )
                case _:
                    result = await client.generate(
                        prompt=str(payload["prompt"]),
                        size=str(payload.get("size", "1536x1024")),
                        quality=str(payload.get("quality", "medium")),
                        n=int(payload.get("n", 1)),
                        model=str(payload.get("model", OpenAIImagesIntegration.DEFAULT_MODEL)),
                        output_format=str(payload.get("output_format", "webp")),
                    )
        return ActionConnectorResult(
            output_json=result.data if isinstance(result.data, dict) else {"data": result.data},
            metadata_json={"vendor": "openai-images"},
            cost_cents=max(0, round(result.cost_usd * 100)),
        )


def _artifact_path(asset_dir: Path, artifact_ref: str) -> Path:
    """Resolve a generated-assets artifact ref to a local file path."""
    if artifact_ref.startswith("/generated-assets/"):
        relative = artifact_ref.removeprefix("/generated-assets/")
    elif artifact_ref.startswith("generated-assets/"):
        relative = artifact_ref.removeprefix("generated-assets/")
    else:
        relative = artifact_ref.lstrip("/")
    base = asset_dir.resolve()
    candidate = (base / relative).resolve()
    if base != candidate and base not in candidate.parents:
        raise ValidationError("input_image_refs must stay inside generated assets")
    if not candidate.is_file():
        raise ValidationError(f"input image ref {artifact_ref!r} does not point to a file")
    return candidate


__all__ = ["OpenAIImagesActionConnector"]
