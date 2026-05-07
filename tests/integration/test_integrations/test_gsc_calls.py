"""GSC wrapper API-call tests (search_analytics, inspect_url, etc.)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from pytest_httpx import HTTPXMock

from content_stack.integrations.gsc import GscIntegration


def _payload() -> bytes:
    return json.dumps(
        {
            "access_token": "ya29.fake",
            "refresh_token": "1//rt-fake",
            "expires_at": "2099-01-01T00:00:00",
            "scope": "webmasters.readonly indexing",
            "token_type": "Bearer",
        }
    ).encode("utf-8")


def test_search_analytics_query(httpx_mock: HTTPXMock, project_id: int) -> None:
    httpx_mock.add_response(
        method="POST",
        url=(
            "https://searchconsole.googleapis.com/webmasters/v3/sites/"
            "https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
        ),
        json={"rows": [{"clicks": 10, "impressions": 100}]},
    )

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = GscIntegration(payload=_payload(), project_id=project_id, http=client)
            return await integ.search_analytics(
                site_url="https://example.com/",
                start_date="2025-01-01",
                end_date="2025-01-07",
                dimensions=["query"],
            )

    result = asyncio.run(go())
    assert result.data["rows"][0]["clicks"] == 10


def test_inspect_url(httpx_mock: HTTPXMock, project_id: int) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
        json={"inspectionResult": {"indexStatusResult": {"verdict": "PASS"}}},
    )

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = GscIntegration(payload=_payload(), project_id=project_id, http=client)
            return await integ.inspect_url(
                site_url="https://example.com/",
                inspection_url="https://example.com/page",
            )

    result = asyncio.run(go())
    assert result.data["inspectionResult"]["indexStatusResult"]["verdict"] == "PASS"


def test_test_credentials_lists_sites(httpx_mock: HTTPXMock, project_id: int) -> None:
    """``test_credentials`` lists registered sites on the GSC account."""
    httpx_mock.add_response(
        method="GET",
        url="https://searchconsole.googleapis.com/webmasters/v3/sites",
        json={
            "siteEntry": [
                {"siteUrl": "https://a.com/", "permissionLevel": "siteOwner"},
                {"siteUrl": "https://b.com/", "permissionLevel": "siteFullUser"},
            ]
        },
    )

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = GscIntegration(payload=_payload(), project_id=project_id, http=client)
            return await integ.test_credentials()

    out = asyncio.run(go())
    assert out["ok"] is True
    assert out["sites_count"] == 2


def test_pagespeed_call(httpx_mock: HTTPXMock, project_id: int) -> None:
    """PSI uses GET with query params; key is optional."""
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://pagespeedonline.googleapis.com/pagespeedonline/v5/"
            "runPagespeed?url=https%3A%2F%2Fexample.com%2F&strategy=mobile"
        ),
        json={"lighthouseResult": {"categories": {"performance": {"score": 0.9}}}},
    )

    async def go() -> Any:
        async with httpx.AsyncClient() as client:
            integ = GscIntegration(payload=_payload(), project_id=project_id, http=client)
            return await integ.pagespeed(url="https://example.com/", strategy="mobile")

    result = asyncio.run(go())
    assert result.data["lighthouseResult"]["categories"]["performance"]["score"] == 0.9
