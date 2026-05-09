"""EEAT evaluations repository.

The criteria themselves live in ``projects.EeatCriteriaRepository`` (M1
already seeds 80 rows with three ``tier='core'`` veto items per D7).
This module hosts the *evaluations* — the per-criterion ``pass|partial|fail``
verdicts written by skill #11 (eeat-gate) into ``eeat_evaluations``.

The repo computes per-dimension and per-system *scores*; the SHIP/FIX/BLOCK
verdict itself is computed by skill #11 (M7) from these scores plus the
core-veto check. PLAN.md L1012-L1031 has the contract.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from content_stack.db.models import (
    EeatCategory,
    EeatCriterion,
    EeatEvaluation,
    EeatTier,
    EeatVerdict,
)
from content_stack.repositories.base import (
    Envelope,
    ValidationError,
)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Output models.
# ---------------------------------------------------------------------------


class EeatEvaluationOut(BaseModel):
    """Public shape for ``eeat_evaluations`` rows."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    article_id: int
    criterion_id: int
    run_id: int
    verdict: EeatVerdict
    notes: str | None
    evaluated_at: datetime


class EeatEvaluationCreate(BaseModel):
    """Input for ``record`` / ``bulk_record``."""

    criterion_id: int
    verdict: EeatVerdict
    notes: str | None = None


class EeatScoreReport(BaseModel):
    """Output of ``score`` — per-dimension + per-system + coverage signals.

    PLAN.md L1014-L1027:
      - dimension_scores: 0..100 average per category C/O/R/E/Exp/Ept/A/T
      - system_scores: GEO = mean(C,O,R,E); SEO = mean(Exp,Ept,A,T)
      - coverage: dict of category → bool (True iff at least one active
        criterion with at least one evaluation)
      - vetoes_failed: list of code strings — tier='core' criteria with
        verdict='fail'
    """

    dimension_scores: dict[str, float]
    system_scores: dict[str, float]
    coverage: dict[str, bool]
    vetoes_failed: list[str]
    total_evaluations: int


# ---------------------------------------------------------------------------
# Repository.
# ---------------------------------------------------------------------------


# Verdict → numeric score for averaging. PLAN.md L1014 narrates 0..100
# with pass=100, partial=50, fail=0.
_VERDICT_SCORE: dict[EeatVerdict, float] = {
    EeatVerdict.PASS: 100.0,
    EeatVerdict.PARTIAL: 50.0,
    EeatVerdict.FAIL: 0.0,
}


class EeatEvaluationRepository:
    """Per-article EEAT evaluation grain."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def record(
        self,
        *,
        article_id: int,
        criterion_id: int,
        run_id: int,
        verdict: EeatVerdict,
        notes: str | None = None,
    ) -> Envelope[EeatEvaluationOut]:
        """Insert a single evaluation row."""
        row = EeatEvaluation(
            article_id=article_id,
            criterion_id=criterion_id,
            run_id=run_id,
            verdict=verdict,
            notes=notes,
            evaluated_at=_utcnow(),
        )
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=EeatEvaluationOut.model_validate(row))

    def bulk_record(
        self,
        *,
        article_id: int,
        run_id: int,
        evaluations: Iterable[EeatEvaluationCreate],
    ) -> Envelope[list[EeatEvaluationOut]]:
        """Insert N evaluation rows in one transaction.

        Used by skill #11 to write the full 80-row audit atomically.
        """
        materialised = list(evaluations)
        if not materialised:
            raise ValidationError("evaluations list must be non-empty")
        rows = [
            EeatEvaluation(
                article_id=article_id,
                criterion_id=e.criterion_id,
                run_id=run_id,
                verdict=e.verdict,
                notes=e.notes,
                evaluated_at=_utcnow(),
            )
            for e in materialised
        ]
        for r in rows:
            self._s.add(r)
        self._s.commit()
        for r in rows:
            self._s.refresh(r)
        return Envelope(data=[EeatEvaluationOut.model_validate(r) for r in rows])

    def list(
        self,
        *,
        article_id: int | None = None,
        run_id: int | None = None,
    ) -> list[EeatEvaluationOut]:
        """List evaluations filtered by article and/or run.

        At least one of ``article_id`` / ``run_id`` must be set so the
        query is bounded.
        """
        if article_id is None and run_id is None:
            raise ValidationError("must provide article_id or run_id")
        stmt = select(EeatEvaluation)
        if article_id is not None:
            stmt = stmt.where(EeatEvaluation.article_id == article_id)
        if run_id is not None:
            stmt = stmt.where(EeatEvaluation.run_id == run_id)
        rows = self._s.exec(stmt.order_by(EeatEvaluation.id.asc())).all()  # type: ignore[union-attr,attr-defined]
        return [EeatEvaluationOut.model_validate(r) for r in rows]

    def score(self, *, article_id: int, run_id: int) -> EeatScoreReport:
        """Aggregate evaluations into per-dimension and per-system scores.

        Joins ``eeat_evaluations`` ↔ ``eeat_criteria`` so we can group by
        ``category`` and check ``tier='core'`` for veto-failure detection.
        """
        rows = self._s.exec(
            select(EeatEvaluation, EeatCriterion).where(
                EeatEvaluation.article_id == article_id,
                EeatEvaluation.run_id == run_id,
                EeatEvaluation.criterion_id == EeatCriterion.id,
            )
        ).all()
        # Bin per dimension.
        per_dim_scores: dict[EeatCategory, list[float]] = {c: [] for c in EeatCategory}
        coverage: dict[EeatCategory, bool] = {c: False for c in EeatCategory}
        vetoes_failed: list[str] = []
        for ev, crit in rows:
            per_dim_scores[crit.category].append(_VERDICT_SCORE[ev.verdict])
            coverage[crit.category] = True
            if crit.tier == EeatTier.CORE and ev.verdict == EeatVerdict.FAIL:
                vetoes_failed.append(crit.code)

        dim_scores = {
            cat.value: round(sum(scores) / len(scores), 2) if scores else 0.0
            for cat, scores in per_dim_scores.items()
        }
        # System scores per PLAN.md L444.
        # GEO = mean(C, O, R, E); SEO = mean(Exp, Ept, A, T).
        geo_keys = (EeatCategory.C, EeatCategory.O, EeatCategory.R, EeatCategory.E)
        seo_keys = (EeatCategory.EXP, EeatCategory.EPT, EeatCategory.A, EeatCategory.T)
        geo_score = round(sum(dim_scores[k.value] for k in geo_keys) / len(geo_keys), 2)
        seo_score = round(sum(dim_scores[k.value] for k in seo_keys) / len(seo_keys), 2)
        return EeatScoreReport(
            dimension_scores=dim_scores,
            system_scores={"GEO": geo_score, "SEO": seo_score},
            coverage={cat.value: covered for cat, covered in coverage.items()},
            vetoes_failed=sorted(vetoes_failed),
            total_evaluations=len(rows),
        )


__all__ = [
    "EeatEvaluationCreate",
    "EeatEvaluationOut",
    "EeatEvaluationRepository",
    "EeatScoreReport",
]
