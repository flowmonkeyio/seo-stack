"""OpenAI Images wrapper tests."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from pytest_httpx import HTTPXMock

from content_stack.integrations.openai_images import OpenAIImagesIntegration


def test_generate_returns_url(httpx_mock: HTTPXMock, project_id: int) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.openai.com/v1/images/generations",
        json={"data": [{"url": "https://example.com/image.png"}]},
    )

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = OpenAIImagesIntegration(
                payload=b"sk-openai", project_id=project_id, http=client
            )
            return await integ.generate(prompt="a cat", n=1)

    result = asyncio.run(go())
    assert result.data["data"][0]["url"].endswith("image.png")
    # Default 1024x1024 standard estimate is $0.04.
    assert result.cost_usd == 0.04


def test_test_credentials_lists_models(httpx_mock: HTTPXMock, project_id: int) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://api.openai.com/v1/models",
        json={"data": [{"id": "gpt-4"}, {"id": "dall-e-3"}]},
    )

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = OpenAIImagesIntegration(
                payload=b"sk-openai", project_id=project_id, http=client
            )
            return await integ.test_credentials()

    out = asyncio.run(go())
    assert out["ok"] is True
    assert out["models_count"] == 2
