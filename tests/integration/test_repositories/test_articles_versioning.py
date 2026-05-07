"""Tests for create_version + list_versions on the article repo."""

from __future__ import annotations

from sqlmodel import Session

from content_stack.repositories.articles import ArticleRepository


def test_create_version_snapshots_and_bumps(session: Session, project_id: int) -> None:
    repo = ArticleRepository(session)
    art = repo.create(project_id=project_id, topic_id=None, title="V", slug="vers").data
    e = art.step_etag
    e = repo.set_brief(art.id, {"primary_kw": "kw"}, expected_etag=e).data.step_etag
    e = repo.set_outline(art.id, "outline", expected_etag=e).data.step_etag
    e = repo.set_draft(art.id, "draft body", expected_etag=e).data.step_etag

    snap = repo.create_version(art.id)
    assert snap.data.version == 1
    assert snap.data.outline_md == "outline"
    assert snap.data.draft_md == "draft body"
    # The source row's version should now be 2.
    refreshed = repo.get(art.id)
    assert refreshed.version == 2
    assert refreshed.last_refreshed_at is not None


def test_list_versions_paginates(session: Session, project_id: int) -> None:
    repo = ArticleRepository(session)
    art = repo.create(project_id=project_id, topic_id=None, title="V2", slug="vers2").data
    repo.set_brief(art.id, {}, expected_etag=art.step_etag)
    repo.create_version(art.id)
    repo.create_version(art.id)
    page = repo.list_versions(art.id)
    assert len(page.items) == 2
