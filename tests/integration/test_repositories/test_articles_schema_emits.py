"""Schema emit invariant: at most one is_primary per article."""

from __future__ import annotations

from sqlmodel import Session

from content_stack.repositories.articles import (
    ArticleRepository,
    SchemaEmitRepository,
)


def test_set_primary_unsets_others(session: Session, project_id: int) -> None:
    art_repo = ArticleRepository(session)
    se_repo = SchemaEmitRepository(session)

    art = art_repo.create(project_id=project_id, topic_id=None, title="S", slug="schema").data
    se_repo.set(
        article_id=art.id,
        type="Article",
        schema_json={"@type": "Article"},
        is_primary=True,
    )
    se_repo.set(
        article_id=art.id,
        type="FAQPage",
        schema_json={"@type": "FAQPage"},
        is_primary=True,
    )
    rows = se_repo.list_for_article(art.id)
    primaries = [r for r in rows if r.is_primary]
    assert len(primaries) == 1
    assert primaries[0].type == "FAQPage"


def test_validate_marks_validated_at(session: Session, project_id: int) -> None:
    art_repo = ArticleRepository(session)
    se_repo = SchemaEmitRepository(session)

    art = art_repo.create(
        project_id=project_id, topic_id=None, title="V", slug="schema-validate"
    ).data
    env = se_repo.set(
        article_id=art.id,
        type="Article",
        schema_json={"@type": "Article"},
    )
    assert env.data.validated_at is None
    out = se_repo.validate(env.data.id)
    assert out.data.validated_at is not None
