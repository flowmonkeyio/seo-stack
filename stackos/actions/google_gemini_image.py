"""Google Gemini image action connector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from stackos.actions.connectors import (
    ActionConnectorRequest,
    ActionConnectorResult,
    ActionValidationIssue,
)
from stackos.config import Settings
from stackos.integrations.google_gemini_image import GoogleGeminiImageIntegration
from stackos.mcp.errors import IntegrationDownError
from stackos.repositories.base import ValidationError
from stackos.repositories.resources import ArtifactRepository


class GoogleGeminiImageActionConnector:
    """Decision-free adapter from utils Google Gemini image actions to the wrapper."""

    key = "google-gemini-image"
    _MODELS = GoogleGeminiImageIntegration.MODELS
    _GEMINI_3_MODELS = GoogleGeminiImageIntegration.GEMINI_3_MODELS

    def validate(self, request: ActionConnectorRequest) -> list[ActionValidationIssue]:
        payload = request.input_json
        issues = self._validate_prompt_and_model(payload)
        model = self._model(payload)
        match request.operation:
            case "image.generate":
                issues.extend(self._validate_shape_controls(payload, model=model))
            case "image.edit":
                issues.extend(self._validate_shape_controls(payload, model=model))
                issues.extend(self._validate_input_refs(request, model=model))
            case _:
                issues.append(
                    ActionValidationIssue(
                        path="$.operation",
                        message=f"unsupported Google Gemini image operation {request.operation!r}",
                        code="unknown_operation",
                    )
                )
        return issues

    def _validate_prompt_and_model(
        self,
        payload: dict[str, Any],
    ) -> list[ActionValidationIssue]:
        issues: list[ActionValidationIssue] = []
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            issues.append(
                ActionValidationIssue(
                    path="$.prompt",
                    message="prompt is required",
                    code="required",
                )
            )
        model = payload.get("model", GoogleGeminiImageIntegration.DEFAULT_MODEL)
        if not isinstance(model, str) or model not in self._MODELS:
            issues.append(
                ActionValidationIssue(
                    path="$.model",
                    message="model must be a supported Gemini image model",
                    code="enum_mismatch",
                )
            )
        return issues

    def _validate_shape_controls(
        self,
        payload: dict[str, Any],
        *,
        model: str,
    ) -> list[ActionValidationIssue]:
        issues: list[ActionValidationIssue] = []
        aspect_ratio = payload.get("aspect_ratio")
        if aspect_ratio is not None:
            supported = GoogleGeminiImageIntegration.aspect_ratios_for_model(model)
            if not isinstance(aspect_ratio, str) or aspect_ratio not in supported:
                issues.append(
                    ActionValidationIssue(
                        path="$.aspect_ratio",
                        message="aspect_ratio must be supported by the selected Gemini image model",
                        code="enum_mismatch",
                    )
                )
        image_size = payload.get("image_size", "1K")
        if model in self._GEMINI_3_MODELS:
            supported = GoogleGeminiImageIntegration.image_sizes_for_model(model)
            if not isinstance(image_size, str) or image_size not in supported:
                issues.append(
                    ActionValidationIssue(
                        path="$.image_size",
                        message=(
                            "image_size must be one of "
                            f"{', '.join(_stable_image_sizes(supported))} for {model}"
                        ),
                        code="enum_mismatch",
                    )
                )
        elif "image_size" in payload:
            issues.append(
                ActionValidationIssue(
                    path="$.image_size",
                    message="image_size is only supported for Gemini 3 image models",
                    code="model_mismatch",
                )
            )
        return issues

    def _validate_input_refs(
        self,
        request: ActionConnectorRequest,
        *,
        model: str,
    ) -> list[ActionValidationIssue]:
        payload = request.input_json
        refs = payload.get("input_image_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) for ref in refs):
            return [
                ActionValidationIssue(
                    path="$.input_image_refs",
                    message="input_image_refs must be a non-empty list of generated asset refs",
                    code="required",
                )
            ]
        max_refs = GoogleGeminiImageIntegration.max_input_images_for_model(model)
        if len(refs) > max_refs:
            return [
                ActionValidationIssue(
                    path="$.input_image_refs",
                    message=f"{model} accepts at most {max_refs} input images through StackOS",
                    code="range",
                )
            ]
        asset_dir = request.asset_dir or Settings().generated_assets_dir
        try:
            paths = [_artifact_path(asset_dir, ref) for ref in refs]
            prompt = payload.get("prompt")
            GoogleGeminiImageIntegration.ensure_inline_image_preflight(
                prompt=prompt if isinstance(prompt, str) else "",
                paths=paths,
            )
        except (IntegrationDownError, ValidationError) as exc:
            return [
                ActionValidationIssue(
                    path="$.input_image_refs",
                    message=getattr(exc, "detail", str(exc)),
                    code="invalid_image_ref",
                )
            ]
        return []

    def estimate_cost_cents(self, request: ActionConnectorRequest) -> int:
        payload = request.input_json
        model = self._model(payload)
        image_size = str(
            payload.get("image_size") or ("1K" if model in self._GEMINI_3_MODELS else "")
        )
        input_refs = payload.get("input_image_refs")
        input_images = len(input_refs) if isinstance(input_refs, list) else 0
        estimated = GoogleGeminiImageIntegration.estimate_image_cost_usd(
            model=model,
            image_size=image_size,
            input_images=input_images,
        )
        if estimated <= 0:
            return 0
        return max(1, round(estimated * 100))

    async def execute(self, request: ActionConnectorRequest) -> ActionConnectorResult:
        if request.credential is None:
            raise ValidationError("google-gemini-image action requires a resolved credential")
        payload = request.input_json
        asset_dir = request.asset_dir or Settings().generated_assets_dir
        model = self._model(payload)
        image_size = (
            str(payload["image_size"])
            if model in self._GEMINI_3_MODELS and isinstance(payload.get("image_size"), str)
            else None
        )
        async with httpx.AsyncClient(timeout=180.0) as http:
            client = GoogleGeminiImageIntegration(
                payload=request.credential.secret_payload,
                project_id=request.project_id,
                http=http,
                asset_dir=asset_dir,
            )
            if request.operation == "image.edit":
                result = await client.edit_image(
                    prompt=str(payload["prompt"]),
                    input_image_paths=[
                        _artifact_path(asset_dir, str(ref)) for ref in payload["input_image_refs"]
                    ],
                    model=model,
                    aspect_ratio=(
                        str(payload["aspect_ratio"])
                        if isinstance(payload.get("aspect_ratio"), str)
                        else None
                    ),
                    image_size=image_size,
                )
            else:
                result = await client.generate_image(
                    prompt=str(payload["prompt"]),
                    model=model,
                    aspect_ratio=(
                        str(payload["aspect_ratio"])
                        if isinstance(payload.get("aspect_ratio"), str)
                        else "1:1"
                    ),
                    image_size=image_size,
                )
        output_json = result.data if isinstance(result.data, dict) else {"data": result.data}
        output_json = _register_generated_image_artifacts(request, output_json)
        return ActionConnectorResult(
            output_json=output_json,
            metadata_json={"vendor": "google-gemini-image"},
            cost_cents=_cost_usd_to_cents(result.cost_usd),
        )

    @staticmethod
    def _model(payload: dict[str, Any]) -> str:
        raw = payload.get("model", GoogleGeminiImageIntegration.DEFAULT_MODEL)
        return raw if isinstance(raw, str) else GoogleGeminiImageIntegration.DEFAULT_MODEL


def _artifact_path(asset_dir: Path, artifact_ref: str) -> Path:
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


def _register_generated_image_artifacts(
    request: ActionConnectorRequest,
    output_json: dict[str, Any],
) -> dict[str, Any]:
    if request.session is None:
        return output_json
    items = output_json.get("data")
    if not isinstance(items, list):
        return output_json
    asset_dir = (request.asset_dir or Settings().generated_assets_dir).resolve()
    repository = ArtifactRepository(request.session)
    registered_items: list[Any] = []
    artifact_refs: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            registered_items.append(item)
            continue
        uri = item.get("url")
        if not isinstance(uri, str) or not uri.startswith("/generated-assets/"):
            registered_items.append(item)
            continue
        path = _artifact_path(asset_dir, uri)
        file_format = str(item.get("file_format") or path.suffix.removeprefix(".") or "png")
        artifact = repository.create(
            project_id=request.project_id,
            plugin_slug="utils",
            kind="image",
            uri=uri,
            name=path.name,
            mime_type=_mime_type(file_format),
            size_bytes=path.stat().st_size,
            metadata_json={
                "provider_key": "google-gemini-image",
                "operation": request.operation,
                "model": item.get("source_model"),
                "file_format": file_format,
                "candidate_index": item.get("candidate_index"),
                "part_index": item.get("part_index"),
            },
            provenance_json={
                "source": "google-gemini-image-action",
                "action_ref": request.action_ref,
            },
        ).data
        clean = dict(item)
        clean["artifact_ref"] = uri
        clean["artifact_id"] = artifact.id
        registered_items.append(clean)
        artifact_refs.append(uri)
    if not artifact_refs:
        return output_json
    out = dict(output_json)
    out["data"] = registered_items
    out["artifact_refs"] = artifact_refs
    return out


def _mime_type(file_format: str) -> str:
    if file_format in {"jpg", "jpeg"}:
        return "image/jpeg"
    if file_format == "webp":
        return "image/webp"
    return "image/png"


def _cost_usd_to_cents(cost_usd: float) -> int:
    if cost_usd <= 0:
        return 0
    return max(1, round(cost_usd * 100))


def _stable_image_sizes(values: frozenset[str]) -> list[str]:
    order = ["512", "1K", "2K", "4K"]
    return [value for value in order if value in values]


__all__ = ["GoogleGeminiImageActionConnector"]
