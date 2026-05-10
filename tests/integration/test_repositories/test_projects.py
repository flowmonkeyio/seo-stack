"""Integration tests for the project + presets repositories."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel, select

from content_stack.db.connection import make_engine
from content_stack.db.models import EeatCriterion, EeatTier
from content_stack.repositories.base import (
    BudgetExceededError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from content_stack.repositories.projects import (
    ComplianceRuleRepository,
    EeatCriteriaRepository,
    IntegrationBudgetRepository,
    IntegrationCredentialRepository,
    ProjectRepository,
    PublishTargetRepository,
    ScheduledJobRepository,
    VoiceProfileRepository,
)


def test_create_project_seeds_80_eeat_rows_in_one_transaction(session: Session) -> None:
    """D7 invariant: creating a project transactionally seeds 80 EEAT rows."""
    repo = ProjectRepository(session)
    env = repo.create(
        slug="acme",
        name="Acme",
        domain="acme.example",
        locale="en-US",
    )
    assert env.data.slug == "acme"
    rows = session.exec(select(EeatCriterion).where(EeatCriterion.project_id == env.data.id)).all()
    assert len(rows) == 80
    cores = sorted(r.code for r in rows if r.tier == EeatTier.CORE)
    assert cores == ["C01", "R10", "T04"]


def test_duplicate_slug_raises_conflict(session: Session) -> None:
    repo = ProjectRepository(session)
    repo.create(slug="dup", name="One", domain="x", locale="en")
    with pytest.raises(ConflictError) as exc_info:
        repo.create(slug="dup", name="Two", domain="y", locale="en")
    assert exc_info.value.code == -32008
    assert "slug" in exc_info.value.detail


def test_get_by_id_and_slug(session: Session) -> None:
    repo = ProjectRepository(session)
    env = repo.create(slug="get-test", name="g", domain="x", locale="en")
    by_id = repo.get(env.data.id)
    by_slug = repo.get("get-test")
    assert by_id.id == by_slug.id == env.data.id


def test_list_paginates(session: Session) -> None:
    repo = ProjectRepository(session)
    for i in range(5):
        repo.create(slug=f"p{i}", name=f"p{i}", domain="x", locale="en")
    page = repo.list(limit=2)
    assert len(page.items) == 2
    assert page.next_cursor is not None
    page2 = repo.list(limit=10, after_id=page.next_cursor)
    assert len(page2.items) == 3


def test_update_refuses_slug_change(session: Session) -> None:
    repo = ProjectRepository(session)
    env = repo.create(slug="immut", name="i", domain="x", locale="en")
    with pytest.raises(ValidationError):
        repo.update(env.data.id, slug="new-slug")


def test_update_modifies_other_fields(session: Session) -> None:
    repo = ProjectRepository(session)
    env = repo.create(slug="upd", name="orig", domain="x", locale="en")
    out = repo.update(env.data.id, name="changed", niche="affiliate")
    assert out.data.name == "changed"
    assert out.data.niche == "affiliate"


def test_set_active_unsets_others(session: Session) -> None:
    repo = ProjectRepository(session)
    a = repo.create(slug="aa", name="a", domain="x", locale="en")
    b = repo.create(slug="bb", name="b", domain="x", locale="en")
    repo.set_active(a.data.id)
    repo.set_active(b.data.id)
    assert repo.get(a.data.id).is_active is False
    assert repo.get(b.data.id).is_active is True


def test_get_active_returns_most_recent(session: Session) -> None:
    repo = ProjectRepository(session)
    repo.create(slug="x", name="x", domain="x", locale="en")
    b = repo.create(slug="y", name="y", domain="x", locale="en")
    repo.set_active(b.data.id)
    active = repo.get_active()
    assert active is not None
    assert active.id == b.data.id


def test_soft_delete_clears_active(session: Session) -> None:
    repo = ProjectRepository(session)
    a = repo.create(slug="d", name="d", domain="x", locale="en")
    repo.set_active(a.data.id)
    repo.delete(a.data.id)
    assert repo.get(a.data.id).is_active is False


def test_get_missing_raises_notfound(session: Session) -> None:
    repo = ProjectRepository(session)
    with pytest.raises(NotFoundError):
        repo.get(9999)
    with pytest.raises(NotFoundError):
        repo.get("does-not-exist")


# -------- Voice profiles --------


def test_voice_set_active_flips_others(session: Session, project_id: int) -> None:
    repo = VoiceProfileRepository(session)
    a = repo.set(project_id=project_id, name="A", voice_md="...", is_default=True)
    b = repo.set(project_id=project_id, name="B", voice_md="...")
    assert repo.get(a.data.id).is_default is True
    repo.set_active(b.data.id)
    assert repo.get(a.data.id).is_default is False
    assert repo.get(b.data.id).is_default is True


# -------- Compliance --------


def test_compliance_crud(session: Session, project_id: int) -> None:
    from content_stack.db.models import CompliancePosition, ComplianceRuleKind

    repo = ComplianceRuleRepository(session)
    env = repo.add(
        project_id=project_id,
        kind=ComplianceRuleKind.AFFILIATE_DISCLOSURE,
        title="Affiliates",
        position=CompliancePosition.HEADER,
    )
    rules = repo.list(project_id)
    assert len(rules) == 1
    repo.update(env.data.id, body_md="Updated body")
    rules = repo.list(project_id)
    assert rules[0].body_md == "Updated body"
    repo.remove(env.data.id)
    assert len(repo.list(project_id)) == 0


# -------- EEAT criteria + D7 invariant --------


def test_d7_core_cannot_be_deactivated(session: Session, project_id: int) -> None:
    repo = EeatCriteriaRepository(session)
    rows = repo.list(project_id)
    core = next(r for r in rows if r.tier == EeatTier.CORE and r.code == "T04")
    with pytest.raises(ConflictError) as exc_info:
        repo.toggle(core.id, active=False)
    assert exc_info.value.code == -32008
    assert "tier='core'" in exc_info.value.detail


def test_d7_core_cannot_be_un_required(session: Session, project_id: int) -> None:
    repo = EeatCriteriaRepository(session)
    rows = repo.list(project_id)
    core = next(r for r in rows if r.tier == EeatTier.CORE and r.code == "C01")
    with pytest.raises(ConflictError):
        repo.toggle(core.id, required=False)


def test_recommended_can_be_toggled(session: Session, project_id: int) -> None:
    repo = EeatCriteriaRepository(session)
    rows = repo.list(project_id)
    rec = next(r for r in rows if r.tier == EeatTier.RECOMMENDED)
    out = repo.toggle(rec.id, active=False)
    assert out.data.active is False


def test_eeat_score_weight(session: Session, project_id: int) -> None:
    repo = EeatCriteriaRepository(session)
    rows = repo.list(project_id)
    rec = rows[0]
    out = repo.score(rec.id, weight=85)
    assert out.data.weight == 85
    with pytest.raises(ValidationError):
        repo.score(rec.id, weight=200)


def test_bulk_set_atomic_on_d7_violation(session: Session, project_id: int) -> None:
    repo = EeatCriteriaRepository(session)
    rows = repo.list(project_id)
    rec = next(r for r in rows if r.tier == EeatTier.RECOMMENDED)
    core = next(r for r in rows if r.tier == EeatTier.CORE)
    items = [
        {"id": rec.id, "weight": 5},
        {"id": core.id, "active": False},  # violates D7
    ]
    with pytest.raises(ConflictError):
        repo.bulk_set(project_id, items)
    # The recommended row's weight change should be rolled back.
    refreshed = repo.list(project_id)
    rec2 = next(r for r in refreshed if r.id == rec.id)
    assert rec2.weight == 10  # original


# -------- Publish targets --------


def test_publish_targets_set_primary_unique(session: Session, project_id: int) -> None:
    from content_stack.db.models import PublishTargetKind

    repo = PublishTargetRepository(session)
    repo.add(project_id=project_id, kind=PublishTargetKind.NUXT_CONTENT, is_primary=True)
    b = repo.add(project_id=project_id, kind=PublishTargetKind.WORDPRESS)
    repo.set_primary(b.data.id)
    rows = repo.list(project_id)
    primary_count = sum(1 for r in rows if r.is_primary)
    assert primary_count == 1
    primary_id = next(r.id for r in rows if r.is_primary)
    assert primary_id == b.data.id


def test_publish_targets_first_target_becomes_primary(session: Session, project_id: int) -> None:
    from content_stack.db.models import PublishTargetKind

    repo = PublishTargetRepository(session)
    out = repo.add(project_id=project_id, kind=PublishTargetKind.NUXT_CONTENT)

    assert out.data.is_primary is True


def test_publish_targets_cannot_unset_only_primary(session: Session, project_id: int) -> None:
    from content_stack.db.models import PublishTargetKind

    repo = PublishTargetRepository(session)
    out = repo.add(project_id=project_id, kind=PublishTargetKind.NUXT_CONTENT)

    with pytest.raises(ConflictError):
        repo.update(out.data.id, is_primary=False)


def test_publish_targets_remove_primary_promotes_remaining(
    session: Session, project_id: int
) -> None:
    from content_stack.db.models import PublishTargetKind

    repo = PublishTargetRepository(session)
    first = repo.add(project_id=project_id, kind=PublishTargetKind.NUXT_CONTENT).data
    second = repo.add(project_id=project_id, kind=PublishTargetKind.WORDPRESS).data

    repo.remove(first.id)
    rows = repo.list(project_id)

    assert len(rows) == 1
    assert rows[0].id == second.id
    assert rows[0].is_primary is True


# -------- Integrations --------


def test_integration_credential_set_then_remove(session: Session, project_id: int) -> None:
    repo = IntegrationCredentialRepository(session)
    out = repo.set(
        project_id=project_id,
        kind="dataforseo",
        plaintext_payload=b"API_KEY",
        config_json={"login": "u"},
    )
    creds = repo.list(project_id)
    assert len(creds) == 1
    assert creds[0].kind == "dataforseo"
    repo.remove(out.data.id)
    assert len(repo.list(project_id)) == 0


def test_integration_credential_set_then_get_decrypted(session: Session, project_id: int) -> None:
    """M4 contract: ``set`` encrypts; ``get_decrypted`` round-trips.

    Exercises the AES-256-GCM seam directly. AAD is bound to
    ``(project_id, kind)``; mutating either column on disk would render
    the row undecryptable. We verify three things:

    1. Round-trip yields the original plaintext bytes.
    2. The persisted row exposes a fresh per-row 12-byte nonce + non-empty
       ciphertext.
    3. Tampering with ``project_id`` (the AAD) makes ``decrypt`` raise
       ``CryptoError``.
    """
    from content_stack.crypto.aes_gcm import CryptoError, decrypt

    repo = IntegrationCredentialRepository(session)
    env = repo.set(
        project_id=project_id,
        kind="firecrawl",
        plaintext_payload=b"sk-live-secret-123",
    )
    plaintext = repo.get_decrypted(env.data.id)
    assert plaintext == b"sk-live-secret-123"

    raw = repo.fetch_row(env.data.id)
    assert raw.encrypted_payload is not None and len(raw.encrypted_payload) > 0
    assert raw.nonce is not None and len(raw.nonce) == 12

    # AAD tamper — pass a different project_id; the auth tag mismatch
    # surfaces as ``CryptoError``.
    with pytest.raises(CryptoError):
        decrypt(
            raw.encrypted_payload,
            nonce=raw.nonce,
            project_id=(project_id or 0) + 9999,
            kind="firecrawl",
        )


# -------- Budgets --------


def test_budget_record_call_pre_emption(session: Session, project_id: int) -> None:
    repo = IntegrationBudgetRepository(session)
    repo.set(project_id=project_id, kind="dataforseo", monthly_budget_usd=1.0)
    repo.record_call(project_id=project_id, kind="dataforseo", cost_usd=0.5)
    repo.record_call(project_id=project_id, kind="dataforseo", cost_usd=0.4)
    # Next call would push past the cap.
    with pytest.raises(BudgetExceededError) as exc_info:
        repo.record_call(project_id=project_id, kind="dataforseo", cost_usd=0.2)
    assert exc_info.value.code == -32012


def test_budget_month_rollover(session: Session, project_id: int) -> None:
    repo = IntegrationBudgetRepository(session)
    repo.set(project_id=project_id, kind="firecrawl", monthly_budget_usd=1.0)
    # Spend in January.
    jan = datetime(2026, 1, 15, 12, 0, 0)
    repo.record_call(project_id=project_id, kind="firecrawl", cost_usd=0.8, now=jan)
    # Cross into February — counters reset, the same call now succeeds again.
    feb = datetime(2026, 2, 1, 0, 0, 0)
    out = repo.record_call(project_id=project_id, kind="firecrawl", cost_usd=0.8, now=feb)
    assert out.data.current_month_calls == 1
    assert out.data.current_month_spend == pytest.approx(0.8)


def test_budget_preemption_uses_atomic_increment_with_stale_session(tmp_path) -> None:
    engine = make_engine(tmp_path / "budget-race.sqlite")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as setup:
        project_id = (
            ProjectRepository(setup)
            .create(
                slug="budget-race",
                name="budget-race",
                domain="example.com",
                locale="en-US",
            )
            .data.id
        )
        assert project_id is not None
        IntegrationBudgetRepository(setup).set(
            project_id=project_id,
            kind="dataforseo",
            monthly_budget_usd=1.0,
        )

    with Session(engine) as s1, Session(engine) as s2:
        repo1 = IntegrationBudgetRepository(s1)
        repo2 = IntegrationBudgetRepository(s2)
        repo2.get(project_id, "dataforseo")

        repo1.record_call(project_id=project_id, kind="dataforseo", cost_usd=0.6)
        with pytest.raises(BudgetExceededError):
            repo2.record_call(project_id=project_id, kind="dataforseo", cost_usd=0.6)

    with Session(engine) as check:
        budget = IntegrationBudgetRepository(check).get(project_id, "dataforseo")
        assert budget.current_month_spend == pytest.approx(0.6)
        assert budget.current_month_calls == 1


# -------- Scheduled jobs --------


def test_scheduled_jobs(session: Session, project_id: int) -> None:
    repo = ScheduledJobRepository(session)
    env = repo.set(project_id=project_id, kind="gsc-pull", cron_expr="0 3 * * *")
    rows = repo.list(project_id)
    assert len(rows) == 1
    assert rows[0].cron_expr == "0 3 * * *"
    repo.toggle(env.data.id, enabled=False)
    rows = repo.list(project_id)
    assert rows[0].enabled is False
