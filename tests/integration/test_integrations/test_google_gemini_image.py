"""Google Gemini image wrapper tests."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pytest_httpx import HTTPXMock

from stackos.integrations.google_gemini_image import GoogleGeminiImageIntegration
from stackos.mcp.errors import IntegrationDownError


def test_generate_image_requests_generate_content_and_persists_inline_image(
    httpx_mock: HTTPXMock,
    project_id: int,
    tmp_path: Path,
) -> None:
    image_bytes = b"google-png"
    httpx_mock.add_response(
        method="POST",
        url=(
            "https://generativelanguage.googleapis.com/v1/models/"
            "gemini-3.1-flash-image:generateContent"
        ),
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "created"},
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": base64.b64encode(image_bytes).decode("ascii"),
                                }
                            },
                        ]
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "totalTokenCount": 1120,
                "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 42}],
            },
        },
    )

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = GoogleGeminiImageIntegration(
                payload=b"gemini-key",
                project_id=project_id,
                http=client,
                asset_dir=tmp_path,
            )
            return await integ.generate_image(
                prompt="image prompt",
                aspect_ratio="16:9",
                image_size="512",
            )

    result = asyncio.run(go())
    request = httpx_mock.get_requests()[0]
    body = json.loads(request.content.decode("utf-8"))
    item = result.data["data"][0]
    assert request.headers["x-goog-api-key"] == "gemini-key"
    assert body == {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "image prompt"}],
            }
        ],
        "generationConfig": {
            "responseModalities": ["Image"],
            "responseFormat": {"image": {"aspectRatio": "16:9", "imageSize": "512"}},
        },
    }
    assert item["url"].startswith("/generated-assets/google-gemini-image/google-gemini-image-")
    assert item["file_format"] == "png"
    assert item["source_model"] == "gemini-3.1-flash-image"
    assert result.data["text"] == ["created"]
    assert result.data["usage"] == {
        "total_count": 1120,
        "prompt_units_details": [{"modality": "TEXT", "count": 42}],
    }
    path = tmp_path / item["url"].removeprefix("/generated-assets/")
    assert path.read_bytes() == image_bytes
    assert result.cost_usd == 0.045


def test_edit_image_sends_inline_reference_and_pro_input_cost(
    httpx_mock: HTTPXMock,
    project_id: int,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.jpg"
    source.write_bytes(b"source-jpeg")
    httpx_mock.add_response(
        method="POST",
        url=(
            "https://generativelanguage.googleapis.com/v1/models/gemini-3-pro-image:generateContent"
        ),
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": base64.b64encode(b"edited-jpeg").decode("ascii"),
                                }
                            }
                        ]
                    }
                }
            ]
        },
    )

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = GoogleGeminiImageIntegration(
                payload=b"gemini-key",
                project_id=project_id,
                http=client,
                asset_dir=tmp_path,
            )
            return await integ.edit_image(
                prompt="keep the product, change the set",
                input_image_paths=[source],
                model="gemini-3-pro-image",
                aspect_ratio="3:2",
                image_size="4K",
            )

    result = asyncio.run(go())
    request = httpx_mock.get_requests()[0]
    body = json.loads(request.content.decode("utf-8"))
    parts = body["contents"][0]["parts"]
    assert parts[0] == {"text": "keep the product, change the set"}
    assert parts[1]["inline_data"] == {
        "mime_type": "image/jpeg",
        "data": base64.b64encode(b"source-jpeg").decode("ascii"),
    }
    assert body["generationConfig"]["responseFormat"]["image"] == {
        "aspectRatio": "3:2",
        "imageSize": "4K",
    }
    assert result.data["data"][0]["file_format"] == "jpg"
    assert result.cost_usd == pytest.approx(0.2411)


def test_gemini_25_omits_image_size_from_generation_config(
    httpx_mock: HTTPXMock,
    project_id: int,
    tmp_path: Path,
) -> None:
    httpx_mock.add_response(
        method="POST",
        url=(
            "https://generativelanguage.googleapis.com/v1/models/"
            "gemini-2.5-flash-image:generateContent"
        ),
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": base64.b64encode(b"legacy-png").decode("ascii"),
                                }
                            }
                        ]
                    }
                }
            ]
        },
    )

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = GoogleGeminiImageIntegration(
                payload=b"gemini-key",
                project_id=project_id,
                http=client,
                asset_dir=tmp_path,
            )
            return await integ.generate_image(
                prompt="legacy model",
                model="gemini-2.5-flash-image",
                aspect_ratio="21:9",
                image_size=None,
            )

    result = asyncio.run(go())
    body = json.loads(httpx_mock.get_requests()[0].content.decode("utf-8"))
    assert body["generationConfig"] == {
        "responseModalities": ["Image"],
        "responseFormat": {"image": {"aspectRatio": "21:9"}},
    }
    assert result.cost_usd == 0.039


def test_inline_reference_preflight_rejects_payloads_at_request_limit(
    httpx_mock: HTTPXMock,
    project_id: int,
    tmp_path: Path,
) -> None:
    source = tmp_path / "too-large.png"
    source.write_bytes(b"x" * 15_000_000)

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = GoogleGeminiImageIntegration(
                payload=b"gemini-key",
                project_id=project_id,
                http=client,
                asset_dir=tmp_path,
            )
            return await integ.edit_image(prompt="oversized", input_image_paths=[source])

    with pytest.raises(IntegrationDownError) as exc_info:
        asyncio.run(go())

    assert "under 20 MB" in exc_info.value.detail
    assert httpx_mock.get_requests() == []


def test_test_credentials_is_explicitly_non_billable_format_only(project_id: int) -> None:
    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = GoogleGeminiImageIntegration(
                payload=b"gemini-key",
                project_id=project_id,
                http=client,
            )
            return await integ.test_credentials()

    result = asyncio.run(go())
    assert result["ok"] is True
    assert result["status"] == "format-only"
    assert result["probe_mode"] == "non_billable_format_only"
