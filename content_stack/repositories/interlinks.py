"""Interlinks repository.

Implements the M1 scope of the interlinker (skill #15) data layer:
suggest, apply, dismiss, repair, list, bulk_apply.

The actual edit to ``articles.edited_md`` (rewriting body markdown to
embed the link target) happens in skill #15 (M7). The repository
**only** flips the link-row status; M7 reads the applied rows and
rewrites the article body. Documented inline.

Repair flow (audit M-05): when an article is unpublished or moved to
``refresh_due``, its incoming links should not silently disappear.
``repair`` walks links pointing AT the un-published article and
transitions ``applied → broken`` so the UI can flag them and skill #15
can heal in the next pass.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from content_stack.db.models import (
    INTERNAL_LINK_STATUS_TRANSITIONS,
    InternalLink,
    InternalLinkStatus,
)
from content_stack.repositories.base import (
    ConflictError,
    Envelope,
    NotFoundError,
    Page,
    cursor_paginate,
    validate_transition,
)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


class InternalLinkOut(BaseModel):
    """Public shape for ``internal_links`` rows."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    from_article_id: int
    to_article_id: int
    anchor_text: str
    position: int | None
    status: InternalLinkStatus
    created_at: datetime
    updated_at: datetime


class InterlinkSuggestion(BaseModel):
    """Input for ``suggest`` — one row per proposed link."""

    from_article_id: int
    to_article_id: int
    anchor_text: str
    position: int | None = None


class InterlinkRepository:
    """Internal-link CRUD + state-machine + repair."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def suggest(
        self, project_id: int, suggestions: Iterable[InterlinkSuggestion]
    ) -> Envelope[list[InternalLinkOut]]:
        """Insert N link rows with ``status='suggested'``."""
        materialised = list(suggestions)
        rows = [
            InternalLink(
                project_id=project_id,
                from_article_id=s.from_article_id,
                to_article_id=s.to_article_id,
                anchor_text=s.anchor_text,
                position=s.position,
                status=InternalLinkStatus.SUGGESTED,
            )
            for s in materialised
        ]
        for r in rows:
            self._s.add(r)
        try:
            self._s.commit()
        except IntegrityError as exc:
            self._s.rollback()
            raise ConflictError(
                "live internal link already exists",
                data={
                    "project_id": project_id,
                    "links": [
                        {
                            "from_article_id": s.from_article_id,
                            "to_article_id": s.to_article_id,
                            "anchor_text": s.anchor_text,
                            "position": s.position,
                        }
                        for s in materialised
                    ],
                },
            ) from exc
        for r in rows:
            self._s.refresh(r)
        return Envelope(
            data=[InternalLinkOut.model_validate(r) for r in rows],
            project_id=project_id,
        )

    def apply(self, link_id: int) -> Envelope[InternalLinkOut]:
        """Move a link from ``suggested → applied``.

        **Important**: this method ONLY flips the row's status. The actual
        rewrite of ``articles.edited_md`` to embed the anchor at the
        chosen position is M7 work (skill #15 — interlinker). The
        skill reads the ``status='applied'`` rows after this method
        completes and rewrites the body.
        """
        row = self._fetch(link_id)
        validate_transition(
            row.status,
            InternalLinkStatus.APPLIED,
            INTERNAL_LINK_STATUS_TRANSITIONS,
            label="internal_link.status",
        )
        row.status = InternalLinkStatus.APPLIED
        row.updated_at = _utcnow()
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=InternalLinkOut.model_validate(row), project_id=row.project_id)

    def dismiss(self, link_id: int) -> Envelope[InternalLinkOut]:
        """Move a link to ``dismissed`` (terminal)."""
        row = self._fetch(link_id)
        validate_transition(
            row.status,
            InternalLinkStatus.DISMISSED,
            INTERNAL_LINK_STATUS_TRANSITIONS,
            label="internal_link.status",
        )
        row.status = InternalLinkStatus.DISMISSED
        row.updated_at = _utcnow()
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=InternalLinkOut.model_validate(row), project_id=row.project_id)

    def repair(self, article_id: int) -> Envelope[list[InternalLinkOut]]:
        """Mark all live links pointing at ``article_id`` as ``broken``.

        Per audit M-05: when an article is unpublished (``mark_refresh_due``
        or status←``aborted-publish``), incoming applied links no longer
        resolve. We flip them to ``broken`` so the UI flags them and skill
        #15 can re-suggest in the next pass.

        Only ``applied`` links transition; ``suggested`` rows are left
        alone (they were never realised), and ``dismissed`` rows are
        terminal.
        """
        rows = self._s.exec(
            select(InternalLink).where(
                InternalLink.to_article_id == article_id,
                InternalLink.status == InternalLinkStatus.APPLIED,
            )
        ).all()
        out: list[InternalLink] = []
        for row in rows:
            row.status = InternalLinkStatus.BROKEN
            row.updated_at = _utcnow()
            self._s.add(row)
            out.append(row)
        self._s.commit()
        for r in out:
            self._s.refresh(r)
        project_id = out[0].project_id if out else None
        return Envelope(
            data=[InternalLinkOut.model_validate(r) for r in out],
            project_id=project_id,
        )

    def bulk_apply(self, ids: Iterable[int]) -> Envelope[list[InternalLinkOut]]:
        """Apply many suggestions in one transaction.

        All-or-nothing: any illegal transition rolls the batch back.
        """
        ids_list = list(ids)
        rows = self._s.exec(
            select(InternalLink).where(InternalLink.id.in_(ids_list))  # type: ignore[union-attr,attr-defined]
        ).all()
        if len(rows) != len(ids_list):
            found = {r.id for r in rows}
            missing = sorted(set(ids_list) - found)
            raise NotFoundError(f"internal links not found: {missing}", data={"missing": missing})
        for r in rows:
            validate_transition(
                r.status,
                InternalLinkStatus.APPLIED,
                INTERNAL_LINK_STATUS_TRANSITIONS,
                label="internal_link.status",
            )
        for r in rows:
            r.status = InternalLinkStatus.APPLIED
            r.updated_at = _utcnow()
            self._s.add(r)
        self._s.commit()
        for r in rows:
            self._s.refresh(r)
        return Envelope(
            data=[InternalLinkOut.model_validate(r) for r in rows],
            project_id=rows[0].project_id if rows else None,
        )

    def list(
        self,
        project_id: int,
        *,
        status: InternalLinkStatus | None = None,
        from_article_id: int | None = None,
        to_article_id: int | None = None,
        limit: int | None = None,
        after_id: int | None = None,
    ) -> Page[InternalLinkOut]:
        """Cursor-paginated list with filters."""
        stmt = select(InternalLink).where(InternalLink.project_id == project_id)
        if status is not None:
            stmt = stmt.where(InternalLink.status == status)
        if from_article_id is not None:
            stmt = stmt.where(InternalLink.from_article_id == from_article_id)
        if to_article_id is not None:
            stmt = stmt.where(InternalLink.to_article_id == to_article_id)
        return cursor_paginate(
            self._s,
            stmt,
            id_col=InternalLink.id,
            limit=limit,
            after_id=after_id,
            converter=InternalLinkOut.model_validate,
        )

    def _fetch(self, link_id: int) -> InternalLink:
        row = self._s.get(InternalLink, link_id)
        if row is None:
            raise NotFoundError(f"internal link {link_id} not found")
        return row


__all__ = [
    "InterlinkRepository",
    "InterlinkSuggestion",
    "InternalLinkOut",
]
