"""Tests for ArticlePublishRepository — multi-target publish + canonical."""

from __future__ import annotations

from sqlmodel import Session

from content_stack.db.models import (
    Article,
    ArticlePublishStatus,
    ArticleStatus,
    PublishTargetKind,
    RunKind,
)
from content_stack.repositories.articles import (
    ArticlePublishRepository,
    ArticleRepository,
)
from content_stack.repositories.projects import PublishTargetRepository
from content_stack.repositories.runs import RunRepository


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


def test_record_external_publish_idempotent_upsert(session: Session, project_id: int) -> None:
    """Targetless publishes upsert on ``(article_id, version_published)``."""
    art_repo = ArticleRepository(session)
    pub_repo = ArticlePublishRepository(session)

    art = art_repo.create(project_id=project_id, topic_id=None, title="E", slug="external").data
    pub_repo.record_external(
        article_id=art.id,
        version_published=1,
        published_url="https://example.com/external",
        frontmatter_json={"external_path": "manual"},
        mark_article_published=False,
    )
    pub_repo.record_external(
        article_id=art.id,
        version_published=1,
        published_url="https://example.com/external-updated",
        external_ref="post-123",
        mark_article_published=False,
    )

    rows = pub_repo.list_for_article(art.id)
    assert len(rows) == 1
    assert rows[0].target_id is None
    assert rows[0].published_url == "https://example.com/external-updated"
    assert rows[0].frontmatter_json == {"publisher": "agent", "external_ref": "post-123"}


def test_record_external_can_mark_article_published(session: Session, project_id: int) -> None:
    """The agent-publish write records the row and advances first publish."""
    art_repo = ArticleRepository(session)
    pub_repo = ArticlePublishRepository(session)
    run = RunRepository(session).start(project_id=project_id, kind=RunKind.PROCEDURE).data

    art = art_repo.create(project_id=project_id, topic_id=None, title="M", slug="mark").data
    row = session.get(Article, art.id)
    assert row is not None
    row.status = ArticleStatus.EEAT_PASSED
    session.add(row)
    session.commit()
    session.refresh(row)

    env = pub_repo.record_external(
        article_id=art.id,
        version_published=1,
        published_url="https://example.com/mark",
        expected_etag=row.step_etag,
        run_id=run.id,
    )

    assert env.data.target_id is None
    assert env.data.status == ArticlePublishStatus.PUBLISHED
    assert art_repo.get(art.id).status == ArticleStatus.PUBLISHED


def test_set_canonical_target(session: Session, project_id: int) -> None:
    art_repo = ArticleRepository(session)
    target_repo = PublishTargetRepository(session)
    pub_repo = ArticlePublishRepository(session)

    art = art_repo.create(project_id=project_id, topic_id=None, title="C", slug="canon").data
    nuxt = target_repo.add(project_id=project_id, kind=PublishTargetKind.NUXT_CONTENT).data
    out = pub_repo.set_canonical(article_id=art.id, target_id=nuxt.id)
    assert out.data.canonical_target_id == nuxt.id
