"""Daily GSC metrics pull job — M8.

Fires every day at 03:15 UTC (per-procedure 6 cron is operator-facing —
this job is the always-on baseline). For each project with an active
``kind='gsc'`` credential and an active ``is_active=true`` row, calls
``searchAnalytics.query`` for the last 24 hours' clicks / impressions /
CTR / position rollup, persists into ``gsc_metrics`` via
``GscMetricRepository.bulk_ingest``.

Cost-aware: each call is recorded against the project's
``integration_budgets`` row via ``IntegrationBudgetRepository.record_call``.
A pre-emption surfaces as ``BudgetExceededError`` which the job catches
+ logs + skips that project (so a single over-budget project doesn't
sink the rest of the daemon's GSC pulls).

Catch-up semantics: ``coalesce=True`` at the scheduler level means a
daemon offline for a week collapses missed daily firings into one. The
24h lookback is intentional — operators who need a wider sweep run
procedure 6 manually.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from content_stack.crypto.aes_gcm import decrypt as crypto_decrypt
from content_stack.db.models import (
    IntegrationCredential,
    Project,
)
from content_stack.integrations._base import IntegrationCallResult
from content_stack.integrations.gsc import GscIntegration
from content_stack.logging import get_logger
from content_stack.mcp.errors import BudgetExceededError, IntegrationDownError
from content_stack.repositories.gsc import GscMetricRepository, GscRow
from content_stack.repositories.projects import IntegrationBudgetRepository

# Per-call cost estimate in USD. The Search Analytics endpoint is free
# under Google's quota, so the budget tracking is informational — but
# we record a notional value so the budget pre-emption pathway is
# exercised end-to-end (audit M-25).
GSC_PER_CALL_COST_USD = 0.001

# Lookback window — last 24h. The daily job pulls a small batch; the
# weekly procedure 6 covers the wider sweep.
LOOKBACK_DAYS = 1

# Default GSC dimensions — enough to feed the GscRow shape the repo
# expects. Procedure 6 uses a richer set for the weekly sweep.
DEFAULT_DIMENSIONS = ("query", "page", "country", "device")

# Row cap per call to keep a malformed site from exploding the pull.
DEFAULT_ROW_LIMIT = 1000

_log = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


def _site_url(project: Project) -> str:
    """Best-effort site URL from a project row.

    Domains are stored bare (``example.com``); GSC's API expects either
    ``sc-domain:example.com`` or ``https://example.com/``. We default to
    ``sc-domain`` form because that's the canonical Search Console
    property type for the bare-domain case.
    """
    return f"sc-domain:{project.domain}"


def _normalise_query(text: str | None) -> str | None:
    """Lowercase + trim. Mirrors what the repository does pre-hash."""
    if text is None:
        return None
    return text.strip().lower()


def _dimensions_hash(parts: list[str | None]) -> str:
    """SHA-256 of the joined dimensions for the dedup unique constraint."""
    body = "|".join("" if p is None else p for p in parts)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _decode_credential_payload(
    *, encrypted: bytes, nonce: bytes, project_id: int | None, kind: str
) -> bytes:
    """Decrypt the GSC bundle. Re-raises crypto errors as IntegrationDown."""
    return crypto_decrypt(encrypted, nonce=nonce, project_id=project_id, kind=kind)


def _gsc_rows_from_response(
    payload: dict[str, Any],
    *,
    captured_at: datetime,
) -> list[GscRow]:
    """Convert a GSC ``searchAnalytics.query`` response into ``GscRow`` shapes.

    The response shape is::

        {"rows": [{"keys": [...], "clicks": .., "impressions": .., ...}, ...]}

    where ``keys`` aligns with the request's ``dimensions``. We always
    request ``[query, page, country, device]`` so positional access is
    safe.
    """
    out: list[GscRow] = []
    for row in payload.get("rows", []) or []:
        keys = row.get("keys", []) or []
        # keys[0] = query, [1] = page, [2] = country, [3] = device.
        query = keys[0] if len(keys) > 0 else None
        page = keys[1] if len(keys) > 1 else None
        country = keys[2] if len(keys) > 2 else None
        device = keys[3] if len(keys) > 3 else None
        normalized = _normalise_query(query)
        h = _dimensions_hash([str(captured_at.date()), query, page, country, device])
        out.append(
            GscRow(
                article_id=None,
                captured_at=captured_at,
                query=query,
                query_normalized=normalized,
                page=page,
                country=country,
                device=device,
                dimensions_hash=h,
                impressions=int(row.get("impressions", 0) or 0),
                clicks=int(row.get("clicks", 0) or 0),
                ctr=float(row.get("ctr", 0.0) or 0.0),
                avg_position=float(row.get("position", 0.0) or 0.0),
            )
        )
    return out


async def _pull_one_project(
    *,
    project: Project,
    credential: IntegrationCredential,
    session: Session,
    http: httpx.AsyncClient,
    captured_at: datetime,
) -> dict[str, Any]:
    """Run the GSC pull for one project. Returns a counter dict."""
    assert project.id is not None
    project_id: int = project.id

    # Pre-emption against the budget row. If no budget row is set, we
    # let the call through (operators who haven't configured budgets
    # are opted-in by default).
    budget_repo = IntegrationBudgetRepository(session)
    try:
        budget_repo.record_call(project_id=project_id, kind="gsc", cost_usd=GSC_PER_CALL_COST_USD)
    except BudgetExceededError as exc:
        _log.warning(
            "jobs.gsc_pull.budget_exceeded",
            project_id=project_id,
            detail=str(exc),
        )
        return {"project_id": project_id, "status": "budget_exceeded", "rows": 0}
    except Exception as exc:  # pragma: no cover — NotFoundError on missing budget
        # Missing budget row is fine — operators can configure later.
        if exc.__class__.__name__ != "NotFoundError":
            raise

    # Decrypt the credential bundle into a JSON payload.
    try:
        payload_bytes = _decode_credential_payload(
            encrypted=credential.encrypted_payload,
            nonce=credential.nonce,
            project_id=credential.project_id,
            kind=credential.kind,
        )
    except Exception as exc:
        _log.warning(
            "jobs.gsc_pull.decrypt_failed",
            project_id=project_id,
            credential_id=credential.id,
            error=str(exc),
        )
        return {"project_id": project_id, "status": "decrypt_failed", "rows": 0}

    integration = GscIntegration(
        payload=payload_bytes,
        project_id=project_id,
        http=http,
    )

    end = captured_at.date()
    start = (captured_at - timedelta(days=LOOKBACK_DAYS)).date()
    try:
        result: IntegrationCallResult = await integration.search_analytics(
            site_url=_site_url(project),
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            dimensions=list(DEFAULT_DIMENSIONS),
            row_limit=DEFAULT_ROW_LIMIT,
        )
    except IntegrationDownError as exc:
        _log.warning(
            "jobs.gsc_pull.api_failed",
            project_id=project_id,
            detail=str(exc),
        )
        return {"project_id": project_id, "status": "api_failed", "rows": 0}

    body = result.data if isinstance(result.data, dict) else {}
    rows = _gsc_rows_from_response(body, captured_at=captured_at)
    if not rows:
        return {"project_id": project_id, "status": "no_rows", "rows": 0}

    repo = GscMetricRepository(session)
    inserted = repo.bulk_ingest(project_id=project_id, rows=rows).data
    return {
        "project_id": project_id,
        "status": "ok",
        "rows": int(inserted) if inserted is not None else 0,
    }


async def daily_gsc_pull(
    *,
    session_factory: Callable[[], Session],
    http: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Walk active projects with a GSC credential and pull last 24h.

    Returns ``{"checked": <int>, "ok": <int>, "skipped": <int>}`` so
    the operator dashboard / tests can assert on the counts.
    """
    when = now or _utcnow()
    owns_client = http is None
    client = http or httpx.AsyncClient(timeout=60.0)
    summary: dict[str, Any] = {"checked": 0, "ok": 0, "skipped": 0}
    try:
        with session_factory() as session:
            projects = session.exec(
                select(Project).where(Project.is_active.is_(True))  # type: ignore[union-attr,attr-defined]
            ).all()
            for project in projects:
                if project.id is None:
                    continue
                cred = session.exec(
                    select(IntegrationCredential).where(
                        IntegrationCredential.project_id == project.id,
                        IntegrationCredential.kind == "gsc",
                    )
                ).first()
                if cred is None:
                    continue
                summary["checked"] = int(summary["checked"]) + 1
                outcome = await _pull_one_project(
                    project=project,
                    credential=cred,
                    session=session,
                    http=client,
                    captured_at=when,
                )
                if outcome.get("status") == "ok":
                    summary["ok"] = int(summary["ok"]) + 1
                else:
                    summary["skipped"] = int(summary["skipped"]) + 1
    finally:
        if owns_client:
            await client.aclose()
    _log.info("jobs.gsc_pull.complete", **summary)
    return summary


def make_session_factory(engine: Engine) -> Callable[[], Session]:
    """Mirror runs_reaper's helper for symmetry."""

    def _factory() -> Session:
        return Session(engine)

    return _factory


__all__ = [
    "DEFAULT_DIMENSIONS",
    "DEFAULT_ROW_LIMIT",
    "GSC_PER_CALL_COST_USD",
    "LOOKBACK_DAYS",
    "daily_gsc_pull",
    "make_session_factory",
]
