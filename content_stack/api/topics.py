"""Topics router — ``/api/v1/projects/{id}/topics`` + ``/api/v1/topics/{id}``.

PLAN.md L575-L577 + ``TopicRepository``. Two prefixes: project-scoped
list/create/bulk and topic-scoped read/update/transition.
"""

from __future__ import annotations

from typing import Annotated, Any

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
from content_stack.db.models import TopicIntent, TopicSource, TopicStatus
from content_stack.repositories.clusters import (
    TopicCreate,
    TopicOut,
    TopicRepository,
)

project_router = APIRouter(prefix="/api/v1/projects", tags=["topics"])
topic_router = APIRouter(prefix="/api/v1/topics", tags=["topics"])


class TopicCreateRequest(TopicCreate):
    """Inherits ``TopicCreate`` so the wire shape matches MCP exactly."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "How to evaluate a sportsbook",
                "primary_kw": "best sportsbook",
                "intent": "informational",
                "status": "queued",
                "source": "manual",
            }
        }
    )


class BulkTopicCreateRequest(BaseModel):
    """Body for ``POST /projects/{id}/topics/bulk``."""

    items: list[TopicCreateRequest] = Field(min_length=1, max_length=500)


class TopicUpdateRequest(BaseModel):
    """UI-permissive PATCH body."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    primary_kw: str | None = Field(default=None, max_length=300)
    secondary_kws: list[str] | None = None
    intent: TopicIntent | None = None
    status: TopicStatus | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    source: TopicSource | None = None
    cluster_id: int | None = None


class BulkUpdateStatusRequest(BaseModel):
    """Body for ``POST /projects/{id}/topics/bulk-update-status``."""

    ids: list[int] = Field(min_length=1)
    status: TopicStatus


@project_router.get(
    "/{project_id}/topics",
    response_model=PageResponse[TopicOut],
)
async def list_topics(
    project_id: int,
    page: PaginationParams = Depends(pagination_params),
    status: TopicStatus | None = Query(None),
    source: TopicSource | None = Query(None),
    cluster_id: int | None = Query(None),
    sort: Annotated[str, Query(pattern=r"^-?(priority|id)$")] = "priority",
    session: Session = Depends(get_session),
) -> PageResponse[TopicOut]:
    """List topics; default sort applies the audit B-16 queue tiebreaker.

    Filters: ``status``, ``source``, ``cluster_id``. Sort: ``priority``,
    ``-priority``, ``id``, ``-id``.
    """
    sort_lit: Any = sort  # repo restricts to a Literal at type level
    return page_response(
        TopicRepository(session).list(
            project_id,
            status=status,
            source=source,
            cluster_id=cluster_id,
            sort=sort_lit,
            limit=page.limit,
            after_id=page.after,
        )
    )


@project_router.post(
    "/{project_id}/topics",
    response_model=WriteResponse[TopicOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_topic(
    project_id: int,
    body: TopicCreateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[TopicOut]:
    """Insert a single topic row."""
    return write_response(TopicRepository(session).create(project_id, body))


@project_router.post(
    "/{project_id}/topics/bulk",
    response_model=WriteResponse[list[TopicOut]],
    status_code=status.HTTP_201_CREATED,
)
async def bulk_create_topics(
    project_id: int,
    body: BulkTopicCreateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[list[TopicOut]]:
    """Insert N topics; response order matches request order (audit M-13)."""
    return write_response(TopicRepository(session).bulk_create(project_id, list(body.items)))


@project_router.post(
    "/{project_id}/topics/bulk-update-status",
    response_model=WriteResponse[list[TopicOut]],
)
async def bulk_update_topic_status(
    project_id: int,
    body: BulkUpdateStatusRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[list[TopicOut]]:
    """Move N topics to ``status`` if every transition is legal (all-or-nothing)."""
    return write_response(
        TopicRepository(session).bulk_update_status(project_id, body.ids, body.status)
    )


@topic_router.get("/{topic_id}", response_model=TopicOut)
async def get_topic(topic_id: int, session: Session = Depends(get_session)) -> TopicOut:
    """Single topic fetch."""
    return TopicRepository(session).get(topic_id)


@topic_router.patch("/{topic_id}", response_model=WriteResponse[TopicOut])
async def update_topic(
    topic_id: int,
    body: TopicUpdateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[TopicOut]:
    """UI-permissive PATCH; status transitions go through ``validate_transition``."""
    patch = body.model_dump(exclude_unset=True)
    return write_response(TopicRepository(session).update(topic_id, **patch))


@topic_router.post("/{topic_id}/approve", response_model=WriteResponse[TopicOut])
async def approve_topic(
    topic_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[TopicOut]:
    """Convenience: ``status='approved'``."""
    return write_response(TopicRepository(session).approve(topic_id))


@topic_router.post("/{topic_id}/reject", response_model=WriteResponse[TopicOut])
async def reject_topic(
    topic_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[TopicOut]:
    """Convenience: ``status='rejected'``."""
    return write_response(TopicRepository(session).reject(topic_id))


__all__ = ["project_router", "topic_router"]
