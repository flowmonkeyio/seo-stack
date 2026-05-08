"""Daily drift / GSC rollup job — M8.

Per audit M-01: every day at 04:00 UTC (after the daily GSC pull at
03:15) we aggregate yesterday's raw ``gsc_metrics`` rows into the
``gsc_metrics_daily`` rollup, then prune raw rows older than 90 days.

The rollup grain is ``(project_id, article_id, day)`` — already
implemented in ``GscMetricsDailyRepository.rollup``. This job iterates
across active projects and calls that repository method per project for
yesterday's date.

Retention: per audit M-01 raw ``gsc_metrics`` rows older than 90 days
are deleted *after* a successful rollup. This keeps the raw table from
growing without bound while preserving the daily rollup for long-term
analysis.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, delete, select

from content_stack.db.models import GscMetric, Project
from content_stack.logging import get_logger
from content_stack.repositories.gsc import GscMetricsDailyRepository

# Audit M-01: 90-day retention on raw gsc_metrics rows.
RAW_RETENTION_DAYS = 90

_log = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


async def daily_drift_rollup(
    *,
    session_factory: Callable[[], Session],
    now: datetime | None = None,
    rollup_for: date | None = None,
) -> dict[str, Any]:
    """Aggregate yesterday's raw GSC rows into daily rollups + prune retention.

    Returns ``{"rolled_up_projects": int, "rows_pruned": int}``.

    ``rollup_for`` lets tests target a specific date; production passes
    ``None`` and we use yesterday relative to ``now``.
    """
    when = now or _utcnow()
    target_day = rollup_for or (when - timedelta(days=1)).date()
    cutoff_dt = when - timedelta(days=RAW_RETENTION_DAYS)

    rolled_projects = 0
    with session_factory() as session:
        projects = session.exec(
            select(Project).where(Project.is_active.is_(True))  # type: ignore[union-attr,attr-defined]
        ).all()
        for project in projects:
            if project.id is None:
                continue
            repo = GscMetricsDailyRepository(session)
            try:
                env = repo.rollup(project.id, day=target_day)
                if env.data and env.data > 0:
                    rolled_projects += 1
            except Exception as exc:  # pragma: no cover — defensive
                _log.warning(
                    "jobs.drift_rollup.project_failed",
                    project_id=project.id,
                    error=str(exc),
                )
                continue

        # Retention prune. Single delete statement so it runs in O(1)
        # round trips regardless of row count. SQLite ``DELETE`` honours
        # the timestamp comparator natively.
        delete_stmt = delete(GscMetric).where(GscMetric.captured_at < cutoff_dt)  # type: ignore[arg-type]
        result = session.exec(delete_stmt)  # type: ignore[call-overload]
        rows_pruned = getattr(result, "rowcount", 0) or 0
        session.commit()

    summary = {
        "rolled_up_projects": rolled_projects,
        "rows_pruned": int(rows_pruned),
        "target_day": target_day.isoformat(),
    }
    _log.info("jobs.drift_rollup.complete", **summary)
    return summary


def make_session_factory(engine: Engine) -> Callable[[], Session]:
    """Mirror runs_reaper's helper."""

    def _factory() -> Session:
        return Session(engine)

    return _factory


__all__ = [
    "RAW_RETENTION_DAYS",
    "daily_drift_rollup",
    "make_session_factory",
]
