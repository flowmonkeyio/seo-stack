"""GSC router — bulk ingest, queries, rollup, redirects.

PLAN.md L599-L601 + ``GscMetricRepository`` / ``GscMetricsDailyRepository``
/ ``RedirectRepository``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from content_stack.api.deps import get_session
from content_stack.api.envelopes import WriteResponse, write_response
from content_stack.api.pagination import (
    PageResponse,
    PaginationParams,
    page_response,
    pagination_params,
)
from content_stack.db.models import RedirectKind
from content_stack.repositories.gsc import (
    GscMetricOut,
    GscMetricRepository,
    GscMetricsDailyRepository,
    GscRow,
    RedirectOut,
    RedirectRepository,
)

bulk_router = APIRouter(prefix="/api/v1/gsc", tags=["gsc"])
project_router = APIRouter(prefix="/api/v1/projects", tags=["gsc"])
article_router = APIRouter(prefix="/api/v1/articles", tags=["gsc"])


class BulkIngestRequest(BaseModel):
    """Body for ``POST /gsc/bulk``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": 1,
                "rows": [
                    {
                        "captured_at": "2026-05-07T00:00:00",
                        "dimensions_hash": "abc123",
                        "impressions": 100,
                        "clicks": 5,
                        "ctr": 0.05,
                        "avg_position": 7.2,
                    }
                ],
            }
        }
    )

    project_id: int
    rows: list[GscRow] = Field(min_length=1)


class BulkIngestResponse(BaseModel):
    """Wire shape for the bulk-ingest result."""

    inserted: int


class CreateRedirectRequest(BaseModel):
    """Body for ``POST /projects/{id}/redirects``."""

    from_url: str = Field(min_length=1, max_length=2048)
    to_article_id: int | None = None
    kind: RedirectKind = RedirectKind.R301


@bulk_router.post(
    "/bulk",
    response_model=WriteResponse[BulkIngestResponse],
    status_code=status.HTTP_201_CREATED,
)
async def bulk_ingest(
    body: BulkIngestRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[BulkIngestResponse]:
    """Ingest GSC rows; dedup via the ``uq_gsc_metrics_dedup`` unique index."""
    env = GscMetricRepository(session).bulk_ingest(body.project_id, body.rows)
    # Repo returns Envelope[int]; wrap as BulkIngestResponse.
    return WriteResponse[BulkIngestResponse](
        data=BulkIngestResponse(inserted=env.data),
        project_id=env.project_id,
        run_id=env.run_id,
    )


@project_router.get(
    "/{project_id}/gsc",
    response_model=list[GscMetricOut],
)
async def query_project_gsc(
    project_id: int,
    since: Annotated[datetime, Query()],
    until: Annotated[datetime, Query()],
    session: Session = Depends(get_session),
) -> list[GscMetricOut]:
    """Return raw rows for a project in ``[since, until)``."""
    return GscMetricRepository(session).query_project(project_id, since=since, until=until)


@article_router.get(
    "/{article_id}/gsc",
    response_model=list[GscMetricOut],
)
async def query_article_gsc(
    article_id: int,
    since: Annotated[datetime, Query()],
    until: Annotated[datetime, Query()],
    session: Session = Depends(get_session),
) -> list[GscMetricOut]:
    """Return raw rows for an article in ``[since, until)``."""
    return GscMetricRepository(session).query_article(article_id, since=since, until=until)


@project_router.post(
    "/{project_id}/gsc/rollup",
    response_model=WriteResponse[BulkIngestResponse],
)
async def rollup_gsc(
    project_id: int,
    day: Annotated[date, Query()],
    session: Session = Depends(get_session),
) -> WriteResponse[BulkIngestResponse]:
    """Aggregate ``gsc_metrics`` for ``day`` into ``gsc_metrics_daily``.

    M9 schedules this nightly per project; M2 just exposes the operation.
    """
    env = GscMetricsDailyRepository(session).rollup(project_id, day=day)
    return WriteResponse[BulkIngestResponse](
        data=BulkIngestResponse(inserted=env.data),
        project_id=env.project_id,
        run_id=env.run_id,
    )


@project_router.get(
    "/{project_id}/redirects",
    response_model=PageResponse[RedirectOut],
)
async def list_redirects(
    project_id: int,
    page: PaginationParams = Depends(pagination_params),
    session: Session = Depends(get_session),
) -> PageResponse[RedirectOut]:
    """List redirects for a project."""
    return page_response(
        RedirectRepository(session).list(project_id, limit=page.limit, after_id=page.after)
    )


@project_router.post(
    "/{project_id}/redirects",
    response_model=WriteResponse[RedirectOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_redirect(
    project_id: int,
    body: CreateRedirectRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[RedirectOut]:
    """Insert a 301/302 redirect."""
    return write_response(
        RedirectRepository(session).create(
            project_id=project_id,
            from_url=body.from_url,
            to_article_id=body.to_article_id,
            kind=body.kind,
        )
    )


__all__ = ["article_router", "bulk_router", "project_router"]
