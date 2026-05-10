"""Tests for InterlinkRepository — suggest, apply, dismiss, repair."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from content_stack.db.models import InternalLinkStatus
from content_stack.repositories.articles import ArticleRepository
from content_stack.repositories.base import ConflictError
from content_stack.repositories.interlinks import (
    InterlinkRepository,
    InterlinkSuggestion,
)


def _two_articles(session: Session, project_id: int) -> tuple[int, int]:
    repo = ArticleRepository(session)
    a = repo.create(project_id=project_id, topic_id=None, title="A", slug="a-1").data
    b = repo.create(project_id=project_id, topic_id=None, title="B", slug="b-2").data
    assert a.id is not None and b.id is not None
    return a.id, b.id


def test_suggest_apply_dismiss_flow(session: Session, project_id: int) -> None:
    a, b = _two_articles(session, project_id)
    repo = InterlinkRepository(session)
    env = repo.suggest(
        project_id,
        [
            InterlinkSuggestion(
                from_article_id=a,
                to_article_id=b,
                anchor_text="related",
                position=1,
            )
        ],
    )
    link_id = env.data[0].id
    assert env.data[0].status == InternalLinkStatus.SUGGESTED

    out = repo.apply(link_id)
    assert out.data.status == InternalLinkStatus.APPLIED


def test_dismiss_terminal(session: Session, project_id: int) -> None:
    a, b = _two_articles(session, project_id)
    repo = InterlinkRepository(session)
    env = repo.suggest(
        project_id,
        [InterlinkSuggestion(from_article_id=a, to_article_id=b, anchor_text="d")],
    )
    link_id = env.data[0].id
    repo.dismiss(link_id)
    # Cannot transition out of dismissed.
    with pytest.raises(ConflictError):
        repo.apply(link_id)


def test_repair_flips_applied_to_broken(session: Session, project_id: int) -> None:
    a, b = _two_articles(session, project_id)
    repo = InterlinkRepository(session)
    env = repo.suggest(
        project_id,
        [InterlinkSuggestion(from_article_id=a, to_article_id=b, anchor_text="x")],
    )
    repo.apply(env.data[0].id)
    out = repo.repair(b)
    assert len(out.data) == 1
    assert out.data[0].status == InternalLinkStatus.BROKEN


def test_partial_unique_blocks_live_dupe(session: Session, project_id: int) -> None:
    """Tests the audit B-09 partial unique on internal_links."""
    a, b = _two_articles(session, project_id)
    repo = InterlinkRepository(session)
    repo.suggest(
        project_id,
        [
            InterlinkSuggestion(
                from_article_id=a,
                to_article_id=b,
                anchor_text="dup",
                position=1,
            )
        ],
    )
    # Inserting a second identical-live row should fail at DB level and be
    # surfaced as the repository's conflict error.
    with pytest.raises(ConflictError):
        repo.suggest(
            project_id,
            [
                InterlinkSuggestion(
                    from_article_id=a,
                    to_article_id=b,
                    anchor_text="dup",
                    position=1,
                )
            ],
        )


def test_partial_unique_blocks_live_dupe_with_default_position(
    session: Session, project_id: int
) -> None:
    """B-09: ``position=None`` is still one live uniqueness bucket."""
    a, b = _two_articles(session, project_id)
    repo = InterlinkRepository(session)
    suggestion = InterlinkSuggestion(from_article_id=a, to_article_id=b, anchor_text="default-pos")
    repo.suggest(project_id, [suggestion])

    with pytest.raises(ConflictError):
        repo.suggest(project_id, [suggestion])


def test_bulk_apply(session: Session, project_id: int) -> None:
    a, b = _two_articles(session, project_id)
    repo = InterlinkRepository(session)
    env = repo.suggest(
        project_id,
        [
            InterlinkSuggestion(
                from_article_id=a,
                to_article_id=b,
                anchor_text="multi-1",
                position=1,
            ),
            InterlinkSuggestion(
                from_article_id=a,
                to_article_id=b,
                anchor_text="multi-2",
                position=2,
            ),
        ],
    )
    ids = [link.id for link in env.data]
    out = repo.bulk_apply(ids)
    assert all(link.status == InternalLinkStatus.APPLIED for link in out.data)
