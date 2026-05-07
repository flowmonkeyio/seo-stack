"""Auth bootstrap endpoint tests — ``GET /api/v1/auth/ui-token``.

This endpoint is whitelisted from bearer-token auth so the same-origin
Vue UI can bootstrap its token at boot. The HostHeaderMiddleware (loopback
only) and CORSMiddleware (same-origin) are the upstream defences.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_ui_token_returns_token_without_authorization(
    client: TestClient,
    auth_token: str,
) -> None:
    """The UI calls this endpoint *before* it has a token; whitelist required."""
    resp = client.get("/api/v1/auth/ui-token")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"token": auth_token}


def test_ui_token_is_in_auth_whitelist() -> None:
    """Module-level invariant: the new path is in WHITELIST_PREFIXES."""
    from content_stack.auth import WHITELIST_PREFIXES, requires_auth

    assert "/api/v1/auth/ui-token" in WHITELIST_PREFIXES
    assert requires_auth("/api/v1/auth/ui-token") is False


def test_ui_token_rejects_non_loopback_host(client: TestClient) -> None:
    """HostHeaderMiddleware still runs for whitelisted paths — non-loopback → 421."""
    resp = client.get(
        "/api/v1/auth/ui-token",
        headers={"host": "evil.example.com"},
    )
    assert resp.status_code == 421


def test_ui_token_response_shape_only_carries_token(
    client: TestClient,
    auth_token: str,
) -> None:
    """Body must be ``{token: str}`` exactly — no leakage of other state.

    Guards against accidentally exposing settings or app-state internals
    via the bootstrap response.
    """
    resp = client.get("/api/v1/auth/ui-token")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"token"}
    assert body["token"] == auth_token
    assert isinstance(body["token"], str)
    assert len(body["token"]) > 0
