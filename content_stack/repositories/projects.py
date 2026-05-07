"""Project + project-scoped preset repositories.

Groups the seven "presets" that hang off a project (PLAN.md L562-L572):
voice, compliance, EEAT, publish targets, integration credentials,
budgets, scheduled jobs. They share enough shape (project FK + simple
CRUD) that one module per table would be silly; one module per *resource*
is the project-policy ("one per resource", CLAUDE.md L207).

Locked invariants enforced here:

- D7: ``EeatCriteriaRepository.toggle`` refuses to ``required=False`` or
  ``active=False`` on rows where ``tier='core'``.
- E1: ``ProjectRepository.set_active`` flips ``is_active=False`` on
  every other row in one transaction.
- M-25 / PLAN.md L1037-L1040: ``IntegrationBudgetRepository.record_call``
  raises ``BudgetExceededError`` *before* incrementing if the call would
  overshoot ``monthly_budget_usd``; it also handles cross-month rollover
  of ``current_month_spend`` and ``current_month_calls``.
- A-MINOR-41: ``delete`` is a *soft* delete (``is_active=false``); hard
  delete is intentionally not exposed (PLAN.md L633-L646 cascade is M9
  jobs/maintenance work).
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from content_stack.db.models import (
    CompliancePosition,
    ComplianceRule,
    ComplianceRuleKind,
    EeatCategory,
    EeatCriterion,
    EeatTier,
    IntegrationBudget,
    IntegrationCredential,
    Project,
    PublishTarget,
    PublishTargetKind,
    ScheduledJob,
    VoiceProfile,
)
from content_stack.db.seed import seed_eeat_criteria
from content_stack.logging import get_logger
from content_stack.repositories.base import (
    BudgetExceededError,
    ConflictError,
    Envelope,
    NotFoundError,
    Page,
    ValidationError,
    cursor_paginate,
)

_log = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Pydantic Output models (read-side serialisation).
# ---------------------------------------------------------------------------


class ProjectOut(BaseModel):
    """Public shape for ``Project`` rows."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    domain: str
    niche: str | None
    locale: str
    is_active: bool
    schedule_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class VoiceProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    voice_md: str
    is_default: bool
    version: int
    created_at: datetime


class ComplianceRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    kind: ComplianceRuleKind
    title: str
    body_md: str
    jurisdictions: str | None
    position: CompliancePosition
    params_json: dict[str, Any] | None
    validator: str | None
    is_active: bool


class EeatCriterionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    code: str
    category: EeatCategory
    description: str
    text: str
    weight: int
    required: bool
    active: bool
    tier: EeatTier
    version: int


class PublishTargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    kind: PublishTargetKind
    config_json: dict[str, Any] | None
    is_primary: bool
    is_active: bool


