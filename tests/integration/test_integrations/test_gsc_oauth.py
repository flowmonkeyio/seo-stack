"""GSC OAuth helpers + refresh worker — full flow under pytest-httpx."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pytest_httpx import HTTPXMock
from sqlmodel import Session

from content_stack.integrations.gsc import (
    AUTHORIZE_ENDPOINT,
    TOKEN_ENDPOINT,
    build_authorize_url,
    exchange_code,
    refresh_access_token,
)
from content_stack.jobs.oauth_refresh import refresh_expiring_gsc_tokens
from content_stack.repositories.projects import IntegrationCredentialRepository


@pytest.fixture(autouse=True)
def _set_oauth_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the OAuth client_id/client_secret env vars for every test in this module."""
    monkeypatch.setenv("GSC_OAUTH_CLIENT_ID", "client-id-fake")
    monkeypatch.setenv("GSC_OAUTH_CLIENT_SECRET", "client-secret-fake")


def test_build_authorize_url_includes_required_params() -> None:
    """The consent URL carries client_id, scope, redirect_uri, state, and prompt=consent."""
    url = build_authorize_url(
        state="rand-1",
        redirect_uri="http://localhost:5180/api/v1/integrations/gsc/oauth/callback",
    )
    assert url.startswith(AUTHORIZE_ENDPOINT)
    assert "state=rand-1" in url
    assert "client_id=client-id-fake" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    # Both required scopes should be present.
    assert "webmasters.readonly" in url
    assert "indexing" in url


def test_exchange_code_round_trips_token_bundle(httpx_mock: HTTPXMock) -> None:
    """``exchange_code`` POSTs to Google and decodes the token bundle."""
    httpx_mock.add_response(
        method="POST",
        url=TOKEN_ENDPOINT,
        json={
            "access_token": "ya29.fresh",
            "refresh_token": "1//rt",
            "expires_in": 3600,
            "scope": "webmasters.readonly indexing",
            "token_type": "Bearer",
        },
    )

    async def go() -> dict:
        return await exchange_code(
            code="auth-code-123",
            redirect_uri="http://localhost:5180/api/v1/integrations/gsc/oauth/callback",
        )

    payload = asyncio.run(go())
    assert payload["access_token"] == "ya29.fresh"
    assert payload["refresh_token"] == "1//rt"
    # ``expires_at`` derived from ``expires_in``.
    assert "expires_at" in payload


def test_refresh_access_token_grants_new_access_token(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=TOKEN_ENDPOINT,
        json={
            "access_token": "ya29.new",
            "expires_in": 3600,
            "scope": "webmasters.readonly indexing",
            "token_type": "Bearer",
        },
    )

    async def go() -> dict:
        return await refresh_access_token(refresh_token="1//rt-old")

    out = asyncio.run(go())
    assert out["access_token"] == "ya29.new"
    assert "expires_at" in out


def test_refresh_expiring_tokens_walks_db_and_refreshes(
    httpx_mock: HTTPXMock,
    session: Session,
    project_id: int,
) -> None:
    """The job picks up rows expiring within 10 minutes and re-encrypts them."""
    repo = IntegrationCredentialRepository(session)
    expiring = datetime.now(tz=UTC).replace(tzinfo=None) + timedelta(minutes=5)
    bundle = {
        "access_token": "ya29.old",
        "refresh_token": "1//rt-active",
        "expires_at": expiring.isoformat(),
        "scope": "webmasters.readonly indexing",
        "token_type": "Bearer",
    }
    out = repo.set(
        project_id=project_id,
        kind="gsc",
        plaintext_payload=json.dumps(bundle).encode("utf-8"),
        expires_at=expiring,
    )

    httpx_mock.add_response(
        method="POST",
        url=TOKEN_ENDPOINT,
        json={
            "access_token": "ya29.refreshed",
            "expires_in": 3600,
            "scope": "webmasters.readonly indexing",
            "token_type": "Bearer",
        },
    )

    async def go() -> dict:
        async with httpx.AsyncClient() as client:
            return await refresh_expiring_gsc_tokens(session, http=client)

    counter = asyncio.run(go())
    assert counter["checked"] == 1
    assert counter["refreshed"] == 1
    assert counter["failed"] == 0
    # The persisted bundle now has the new access token; refresh_token preserved.
    plaintext = repo.get_decrypted(out.data.id)
    new_bundle = json.loads(plaintext.decode("utf-8"))
    assert new_bundle["access_token"] == "ya29.refreshed"
    assert new_bundle["refresh_token"] == "1//rt-active"


def test_refresh_skips_rows_not_yet_expiring(
    httpx_mock: HTTPXMock,
    session: Session,
    project_id: int,
) -> None:
    """A row expiring far in the future is not refreshed."""
    repo = IntegrationCredentialRepository(session)
    distant = datetime.now(tz=UTC).replace(tzinfo=None) + timedelta(days=30)
    bundle = {
        "access_token": "ya29.long-lived",
        "refresh_token": "1//rt",
        "expires_at": distant.isoformat(),
    }
    repo.set(
        project_id=project_id,
        kind="gsc",
        plaintext_payload=json.dumps(bundle).encode("utf-8"),
        expires_at=distant,
    )

    async def go() -> dict:
        async with httpx.AsyncClient() as client:
            return await refresh_expiring_gsc_tokens(session, http=client)

    counter = asyncio.run(go())
    assert counter["refreshed"] == 0
    assert counter["checked"] == 1
    # No HTTP calls were made.
    assert len(httpx_mock.get_requests()) == 0
