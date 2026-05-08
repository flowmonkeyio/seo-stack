"""Daily drift / GSC rollup job — aggregation + 90d retention."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from content_stack.db.models import GscMetric, GscMetricDaily, Project
from content_stack.jobs.drift_rollup import (
    RAW_RETENTION_DAYS,
    daily_drift_rollup,
    make_session_factory,
)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


def _seed_active_project(session: Session, *, slug: str = "drift-test") -> int:
    project = Project(
        slug=slug,
        name="drift test",
        domain=f"{slug}.example.com",
        locale="en-US",
        is_active=True,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    assert project.id is not None
    return project.id


def _seed_metric(
    session: Session,
    *,
    project_id: int,
    captured_at: datetime,
    impressions: int = 100,
    clicks: int = 5,
) -> None:
    row = GscMetric(
        project_id=project_id,
        article_id=None,
        captured_at=captured_at,
        query="test query",
        query_normalized="test query",
        page="/test",
        country="us",
        device="desktop",
        dimensions_hash=f"hash-{captured_at.isoformat()}-{impressions}",
        impressions=impressions,
        clicks=clicks,
        ctr=clicks / impressions if impressions else 0.0,
        avg_position=5.0,
    )
    session.add(row)
    session.commit()


async def test_drift_rollup_aggregates_yesterday(engine: object) -> None:
    """Yesterday's raw rows roll up into one daily row per project."""
    yesterday = _utcnow() - timedelta(days=1)
    with Session(engine) as s:  # type: ignore[arg-type]
        pid = _seed_active_project(s, slug="rollup-1")
        _seed_metric(s, project_id=pid, captured_at=yesterday, impressions=100, clicks=5)
        _seed_metric(s, project_id=pid, captured_at=yesterday, impressions=80, clicks=3)

    summary = await daily_drift_rollup(
        session_factory=make_session_factory(engine),  # type: ignore[arg-type]
    )
    assert summary["rolled_up_projects"] >= 1

    with Session(engine) as s:  # type: ignore[arg-type]
        rows = s.exec(select(GscMetricDaily).where(GscMetricDaily.project_id == pid)).all()
    assert len(rows) >= 1
    daily = rows[0]
    assert daily.impressions_sum == 180
    assert daily.clicks_sum == 8


async def test_drift_rollup_prunes_old_raw_rows(engine: object) -> None:
    """Rows older than 90 days are deleted after rollup."""
    far_past = _utcnow() - timedelta(days=RAW_RETENTION_DAYS + 5)
    yesterday = _utcnow() - timedelta(days=1)
    with Session(engine) as s:  # type: ignore[arg-type]
        pid = _seed_active_project(s, slug="rollup-prune")
        _seed_metric(s, project_id=pid, captured_at=far_past, impressions=999, clicks=99)
        _seed_metric(s, project_id=pid, captured_at=yesterday)

    summary = await daily_drift_rollup(
        session_factory=make_session_factory(engine),  # type: ignore[arg-type]
    )
    assert summary["rows_pruned"] >= 1

    with Session(engine) as s:  # type: ignore[arg-type]
        old = s.exec(
            select(GscMetric).where(
                GscMetric.captured_at < _utcnow() - timedelta(days=RAW_RETENTION_DAYS)
            )
        ).all()
    assert old == []


async def test_drift_rollup_skips_inactive_projects(engine: object) -> None:
    """``is_active=False`` projects don't get rolled up."""
    yesterday = _utcnow() - timedelta(days=1)
    with Session(engine) as s:  # type: ignore[arg-type]
        # Inactive project (is_active=False default).
        inactive = Project(
            slug="inactive-rollup",
            name="inactive",
            domain="inactive.example",
            locale="en-US",
            is_active=False,
        )
        s.add(inactive)
        s.commit()
        s.refresh(inactive)
        assert inactive.id is not None
        _seed_metric(s, project_id=inactive.id, captured_at=yesterday)

    summary = await daily_drift_rollup(
        session_factory=make_session_factory(engine),  # type: ignore[arg-type]
    )
    # No active projects → 0 rolled up.
    assert summary["rolled_up_projects"] == 0
