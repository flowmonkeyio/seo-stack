"""GSC OAuth-token refresh job (PLAN.md L1090-L1096).

Walks every ``integration_credentials`` row with ``kind='gsc'`` whose
``expires_at`` is within 10 minutes of now, refreshes the access token
via the ``refresh_token`` grant, re-encrypts the new bundle, and
updates ``expires_at`` + ``last_refreshed_at``.

In M4 the job is exposed via:

- ``python -m content_stack.jobs.oauth_refresh --once`` for ad-hoc
  operator use (also wired via ``make oauth-refresh``).
- An import-side hook for M8 to register against APScheduler.

We never log the refresh-token value; the structlog event reports the
shape (length + first 4 chars) so a botched refresh is debuggable
without leaking the secret.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlmodel import Session, select

from content_stack.config import get_settings
from content_stack.crypto.aes_gcm import (
    configure_seed_path,
)
from content_stack.crypto.aes_gcm import (
    decrypt as crypto_decrypt,
)
from content_stack.crypto.aes_gcm import (
    encrypt as crypto_encrypt,
)
from content_stack.db.connection import make_engine
from content_stack.db.models import IntegrationCredential
from content_stack.integrations.gsc import refresh_access_token
from content_stack.logging import configure_logging, get_logger

# Lead time before expiry — refresh anything expiring within 10 minutes.
REFRESH_LEAD_TIME = timedelta(minutes=10)

_log = get_logger(__name__)


def _now_utc() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


def _shape_token(token: str) -> str:
    """Return a redacted shape for logging.

    Format: ``<length>:<first 4 chars>...``. Never the full secret.
    """
    if not token:
        return "<empty>"
    return f"len={len(token)}:prefix={token[:4]!r}"


async def _refresh_one(
    session: Session,
    row: IntegrationCredential,
    *,
    http: httpx.AsyncClient,
) -> bool:
    """Refresh a single GSC credential row.

    Returns ``True`` on success; logs a warning + returns ``False`` on
    failure so the loop continues with the remaining rows. We never let
    an exception abort the whole job — one bad refresh shouldn't take
    down the worker.
    """
    try:
        plaintext = crypto_decrypt(
            row.encrypted_payload,
            nonce=row.nonce,
            project_id=row.project_id,
            kind=row.kind,
        )
        bundle: dict[str, Any] = json.loads(plaintext.decode("utf-8"))
        refresh_token = bundle.get("refresh_token")
        if not refresh_token:
            _log.warning(
                "oauth_refresh.no_refresh_token",
                credential_id=row.id,
                project_id=row.project_id,
            )
            return False
        new_tokens = await refresh_access_token(refresh_token=refresh_token, http=http)
        # Merge: Google may not return a new ``refresh_token``; preserve
        # the existing one in that case.
        merged = dict(bundle)
        merged.update({k: v for k, v in new_tokens.items() if v is not None})
        merged.setdefault("refresh_token", refresh_token)
        new_payload, new_nonce = crypto_encrypt(
            json.dumps(merged).encode("utf-8"),
            project_id=row.project_id,
            kind=row.kind,
        )
        # Compute the new expires_at if the token endpoint reported one.
        new_expires_at: datetime | None = None
        if "expires_at" in merged:
            try:
                # ISO timestamp from ``exchange_code`` / ``refresh_access_token``.
                expires_iso = str(merged["expires_at"])
                new_expires_at = datetime.fromisoformat(expires_iso.rstrip("Z"))
            except ValueError:
                new_expires_at = None

        row.encrypted_payload = new_payload
        row.nonce = new_nonce
        row.expires_at = new_expires_at
        row.last_refreshed_at = _now_utc()
        session.add(row)
        session.commit()

        _log.info(
            "oauth_refresh.success",
            credential_id=row.id,
            project_id=row.project_id,
            new_access_token=_shape_token(str(merged.get("access_token", ""))),
            new_expires_at=str(new_expires_at) if new_expires_at else None,
        )
        return True
    except Exception as exc:  # pragma: no cover — defensive
        _log.warning(
            "oauth_refresh.failure",
            credential_id=row.id,
            project_id=row.project_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        session.rollback()
        return False


async def refresh_expiring_gsc_tokens(
    session: Session,
    *,
    now: datetime | None = None,
    http: httpx.AsyncClient | None = None,
) -> dict[str, int]:
    """Refresh every GSC credential expiring within ``REFRESH_LEAD_TIME``.

    Returns a counter dict ``{"checked", "refreshed", "failed"}``.

    The ``http`` client is injected for tests (``pytest-httpx``); in
    production the job creates its own short-lived client.
    """
    when = now or _now_utc()
    cutoff = when + REFRESH_LEAD_TIME

    rows = session.exec(
        select(IntegrationCredential).where(
            IntegrationCredential.kind == "gsc",
        )
    ).all()

    expiring = [r for r in rows if r.expires_at is not None and r.expires_at <= cutoff]

    refreshed = 0
    failed = 0
    owns_client = http is None
    client = http or httpx.AsyncClient(timeout=30.0)
    try:
        for row in expiring:
            ok = await _refresh_one(session, row, http=client)
            if ok:
                refreshed += 1
            else:
                failed += 1
    finally:
        if owns_client:
            await client.aclose()

    counter = {"checked": len(rows), "refreshed": refreshed, "failed": failed}
    _log.info("oauth_refresh.complete", **counter)
    return counter


def _run_once() -> int:
    """CLI entrypoint used by ``make oauth-refresh``."""
    settings = get_settings()
    settings.ensure_dirs()
    configure_logging(log_path=settings.log_path, level=settings.log_level)
    configure_seed_path(settings.seed_path)
    engine = make_engine(settings.db_path)
    try:
        with Session(engine) as session:
            counter = asyncio.run(refresh_expiring_gsc_tokens(session))
        print(
            f"oauth_refresh: checked={counter['checked']} "
            f"refreshed={counter['refreshed']} failed={counter['failed']}",
            flush=True,
        )
        return 0 if counter["failed"] == 0 else 1
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh expiring GSC OAuth tokens")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single refresh pass and exit (default; only flag supported in M4).",
    )
    args = parser.parse_args(argv)
    if args.once or argv is None:
        return _run_once()
    # M8 will add a long-running daemon mode (--watch); for M4 we always
    # execute once even without ``--once`` so ``make oauth-refresh`` is
    # the same shape as the future scheduled invocation.
    return _run_once()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = [
    "REFRESH_LEAD_TIME",
    "main",
    "refresh_expiring_gsc_tokens",
]