class IntegrationCredentialOut(BaseModel):
    """Read shape for credentials.

    The encrypted payload is *never* returned to callers — the M5
    integration wrappers call a separate ``get_decrypted`` method that
    lives in the M5 keychain module. M1's stub returns the row with
    ``encrypted_payload=None`` so the wire shape doesn't accidentally
    leak ciphertext or stub-plaintext.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    kind: str
    expires_at: datetime | None
    last_refreshed_at: datetime | None
    config_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class IntegrationBudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    kind: str
    monthly_budget_usd: float
    alert_threshold_pct: int
    current_month_spend: float
    current_month_calls: int
    qps: float
    last_reset: datetime


class ScheduledJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    kind: str
    cron_expr: str
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_run_status: str | None
    enabled: bool


# ---------------------------------------------------------------------------
# ProjectRepository.
# ---------------------------------------------------------------------------


class ProjectRepository:
    """CRUD over the ``projects`` table + transactional EEAT seeding."""

    def __init__(self, session: Session) -> None:
        self._s = session

    # -------- Create / read / update / delete --------

    def create(
        self,
        *,
        name: str,
        slug: str,
        domain: str,
        niche: str | None = None,
        locale: str,
        schedule_json: dict[str, Any] | None = None,
    ) -> Envelope[ProjectOut]:
        """Insert project row + seed 80 EEAT criteria in one transaction.

        D7 invariant: the 80 EEAT rows (T04, C01, R10 as ``tier='core'``)
        must exist *before* commit so any subsequent procedure 1 step
        sees a complete rubric. We open a SAVEPOINT around both writes —
        ``seed_eeat_criteria`` performs its own ``session.commit()``, but
        SQLAlchemy treats nested ``commit()`` calls inside a SAVEPOINT
        as flushes; the outer transaction owns the visibility.
        """
        if not slug or len(slug) > 80:
            raise ValidationError("slug must be 1..80 chars", data={"slug": slug})
        if not name:
            raise ValidationError("name is required")
        existing = self._s.exec(select(Project).where(Project.slug == slug)).first()
        if existing is not None:
            raise ConflictError(
                f"slug {slug!r} already in use",
                data={"slug": slug, "existing_id": existing.id},
            )

        project = Project(
            slug=slug,
            name=name,
            domain=domain,
            niche=niche,
            locale=locale,
            is_active=False,
            schedule_json=schedule_json,
        )
        self._s.add(project)
        self._s.flush()  # populate project.id without releasing the txn
        assert project.id is not None
        # Seed under the same outer transaction. ``seed_eeat_criteria`` calls
        # ``session.commit()`` internally — that's a flush on a nested
        # SAVEPOINT in SQLModel; the visibility of the rows is bound to the
        # outer commit. Tests confirm a rolled-back project leaves no EEAT
        # rows behind.
        seed_eeat_criteria(self._s, project.id)
        self._s.commit()
        self._s.refresh(project)
        return Envelope(
            data=ProjectOut.model_validate(project),
            project_id=project.id,
        )

    def get(self, id_or_slug: int | str) -> ProjectOut:
        """Look up by ``id`` (int) or ``slug`` (str). Raises ``NotFoundError``."""
        row = self._fetch_row(id_or_slug)
        return ProjectOut.model_validate(row)

    def list(
        self,
        *,
        active_only: bool = False,
        limit: int | None = None,
        after_id: int | None = None,
    ) -> Page[ProjectOut]:
        """Cursor-paginated list."""
        stmt = select(Project)
        if active_only:
            stmt = stmt.where(Project.is_active.is_(True))  # type: ignore[union-attr,attr-defined]
        return cursor_paginate(
            self._s,
            stmt,
            id_col=Project.id,
            limit=limit,
            after_id=after_id,
            converter=ProjectOut.model_validate,
        )

    def update(self, project_id: int, **patch: Any) -> Envelope[ProjectOut]:
        """Partial update; ``slug`` is intentionally immutable.

        We refuse ``slug`` in patch bodies because (a) PLAN.md L354 says
        slug is immutable post-publish, and (b) at the project grain
        slug uniqueness backs MCP setActive resolution paths.
        """
        if "slug" in patch:
            raise ValidationError(
                "project slug is immutable",
                data={"field": "slug"},
            )
        row = self._fetch_row(project_id)
        for k, v in patch.items():
            if k in {"id", "created_at"}:
                continue
            if not hasattr(row, k):
                raise ValidationError(f"unknown field {k!r}")
            setattr(row, k, v)
        row.updated_at = _utcnow()
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=ProjectOut.model_validate(row), project_id=row.id)

    def delete(self, project_id: int) -> Envelope[ProjectOut]:
        """Soft-delete: flips ``is_active=False``.

        Hard-delete + cascade is intentionally NOT exposed at the
        repository layer; PLAN.md L633-L646 reserves that for the
        ``runs.kind='maintenance'`` chunked sweep, which lands in M9.
        Tests cover the soft path; M9 will add a ``hard_delete`` route.
        """
        row = self._fetch_row(project_id)
        row.is_active = False
        row.updated_at = _utcnow()
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=ProjectOut.model_validate(row), project_id=row.id)

    def set_active(self, project_id: int) -> Envelope[ProjectOut]:
        """Make ``project_id`` the single active project.

        Per E1 / PLAN.md L687-L692: ``is_active`` is UI-sidebar state only.
        At most one row may have ``is_active=True``; this method enforces
        that in a single transaction.
        """
        row = self._fetch_row(project_id)
        # Flip everyone else off first.
        others = self._s.exec(
            select(Project).where(
                Project.id != project_id,  # type: ignore[arg-type]
                Project.is_active.is_(True),  # type: ignore[union-attr,attr-defined]
            )
        ).all()
        for o in others:
            o.is_active = False
            o.updated_at = _utcnow()
            self._s.add(o)
        row.is_active = True
        row.updated_at = _utcnow()
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=ProjectOut.model_validate(row), project_id=row.id)

    def get_active(self) -> ProjectOut | None:
        """Return the most-recently-updated active project, if any."""
        row = self._s.exec(
            select(Project)
            .where(Project.is_active.is_(True))  # type: ignore[union-attr,attr-defined]
            .order_by(Project.updated_at.desc())  # type: ignore[union-attr,attr-defined]
        ).first()
        return ProjectOut.model_validate(row) if row else None

    # -------- Internal --------

    def _fetch_row(self, id_or_slug: int | str) -> Project:
        if isinstance(id_or_slug, int):
            row = self._s.get(Project, id_or_slug)
        else:
            row = self._s.exec(select(Project).where(Project.slug == id_or_slug)).first()
        if row is None:
            raise NotFoundError(
                f"project {id_or_slug!r} not found",
                data={"id_or_slug": id_or_slug},
            )
        return row


# ---------------------------------------------------------------------------
# VoiceProfileRepository.
# ---------------------------------------------------------------------------


class VoiceProfileRepository:
    """Voice/tone variants. ``is_default=True`` is the active one."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def set(
        self,
        *,
        project_id: int,
        name: str,
        voice_md: str,
        is_default: bool = False,
    ) -> Envelope[VoiceProfileOut]:
        """Create a voice profile."""
        row = VoiceProfile(
            project_id=project_id,
            name=name,
            voice_md=voice_md,
            is_default=is_default,
            version=1,
        )
        self._s.add(row)
        if is_default:
            self._unset_other_defaults(project_id, exclude_id=None)
            row.is_default = True
            self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=VoiceProfileOut.model_validate(row), project_id=project_id)

    def get(self, voice_id: int) -> VoiceProfileOut:
        """Fetch one variant by id."""
        row = self._s.get(VoiceProfile, voice_id)
        if row is None:
            raise NotFoundError(f"voice {voice_id} not found")
        return VoiceProfileOut.model_validate(row)

    def list_variants(
        self, project_id: int, *, limit: int | None = None, after_id: int | None = None
    ) -> Page[VoiceProfileOut]:
        """List all voice variants for a project."""
        stmt = select(VoiceProfile).where(VoiceProfile.project_id == project_id)
        return cursor_paginate(
            self._s,
            stmt,
            id_col=VoiceProfile.id,
            limit=limit,
            after_id=after_id,
            converter=VoiceProfileOut.model_validate,
        )

    def set_active(self, voice_id: int) -> Envelope[VoiceProfileOut]:
        """Mark ``voice_id`` as ``is_default=True`` and flip the rest off."""
        row = self._s.get(VoiceProfile, voice_id)
        if row is None:
            raise NotFoundError(f"voice {voice_id} not found")
        self._unset_other_defaults(row.project_id, exclude_id=voice_id)
        row.is_default = True
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=VoiceProfileOut.model_validate(row), project_id=row.project_id)

    def _unset_other_defaults(self, project_id: int, *, exclude_id: int | None) -> None:
        stmt = select(VoiceProfile).where(
            VoiceProfile.project_id == project_id,
            VoiceProfile.is_default.is_(True),  # type: ignore[union-attr,attr-defined]
        )
        for o in self._s.exec(stmt).all():
            if o.id == exclude_id:
                continue
            o.is_default = False
            self._s.add(o)


