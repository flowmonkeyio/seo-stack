"""Authors router — ``/api/v1/projects/{id}/authors[/{aid}]``.

PLAN.md L566 + ``AuthorRepository``. CRUD with ``(project_id, slug)``
uniqueness enforced at the DB level.
"""

from __future__ import annotations

from typing import Any

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
from content_stack.repositories.authors import AuthorOut, AuthorRepository

router = APIRouter(prefix="/api/v1/projects", tags=["authors"])


class AuthorCreateRequest(BaseModel):
    """Body for ``POST /projects/{id}/authors``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Jane Doe",
                "slug": "jane-doe",
                "role": "Senior Editor",
                "bio_md": "20 years in iGaming.",
            }
        }
    )

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=80)
    bio_md: str | None = None
    headshot_url: str | None = Field(default=None, max_length=2048)
    role: str | None = Field(default=None, max_length=120)
    credentials_md: str | None = None
    social_links_json: dict[str, Any] | None = None
    schema_person_json: dict[str, Any] | None = None


class AuthorUpdateRequest(BaseModel):
    """Body for ``PATCH /projects/{id}/authors/{aid}``."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=80)
    bio_md: str | None = None
    headshot_url: str | None = Field(default=None, max_length=2048)
    role: str | None = Field(default=None, max_length=120)
    credentials_md: str | None = None
    social_links_json: dict[str, Any] | None = None
    schema_person_json: dict[str, Any] | None = None


@router.get(
    "/{project_id}/authors",
    response_model=PageResponse[AuthorOut],
)
async def list_authors(
    project_id: int,
    page: PaginationParams = Depends(pagination_params),
    session: Session = Depends(get_session),
) -> PageResponse[AuthorOut]:
    """Cursor-paginated authors list."""
    return page_response(
        AuthorRepository(session).list(project_id, limit=page.limit, after_id=page.after)
    )


@router.post(
    "/{project_id}/authors",
    response_model=WriteResponse[AuthorOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_author(
    project_id: int,
    body: AuthorCreateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[AuthorOut]:
    """Insert an author (FK uniqueness enforced at DB level)."""
    return write_response(
        AuthorRepository(session).create(
            project_id=project_id,
            name=body.name,
            slug=body.slug,
            bio_md=body.bio_md,
            headshot_url=body.headshot_url,
            role=body.role,
            credentials_md=body.credentials_md,
            social_links_json=body.social_links_json,
            schema_person_json=body.schema_person_json,
        )
    )


@router.get(
    "/{project_id}/authors/{author_id}",
    response_model=AuthorOut,
)
async def get_author(
    project_id: int,
    author_id: int,
    session: Session = Depends(get_session),
) -> AuthorOut:
    """Fetch a single author."""
    _ = project_id
    return AuthorRepository(session).get(author_id)


@router.patch(
    "/{project_id}/authors/{author_id}",
    response_model=WriteResponse[AuthorOut],
)
async def update_author(
    project_id: int,
    author_id: int,
    body: AuthorUpdateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[AuthorOut]:
    """Patch an author. Slug remains unique per project."""
    _ = project_id
    patch = body.model_dump(exclude_unset=True)
    return write_response(AuthorRepository(session).update(author_id, **patch))


@router.delete(
    "/{project_id}/authors/{author_id}",
    response_model=WriteResponse[AuthorOut],
)
async def delete_author(
    project_id: int,
    author_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[AuthorOut]:
    """Hard-delete an author; FK ``ON DELETE SET NULL`` clears references."""
    _ = project_id
    return write_response(AuthorRepository(session).remove(author_id))


__all__ = ["router"]
