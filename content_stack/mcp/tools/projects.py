"""project / voice / compliance / eeat / target / integration / budget / schedule MCP tools.

Each tool is a thin adapter around the corresponding repository method
in ``content_stack.repositories.projects`` (and ``runs`` for the cost
queries). Inputs declare strict-extra ``forbid``; outputs are either
the bare repo Out type (reads) or ``WriteEnvelope[OutType]`` (mutations).

The integration-test methods (``integration.test``, ``integration.testGsc``)
are M5 work; they raise ``MilestoneDeferralError`` so the tool is
discoverable but documents the deferral cleanly.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict

from content_stack.db.models import (
    CompliancePosition,
    ComplianceRuleKind,
    PublishTargetKind,
)
from content_stack.mcp.context import MCPContext
from content_stack.mcp.contract import MCPInput, WriteEnvelope
from content_stack.mcp.errors import MilestoneDeferralError
from content_stack.mcp.server import ToolRegistry, ToolSpec
from content_stack.mcp.streaming import ProgressEmitter
from content_stack.repositories.base import Page
from content_stack.repositories.projects import (
    ComplianceRuleOut,
    ComplianceRuleRepository,
    EeatCriteriaRepository,
    EeatCriterionOut,
    IntegrationBudgetOut,
    IntegrationBudgetRepository,
    IntegrationCredentialOut,
    IntegrationCredentialRepository,
    ProjectOut,
    ProjectRepository,
    PublishTargetOut,
    PublishTargetRepository,
    ScheduledJobOut,
    ScheduledJobRepository,
    VoiceProfileOut,
    VoiceProfileRepository,
)

# ---------------------------------------------------------------------------
# project.* inputs.
# ---------------------------------------------------------------------------


class ProjectListInput(MCPInput):
    """List projects (optionally filter to active only)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"active_only": False, "limit": 50}},
    )

    active_only: bool = False
    limit: int | None = None
    after_id: int | None = None


class ProjectCreateInput(MCPInput):
    """Create a project + seed 80 EEAT criteria atomically (D7)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "slug": "betsage",
                "name": "BetSage",
                "domain": "betsage.com",
                "niche": "sportsbetting",
                "locale": "en-US",
            }
        },
    )

    slug: str
    name: str
    domain: str
    niche: str | None = None
    locale: str
    schedule_json: dict[str, Any] | None = None


class ProjectGetInput(MCPInput):
    """Look up a project by id or slug."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"id_or_slug": "betsage"}}
    )

    id_or_slug: int | str


class ProjectUpdateInput(MCPInput):
    """Patch project fields (slug is immutable)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "patch": {"name": "BetSage Pro"}}},
    )

    project_id: int
    patch: dict[str, Any]


class ProjectIdInput(MCPInput):
    """Project-id-only mutator (delete / activate / setActive)."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int


