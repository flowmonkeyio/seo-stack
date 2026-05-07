"""Tests for EeatEvaluationRepository — bulk_record + score."""

from __future__ import annotations

from sqlmodel import Session

from content_stack.db.models import EeatVerdict, RunKind
from content_stack.repositories.articles import ArticleRepository
from content_stack.repositories.eeat import (
    EeatEvaluationCreate,
    EeatEvaluationRepository,
)
from content_stack.repositories.projects import EeatCriteriaRepository
from content_stack.repositories.runs import RunRepository


def test_bulk_record_for_full_audit(session: Session, project_id: int) -> None:
    art_repo = ArticleRepository(session)
    crit_repo = EeatCriteriaRepository(session)
    run_repo = RunRepository(session)
    eeat_repo = EeatEvaluationRepository(session)

    art = art_repo.create(project_id=project_id, topic_id=None, title="E", slug="eeat-art").data
    run = run_repo.start(project_id=project_id, kind=RunKind.EEAT_AUDIT).data
    crits = crit_repo.list(project_id)
    assert len(crits) == 80

    evaluations = [
        EeatEvaluationCreate(
            criterion_id=c.id,
            verdict=EeatVerdict.PASS,
            notes=None,
        )
        for c in crits
    ]
    env = eeat_repo.bulk_record(
        article_id=art.id,
        run_id=run.id,
        evaluations=evaluations,
    )
    assert len(env.data) == 80


def test_score_dimension_and_system(session: Session, project_id: int) -> None:
    art_repo = ArticleRepository(session)
    crit_repo = EeatCriteriaRepository(session)
    run_repo = RunRepository(session)
    eeat_repo = EeatEvaluationRepository(session)

    art = art_repo.create(project_id=project_id, topic_id=None, title="S", slug="score-art").data
    run = run_repo.start(project_id=project_id, kind=RunKind.EEAT_AUDIT).data
    crits = crit_repo.list(project_id)
    eeat_repo.bulk_record(
        article_id=art.id,
        run_id=run.id,
        evaluations=[
            EeatEvaluationCreate(criterion_id=c.id, verdict=EeatVerdict.PASS) for c in crits
        ],
    )
    score = eeat_repo.score(article_id=art.id, run_id=run.id)
    assert score.total_evaluations == 80
    # All passes → all dimensions are 100, GEO=SEO=100.
    assert all(v == 100.0 for v in score.dimension_scores.values())
    assert score.system_scores["GEO"] == 100.0
    assert score.system_scores["SEO"] == 100.0
    assert score.vetoes_failed == []
    assert all(score.coverage.values())  # 100% coverage


def test_core_veto_failure_surfaces(session: Session, project_id: int) -> None:
    art_repo = ArticleRepository(session)
    crit_repo = EeatCriteriaRepository(session)
    run_repo = RunRepository(session)
    eeat_repo = EeatEvaluationRepository(session)
    from content_stack.db.models import EeatTier

    art = art_repo.create(project_id=project_id, topic_id=None, title="V", slug="veto-art").data
    run = run_repo.start(project_id=project_id, kind=RunKind.EEAT_AUDIT).data
    crits = crit_repo.list(project_id)
    cores = [c for c in crits if c.tier == EeatTier.CORE]
    eeat_repo.bulk_record(
        article_id=art.id,
        run_id=run.id,
        evaluations=[
            EeatEvaluationCreate(
                criterion_id=c.id,
                verdict=(EeatVerdict.FAIL if c.tier == EeatTier.CORE else EeatVerdict.PASS),
            )
            for c in crits
        ],
    )
    score = eeat_repo.score(article_id=art.id, run_id=run.id)
    failed = sorted(score.vetoes_failed)
    assert failed == sorted(c.code for c in cores)