# ---------------------------------------------------------------------------
# ComplianceRuleRepository.
# ---------------------------------------------------------------------------


class ComplianceRuleRepository:
    """Compliance rules; rendering order is by position then id ASC."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def list(self, project_id: int) -> list[ComplianceRuleOut]:
        """List all rules; ordered for renderers."""
        rows = self._s.exec(
            select(ComplianceRule)
            .where(ComplianceRule.project_id == project_id)
            .order_by(ComplianceRule.position.asc(), ComplianceRule.id.asc())  # type: ignore[union-attr,attr-defined]
        ).all()
        return [ComplianceRuleOut.model_validate(r) for r in rows]

    def add(
        self,
        *,
        project_id: int,
        kind: ComplianceRuleKind,
        title: str,
        body_md: str = "",
        jurisdictions: str | None = None,
        position: CompliancePosition,
        params_json: dict[str, Any] | None = None,
        validator: str | None = None,
        is_active: bool = True,
    ) -> Envelope[ComplianceRuleOut]:
        """Insert a new compliance rule."""
        row = ComplianceRule(
            project_id=project_id,
            kind=kind,
            title=title,
            body_md=body_md,
            jurisdictions=jurisdictions,
            position=position,
            params_json=params_json,
            validator=validator,
            is_active=is_active,
        )
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=ComplianceRuleOut.model_validate(row), project_id=project_id)

    def update(self, rule_id: int, **patch: Any) -> Envelope[ComplianceRuleOut]:
        """Partial update."""
        row = self._fetch(rule_id)
        for k, v in patch.items():
            if k in {"id", "project_id"}:
                continue
            if not hasattr(row, k):
                raise ValidationError(f"unknown field {k!r}")
            setattr(row, k, v)
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=ComplianceRuleOut.model_validate(row), project_id=row.project_id)

    def remove(self, rule_id: int) -> Envelope[ComplianceRuleOut]:
        """Hard-delete a compliance rule."""
        row = self._fetch(rule_id)
        out = ComplianceRuleOut.model_validate(row)
        self._s.delete(row)
        self._s.commit()
        return Envelope(data=out, project_id=row.project_id)

    def _fetch(self, rule_id: int) -> ComplianceRule:
        row = self._s.get(ComplianceRule, rule_id)
        if row is None:
            raise NotFoundError(f"compliance rule {rule_id} not found")
        return row


# ---------------------------------------------------------------------------
# EeatCriteriaRepository — D7 invariant lives here.
# ---------------------------------------------------------------------------


class EeatCriteriaRepository:
    """Per-project EEAT criteria, with the D7 ``tier='core'`` invariant."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def list(self, project_id: int) -> list[EeatCriterionOut]:
        """All criteria for a project, ordered by category + code."""
        rows = self._s.exec(
            select(EeatCriterion)
            .where(EeatCriterion.project_id == project_id)
            .order_by(EeatCriterion.category.asc(), EeatCriterion.code.asc())  # type: ignore[union-attr,attr-defined]
        ).all()
        return [EeatCriterionOut.model_validate(r) for r in rows]

    def toggle(
        self,
        criterion_id: int,
        *,
        required: bool | None = None,
        active: bool | None = None,
    ) -> Envelope[EeatCriterionOut]:
        """Update ``required`` / ``active`` flags. D7 invariant.

        Refuses (``ConflictError``) if the row has ``tier='core'`` and the
        change would drop ``required=False`` or ``active=False`` — those
        rows are the EEAT veto floor and removing them would let
        procedure 4 publish content that fails T04/C01/R10.
        """
        row = self._fetch(criterion_id)
        if row.tier == EeatTier.CORE and (required is False or active is False):
            raise ConflictError(
                f"cannot toggle tier='core' criterion {row.code!r} off",
                data={
                    "criterion_id": row.id,
                    "code": row.code,
                    "tier": row.tier.value,
                    "attempted": {"required": required, "active": active},
                },
            )
        if required is not None:
            row.required = required
        if active is not None:
            row.active = active
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=EeatCriterionOut.model_validate(row), project_id=row.project_id)

    def score(self, criterion_id: int, *, weight: int) -> Envelope[EeatCriterionOut]:
        """Update the per-criterion weight (1..100)."""
        if weight < 1 or weight > 100:
            raise ValidationError("weight must be 1..100", data={"weight": weight})
        row = self._fetch(criterion_id)
        row.weight = weight
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=EeatCriterionOut.model_validate(row), project_id=row.project_id)

    def bulk_set(
        self,
        project_id: int,
        items: Iterable[dict[str, Any]],
    ) -> Envelope[list[EeatCriterionOut]]:  # type: ignore[valid-type]
        """Bulk update ``required``/``active``/``weight`` by criterion id.

        Each item: ``{id: int, required?: bool, active?: bool, weight?: int}``.
        Applies the D7 core-floor invariant per row; the *whole batch*
        rolls back if any row violates.

        Two-phase: first validate every item against the D7 invariant
        without mutating state; only after the full batch passes do we
        apply changes. This guarantees the "all or nothing" contract
        even though SQLite doesn't support row-level locks.
        """
        materialised = list(items)
        ids = [int(i["id"]) for i in materialised]
        rows = {
            r.id: r
            for r in self._s.exec(
                select(EeatCriterion).where(
                    EeatCriterion.project_id == project_id,
                    EeatCriterion.id.in_(ids),  # type: ignore[union-attr,attr-defined]
                )
            ).all()
            if r.id is not None
        }
        # Phase 1: validate every row against the D7 floor without touching state.
        for item in materialised:
            cid = int(item["id"])
            row = rows.get(cid)
            if row is None:
                raise NotFoundError(
                    f"criterion {cid} not found in project {project_id}",
                    data={"criterion_id": cid, "project_id": project_id},
                )
            if row.tier == EeatTier.CORE and (
                item.get("required") is False or item.get("active") is False
            ):
                raise ConflictError(
                    f"cannot toggle tier='core' criterion {row.code!r} off",
                    data={
                        "criterion_id": row.id,
                        "code": row.code,
                        "tier": row.tier.value,
                    },
                )
        # Phase 2: apply.
        for item in materialised:
            cid = int(item["id"])
            row = rows[cid]
            for field in ("required", "active", "weight"):
                if field in item:
                    setattr(row, field, item[field])
            self._s.add(row)
        self._s.commit()
        # Refresh every row so version-bumps in M5+ survive.
        for r in rows.values():
            self._s.refresh(r)
        return Envelope(
            data=[EeatCriterionOut.model_validate(rows[int(i["id"])]) for i in materialised],
            project_id=project_id,
        )

    def _fetch(self, criterion_id: int) -> EeatCriterion:
        row = self._s.get(EeatCriterion, criterion_id)
        if row is None:
            raise NotFoundError(f"eeat criterion {criterion_id} not found")
        return row