class ProjectGetActiveInput(MCPInput):
    """No params; returns the most-recently-updated active project."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {}})


# ---------------------------------------------------------------------------
# project.* handlers.
# ---------------------------------------------------------------------------


async def _project_list(
    inp: ProjectListInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> Page[ProjectOut]:
    """List projects with cursor pagination."""
    repo = ProjectRepository(ctx.session)
    return repo.list(active_only=inp.active_only, limit=inp.limit, after_id=inp.after_id)


async def _project_create(
    inp: ProjectCreateInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> WriteEnvelope[ProjectOut]:
    """Create a project + seed EEAT criteria in one transaction."""
    repo = ProjectRepository(ctx.session)
    env = repo.create(
        slug=inp.slug,
        name=inp.name,
        domain=inp.domain,
        niche=inp.niche,
        locale=inp.locale,
        schedule_json=inp.schedule_json,
    )
    return WriteEnvelope[ProjectOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _project_get(
    inp: ProjectGetInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> ProjectOut:
    """Fetch a project by id (int) or slug (str)."""
    repo = ProjectRepository(ctx.session)
    return repo.get(inp.id_or_slug)


async def _project_update(
    inp: ProjectUpdateInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> WriteEnvelope[ProjectOut]:
    """Patch mutable project fields."""
    repo = ProjectRepository(ctx.session)
    env = repo.update(inp.project_id, **inp.patch)
    return WriteEnvelope[ProjectOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _project_delete(
    inp: ProjectIdInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> WriteEnvelope[ProjectOut]:
    """Soft-delete (sets is_active=False)."""
    repo = ProjectRepository(ctx.session)
    env = repo.delete(inp.project_id)
    return WriteEnvelope[ProjectOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _project_activate(
    inp: ProjectIdInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> WriteEnvelope[ProjectOut]:
    """Mark active (mirrors REST POST /projects/{id}/activate)."""
    repo = ProjectRepository(ctx.session)
    env = repo.set_active(inp.project_id)
    return WriteEnvelope[ProjectOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _project_set_active(
    inp: ProjectIdInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> WriteEnvelope[ProjectOut]:
    """UI-state setter for the active project (E1)."""
    repo = ProjectRepository(ctx.session)
    env = repo.set_active(inp.project_id)
    return WriteEnvelope[ProjectOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _project_get_active(
    _inp: ProjectGetActiveInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> ProjectOut | None:
    """Return the most-recently-updated active project, if any."""
    repo = ProjectRepository(ctx.session)
    return repo.get_active()


# ---------------------------------------------------------------------------
# voice.* tools.
# ---------------------------------------------------------------------------


class VoiceSetInput(MCPInput):
    """Create a voice variant; flips others off when ``is_default=True``."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "project_id": 1,
                "name": "default",
                "voice_md": "# Voice\n",
                "is_default": True,
            }
        },
    )

    project_id: int
    name: str
    voice_md: str
    is_default: bool = False


class VoiceGetInput(MCPInput):
    """Look up a voice profile by id."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"voice_id": 1}})

    voice_id: int


class VoiceListInput(MCPInput):
    """List variants for a project."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int
    limit: int | None = None
    after_id: int | None = None


class VoiceSetActiveInput(MCPInput):
    """Mark a voice profile as the active one for its project."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"voice_id": 1}})

    voice_id: int


async def _voice_set(
    inp: VoiceSetInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[VoiceProfileOut]:
    """Insert a voice profile."""
    env = VoiceProfileRepository(ctx.session).set(
        project_id=inp.project_id,
        name=inp.name,
        voice_md=inp.voice_md,
        is_default=inp.is_default,
    )
    return WriteEnvelope[VoiceProfileOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _voice_get(
    inp: VoiceGetInput, ctx: MCPContext, _emit: ProgressEmitter
) -> VoiceProfileOut:
    """Fetch one voice profile."""
    return VoiceProfileRepository(ctx.session).get(inp.voice_id)


async def _voice_list(
    inp: VoiceListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> Page[VoiceProfileOut]:
    """List variants."""
    return VoiceProfileRepository(ctx.session).list_variants(
        inp.project_id, limit=inp.limit, after_id=inp.after_id
    )


async def _voice_set_active(
    inp: VoiceSetActiveInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[VoiceProfileOut]:
    """Make a voice profile the active default."""
    env = VoiceProfileRepository(ctx.session).set_active(inp.voice_id)
    return WriteEnvelope[VoiceProfileOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


# ---------------------------------------------------------------------------
# compliance.* tools.
# ---------------------------------------------------------------------------


class ComplianceListInput(MCPInput):
    """List compliance rules for a project."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int


class ComplianceAddInput(MCPInput):
    """Insert a compliance rule."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "project_id": 1,
                "kind": "disclosure",
                "title": "Affiliate",
                "position": "post_intro",
            }
        },
    )

    project_id: int
    kind: ComplianceRuleKind
    title: str
    body_md: str = ""
    jurisdictions: str | None = None
    position: CompliancePosition
    params_json: dict[str, Any] | None = None
    validator: str | None = None
    is_active: bool = True


class ComplianceUpdateInput(MCPInput):
    """Patch a compliance rule by id."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"rule_id": 1, "patch": {"title": "Updated"}}}
    )

    rule_id: int
    patch: dict[str, Any]


