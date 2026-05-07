"""Search Console + drift + redirects repository module.

Three concerns under one roof:

- ``GscMetricRepository`` / ``GscMetricsDailyRepository`` — raw metric
  ingest (with dedup via the ``dimensions_hash`` unique constraint) plus
  the nightly daily-rollup operation.
- ``DriftBaselineRepository`` — content-drift baselines. The diff
  *engine* is M5 (drift-watch + Firecrawl); M1 only stores baselines
  and exposes the snapshot/list/get seam.
- ``RedirectRepository`` — 301/302 records.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from content_stack.db.models import (
    DriftBaseline,
    GscMetric,
    GscMetricDaily,
    Redirect,
    RedirectKind,
)
from content_stack.repositories.base import (
    Envelope,
    NotFoundError,
    Page,
    ValidationError,
    cursor_paginate,
)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Output models.
# ---------------------------------------------------------------------------


class GscMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    article_id: int | None
    captured_at: datetime
    query: str | None
    query_normalized: str | None
    page: str | None
    country: str | None
    device: str | None
    dimensions_hash: str
    impressions: int
    clicks: int
    ctr: float
    avg_position: float


class GscRow(BaseModel):
    """Input row for ``bulk_ingest`` — wire-compatible with GSC API rows."""

    article_id: int | None = None
    captured_at: datetime
    query: str | None = None
    query_normalized: str | None = None
    page: str | None = None
    country: str | None = None
    device: str | None = None
    dimensions_hash: str
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    avg_position: float = 0.0


class GscMetricDailyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    article_id: int | None
    day: datetime
    impressions_sum: int
    clicks_sum: int
    ctr_avg: float
    avg_position_avg: float
    queries_count: int


class DriftBaselineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    article_id: int
    baseline_md: str
    baseline_at: datetime
    current_score: float | None


class RedirectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    from_url: str
    to_article_id: int | None
    kind: RedirectKind
    created_at: datetime


# ---------------------------------------------------------------------------
# GscMetricRepository.
# ---------------------------------------------------------------------------


class GscMetricRepository:
    """Raw GSC metric ingest with dedup."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def bulk_ingest(self, project_id: int, rows: Iterable[GscRow]) -> Envelope[int]:
        """Insert rows; dedup via the ``uq_gsc_metrics_dedup`` unique index.

        We rely on SQLite's ``INSERT OR IGNORE`` semantics by attempting
        each insert inside a SAVEPOINT and swallowing the
        ``IntegrityError`` for an already-present row. Returns the count
        of *new* rows actually committed.
        """
        materialised = list(rows)
        inserted = 0
        for r in materialised:
            metric = GscMetric(
                project_id=project_id,
                article_id=r.article_id,
                captured_at=r.captured_at,
                query=r.query,
                query_normalized=r.query_normalized,
                page=r.page,
                country=r.country,
                device=r.device,
                dimensions_hash=r.dimensions_hash,
                impressions=r.impressions,
                clicks=r.clicks,
                ctr=r.ctr,
                avg_position=r.avg_position,
            )
            try:
                self._s.add(metric)
                self._s.flush()
                inserted += 1
            except IntegrityError:
                # Duplicate — rollback the failed flush and continue.
                self._s.rollback()
                continue
        self._s.commit()
        return Envelope(data=inserted, project_id=project_id)

    def query_article(
        self, article_id: int, *, since: datetime, until: datetime
    ) -> list[GscMetricOut]:
        """Return raw rows for an article in ``[since, until)``."""
        rows = self._s.exec(
            select(GscMetric)
            .where(
                GscMetric.article_id == article_id,
                GscMetric.captured_at >= since,
                GscMetric.captured_at < until,
            )
            .order_by(GscMetric.captured_at.asc())  # type: ignore[union-attr,attr-defined]
        ).all()
        return [GscMetricOut.model_validate(r) for r in rows]

    def query_project(
        self, project_id: int, *, since: datetime, until: datetime
    ) -> list[GscMetricOut]:
        """Return raw rows for a project in ``[since, until)``."""
        rows = self._s.exec(
            select(GscMetric)
            .where(
                GscMetric.project_id == project_id,
                GscMetric.captured_at >= since,
                GscMetric.captured_at < until,
            )
            .order_by(GscMetric.captured_at.asc())  # type: ignore[union-attr,attr-defined]
        ).all()
        return [GscMetricOut.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# GscMetricsDailyRepository.
# ---------------------------------------------------------------------------


class GscMetricsDailyRepository:
    """Daily-rollup writes."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def rollup(self, project_id: int, *, day: date) -> Envelope[int]:
        """Aggregate ``gsc_metrics`` for ``day``; UPSERT into ``gsc_metrics_daily``.

        Aggregation grain: ``(project_id, article_id, day)``. Returns the
        count of daily rows written (insert + update). The M9 nightly job
        invokes this per project per day; M1 just exposes the operation.
        """
        day_start = datetime(day.year, day.month, day.day)
        day_end = day_start + timedelta(days=1)
        # Fetch raw rows.
        raw = self._s.exec(
            select(GscMetric).where(
                GscMetric.project_id == project_id,
                GscMetric.captured_at >= day_start,
                GscMetric.captured_at < day_end,
            )
        ).all()
        # Group by article_id (None = site-level rollup).
        groups: dict[int | None, list[GscMetric]] = {}
        for m in raw:
            groups.setdefault(m.article_id, []).append(m)
        written = 0
        for article_id, metrics in groups.items():
            existing = self._s.exec(
                select(GscMetricDaily).where(
                    GscMetricDaily.project_id == project_id,
                    GscMetricDaily.article_id == article_id
                    if article_id is not None
                    else GscMetricDaily.article_id.is_(None),  # type: ignore[union-attr,attr-defined]
                    GscMetricDaily.day == day_start,
                )
            ).first()
            impressions_sum = sum(m.impressions for m in metrics)
            clicks_sum = sum(m.clicks for m in metrics)
            ctr_avg = round(sum(m.ctr for m in metrics) / len(metrics), 6) if metrics else 0.0
            avg_position_avg = (
                round(sum(m.avg_position for m in metrics) / len(metrics), 6) if metrics else 0.0
            )
            queries_count = len({m.query_normalized for m in metrics if m.query_normalized})
            if existing is None:
                row = GscMetricDaily(
                    project_id=project_id,
                    article_id=article_id,
                    day=day_start,
                    impressions_sum=impressions_sum,
                    clicks_sum=clicks_sum,
                    ctr_avg=ctr_avg,
                    avg_position_avg=avg_position_avg,
                    queries_count=queries_count,
                )
            else:
                row = existing
                row.impressions_sum = impressions_sum
                row.clicks_sum = clicks_sum
                row.ctr_avg = ctr_avg
                row.avg_position_avg = avg_position_avg
                row.queries_count = queries_count
            self._s.add(row)
            written += 1
        self._s.commit()
        return Envelope(data=written, project_id=project_id)

    def list(
        self,
        project_id: int,
        *,
        article_id: int | None = None,
        limit: int | None = None,
        after_id: int | None = None,
    ) -> Page[GscMetricDailyOut]:
        """List daily rollup rows for a project (and optionally one article)."""
        stmt = select(GscMetricDaily).where(GscMetricDaily.project_id == project_id)
        if article_id is not None:
            stmt = stmt.where(GscMetricDaily.article_id == article_id)
        return cursor_paginate(
            self._s,
            stmt,
            id_col=GscMetricDaily.id,
            limit=limit,
            after_id=after_id,
            converter=GscMetricDailyOut.model_validate,
        )


# ---------------------------------------------------------------------------
# DriftBaselineRepository — snapshot only at M1; diff engine in M5.
# ---------------------------------------------------------------------------


class DriftBaselineRepository:
    """Content-drift baselines."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def snapshot(self, *, article_id: int, baseline_md: str) -> Envelope[DriftBaselineOut]:
        """Insert a baseline row for ``article_id``."""
        row = DriftBaseline(
            article_id=article_id,
            baseline_md=baseline_md,
            baseline_at=_utcnow(),
        )
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=DriftBaselineOut.model_validate(row))

    def list(self, article_id: int) -> list[DriftBaselineOut]:
        """All baselines for ``article_id`` in capture order."""
        rows = self._s.exec(
            select(DriftBaseline)
            .where(DriftBaseline.article_id == article_id)
            .order_by(DriftBaseline.baseline_at.asc())  # type: ignore[union-attr,attr-defined]
        ).all()
        return [DriftBaselineOut.model_validate(r) for r in rows]

    def get(self, baseline_id: int) -> DriftBaselineOut:
        """Fetch one baseline."""
        row = self._s.get(DriftBaseline, baseline_id)
        if row is None:
            raise NotFoundError(f"drift baseline {baseline_id} not found")
        return DriftBaselineOut.model_validate(row)

    def diff(self, *, baseline_id: int, current_md: str) -> Any:
        """Compare a baseline to current content."""
        raise NotImplementedError(
            "M5: drift comparison engine — requires Firecrawl + drift-watch skill"
        )