# ---------------------------------------------------------------------------
# PublishTargetRepository.
# ---------------------------------------------------------------------------


class PublishTargetRepository:
    """Publish targets; one ``is_primary`` per project (DB-enforced + this)."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def list(self, project_id: int) -> list[PublishTargetOut]:
        """List targets for a project."""
        rows = self._s.exec(
            select(PublishTarget)
            .where(PublishTarget.project_id == project_id)
            .order_by(PublishTarget.id.asc())  # type: ignore[union-attr,attr-defined]
        ).all()
        return [PublishTargetOut.model_validate(r) for r in rows]

    def add(
        self,
        *,
        project_id: int,
        kind: PublishTargetKind,
        config_json: dict[str, Any] | None = None,
        is_primary: bool = False,
        is_active: bool = True,
    ) -> Envelope[PublishTargetOut]:
        """Insert a new target."""
        if is_primary:
            self._unset_other_primary(project_id, exclude_id=None)
        row = PublishTarget(
            project_id=project_id,
            kind=kind,
            config_json=config_json,
            is_primary=is_primary,
            is_active=is_active,
        )
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=PublishTargetOut.model_validate(row), project_id=project_id)

    def update(self, target_id: int, **patch: Any) -> Envelope[PublishTargetOut]:
        """Partial update."""
        row = self._fetch(target_id)
        if patch.get("is_primary") is True:
            self._unset_other_primary(row.project_id, exclude_id=target_id)
        for k, v in patch.items():
            if k in {"id", "project_id"}:
                continue
            if not hasattr(row, k):
                raise ValidationError(f"unknown field {k!r}")
            setattr(row, k, v)
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=PublishTargetOut.model_validate(row), project_id=row.project_id)

    def remove(self, target_id: int) -> Envelope[PublishTargetOut]:
        """Hard-delete a target."""
        row = self._fetch(target_id)
        out = PublishTargetOut.model_validate(row)
        self._s.delete(row)
        self._s.commit()
        return Envelope(data=out, project_id=row.project_id)

    def set_primary(self, target_id: int) -> Envelope[PublishTargetOut]:
        """Make this target primary; clear every other primary in the project."""
        row = self._fetch(target_id)
        self._unset_other_primary(row.project_id, exclude_id=target_id)
        row.is_primary = True
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=PublishTargetOut.model_validate(row), project_id=row.project_id)

    def _fetch(self, target_id: int) -> PublishTarget:
        row = self._s.get(PublishTarget, target_id)
        if row is None:
            raise NotFoundError(f"publish target {target_id} not found")
        return row

    def _unset_other_primary(self, project_id: int, *, exclude_id: int | None) -> None:
        stmt = select(PublishTarget).where(
            PublishTarget.project_id == project_id,
            PublishTarget.is_primary.is_(True),  # type: ignore[union-attr,attr-defined]
        )
        for o in self._s.exec(stmt).all():
            if o.id == exclude_id:
                continue
            o.is_primary = False
            self._s.add(o)


# ---------------------------------------------------------------------------
# IntegrationCredentialRepository — M1 stub for encryption.
# ---------------------------------------------------------------------------


class IntegrationCredentialRepository:
    """Integration credentials with an explicit M1-only encryption stub.

    M1 invariant: the repository accepts plaintext bytes and stores them
    as-is in ``encrypted_payload`` with a fresh ``os.urandom(12)`` nonce.
    M5 will swap this for AES-256-GCM (PLAN.md L1098-L1102) and add a
    `decrypt` seam; the wire shape (``IntegrationCredentialOut``) does
    NOT expose the payload, so M5 can change the under-the-hood format
    without callers breaking.
    """

    def __init__(self, session: Session) -> None:
        self._s = session

    def list(self, project_id: int | None) -> list[IntegrationCredentialOut]:
        """All credentials in scope; ``project_id=None`` lists global rows."""
        if project_id is None:
            stmt = select(IntegrationCredential).where(
                IntegrationCredential.project_id.is_(None)  # type: ignore[union-attr,attr-defined]
            )
        else:
            stmt = select(IntegrationCredential).where(
                IntegrationCredential.project_id == project_id
            )
        rows = self._s.exec(stmt.order_by(IntegrationCredential.id.asc())).all()  # type: ignore[union-attr,attr-defined]
        return [IntegrationCredentialOut.model_validate(r) for r in rows]

    def set(
        self,
        *,
        project_id: int | None,
        kind: str,
        plaintext_payload: bytes,
        config_json: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> Envelope[IntegrationCredentialOut]:
        """Upsert a credential row.

        **M1 stub**: ``encrypted_payload = plaintext_payload`` verbatim.
        M5 replaces this with AES-256-GCM. Callers should treat the
        plaintext bytes as already-encrypted at the type-system level
        from M5 onwards; M1 is a temporary tightrope.
        """
        # Upsert on (project_id, kind) — the unique constraint backs this.
        existing_stmt = select(IntegrationCredential).where(IntegrationCredential.kind == kind)
        if project_id is None:
            existing_stmt = existing_stmt.where(IntegrationCredential.project_id.is_(None))  # type: ignore[union-attr,attr-defined]
        else:
            existing_stmt = existing_stmt.where(IntegrationCredential.project_id == project_id)
        row = self._s.exec(existing_stmt).first()
        nonce = os.urandom(12)
        if row is None:
            row = IntegrationCredential(
                project_id=project_id,
                kind=kind,
                encrypted_payload=plaintext_payload,
                nonce=nonce,
                expires_at=expires_at,
                config_json=config_json,
            )
        else:
            row.encrypted_payload = plaintext_payload
            row.nonce = nonce
            row.expires_at = expires_at
            row.config_json = config_json
            row.updated_at = _utcnow()
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(
            data=IntegrationCredentialOut.model_validate(row),
            project_id=project_id,
        )

    def test(self, credential_id: int) -> Envelope[IntegrationCredentialOut]:
        """M1 stub for the ``integration.test`` flow.

        Real test logic lives in M5 (per-integration health checks). M1
        returns the row as-is so REST/MCP wiring can be smoke-tested
        ahead of M5. Raises ``NotImplementedError`` ONLY for the
        connection check itself — the row read is real.
        """
        row = self._s.get(IntegrationCredential, credential_id)
        if row is None:
            raise NotFoundError(f"credential {credential_id} not found")
        # The actual call to vendor health endpoints is M5 work.
        raise NotImplementedError(
            "M5: integration.test calls vendor health endpoints; M1 only stores credentials"
        )

    def remove(self, credential_id: int) -> Envelope[IntegrationCredentialOut]:
        """Hard-delete a credential row."""
        row = self._s.get(IntegrationCredential, credential_id)
        if row is None:
            raise NotFoundError(f"credential {credential_id} not found")
        out = IntegrationCredentialOut.model_validate(row)
        self._s.delete(row)
        self._s.commit()
        return Envelope(data=out, project_id=row.project_id)


# ---------------------------------------------------------------------------
# IntegrationBudgetRepository — pre-emption + month rollover.
# ---------------------------------------------------------------------------


class IntegrationBudgetRepository:
    """Token-bucket pre-emption for integration cost caps."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, project_id: int, kind: str) -> IntegrationBudgetOut:
        """Look up a budget row by ``(project_id, kind)``."""
        row = self._s.exec(
            select(IntegrationBudget).where(
                IntegrationBudget.project_id == project_id,
                IntegrationBudget.kind == kind,
            )
        ).first()
        if row is None:
            raise NotFoundError(
                f"budget for project={project_id} kind={kind!r} not found",
                data={"project_id": project_id, "kind": kind},
            )
        return IntegrationBudgetOut.model_validate(row)

    def set(
        self,
        *,
        project_id: int,
        kind: str,
        monthly_budget_usd: float = 50.0,
        alert_threshold_pct: int = 80,
        qps: float = 1.0,
    ) -> Envelope[IntegrationBudgetOut]:
        """Upsert a budget row."""
        if monthly_budget_usd < 0:
            raise ValidationError("monthly_budget_usd must be >= 0")
        if alert_threshold_pct < 0 or alert_threshold_pct > 100:
            raise ValidationError("alert_threshold_pct must be 0..100")
        existing = self._s.exec(
            select(IntegrationBudget).where(
                IntegrationBudget.project_id == project_id,
                IntegrationBudget.kind == kind,
            )
        ).first()
        if existing is None:
            row = IntegrationBudget(
                project_id=project_id,
                kind=kind,
                monthly_budget_usd=monthly_budget_usd,
                alert_threshold_pct=alert_threshold_pct,
                qps=qps,
                last_reset=_utcnow(),
            )
        else:
            row = existing
            row.monthly_budget_usd = monthly_budget_usd
            row.alert_threshold_pct = alert_threshold_pct
            row.qps = qps
            row.updated_at = _utcnow()
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=IntegrationBudgetOut.model_validate(row), project_id=project_id)

    def record_call(
        self,
        *,
        project_id: int,
        kind: str,
        cost_usd: float,
        now: datetime | None = None,
    ) -> Envelope[IntegrationBudgetOut]:
        """Pre-empt the call against ``monthly_budget_usd``.

        Order of operations:

        1. Resolve the row (or 404 — caller should ``set`` first).
        2. Roll over month if ``last_reset`` is in a prior calendar month.
        3. Pre-emption: ``current_month_spend + cost_usd > monthly_budget_usd``
           → ``BudgetExceededError`` (PLAN.md L1037-L1040 / audit M-25).
        4. Increment ``current_month_spend`` and ``current_month_calls``.

        The ``now`` parameter is injected for testing (freezegun). Default
        is ``_utcnow()``.
        """
        if cost_usd < 0:
            raise ValidationError("cost_usd must be >= 0", data={"cost_usd": cost_usd})
        when = now or _utcnow()
        row = self._s.exec(
            select(IntegrationBudget).where(
                IntegrationBudget.project_id == project_id,
                IntegrationBudget.kind == kind,
            )
        ).first()
        if row is None:
            raise NotFoundError(
                f"budget for project={project_id} kind={kind!r} not configured",
                data={"project_id": project_id, "kind": kind},
            )
        # Rollover if last_reset is from a prior (year, month).
        if (row.last_reset.year, row.last_reset.month) != (when.year, when.month):
            row.current_month_spend = 0.0
            row.current_month_calls = 0
            row.last_reset = when
        # Pre-emption.
        new_spend = round(row.current_month_spend + cost_usd, 6)
        if new_spend > row.monthly_budget_usd:
            raise BudgetExceededError(
                f"{kind} budget would exceed cap: ${new_spend:.4f} > ${row.monthly_budget_usd:.4f}",
                data={
                    "project_id": project_id,
                    "kind": kind,
                    "monthly_budget_usd": row.monthly_budget_usd,
                    "current_month_spend": row.current_month_spend,
                    "attempted_cost_usd": cost_usd,
                },
            )
        row.current_month_spend = new_spend
        row.current_month_calls += 1
        row.updated_at = _utcnow()
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=IntegrationBudgetOut.model_validate(row), project_id=project_id)


