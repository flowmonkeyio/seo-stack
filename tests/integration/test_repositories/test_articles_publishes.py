"""Tests for ArticlePublishRepository — multi-target publish + canonical."""

from __future__ import annotations

from sqlmodel import Session

from content_stack.db.models import PublishTargetKind
from content_stack.repositories.articles import (
    ArticlePublishRepository,
    ArticleRepository,
)
from content_stack.repositories.projects import PublishTargetRepository


def test_record_publish_for_two_targets(session: Session, project_id: int) -> None:
    art_repo = ArticleRepository(session)
    target_repo = PublishTargetRepository(session)
    pub_repo = ArticlePublishRepository(session)

    art = art_repo.create(project_id=project_id, topic_id=None, title="P", slug="pub-test").data
    nuxt = target_repo.add(project_id=project_id, kind=PublishTargetKind.NUXT_CONTENT).data
    wp = target_repo.add(project_id=project_id, kind=PublishTargetKind.WORDPRESS).data

    pub_repo.record_publish(
        article_id=art.id,
        target_id=nuxt.id,
        version_published=1,
        published_url="https://example.com/p1",
        frontmatter_json={"title": "P"},
    )
    pub_repo.record_publish(
        article_id=art.id,
        target_id=wp.id,
        version_published=1,
        published_url="https://example.com/wp/p1",
    )
    rows = pub_repo.list_for_article(art.id)
    assert len(rows) == 2
    assert {r.target_id for r in rows} == {nuxt.id, wp.id}


def test_record_publish_idempotent_upsert(session: Session, project_id: int) -> None:
    """Re-running record_publish on same key updates rather than duping."""
    art_repo = ArticleRepository(session)
    target_repo = PublishTargetRepository(session)
    pub_repo = ArticlePublishRepository(session)

    art = art_repo.create(project_id=project_id, topic_id=None, title="U", slug="upsert").data
    target = target_repo.add(project_id=project_id, kind=PublishTargetKind.NUXT_CONTENT).data

    pub_repo.record_publish(article_id=art.id, target_id=target.id, version_published=1)
    pub_repo.record_publish(
        article_id=art.id,
        target_id=target.id,
        version_published=1,
        published_url="https://updated.example/p",
    )
    rows = pub_repo.list_for_article(art.id)
    assert len(rows) == 1
    assert rows[0].published_url == "https://updated.example/p"


def test_set_canonical_target(session: Session, project_id: int) -> None:
    art_repo = ArticleRepository(session)
    target_repo = PublishTargetRepository(session)
    pub_repo = ArticlePublishRepository(session)

    art = art_repo.create(project_id=project_id, topic_id=None, title="C", slug="canon").data
    nuxt = target_repo.add(project_id=project_id, kind=PublishTargetKind.NUXT_CONTENT).data
    out = pub_repo.set_canonical(article_id=art.id, target_id=nuxt.id)
    assert out.data.canonical_target_id == nuxt.id
