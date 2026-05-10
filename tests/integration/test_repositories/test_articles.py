"""Integration tests for ArticleRepository — the procedure-4 happy path."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from content_stack.db.models import ArticleStatus
from content_stack.repositories.articles import ArticleRepository, ResearchSourceRepository
from content_stack.repositories.base import (
    ConflictError,
    NotFoundError,
    ValidationError,
)


def test_create_article_initial_state(session: Session, project_id: int) -> None:
    repo = ArticleRepository(session)
    env = repo.create(
        project_id=project_id,
        topic_id=None,
        title="My Article",
        slug="my-article",
    )
    assert env.data.status == ArticleStatus.BRIEFING
    assert env.data.step_etag is not None
    assert env.data.version == 1


def test_full_procedure_4_happy_path(session: Session, project_id: int) -> None:
    """Walk an article through the full briefing → published flow."""
    from content_stack.db.models import RunKind
    from content_stack.repositories.runs import RunRepository

    repo = ArticleRepository(session)
    run_repo = RunRepository(session)
    run = run_repo.start(project_id=project_id, kind=RunKind.PROCEDURE).data

    art = repo.create(project_id=project_id, topic_id=None, title="A", slug="happy-path").data
    etag = art.step_etag

    out = repo.set_brief(art.id, {"primary_kw": "x"}, expected_etag=etag)
    assert out.data.status == ArticleStatus.OUTLINED
    assert out.data.brief_json == {"primary_kw": "x"}
    etag = out.data.step_etag

    out = repo.set_outline(art.id, "# H1\n## H2", expected_etag=etag)
    assert out.data.status == ArticleStatus.OUTLINED
    etag = out.data.step_etag

    # Skill #7 writes intro.
    out = repo.set_draft(art.id, "Intro paragraph.", expected_etag=etag)
    assert out.data.status == ArticleStatus.OUTLINED
    assert out.data.draft_md == "Intro paragraph."
    etag = out.data.step_etag

    # Skill #8 appends body.
    out = repo.set_draft(art.id, " Body.", expected_etag=etag, append=True)
    assert out.data.draft_md == "Intro paragraph. Body."
    etag = out.data.step_etag

    # Skill #9 appends conclusion.
    out = repo.set_draft(art.id, " Conclusion.", expected_etag=etag, append=True)
    assert out.data.draft_md == "Intro paragraph. Body. Conclusion."
    etag = out.data.step_etag

    # Procedure runner closes the draft phase.
    out = repo.mark_drafted(art.id, expected_etag=etag)
    assert out.data.status == ArticleStatus.DRAFTED
    etag = out.data.step_etag

    # Editor pass.
    out = repo.set_edited(art.id, "Edited text.", expected_etag=etag)
    assert out.data.status == ArticleStatus.EDITED
    etag = out.data.step_etag

    # Humanizer pass replaces the edited body without changing status.
    out = repo.set_edited(art.id, "Humanized text.", expected_etag=etag)
    assert out.data.status == ArticleStatus.EDITED
    assert out.data.edited_md == "Humanized text."
    etag = out.data.step_etag

    # EEAT gate verdict=SHIP.
    out = repo.mark_eeat_passed(art.id, expected_etag=etag, run_id=run.id, eeat_criteria_version=1)
    assert out.data.status == ArticleStatus.EEAT_PASSED
    assert out.data.eeat_criteria_version_used == 1
    etag = out.data.step_etag

    # Publish.
    out = repo.mark_published(art.id, expected_etag=etag, run_id=run.id)
    assert out.data.status == ArticleStatus.PUBLISHED


def test_etag_mismatch_raises_conflict(session: Session, project_id: int) -> None:
    repo = ArticleRepository(session)
    art = repo.create(project_id=project_id, topic_id=None, title="B", slug="etag-test").data
    with pytest.raises(ConflictError) as exc_info:
        repo.set_brief(art.id, {"x": 1}, expected_etag="bogus-etag")
    assert exc_info.value.code == -32008
    assert "expected_etag" in exc_info.value.detail


def test_set_brief_from_wrong_status_raises(session: Session, project_id: int) -> None:
    repo = ArticleRepository(session)
    art = repo.create(project_id=project_id, topic_id=None, title="C", slug="wrong-status").data
    out = repo.set_brief(art.id, {"x": 1}, expected_etag=art.step_etag)
    # Now status is OUTLINED, calling set_brief again should fail.
    with pytest.raises(ConflictError) as exc_info:
        repo.set_brief(art.id, {"x": 2}, expected_etag=out.data.step_etag)
    assert "set_brief requires" in exc_info.value.detail


def test_slug_immutable_post_publish(session: Session, project_id: int) -> None:
    from content_stack.db.models import RunKind
    from content_stack.repositories.runs import RunRepository

    repo = ArticleRepository(session)
    run = RunRepository(session).start(project_id=project_id, kind=RunKind.PROCEDURE).data
    art = repo.create(project_id=project_id, topic_id=None, title="D", slug="slug-immut").data
    e = art.step_etag
    e = repo.set_brief(art.id, {"x": 1}, expected_etag=e).data.step_etag
    e = repo.set_outline(art.id, "outline", expected_etag=e).data.step_etag
    e = repo.set_draft(art.id, "draft", expected_etag=e).data.step_etag
    e = repo.mark_drafted(art.id, expected_etag=e).data.step_etag
    e = repo.set_edited(art.id, "edited", expected_etag=e).data.step_etag
    e = repo.mark_eeat_passed(
        art.id, expected_etag=e, run_id=run.id, eeat_criteria_version=1
    ).data.step_etag
    repo.mark_published(art.id, expected_etag=e, run_id=run.id)

    with pytest.raises(ConflictError) as exc_info:
        repo.update_slug(art.id, "new-slug")
    assert "immutable post-publish" in exc_info.value.detail


def test_pre_publish_slug_change(session: Session, project_id: int) -> None:
    repo = ArticleRepository(session)
    art = repo.create(project_id=project_id, topic_id=None, title="E", slug="orig-slug").data
    out = repo.update_slug(art.id, "new-slug")
    assert out.data.slug == "new-slug"


def test_duplicate_slug_raises(session: Session, project_id: int) -> None:
    repo = ArticleRepository(session)
    repo.create(project_id=project_id, topic_id=None, title="F", slug="dup-slug")
    with pytest.raises(ConflictError):
        repo.create(project_id=project_id, topic_id=None, title="F2", slug="dup-slug")


def test_mark_refresh_due_no_etag(session: Session, project_id: int) -> None:
    from content_stack.db.models import RunKind
    from content_stack.repositories.runs import RunRepository

    repo = ArticleRepository(session)
    run = RunRepository(session).start(project_id=project_id, kind=RunKind.PROCEDURE).data
    art = repo.create(project_id=project_id, topic_id=None, title="R", slug="refresh-due").data
    e = art.step_etag
    e = repo.set_brief(art.id, {"x": 1}, expected_etag=e).data.step_etag
    e = repo.set_outline(art.id, "o", expected_etag=e).data.step_etag
    e = repo.set_draft(art.id, "d", expected_etag=e).data.step_etag
    e = repo.mark_drafted(art.id, expected_etag=e).data.step_etag
    e = repo.set_edited(art.id, "e", expected_etag=e).data.step_etag
    e = repo.mark_eeat_passed(
        art.id, expected_etag=e, run_id=run.id, eeat_criteria_version=1
    ).data.step_etag
    repo.mark_published(art.id, expected_etag=e, run_id=run.id)
    out = repo.mark_refresh_due(art.id, reason="GSC drop detected")
    assert out.data.status == ArticleStatus.REFRESH_DUE
    # Reason captured in metadata.
    assert out.data.brief_json is not None
    assert out.data.brief_json["refresh_history"][0]["reason"] == "GSC drop detected"


def test_list_due_for_refresh(session: Session, project_id: int) -> None:
    repo = ArticleRepository(session)
    page = repo.list_due_for_refresh(project_id)
    assert len(page.items) == 0
    # Creating an article in BRIEFING shouldn't appear.
    repo.create(project_id=project_id, topic_id=None, title="X", slug="not-due")
    page = repo.list_due_for_refresh(project_id)
    assert len(page.items) == 0


def test_list_filters(session: Session, project_id: int) -> None:
    repo = ArticleRepository(session)
    repo.create(project_id=project_id, topic_id=None, title="L1", slug="l1")
    repo.create(project_id=project_id, topic_id=None, title="L2", slug="l2")
    page = repo.list(project_id, status=ArticleStatus.BRIEFING)
    assert len(page.items) == 2


def test_research_source_list_can_filter_used(session: Session, project_id: int) -> None:
    art = (
        ArticleRepository(session)
        .create(project_id=project_id, topic_id=None, title="Sources", slug="sources-filter")
        .data
    )
    repo = ResearchSourceRepository(session)
    unused = repo.add(article_id=art.id, url="https://example.com/a", used=False).data
    used = repo.add(article_id=art.id, url="https://example.com/b", used=True).data

    assert [row.id for row in repo.list(art.id)] == [unused.id, used.id]
    assert [row.id for row in repo.list(art.id, used=True)] == [used.id]
    assert [row.id for row in repo.list(art.id, used=False)] == [unused.id]


def test_get_missing_article(session: Session) -> None:
    repo = ArticleRepository(session)
    with pytest.raises(NotFoundError):
        repo.get(99999)


def test_create_validates_slug(session: Session, project_id: int) -> None:
    repo = ArticleRepository(session)
    with pytest.raises(ValidationError):
        repo.create(project_id=project_id, topic_id=None, title="T", slug="")
