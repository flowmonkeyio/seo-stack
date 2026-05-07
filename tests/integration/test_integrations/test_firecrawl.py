"""Firecrawl wrapper tests."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from pytest_httpx import HTTPXMock

from content_stack.integrations.firecrawl import FirecrawlIntegration
from content_stack.mcp.errors import IntegrationDownError


def test_scrape_returns_markdown(httpx_mock: HTTPXMock, project_id: int) -> None:
    """Happy-path scrape decodes the markdown payload."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.firecrawl.dev/v1/scrape",
        json={"data": {"markdown": "# Hello", "url": "https://example.com"}},
    )

    async def go() -> object:
        async with httpx.AsyncClient() as client:
            integ = FirecrawlIntegration(
                payload=b"fc-key",
                project_id=project_id,
                http=client,
            )
            return await integ.scrape(url="https://example.com")

    result = asyncio.run(go())
    assert "Hello" in str(result.data)


def test_5xx_retries_then_raises_integration_down(httpx_mock: HTTPXMock, project_id: int) -> None:
    """Three 503s exhaust retries and raise ``IntegrationDownError``."""
    for _ in range(4):
        httpx_mock.add_response(
            method="POST",
            url="https://api.firecrawl.dev/v1/scrape",
            status_code=503,
        )

    async def go() -> object:
        async with httpx.AsyncClient() as client:
            integ = FirecrawlIntegration(
                payload=b"fc-key",
                project_id=project_id,
                http=client,
            )
            return await integ.scrape(url="https://example.com")

    with pytest.raises(IntegrationDownError):
        asyncio.run(go())
    assert len(httpx_mock.get_requests()) == 4


def test_test_credentials_calls_scrape(httpx_mock: HTTPXMock, project_id: int) -> None:
    """``test_credentials`` issues a scrape against ``example.com``."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.firecrawl.dev/v1/scrape",
        json={"data": {"markdown": "ok"}},
    )

    async def go() -> object:
        async with httpx.AsyncClient() as client:
            integ = FirecrawlIntegration(
                payload=b"fc-key",
                project_id=project_id,
                http=client,
            )
            return await integ.test_credentials()

    out = asyncio.run(go())
    assert out["ok"] is True
    assert out["vendor"] == "firecrawl"


def test_4xx_other_than_429_surfaces_immediately(httpx_mock: HTTPXMock, project_id: int) -> None:
    """A 401 (auth failure) raises ``IntegrationDownError`` after one call."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.firecrawl.dev/v1/scrape",
        status_code=401,
        json={"error": "unauthorized"},
    )

    async def go() -> object:
        async with httpx.AsyncClient() as client:
            integ = FirecrawlIntegration(
                payload=b"fc-key",
                project_id=project_id,
                http=client,
            )
            return await integ.scrape(url="https://example.com")

    with pytest.raises(IntegrationDownError):
        asyncio.run(go())
    assert len(httpx_mock.get_requests()) == 1