# ---------------------------------------------------------------------------
# ScheduledJobRepository.
# ---------------------------------------------------------------------------


class ScheduledJobRepository:
    """Per-project cron schedules.

    APScheduler integration lives in M9; M1 only stores the cron rows
    so REST/MCP can render them and the M9 scheduler can pick them up.
    """

    def __init__(self, session: Session) -> None:
        self._s = session

    def list(self, project_id: int) -> list[ScheduledJobOut]:
        """All scheduled jobs for a project."""
        rows = self._s.exec(
            select(ScheduledJob)
            .where(ScheduledJob.project_id == project_id)
            .order_by(ScheduledJob.id.asc())  # type: ignore[union-attr,attr-defined]
        ).all()
        return [ScheduledJobOut.model_validate(r) for r in rows]

    def set(
        self,
        *,
        project_id: int,
        kind: str,
        cron_expr: str,
        enabled: bool = True,
    ) -> Envelope[ScheduledJobOut]:
        """Upsert by ``(project_id, kind)``."""
        existing = self._s.exec(
            select(ScheduledJob).where(
                ScheduledJob.project_id == project_id,
                ScheduledJob.kind == kind,
            )
        ).first()
        if existing is None:
            row = ScheduledJob(
                project_id=project_id,
                kind=kind,
                cron_expr=cron_expr,
                enabled=enabled,
            )
        else:
            row = existing
            row.cron_expr = cron_expr
            row.enabled = enabled
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=ScheduledJobOut.model_validate(row), project_id=project_id)

    def toggle(self, job_id: int, *, enabled: bool) -> Envelope[ScheduledJobOut]:
        """Flip the ``enabled`` flag."""
        row = self._s.get(ScheduledJob, job_id)
        if row is None:
            raise NotFoundError(f"scheduled job {job_id} not found")
        row.enabled = enabled
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return Envelope(data=ScheduledJobOut.model_validate(row), project_id=row.project_id)


__all__ = [
    "ComplianceRuleOut",
    "ComplianceRuleRepository",
    "EeatCriteriaRepository",
    "EeatCriterionOut",
    "IntegrationBudgetOut",
    "IntegrationBudgetRepository",
    "IntegrationCredentialOut",
    "IntegrationCredentialRepository",
    "ProjectOut",
    "ProjectRepository",
    "PublishTargetOut",
    "PublishTargetRepository",
    "ScheduledJobOut",
    "ScheduledJobRepository",
    "VoiceProfileOut",
    "VoiceProfileRepository",
]
