"""Ahrefs wrapper tests — Enterprise-only with graceful degrade."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from pytest_httpx import HTTPXMock

from content_stack.integrations.ahrefs import AhrefsIntegration
from content_stack.mcp.errors import IntegrationDownError


def test_keywords_for_site_with_key(httpx_mock: HTTPXMock, project_id: int) -> None:
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://api.ahrefs.com/v3/site-explorer/organic-keywords?"
            "target=example.com&country=us&limit=100"
            "&select=keyword%2Cvolume%2Ccpc%2Cposition%2Ckd"
        ),
        json={"keywords": [{"keyword": "x", "volume": 1000}]},
    )

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = AhrefsIntegration(payload=b"ah-key", project_id=project_id, http=client)
            return await integ.keywords_for_site(target="example.com")

    result = asyncio.run(go())
    assert result.data["keywords"][0]["keyword"] == "x"


def test_test_credentials_without_key_raises_with_hint(project_id: int) -> None:
    """Empty payload → graceful Enterprise-only error pointing at docs."""

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = AhrefsIntegration(payload=b"", project_id=project_id, http=client)
            return await integ.test_credentials()

    with pytest.raises(IntegrationDownError) as exc_info:
        asyncio.run(go())
    assert "Enterprise" in exc_info.value.detail
    assert "docs/api-keys.md" in exc_info.value.data["hint"]