class ComplianceRemoveInput(MCPInput):
    """Hard-delete a compliance rule."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"rule_id": 1}})

    rule_id: int


async def _compliance_list(
    inp: ComplianceListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[ComplianceRuleOut]:
    """List rules in render order."""
    return ComplianceRuleRepository(ctx.session).list(inp.project_id)


async def _compliance_add(
    inp: ComplianceAddInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ComplianceRuleOut]:
    """Insert a compliance rule."""
    env = ComplianceRuleRepository(ctx.session).add(
        project_id=inp.project_id,
        kind=inp.kind,
        title=inp.title,
        body_md=inp.body_md,
        jurisdictions=inp.jurisdictions,
        position=inp.position,
        params_json=inp.params_json,
        validator=inp.validator,
        is_active=inp.is_active,
    )
    return WriteEnvelope[ComplianceRuleOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _compliance_update(
    inp: ComplianceUpdateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ComplianceRuleOut]:
    """Patch a compliance rule."""
    env = ComplianceRuleRepository(ctx.session).update(inp.rule_id, **inp.patch)
    return WriteEnvelope[ComplianceRuleOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _compliance_remove(
    inp: ComplianceRemoveInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ComplianceRuleOut]:
    """Hard-delete a rule."""
    env = ComplianceRuleRepository(ctx.session).remove(inp.rule_id)
    return WriteEnvelope[ComplianceRuleOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


# ---------------------------------------------------------------------------
# eeat.* tools.
# ---------------------------------------------------------------------------


class EeatListInput(MCPInput):
    """List criteria (rubric) for a project."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int


class EeatToggleInput(MCPInput):
    """Toggle ``required`` / ``active`` flags. D7 invariant on tier='core'."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"criterion_id": 1, "active": False}}
    )

    criterion_id: int
    required: bool | None = None
    active: bool | None = None


class EeatScoreInput(MCPInput):
    """Set the per-criterion weight (1..100)."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"criterion_id": 1, "weight": 50}}
    )

    criterion_id: int
    weight: int


class EeatBulkSetInput(MCPInput):
    """Bulk update active/required/weight by criterion id."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "items": [{"id": 1, "weight": 100}]}},
    )

    project_id: int
    items: list[dict[str, Any]]


async def _eeat_list(
    inp: EeatListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[EeatCriterionOut]:
    """List rubric items."""
    return EeatCriteriaRepository(ctx.session).list(inp.project_id)


async def _eeat_toggle(
    inp: EeatToggleInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[EeatCriterionOut]:
    """Toggle flags; D7 floor protected."""
    env = EeatCriteriaRepository(ctx.session).toggle(
        inp.criterion_id, required=inp.required, active=inp.active
    )
    return WriteEnvelope[EeatCriterionOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _eeat_score(
    inp: EeatScoreInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[EeatCriterionOut]:
    """Update per-criterion weight."""
    env = EeatCriteriaRepository(ctx.session).score(inp.criterion_id, weight=inp.weight)
    return WriteEnvelope[EeatCriterionOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _eeat_bulk_set(
    inp: EeatBulkSetInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[list[EeatCriterionOut]]:
    """Bulk update flags + weights; D7 invariant validated all-or-nothing."""
    env = EeatCriteriaRepository(ctx.session).bulk_set(inp.project_id, inp.items)
    return WriteEnvelope[list[EeatCriterionOut]](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


# eeat.score is reserved for evaluation aggregation in articles tools — see articles.py.


# ---------------------------------------------------------------------------
# target.* tools.
# ---------------------------------------------------------------------------


class TargetListInput(MCPInput):
    """List publish targets for a project."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int


class TargetAddInput(MCPInput):
    """Insert a publish target (one is_primary=True per project)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"project_id": 1, "kind": "nuxt-content", "is_primary": True}
        },
    )

    project_id: int
    kind: PublishTargetKind
    config_json: dict[str, Any] | None = None
    is_primary: bool = False
    is_active: bool = True


class TargetUpdateInput(MCPInput):
    """Patch a publish target."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"target_id": 1, "patch": {"is_active": False}}},
    )

    target_id: int
    patch: dict[str, Any]


