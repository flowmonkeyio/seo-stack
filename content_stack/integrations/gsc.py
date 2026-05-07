"""Google Search Console + Indexing API + PageSpeed Insights wrapper.

Authentication: OAuth 2.0 with the ``access_token`` + ``refresh_token``
pair persisted in the ``gsc`` credential row's ``encrypted_payload``
(JSON-encoded). The payload shape is::

    {
      "access_token": str,
      "refresh_token": str,
      "expires_at": str,           # ISO8601 UTC
      "scope": str,
      "token_type": "Bearer"
    }

The OAuth client credentials (``client_id`` + ``client_secret``) come
from the ``GSC_OAUTH_CLIENT_ID`` / ``GSC_OAUTH_CLIENT_SECRET`` env vars
— the operator creates them in their *own* Google Cloud project, so we
never see a ``content-stack``-branded client and Google's quotas apply
per operator (PLAN.md L1069-L1080).

Operations:

- ``search_analytics(site, start, end, dimensions)`` — clicks /
  impressions / CTR / position rollup.
- ``inspect_url(site, url)`` — single-URL Inspection API.
- ``bulk_inspect(site, urls)`` — fan-out N inspect_url calls (Indexing
  API has no bulk endpoint).
- ``submit_indexing(url, type)`` — Indexing API ``URL_UPDATED`` ping.
- ``pagespeed(url, strategy)`` — PageSpeed Insights LCP/INP/CLS.

OAuth helpers (used by the API router + ``oauth_refresh`` job):

- ``build_authorize_url(state, redirect_uri)`` — returns the consent URL
  the browser opens.
- ``exchange_code(code, redirect_uri)`` — code → token bundle.
- ``refresh_access_token(refresh_token)`` — refresh-token grant.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from content_stack.integrations._base import BaseIntegration, IntegrationCallResult
from content_stack.mcp.errors import IntegrationDownError

# Google OAuth + API endpoints. Centralised so tests can monkey-patch.
AUTHORIZE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
SEARCH_CONSOLE_BASE = "https://searchconsole.googleapis.com/webmasters/v3"
SEARCH_CONSOLE_INSPECT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
INDEXING_API_BASE = "https://indexing.googleapis.com/v3/urlNotifications:publish"
PAGESPEED_BASE = "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"

# Scopes required by every supported op.
GSC_SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/indexing",
]


def _now_utc() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


def _expires_at_iso(seconds_from_now: int) -> str:
    """Build an ISO8601 (naive UTC) string ``seconds_from_now`` ahead."""
    expires = _now_utc() + timedelta(seconds=seconds_from_now)
    return expires.isoformat()


# ---------------------------------------------------------------------------
# OAuth helpers — used by the REST router + the refresh job.
# ---------------------------------------------------------------------------


def get_client_credentials() -> tuple[str, str]:
    """Return ``(client_id, client_secret)`` from env vars.

    Raises ``IntegrationDownError`` (with hint to docs/api-keys.md) if
    either is missing — the operator must configure the OAuth client in
    their Google Cloud project before any GSC traffic flows.
    """
    client_id = os.environ.get("GSC_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GSC_OAUTH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise IntegrationDownError(
            "GSC OAuth client not configured — set GSC_OAUTH_CLIENT_ID + "
            "GSC_OAUTH_CLIENT_SECRET environment variables (12-step setup in "
            "docs/api-keys.md)",
            data={
                "vendor": "gsc",
                "missing": [
                    name
                    for name, val in [
                        ("GSC_OAUTH_CLIENT_ID", client_id),
                        ("GSC_OAUTH_CLIENT_SECRET", client_secret),
                    ]
                    if not val
                ],
                "hint": "docs/api-keys.md — Google Search Console section",
            },
        )
    return client_id, client_secret


def build_authorize_url(*, state: str, redirect_uri: str) -> str:
    """Return the Google OAuth consent URL.

    The operator's browser opens this; on consent Google redirects back
    to the daemon's ``/api/v1/integrations/gsc/oauth/callback`` with
    ``code`` + ``state``.
    """
    client_id, _ = get_client_credentials()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GSC_SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # forces refresh_token issuance
        "state": state,
    }
    return f"{AUTHORIZE_ENDPOINT}?{urlencode(params)}"


async def exchange_code(
    *,
    code: str,
    redirect_uri: str,
    http: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Exchange an OAuth authorization code for an access + refresh token.

    Raises ``IntegrationDownError`` on a non-200 token response so the
    callback handler returns a typed error rather than a 500.
    """
    client_id, client_secret = get_client_credentials()
    body = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    owns_client = http is None
    client = http or httpx.AsyncClient(timeout=30.0)
    try:
        resp = await client.post(TOKEN_ENDPOINT, data=body)
    finally:
        if owns_client:
            await client.aclose()
    if resp.status_code != 200:
        raise IntegrationDownError(
            f"GSC token exchange failed ({resp.status_code}): {resp.text[:300]}",
            data={"vendor": "gsc", "status": resp.status_code, "op": "exchange_code"},
        )
    payload = resp.json()
    # Normalise the timestamp: Google reports ``expires_in`` (seconds);
    # we persist ``expires_at`` (ISO timestamp) so the refresh worker
    # can compare without recomputing.
    if "expires_in" in payload and "expires_at" not in payload:
        payload["expires_at"] = _expires_at_iso(int(payload["expires_in"]))
    return payload


