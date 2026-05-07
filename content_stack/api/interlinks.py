"""Interlinks router — ``/api/v1/projects/{id}/interlinks/...``.

PLAN.md L593-L596 + ``InterlinkRepository``. Suggest, list, apply,
dismiss, repair (after unpublish), bulk-apply.
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
from content_stack.db.models import InternalLinkStatus
from content_stack.repositories.interlinks import (
    InterlinkRepository,
    InterlinkSuggestion,
    InternalLinkOut,
)

router = APIRouter(prefix="/api/v1/projects", tags=["interlinks"])


class SuggestRequest(BaseModel):
    """Body for ``POST /projects/{id}/interlinks/suggest``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "suggestions": [
                    {
                        "from_article_id": 1,
                        "to_article_id": 2,
                        "anchor_text": "evaluate sportsbooks",
                        "position": 100,
                    }
                ]
            }
        }
    )

    suggestions: list[InterlinkSuggestion] = Field(min_length=1)


class BulkApplyRequest(BaseModel):
    """Body for ``POST /projects/{id}/interlinks/bulk-apply``."""

    ids: list[int] = Field(min_length=1)


class CreateInterlinkRequest(BaseModel):
    """Body for ``POST /projects/{id}/interlinks`` (single suggestion)."""

    from_article_id: int
    to_article_id: int
    anchor_text: str = Field(min_length=1, max_length=300)
    position: int | None = None


class RepairRequest(BaseModel):
    """Body for ``POST /projects/{id}/interlinks/repair``."""

    article_id: int


@router.get(
    "/{project_id}/interlinks",
    response_model=PageResponse[InternalLinkOut],
)
async def list_interlinks(
    project_id: int,
    page: PaginationParams = Depends(pagination_params),
    status: InternalLinkStatus | None = None,
    from_article_id: int | None = None,
    to_article_id: int | None = None,
    session: Session = Depends(get_session),
) -> PageResponse[InternalLinkOut]:
    """Cursor-paginated list with optional filters."""
    return page_response(
        InterlinkRepository(session).list(
            project_id,
            status=status,
            from_article_id=from_article_id,
            to_article_id=to_article_id,
            limit=page.limit,
            after_id=page.after,
        )
    )


@router.post(
    "/{project_id}/interlinks",
    response_model=WriteResponse[list[InternalLinkOut]],
    status_code=status.HTTP_201_CREATED,
)
async def create_interlink(
    project_id: int,
    body: CreateInterlinkRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[list[InternalLinkOut]]:
    """Insert a single suggestion (wraps ``suggest`` for convenience)."""
    return write_response(
        InterlinkRepository(session).suggest(
            project_id,
            [
                InterlinkSuggestion(
                    from_article_id=body.from_article_id,
                    to_article_id=body.to_article_id,
                    anchor_text=body.anchor_text,
                    position=body.position,
                )
            ],
        )
    )


@router.post(
    "/{project_id}/interlinks/suggest",
    response_model=WriteResponse[list[InternalLinkOut]],
    status_code=status.HTTP_201_CREATED,
)
async def suggest_interlinks(
    project_id: int,
    body: SuggestRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[list[InternalLinkOut]]:
    """Insert N link rows with ``status='suggested'``."""
    return write_response(InterlinkRepository(session).suggest(project_id, list(body.suggestions)))


@router.post(
    "/{project_id}/interlinks/{link_id}/apply",
    response_model=WriteResponse[InternalLinkOut],
)
async def apply_interlink(
    project_id: int,
    link_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[InternalLinkOut]:
    """Move a link from ``suggested → applied``.

    Repo only flips the status — body rewrite is M7 (skill #15).
    """
    _ = project_id
    return write_response(InterlinkRepository(session).apply(link_id))


@router.post(
    "/{project_id}/interlinks/{link_id}/dismiss",
    response_model=WriteResponse[InternalLinkOut],
)
async def dismiss_interlink(
    project_id: int,
    link_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[InternalLinkOut]:
    """Move a link to ``dismissed`` (terminal)."""
    _ = project_id
    return write_response(InterlinkRepository(session).dismiss(link_id))


@router.post(
    "/{project_id}/interlinks/repair",
    response_model=WriteResponse[list[InternalLinkOut]],
)
async def repair_interlinks(
    project_id: int,
    body: RepairRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[list[InternalLinkOut]]:
    """Mark all live links pointing at ``article_id`` as ``broken`` (audit M-05)."""
    _ = project_id
    return write_response(InterlinkRepository(session).repair(body.article_id))


@router.post(
    "/{project_id}/interlinks/bulk-apply",
    response_model=WriteResponse[list[InternalLinkOut]],
)
async def bulk_apply_interlinks(
    project_id: int,
    body: BulkApplyRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[list[InternalLinkOut]]:
    """Apply many suggestions in one transaction (all-or-nothing)."""
    _ = project_id
    return write_response(InterlinkRepository(session).bulk_apply(body.ids))


__all__ = ["router"]