class TargetRemoveInput(MCPInput):
    """Hard-delete a publish target."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"target_id": 1}})

    target_id: int


class TargetSetPrimaryInput(MCPInput):
    """Make a target primary (clears any other primary in the project)."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"target_id": 1}})

    target_id: int


async def _target_list(
    inp: TargetListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[PublishTargetOut]:
    return PublishTargetRepository(ctx.session).list(inp.project_id)


async def _target_add(
    inp: TargetAddInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[PublishTargetOut]:
    env = PublishTargetRepository(ctx.session).add(
        project_id=inp.project_id,
        kind=inp.kind,
        config_json=inp.config_json,
        is_primary=inp.is_primary,
        is_active=inp.is_active,
    )
    return WriteEnvelope[PublishTargetOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _target_update(
    inp: TargetUpdateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[PublishTargetOut]:
    env = PublishTargetRepository(ctx.session).update(inp.target_id, **inp.patch)
    return WriteEnvelope[PublishTargetOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _target_remove(
    inp: TargetRemoveInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[PublishTargetOut]:
    env = PublishTargetRepository(ctx.session).remove(inp.target_id)
    return WriteEnvelope[PublishTargetOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _target_set_primary(
    inp: TargetSetPrimaryInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[PublishTargetOut]:
    env = PublishTargetRepository(ctx.session).set_primary(inp.target_id)
    return WriteEnvelope[PublishTargetOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


# ---------------------------------------------------------------------------
# integration.* tools.
# ---------------------------------------------------------------------------


class IntegrationListInput(MCPInput):
    """List integration credentials (project_id=None for global)."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int | None = None


class IntegrationSetInput(MCPInput):
    """Upsert a credential row.

    The ``plaintext_payload_b64`` field carries the raw bytes as base64
    so the JSON wire shape stays valid; the repository M1 stub stores
    them verbatim, M5 will encrypt before persistence.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"project_id": 1, "kind": "openai", "plaintext_payload_b64": "..."}
        },
    )

    project_id: int | None = None
    kind: str
    plaintext_payload_b64: str
    config_json: dict[str, Any] | None = None
    expires_at: str | None = None


class IntegrationTestInput(MCPInput):
    """Test an integration credential — M5 deferral."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"credential_id": 1}})

    credential_id: int


class IntegrationRemoveInput(MCPInput):
    """Hard-delete an integration credential."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"credential_id": 1}})

    credential_id: int


class IntegrationTestGscInput(MCPInput):
    """Test the GSC integration end-to-end — M5 deferral."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int


async def _integration_list(
    inp: IntegrationListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[IntegrationCredentialOut]:
    return IntegrationCredentialRepository(ctx.session).list(inp.project_id)


async def _integration_set(
    inp: IntegrationSetInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[IntegrationCredentialOut]:
    """Upsert an integration credential. M1 stores plaintext; M5 will encrypt."""
    import base64
    from datetime import datetime

    payload = base64.b64decode(inp.plaintext_payload_b64.encode("ascii"))
    expires_at = datetime.fromisoformat(inp.expires_at) if inp.expires_at else None
    env = IntegrationCredentialRepository(ctx.session).set(
        project_id=inp.project_id,
        kind=inp.kind,
        plaintext_payload=payload,
        config_json=inp.config_json,
        expires_at=expires_at,
    )
    return WriteEnvelope[IntegrationCredentialOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _integration_test(
    inp: IntegrationTestInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[IntegrationCredentialOut]:
    """M5 deferral — vendor health check."""
    raise MilestoneDeferralError(
        "integration.test calls vendor health endpoints; lands at M5",
        data={
            "milestone": "M5",
            "hint": "M3 stores credentials only; the actual vendor reachability check is M5 work",
            "credential_id": inp.credential_id,
        },
    )


async def _integration_test_gsc(
    inp: IntegrationTestGscInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[Any]:
    """M5 deferral — exercises the GSC OAuth flow + sample query."""
    raise MilestoneDeferralError(
        "integration.testGsc requires the M5 GSC OAuth integration",
        data={
            "milestone": "M5",
            "hint": "Lands with the gsc-pull job and the OAuth refresh worker",
            "project_id": inp.project_id,
        },
    )


async def _integration_remove(
    inp: IntegrationRemoveInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[IntegrationCredentialOut]:
    env = IntegrationCredentialRepository(ctx.session).remove(inp.credential_id)
    return WriteEnvelope[IntegrationCredentialOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


# ---------------------------------------------------------------------------
# budget.* tools.
# ---------------------------------------------------------------------------


class BudgetListInput(MCPInput):
    """List budget rows for a project."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"project_id": 1, "kind": "openai"}}
    )

    project_id: int
    kind: str


class BudgetSetInput(MCPInput):
    """Upsert a budget row."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"project_id": 1, "kind": "openai", "monthly_budget_usd": 50.0}
        },
    )

    project_id: int
    kind: str
    monthly_budget_usd: float = 50.0
    alert_threshold_pct: int = 80
    qps: float = 1.0


class BudgetUpdateInput(MCPInput):
    """Update budget caps. Same shape as ``set`` for symmetry."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"project_id": 1, "kind": "openai", "monthly_budget_usd": 100.0}
        },
    )

    project_id: int
    kind: str
    monthly_budget_usd: float
    alert_threshold_pct: int = 80
    qps: float = 1.0


class BudgetQueryProjectInput(MCPInput):
    """Look up a budget row by (project_id, kind)."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"project_id": 1, "kind": "openai"}}
    )

    project_id: int
    kind: str


async def _budget_list(
    inp: BudgetListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> IntegrationBudgetOut:
    """Fetch a budget row."""
    return IntegrationBudgetRepository(ctx.session).get(inp.project_id, inp.kind)


async def _budget_set(
    inp: BudgetSetInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[IntegrationBudgetOut]:
    env = IntegrationBudgetRepository(ctx.session).set(
        project_id=inp.project_id,
        kind=inp.kind,
        monthly_budget_usd=inp.monthly_budget_usd,
        alert_threshold_pct=inp.alert_threshold_pct,
        qps=inp.qps,
    )
    return WriteEnvelope[IntegrationBudgetOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _budget_update(
    inp: BudgetUpdateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[IntegrationBudgetOut]:
    env = IntegrationBudgetRepository(ctx.session).set(
        project_id=inp.project_id,
        kind=inp.kind,
        monthly_budget_usd=inp.monthly_budget_usd,
        alert_threshold_pct=inp.alert_threshold_pct,
        qps=inp.qps,
    )
    return WriteEnvelope[IntegrationBudgetOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _budget_query_project(
    inp: BudgetQueryProjectInput, ctx: MCPContext, _emit: ProgressEmitter
) -> IntegrationBudgetOut:
    """Look up a budget row."""
    return IntegrationBudgetRepository(ctx.session).get(inp.project_id, inp.kind)


# ---------------------------------------------------------------------------
# schedule.* tools.
# ---------------------------------------------------------------------------


class ScheduleListInput(MCPInput):
    """List scheduled jobs for a project."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int


class ScheduleSetInput(MCPInput):
    """Upsert a scheduled job."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"project_id": 1, "kind": "gsc-pull", "cron_expr": "0 3 * * *"}
        },
    )

    project_id: int
    kind: str
    cron_expr: str
    enabled: bool = True


class ScheduleToggleInput(MCPInput):
    """Flip the enabled flag on a job."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"job_id": 1, "enabled": False}}
    )

    job_id: int
    enabled: bool


async def _schedule_list(
    inp: ScheduleListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[ScheduledJobOut]:
    return ScheduledJobRepository(ctx.session).list(inp.project_id)


async def _schedule_set(
    inp: ScheduleSetInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ScheduledJobOut]:
    env = ScheduledJobRepository(ctx.session).set(
        project_id=inp.project_id,
        kind=inp.kind,
        cron_expr=inp.cron_expr,
        enabled=inp.enabled,
    )
    return WriteEnvelope[ScheduledJobOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _schedule_toggle(
    inp: ScheduleToggleInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ScheduledJobOut]:
    env = ScheduledJobRepository(ctx.session).toggle(inp.job_id, enabled=inp.enabled)
    return WriteEnvelope[ScheduledJobOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


# ---------------------------------------------------------------------------
# Registration.
# ---------------------------------------------------------------------------


def register(registry: ToolRegistry) -> None:
    """Register every project / preset tool."""
    # project.*
    registry.register(
        ToolSpec(
            "project.list",
            "List projects with optional active-only filter.",
            ProjectListInput,
            Page[ProjectOut],
            _project_list,
        )
    )
    registry.register(
        ToolSpec(
            "project.create",
            "Create a project + seed 80 EEAT criteria atomically (D7).",
            ProjectCreateInput,
            WriteEnvelope[ProjectOut],
            _project_create,
        )
    )
    registry.register(
        ToolSpec(
            "project.get",
            "Look up a project by id (int) or slug (str).",
            ProjectGetInput,
            ProjectOut,
            _project_get,
        )
    )
    registry.register(
        ToolSpec(
            "project.update",
            "Patch project fields; slug is immutable.",
            ProjectUpdateInput,
            WriteEnvelope[ProjectOut],
            _project_update,
        )
    )
    registry.register(
        ToolSpec(
            "project.delete",
            "Soft-delete (sets is_active=False).",
            ProjectIdInput,
            WriteEnvelope[ProjectOut],
            _project_delete,
        )
    )
    registry.register(
        ToolSpec(
            "project.activate",
            "Make a project the active one (E1).",
            ProjectIdInput,
            WriteEnvelope[ProjectOut],
            _project_activate,
        )
    )
    registry.register(
        ToolSpec(
            "project.setActive",
            "UI-state setter for the active project (E1).",
            ProjectIdInput,
            WriteEnvelope[ProjectOut],
            _project_set_active,
        )
    )
    registry.register(
        ToolSpec(
            "project.getActive",
            "Return the most-recently-updated active project, if any.",
            ProjectGetActiveInput,
            ProjectOut,
            _project_get_active,
        )
    )

    # voice.*
    registry.register(
        ToolSpec(
            "voice.set",
            "Insert a voice profile.",
            VoiceSetInput,
            WriteEnvelope[VoiceProfileOut],
            _voice_set,
        )
    )
    registry.register(
        ToolSpec(
            "voice.get", "Fetch one voice profile.", VoiceGetInput, VoiceProfileOut, _voice_get
        )
    )
    registry.register(
        ToolSpec(
            "voice.listVariants",
            "List voice variants for a project.",
            VoiceListInput,
            Page[VoiceProfileOut],
            _voice_list,
        )
    )
    registry.register(
        ToolSpec(
            "voice.setActive",
            "Mark a voice profile as the active default.",
            VoiceSetActiveInput,
            WriteEnvelope[VoiceProfileOut],
            _voice_set_active,
        )
    )

    # compliance.*
    registry.register(
        ToolSpec(
            "compliance.list",
            "List compliance rules for a project.",
            ComplianceListInput,
            list[ComplianceRuleOut],
            _compliance_list,
        )
    )
    registry.register(
        ToolSpec(
            "compliance.add",
            "Insert a compliance rule.",
            ComplianceAddInput,
            WriteEnvelope[ComplianceRuleOut],
            _compliance_add,
        )
    )
    registry.register(
        ToolSpec(
            "compliance.update",
            "Patch a compliance rule.",
            ComplianceUpdateInput,
            WriteEnvelope[ComplianceRuleOut],
            _compliance_update,
        )
    )
    registry.register(
        ToolSpec(
            "compliance.remove",
            "Hard-delete a rule.",
            ComplianceRemoveInput,
            WriteEnvelope[ComplianceRuleOut],
            _compliance_remove,
        )
    )

    # eeat.*
    registry.register(
        ToolSpec(
            "eeat.list",
            "List rubric items for a project.",
            EeatListInput,
            list[EeatCriterionOut],
            _eeat_list,
        )
    )
    registry.register(
        ToolSpec(
            "eeat.toggle",
            "Toggle required/active flags; D7 floor protected.",
            EeatToggleInput,
            WriteEnvelope[EeatCriterionOut],
            _eeat_toggle,
        )
    )
    registry.register(
        ToolSpec(
            "eeat.bulkSet",
            "Bulk-update flags + weights (all-or-nothing).",
            EeatBulkSetInput,
            WriteEnvelope[list[EeatCriterionOut]],
            _eeat_bulk_set,
        )
    )

    # target.*
    registry.register(
        ToolSpec(
            "target.list",
            "List publish targets.",
            TargetListInput,
            list[PublishTargetOut],
            _target_list,
        )
    )
    registry.register(
        ToolSpec(
            "target.add",
            "Insert a publish target.",
            TargetAddInput,
            WriteEnvelope[PublishTargetOut],
            _target_add,
        )
    )
    registry.register(
        ToolSpec(
            "target.update",
            "Patch a publish target.",
            TargetUpdateInput,
            WriteEnvelope[PublishTargetOut],
            _target_update,
        )
    )
    registry.register(
        ToolSpec(
            "target.remove",
            "Hard-delete a publish target.",
            TargetRemoveInput,
            WriteEnvelope[PublishTargetOut],
            _target_remove,
        )
    )
    registry.register(
        ToolSpec(
            "target.setPrimary",
            "Make a target primary (clears any other primary in the project).",
            TargetSetPrimaryInput,
            WriteEnvelope[PublishTargetOut],
            _target_set_primary,
        )
    )

    # integration.*
    registry.register(
        ToolSpec(
            "integration.list",
            "List integration credentials.",
            IntegrationListInput,
            list[IntegrationCredentialOut],
            _integration_list,
        )
    )
    registry.register(
        ToolSpec(
            "integration.set",
            "Upsert an integration credential.",
            IntegrationSetInput,
            WriteEnvelope[IntegrationCredentialOut],
            _integration_set,
        )
    )
    registry.register(
        ToolSpec(
            "integration.test",
            "Exercise an integration credential against the vendor.",
            IntegrationTestInput,
            WriteEnvelope[IntegrationCredentialOut],
            _integration_test,
        )
    )
    registry.register(
        ToolSpec(
            "integration.testGsc",
            "Exercise the GSC OAuth flow end-to-end.",
            IntegrationTestGscInput,
            WriteEnvelope[Any],
            _integration_test_gsc,
        )
    )
    registry.register(
        ToolSpec(
            "integration.remove",
            "Hard-delete an integration credential.",
            IntegrationRemoveInput,
            WriteEnvelope[IntegrationCredentialOut],
            _integration_remove,
        )
    )

    # budget.*
    registry.register(
        ToolSpec(
            "budget.list",
            "Fetch a budget row.",
            BudgetListInput,
            IntegrationBudgetOut,
            _budget_list,
        )
    )
    registry.register(
        ToolSpec(
            "budget.set",
            "Insert/upsert a budget row.",
            BudgetSetInput,
            WriteEnvelope[IntegrationBudgetOut],
            _budget_set,
        )
    )
    registry.register(
        ToolSpec(
            "budget.update",
            "Update an existing budget row.",
            BudgetUpdateInput,
            WriteEnvelope[IntegrationBudgetOut],
            _budget_update,
        )
    )
    registry.register(
        ToolSpec(
            "budget.queryProject",
            "Look up a budget row by (project_id, kind).",
            BudgetQueryProjectInput,
            IntegrationBudgetOut,
            _budget_query_project,
        )
    )

    # schedule.*
    registry.register(
        ToolSpec(
            "schedule.list",
            "List scheduled jobs.",
            ScheduleListInput,
            list[ScheduledJobOut],
            _schedule_list,
        )
    )
    registry.register(
        ToolSpec(
            "schedule.set",
            "Upsert a scheduled job.",
            ScheduleSetInput,
            WriteEnvelope[ScheduledJobOut],
            _schedule_set,
        )
    )
    registry.register(
        ToolSpec(
            "schedule.toggle",
            "Flip the enabled flag on a scheduled job.",
            ScheduleToggleInput,
            WriteEnvelope[ScheduledJobOut],
            _schedule_toggle,
        )
    )


__all__ = ["register"]
