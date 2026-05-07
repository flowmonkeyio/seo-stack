"""Clusters router — ``/api/v1/projects/{id}/clusters`` + ``/api/v1/clusters/{id}``.

PLAN.md L574 + ``ClusterRepository``. Self-FK for hierarchy is exposed
on the read shape (``parent_id``) so the UI can render the tree without
a second call.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
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
from content_stack.db.models import ClusterType
from content_stack.repositories.clusters import ClusterOut, ClusterRepository

# Two routers because the resources live at different prefixes.
project_router = APIRouter(prefix="/api/v1/projects", tags=["clusters"])
cluster_router = APIRouter(prefix="/api/v1/clusters", tags=["clusters"])


class ClusterCreateRequest(BaseModel):
    """Body for ``POST /projects/{id}/clusters``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"name": "How-to guides", "type": "pillar", "parent_id": None},
        }
    )

    name: str = Field(min_length=1, max_length=200)
    type: ClusterType
    parent_id: int | None = None


@project_router.get(
    "/{project_id}/clusters",
    response_model=PageResponse[ClusterOut],
)
async def list_clusters(
    project_id: int,
    page: PaginationParams = Depends(pagination_params),
    session: Session = Depends(get_session),
) -> PageResponse[ClusterOut]:
    """Cursor-paginated cluster list for a project."""
    return page_response(
        ClusterRepository(session).list(project_id, limit=page.limit, after_id=page.after)
    )


@project_router.post(
    "/{project_id}/clusters",
    response_model=WriteResponse[ClusterOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_cluster(
    project_id: int,
    body: ClusterCreateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ClusterOut]:
    """Insert a cluster row.

    Repo enforces ``parent_id``-must-belong-to-same-project.
    """
    return write_response(
        ClusterRepository(session).create(
            project_id=project_id,
            name=body.name,
            type=body.type,
            parent_id=body.parent_id,
        )
    )


@cluster_router.get("/{cluster_id}", response_model=ClusterOut)
async def get_cluster(
    cluster_id: int,
    session: Session = Depends(get_session),
) -> ClusterOut:
    """Fetch one cluster by id."""
    return ClusterRepository(session).get(cluster_id)


__all__ = ["cluster_router", "project_router"]
