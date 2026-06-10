"""Ideogram image wrapper tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pytest_httpx import HTTPXMock

from stackos.integrations.ideogram_images import IdeogramImagesIntegration
from stackos.mcp.errors import IntegrationDownError

PNG_BYTES = b"\x89PNG\r\n\x1a\nideogram-png"
WEBP_BYTES = b"RIFF\x10\x00\x00\x00WEBPideogram-webp"


def test_generate_image_uses_multipart_and_persists_temporary_url(
    httpx_mock: HTTPXMock,
    project_id: int,
    tmp_path: Path,
) -> None:
    provider_url = "https://ideogram.ai/api/images/ephemeral/generated.png?sig=secret"
    provider_url_2 = "https://ideogram.ai/api/images/ephemeral/generated-2.png?sig=secret"
    httpx_mock.add_response(
        method="POST",
        url="https://api.ideogram.ai/v1/ideogram-v4/generate",
        json={
            "created": "2026-06-10 00:00:00+00:00",
            "data": [
                {
                    "prompt": "A storefront poster",
                    "resolution": "2048x2048",
                    "is_image_safe": True,
                    "seed": 12345,
                    "url": provider_url,
                },
                {
                    "prompt": "A storefront poster",
                    "resolution": "2048x2048",
                    "is_image_safe": True,
                    "seed": 67890,
                    "url": provider_url_2,
                },
            ],
            "response_type": "url",
        },
    )
    httpx_mock.add_response(
        method="GET",
        url=provider_url,
        content=PNG_BYTES,
        headers={"content-type": "image/png"},
    )
    httpx_mock.add_response(
        method="GET",
        url=provider_url_2,
        content=PNG_BYTES + b"-second",
        headers={"content-type": "image/png"},
    )

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = IdeogramImagesIntegration(
                payload=b"ideo-key",
                project_id=project_id,
                http=client,
                asset_dir=tmp_path,
            )
            return await integ.generate_image(
                text_prompt="A storefront poster",
                resolution="2048x2048",
                rendering_speed="TURBO",
                enable_copyright_detection=True,
            )

    result = asyncio.run(go())
    post_request = httpx_mock.get_requests()[0]
    item = result.data["data"][0]
    item_2 = result.data["data"][1]
    rendered = json.dumps(result.data)

    assert post_request.headers["Api-Key"] == "ideo-key"
    assert post_request.headers["content-type"].startswith("multipart/form-data; boundary=")
    assert b'name="text_prompt"\r\n\r\nA storefront poster' in post_request.content
    assert b'name="resolution"\r\n\r\n2048x2048' in post_request.content
    assert b'name="rendering_speed"\r\n\r\nTURBO' in post_request.content
    assert b'name="enable_copyright_detection"\r\n\r\ntrue' in post_request.content
    assert item["url"].startswith("/generated-assets/ideogram/ideogram-")
    assert item["file_format"] == "png"
    assert item["source_model"] == "ideogram-v4"
    assert item["provider_url_persisted"] is True
    assert provider_url not in rendered
    assert provider_url_2 not in rendered
    path = tmp_path / item["url"].removeprefix("/generated-assets/")
    path_2 = tmp_path / item_2["url"].removeprefix("/generated-assets/")
    assert path.read_bytes() == PNG_BYTES
    assert path_2.read_bytes() == PNG_BYTES + b"-second"
    assert result.cost_usd == 0.06


def test_remix_image_uploads_reference_and_persists_temporary_url(
    httpx_mock: HTTPXMock,
    project_id: int,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.webp"
    source.write_bytes(WEBP_BYTES)
    provider_url = "https://ideogram.ai/api/images/ephemeral/remix.webp?sig=secret"
    httpx_mock.add_response(
        method="POST",
        url="https://api.ideogram.ai/v1/ideogram-v4/remix",
        json={
            "created": "2026-06-10 00:00:00+00:00",
            "data": [
                {
                    "prompt": "Keep the object, change the background",
                    "resolution": "3072x1024",
                    "is_image_safe": True,
                    "seed": 98765,
                    "url": provider_url,
                }
            ],
            "response_type": "url",
        },
    )
    httpx_mock.add_response(
        method="GET",
        url=provider_url,
        content=WEBP_BYTES,
        headers={"content-type": "image/webp"},
    )

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = IdeogramImagesIntegration(
                payload=b"ideo-key",
                project_id=project_id,
                http=client,
                asset_dir=tmp_path,
            )
            return await integ.remix_image(
                text_prompt="Keep the object, change the background",
                image_path=source,
                image_weight=75,
                resolution="3072x1024",
                rendering_speed="QUALITY",
            )

    result = asyncio.run(go())
    post_request = httpx_mock.get_requests()[0]
    item = result.data["data"][0]

    assert b'name="image_weight"\r\n\r\n75' in post_request.content
    assert (
        b'name="image"; filename="source.webp"\r\nContent-Type: image/webp' in post_request.content
    )
    assert item["url"].startswith("/generated-assets/ideogram/ideogram-")
    assert item["file_format"] == "webp"
    assert result.cost_usd == 0.10


def test_generated_urls_require_asset_dir_to_prevent_temporary_url_leak(
    httpx_mock: HTTPXMock,
    project_id: int,
) -> None:
    provider_url = "https://ideogram.ai/api/images/ephemeral/generated.png?sig=secret"
    httpx_mock.add_response(
        method="POST",
        url="https://api.ideogram.ai/v1/ideogram-v4/generate",
        json={
            "data": [
                {
                    "prompt": "poster",
                    "url": provider_url,
                },
            ],
            "response_type": "url",
        },
    )

    async def go() -> None:
        async with httpx.AsyncClient() as client:
            integ = IdeogramImagesIntegration(
                payload=b"ideo-key",
                project_id=project_id,
                http=client,
            )
            await integ.generate_image(text_prompt="poster")

    with pytest.raises(IntegrationDownError) as exc:
        asyncio.run(go())

    assert "generated-assets persistence" in exc.value.detail
    assert len(httpx_mock.get_requests()) == 1


def test_image_preflight_rejects_unsupported_format_and_oversize(tmp_path: Path) -> None:
    heic = tmp_path / "unsupported.heic"
    heic.write_bytes(b"heic")
    fake_webp = tmp_path / "fake.webp"
    fake_webp.write_bytes(b"source-webp")
    too_large = tmp_path / "large.png"
    too_large.write_bytes(b"x" * 10_000_001)

    with pytest.raises(IntegrationDownError) as format_exc:
        IdeogramImagesIntegration.ensure_image_preflight(heic)
    with pytest.raises(IntegrationDownError) as signature_exc:
        IdeogramImagesIntegration.ensure_image_preflight(fake_webp)
    with pytest.raises(IntegrationDownError) as size_exc:
        IdeogramImagesIntegration.ensure_image_preflight(too_large)

    assert "JPEG, PNG, or WEBP" in format_exc.value.detail
    assert "valid JPEG, PNG, or WEBP bytes" in signature_exc.value.detail
    assert "at most 10 MB" in size_exc.value.detail


def test_test_credentials_is_explicitly_non_billable_format_only(project_id: int) -> None:
    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = IdeogramImagesIntegration(
                payload=b"ideo-key",
                project_id=project_id,
                http=client,
            )
            return await integ.test_credentials()

    result = asyncio.run(go())
    assert result["ok"] is True
    assert result["status"] == "format-only"
    assert result["probe_mode"] == "non_billable_format_only"
