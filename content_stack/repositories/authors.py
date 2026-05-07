"""Author repository.

Authors are per-article attribution rows used by the ``Experience`` and
``Expertise`` EEAT dimensions. CRUD is straightforward; the only
non-trivial bit is the ``(project_id, slug)`` uniqueness, which is
enforced at the DB level (``uq_authors_project_slug``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from content_stack.db.models import Author
from content_stack.repositories.base import (
    ConflictError,
    Envelope,
    NotFoundError,
    Page,
    ValidationError,
    cursor_paginate,
)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


class AuthorOut(BaseModel):
    """Public shape for ``Author`` rows."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    slug: str
    bio_md: str | None
    headshot_url: str | None
    role: str | None
    credentials_md: str | None
    social_links_json: dict[str, Any] | None
    schema_person_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class AuthorRepository:
    """Authors CRUD."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def create(
        self,
        *,
        project_id: int,
        name: str,
        slug: str,
        bio_md: str | None = None,
        headshot_url: str | None = None,
        role: str | None = None,
        credentials_md: str | None = None,
        social_links_json: dict[str, Any] | None = None,
        schema_person_json: dict[str, Any] | None = None,
    ) -> Envelope[AuthorOut]:
        """Insert a new author row.

        ``(project_id, slug)`` is unique; duplicates raise ``ConflictError``.
        """
        if not slug or len(slug) > 80:
            raise ValidationError("slug must be 1..80 chars")
        existing = self._s.exec(
            select(Author).where(
                Author.project_id == project_id,
                Author.slug == slug,
            )
        ).first()
        if existing is not None:
            raise ConflictError(
                f"author slug {slug!r} already exists for project {project_id}",
                data={"slug": slug, "project_id": project_id, "existing_id": existing.id},
            )
        row = Author(
            project_id=project_id,
            name=name,
            slug=slug,
            bio_md=bio_md,
            headshot_url=headshot_url,
            role=role,
            credentials_md=credentials_md,
            social_links_json=social_links_json,
            schema_person_json=schema_person_json,
        )
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=AuthorOut.model_validate(row), project_id=project_id)

    def get(self, author_id: int) -> AuthorOut:
        """Fetch one author by id."""
        row = self._fetch(author_id)
        return AuthorOut.model_validate(row)

    def list(
        self, project_id: int, *, limit: int | None = None, after_id: int | None = None
    ) -> Page[AuthorOut]:
        """Cursor-paginated list."""
        stmt = select(Author).where(Author.project_id == project_id)
        return cursor_paginate(
            self._s,
            stmt,
            id_col=Author.id,
            limit=limit,
            after_id=after_id,
            converter=AuthorOut.model_validate,
        )

    def update(self, author_id: int, **patch: Any) -> Envelope[AuthorOut]:
        """Partial update; ``slug`` is mutable but must remain unique."""
        row = self._fetch(author_id)
        if "slug" in patch and patch["slug"] != row.slug:
            existing = self._s.exec(
                select(Author).where(
                    Author.project_id == row.project_id,
                    Author.slug == patch["slug"],
                )
            ).first()
            if existing is not None:
                raise ConflictError(
                    f"slug {patch['slug']!r} already in use",
                    data={"slug": patch["slug"], "existing_id": existing.id},
                )
        for k, v in patch.items():
            if k in {"id", "project_id", "created_at"}:
                continue
            if not hasattr(row, k):
                raise ValidationError(f"unknown field {k!r}")
            setattr(row, k, v)
        row.updated_at = _utcnow()
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=AuthorOut.model_validate(row), project_id=row.project_id)

    def remove(self, author_id: int) -> Envelope[AuthorOut]:
        """Hard-delete; FK ``ON DELETE SET NULL`` clears references."""
        row = self._fetch(author_id)
        out = AuthorOut.model_validate(row)
        self._s.delete(row)
        self._s.commit()
        return Envelope(data=out, project_id=row.project_id)

    def _fetch(self, author_id: int) -> Author:
        row = self._s.get(Author, author_id)
        if row is None:
            raise NotFoundError(f"author {author_id} not found")
        return row


__all__ = ["AuthorOut", "AuthorRepository"]
