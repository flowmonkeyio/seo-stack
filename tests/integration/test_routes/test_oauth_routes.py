"""GSC OAuth REST flow — authorize → callback → encrypted credential."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pytest_httpx import HTTPXMock


@pytest.fixture(autouse=True)
def _set_oauth_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GSC_OAUTH_CLIENT_ID", "client-id-fake")
    monkeypatch.setenv("GSC_OAUTH_CLIENT_SECRET", "client-secret-fake")


def test_authorize_returns_url_and_state(api: TestClient, project_id: int) -> None:
    """``POST /authorize`` returns a Google consent URL with a state nonce."""
    resp = api.post(
        "/api/v1/integrations/gsc/oauth/authorize",
        json={"project_id": project_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["authorization_url"].startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert body["state"]
    assert "client_id=client-id-fake" in body["authorization_url"]


def test_callback_exchanges_code_and_persists_tokens(
    api: TestClient,
    project_id: int,
    httpx_mock: HTTPXMock,
) -> None:
    """``GET /callback`` exchanges the code, encrypts the bundle, returns 200 HTML."""
    # First authorize so the state nonce + redirect_uri are persisted.
    auth = api.post(
        "/api/v1/integrations/gsc/oauth/authorize",
        json={"project_id": project_id},
    )
    state = auth.json()["state"]

    httpx_mock.add_response(
        method="POST",
        url="https://oauth2.googleapis.com/token",
        json={
            "access_token": "ya29.live",
            "refresh_token": "1//rt-live",
            "expires_in": 3600,
            "scope": "webmasters.readonly indexing",
            "token_type": "Bearer",
        },
    )

    resp = api.get(
        "/api/v1/integrations/gsc/oauth/callback",
        params={"code": "auth-code-789", "state": state},
    )
    assert resp.status_code == 200
    assert "GSC connected" in resp.text or "you can close this tab" in resp.text.lower()

    # The credential row was upserted with encrypted token bundle.
    creds = api.get(f"/api/v1/projects/{project_id}/integrations").json()
    gsc_rows = [c for c in creds if c["kind"] == "gsc"]
    assert len(gsc_rows) == 1
    # The state is removed from the persisted config_json (no leak).
    config = gsc_rows[0]["config_json"] or {}
    assert "oauth_state" not in config


def test_callback_accepts_browser_redirect_without_bearer_header(
    api: TestClient,
    project_id: int,
    httpx_mock: HTTPXMock,
) -> None:
    """Google redirects a normal browser tab, so no Authorization header is present."""
    auth = api.post(
        "/api/v1/integrations/gsc/oauth/authorize",
        json={"project_id": project_id},
    )
    state = auth.json()["state"]
    httpx_mock.add_response(
        method="POST",
        url="https://oauth2.googleapis.com/token",
        json={
            "access_token": "ya29.browser",
            "refresh_token": "1//rt-browser",
            "expires_in": 3600,
            "scope": "webmasters.readonly indexing",
            "token_type": "Bearer",
        },
    )

    api.headers.pop("Authorization", None)
    resp = api.get(
        "/api/v1/integrations/gsc/oauth/callback",
        params={"code": "auth-code-browser", "state": state},
    )
    assert resp.status_code == 200


def test_callback_rejects_state_mismatch(api: TestClient, project_id: int) -> None:
    """A mismatched state nonce → 400 (not 200)."""
    api.post(
        "/api/v1/integrations/gsc/oauth/authorize",
        json={"project_id": project_id},
    )
    resp = api.get(
        "/api/v1/integrations/gsc/oauth/callback",
        params={"code": "x", "state": "wrong-nonce"},
    )
    assert resp.status_code == 400