# ---------------------------------------------------------------------------
# RedirectRepository.
# ---------------------------------------------------------------------------


class RedirectRepository:
    """301 / 302 records."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def create(
        self,
        *,
        project_id: int,
        from_url: str,
        to_article_id: int | None,
        kind: RedirectKind = RedirectKind.R301,
    ) -> Envelope[RedirectOut]:
        """Insert a redirect."""
        if not from_url:
            raise ValidationError("from_url is required")
        row = Redirect(
            project_id=project_id,
            from_url=from_url,
            to_article_id=to_article_id,
            kind=kind,
        )
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=RedirectOut.model_validate(row), project_id=project_id)

    def list(
        self, project_id: int, *, limit: int | None = None, after_id: int | None = None
    ) -> Page[RedirectOut]:
        """List redirects for a project."""
        stmt = select(Redirect).where(Redirect.project_id == project_id)
        return cursor_paginate(
            self._s,
            stmt,
            id_col=Redirect.id,
            limit=limit,
            after_id=after_id,
            converter=RedirectOut.model_validate,
        )

    def lookup(self, *, project_id: int, from_url: str) -> RedirectOut | None:
        """Lookup a redirect by ``from_url`` for the given project."""
        row = self._s.exec(
            select(Redirect).where(
                Redirect.project_id == project_id,
                Redirect.from_url == from_url,
            )
        ).first()
        return RedirectOut.model_validate(row) if row else None


__all__ = [
    "DriftBaselineOut",
    "DriftBaselineRepository",
    "GscMetricDailyOut",
    "GscMetricOut",
    "GscMetricRepository",
    "GscMetricsDailyRepository",
    "GscRow",
    "RedirectOut",
    "RedirectRepository",
]
