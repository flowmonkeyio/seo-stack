"""Tests for GSC + DriftBaseline + Redirect repositories."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlmodel import Session

from content_stack.db.models import RedirectKind
from content_stack.repositories.gsc import (
    DriftBaselineRepository,
    GscMetricRepository,
    GscMetricsDailyRepository,
    GscRow,
    RedirectRepository,
)


def _now() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


def test_bulk_ingest_dedup(session: Session, project_id: int) -> None:
    """Audit M-12 dedup uses ``(project_id, article_id, captured_at, dimensions_hash)``.

    SQLite UNIQUE treats NULLs as distinct (one NULL never equals another),
    so the test pins ``article_id`` to a real article so the dedup index
    can fire. Real-world ingest always has ``article_id`` resolved by the
    GSC pull job (skill #20) before insert.
    """
    from content_stack.repositories.articles import ArticleRepository

    art_repo = ArticleRepository(session)
    art = art_repo.create(project_id=project_id, topic_id=None, title="A", slug="gsc-art").data
    repo = GscMetricRepository(session)
    captured = _now()
    rows = [
        GscRow(
            article_id=art.id,
            captured_at=captured,
            query="x",
            page="/p",
            dimensions_hash="hash-1",
            impressions=100,
            clicks=5,
            ctr=0.05,
            avg_position=3.5,
        ),
        # Duplicate — same dimensions_hash + captured_at + article_id → ignored.
        GscRow(
            article_id=art.id,
            captured_at=captured,
            query="x",
            page="/p",
            dimensions_hash="hash-1",
            impressions=200,
            clicks=10,
            ctr=0.05,
            avg_position=3.5,
        ),
    ]
    env = repo.bulk_ingest(project_id, rows)
    # Even though we sent 2 rows, only 1 is new.
    assert env.data == 1


def test_query_article_window(session: Session, project_id: int) -> None:
    repo = GscMetricRepository(session)
    # Ingest article-attached row.
    repo.bulk_ingest(
        project_id,
        [
            GscRow(
                article_id=None,
                captured_at=_now(),
                dimensions_hash="h-1",
            )
        ],
    )
    rows = repo.query_project(
        project_id, since=_now() - timedelta(hours=1), until=_now() + timedelta(hours=1)
    )
    assert len(rows) == 1


def test_rollup_aggregates(session: Session, project_id: int) -> None:
    raw = GscMetricRepository(session)
    daily = GscMetricsDailyRepository(session)
    today = date.today()
    capture = datetime(today.year, today.month, today.day, 12, 0)
    raw.bulk_ingest(
        project_id,
        [
            GscRow(
                captured_at=capture,
                dimensions_hash=f"hash-{i}",
                impressions=10,
                clicks=1,
                ctr=0.1,
                avg_position=4.0,
                query_normalized="kw",
            )
            for i in range(3)
        ],
    )
    env = daily.rollup(project_id, day=today)
    assert env.data == 1  # one (article_id=None) bucket written


def test_drift_snapshot(session: Session, project_id: int) -> None:
    from content_stack.repositories.articles import ArticleRepository

    art_repo = ArticleRepository(session)
    art = art_repo.create(project_id=project_id, topic_id=None, title="A", slug="drift-a").data
    repo = DriftBaselineRepository(session)
    out = repo.snapshot(article_id=art.id, baseline_md="# Original")
    assert out.data.baseline_md == "# Original"
    rows = repo.list(art.id)
    assert len(rows) == 1


def test_drift_diff_is_m5_stub(session: Session, project_id: int) -> None:
    repo = DriftBaselineRepository(session)
    with pytest.raises(NotImplementedError) as exc_info:
        repo.diff(baseline_id=1, current_md="x")
    assert "M5" in str(exc_info.value)


def test_redirect_lookup(session: Session, project_id: int) -> None:
    repo = RedirectRepository(session)
    repo.create(
        project_id=project_id,
        from_url="/old/page",
        to_article_id=None,
        kind=RedirectKind.R301,
    )
    found = repo.lookup(project_id=project_id, from_url="/old/page")
    assert found is not None
    assert found.kind == RedirectKind.R301
    not_found = repo.lookup(project_id=project_id, from_url="/no")
    assert not_found is None