async def refresh_access_token(
    *,
    refresh_token: str,
    http: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Refresh-token grant; returns a new ``access_token`` + ``expires_at``.

    Note that Google does not (always) return a fresh ``refresh_token`` —
    the caller merges the new fields into the existing bundle.
    """
    client_id, client_secret = get_client_credentials()
    body = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    owns_client = http is None
    client = http or httpx.AsyncClient(timeout=30.0)
    try:
        resp = await client.post(TOKEN_ENDPOINT, data=body)
    finally:
        if owns_client:
            await client.aclose()
    if resp.status_code != 200:
        raise IntegrationDownError(
            f"GSC token refresh failed ({resp.status_code}): {resp.text[:300]}",
            data={
                "vendor": "gsc",
                "status": resp.status_code,
                "op": "refresh_access_token",
            },
        )
    payload = resp.json()
    if "expires_in" in payload and "expires_at" not in payload:
        payload["expires_at"] = _expires_at_iso(int(payload["expires_in"]))
    return payload


# ---------------------------------------------------------------------------
# Vendor wrapper.
# ---------------------------------------------------------------------------


class GscIntegration(BaseIntegration):
    """Wrapper for the GSC family of APIs."""

    kind = "gsc"
    vendor = "gsc"
    default_qps = 1.0

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Decode the JSON token bundle once at construct time.
        try:
            self._tokens: dict[str, Any] = json.loads(self.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise IntegrationDownError(
                "GSC credential payload is not valid JSON; re-run the OAuth flow",
                data={"vendor": "gsc"},
            ) from exc

    def _bearer_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._tokens['access_token']}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Public ops.
    # ------------------------------------------------------------------

    async def search_analytics(
        self,
        *,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: list[str] | None = None,
        row_limit: int = 1000,
    ) -> IntegrationCallResult:
        """``searchanalytics.query`` — clicks/impressions/CTR/position."""
        from urllib.parse import quote

        body: dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "rowLimit": row_limit,
        }
        if dimensions:
            body["dimensions"] = dimensions
        url = f"{SEARCH_CONSOLE_BASE}/sites/{quote(site_url, safe='')}/searchAnalytics/query"
        return await self.call(
            op="search_analytics",
            method="POST",
            url=url,
            json_body=body,
            headers=self._bearer_headers(),
        )

    async def inspect_url(
        self,
        *,
        site_url: str,
        inspection_url: str,
    ) -> IntegrationCallResult:
        """URL Inspection API — coverage, indexing, mobile usability."""
        body = {
            "inspectionUrl": inspection_url,
            "siteUrl": site_url,
        }
        return await self.call(
            op="inspect_url",
            method="POST",
            url=SEARCH_CONSOLE_INSPECT,
            json_body=body,
            headers=self._bearer_headers(),
        )

    async def bulk_inspect(
        self,
        *,
        site_url: str,
        urls: list[str],
    ) -> list[IntegrationCallResult]:
        """Fan out ``inspect_url`` over a list (no bulk endpoint exists).

        Returns a list of ``IntegrationCallResult`` so the caller can
        aggregate per-URL rather than getting a homogenised bundle.
        """
        results: list[IntegrationCallResult] = []
        for u in urls:
            results.append(await self.inspect_url(site_url=site_url, inspection_url=u))
        return results

    async def submit_indexing(
        self,
        *,
        url: str,
        kind: str = "URL_UPDATED",
    ) -> IntegrationCallResult:
        """Indexing API ping — ``URL_UPDATED`` or ``URL_DELETED``."""
        body = {"url": url, "type": kind}
        return await self.call(
            op="submit_indexing",
            method="POST",
            url=INDEXING_API_BASE,
            json_body=body,
            headers=self._bearer_headers(),
        )

    async def pagespeed(
        self,
        *,
        url: str,
        strategy: str = "mobile",
    ) -> IntegrationCallResult:
        """PageSpeed Insights — LCP / INP / CLS / FCP / SI / TBT."""
        # PSI uses an API key; we share the access_token-bearing client
        # for simplicity, but PSI itself accepts no auth on the free
        # tier. We still go through the rate-limited base.
        params: dict[str, Any] = {"url": url, "strategy": strategy}
        # If the caller has a PSI API key in env, pass it along; PSI
        # tolerates absence on the public tier.
        psi_key = os.environ.get("PAGESPEED_API_KEY")
        if psi_key:
            params["key"] = psi_key
        return await self.call(
            op="pagespeed",
            method="GET",
            url=PAGESPEED_BASE,
            params=params,
        )

    # ------------------------------------------------------------------
    # Health check.
    # ------------------------------------------------------------------

    async def test_credentials(self) -> dict[str, Any]:
        """Verify auth via a tiny ``searchanalytics.query``.

        Per PLAN.md L1080: a 401 surfaces as "re-auth needed".
        """
        # Use a placeholder ``site_url`` only when one is in config —
        # otherwise this probe lists sites which doesn't require a
        # specific site.
        url = f"{SEARCH_CONSOLE_BASE}/sites"
        result = await self.call(
            op="test",
            method="GET",
            url=url,
            headers=self._bearer_headers(),
        )
        return {"ok": True, "vendor": "gsc", "sites_count": len(result.data.get("siteEntry", []))}


__all__ = [
    "AUTHORIZE_ENDPOINT",
    "GSC_SCOPES",
    "TOKEN_ENDPOINT",
    "GscIntegration",
    "build_authorize_url",
    "exchange_code",
    "get_client_credentials",
    "refresh_access_token",
]
