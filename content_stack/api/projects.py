"""Projects router + nested presets.

Spans every endpoint under ``/api/v1/projects[/{id}]/...`` per PLAN.md
L553-L572: project CRUD plus the seven presets (voice, compliance,
EEAT, authors are split into their own router, publish-targets,
integrations, schedules, budgets) and the per-project cost summary.

Repository layer enforces every invariant — D7 EEAT floor, project
slug immutability, single-active project, exactly-one primary
publish target — so this router is a thin adapter that translates
HTTP shape ↔ ``ProjectRepository`` etc. method calls.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from content_stack.api.deps import get_session
from content_stack.api.envelopes import WriteResponse, write_response
from content_stack.api.pagination import (
    PageResponse,
    PaginationParams,
    page_response,
    pagination_params,
)
from content_stack.db.models import (
    CompliancePosition,
    ComplianceRuleKind,
    PublishTargetKind,
)
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
from content_stack.repositories.runs import RunRepository

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Request bodies — pydantic models for OpenAPI clarity.
# ---------------------------------------------------------------------------


class ProjectCreateRequest(BaseModel):
    """Body for ``POST /projects``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "slug": "betsage",
                "name": "BetSage",
                "domain": "betsage.com",
                "niche": "sportsbetting",
                "locale": "en-US",
                "schedule_json": None,
            }
        }
    )

    slug: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=1, max_length=255)
    niche: str | None = Field(default=None, max_length=200)
    locale: str = Field(min_length=2, max_length=16)
    schedule_json: dict[str, Any] | None = None


class ProjectUpdateRequest(BaseModel):
    """Body for ``PATCH /projects/{id}`` — UI-permissive, slug rejected.

    ``extra='forbid'`` so a stray ``slug`` (or any other unknown column)
    surfaces as a 422 — repository-side validation is the second line of
    defense; the wire shape is the first per audit B-27.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"name": "BetSage Pro", "is_active": True},
        },
    )

    name: str | None = Field(default=None, min_length=1, max_length=200)
    niche: str | None = Field(default=None, max_length=200)
    locale: str | None = Field(default=None, min_length=2, max_length=16)
    schedule_json: dict[str, Any] | None = None
    is_active: bool | None = None
    domain: str | None = Field(default=None, min_length=1, max_length=255)


class VoiceUpsertRequest(BaseModel):
    """Body for ``POST/PUT /projects/{id}/voice[/{vid}]``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"name": "default", "voice_md": "# Voice\n", "is_default": True},
        }
    )

    name: str = Field(min_length=1, max_length=120)
    voice_md: str = ""
    is_default: bool = False


class ComplianceCreateRequest(BaseModel):
    """Body for ``POST /projects/{id}/compliance``."""

    kind: ComplianceRuleKind
    title: str = Field(min_length=1, max_length=200)
    body_md: str = ""
    jurisdictions: str | None = Field(default=None, max_length=500)
    position: CompliancePosition
    params_json: dict[str, Any] | None = None
    validator: str | None = Field(default=None, max_length=120)
    is_active: bool = True


class ComplianceUpdateRequest(BaseModel):
    """Body for ``PATCH /projects/{id}/compliance/{cid}``."""

    kind: ComplianceRuleKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body_md: str | None = None
    jurisdictions: str | None = Field(default=None, max_length=500)
    position: CompliancePosition | None = None
    params_json: dict[str, Any] | None = None
    validator: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None


class EeatTogglePatch(BaseModel):
    """Body for ``PATCH /projects/{id}/eeat/{eid}``."""

    required: bool | None = None
    active: bool | None = None
    weight: int | None = Field(default=None, ge=1, le=100)


class EeatBulkSetRequest(BaseModel):
    """Body for ``PUT /projects/{id}/eeat`` (bulk_set)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [{"id": 1, "active": True, "weight": 20}],
            }
        }
    )

    items: list[dict[str, Any]]


class PublishTargetCreateRequest(BaseModel):
    """Body for ``POST /projects/{id}/publish-targets``."""

    kind: PublishTargetKind
    config_json: dict[str, Any] | None = None
    is_primary: bool = False
    is_active: bool = True


class PublishTargetUpdateRequest(BaseModel):
    """Body for ``PATCH /projects/{id}/publish-targets/{tid}``."""

    kind: PublishTargetKind | None = None
    config_json: dict[str, Any] | None = None
    is_primary: bool | None = None
    is_active: bool | None = None


class IntegrationCreateRequest(BaseModel):
    """Body for ``POST /projects/{id}/integrations``.

    M4: ``IntegrationCredentialRepository.set`` encrypts the plaintext
    payload via AES-256-GCM with a project-bound AAD (PLAN.md L1106-L1124).
    """

    kind: str = Field(min_length=1, max_length=120)
    plaintext_payload: str = Field(min_length=1)
    config_json: dict[str, Any] | None = None
    expires_at: datetime | None = None


class IntegrationUpdateRequest(BaseModel):
    """Body for ``PATCH /projects/{id}/integrations/{iid}`` — same shape as create."""

    kind: str | None = Field(default=None, min_length=1, max_length=120)
    plaintext_payload: str | None = None
    config_json: dict[str, Any] | None = None
    expires_at: datetime | None = None


class ScheduleUpsertRequest(BaseModel):
    """Body for ``POST/PATCH /projects/{id}/schedules``."""

    kind: str = Field(min_length=1, max_length=120)
    cron_expr: str = Field(min_length=1, max_length=120)
    enabled: bool = True


class BudgetUpsertRequest(BaseModel):
    """Body for ``POST/PATCH /projects/{id}/budgets``."""

    kind: str = Field(min_length=1, max_length=120)
    monthly_budget_usd: float = Field(default=50.0, ge=0)
    alert_threshold_pct: int = Field(default=80, ge=0, le=100)
    qps: float = Field(default=1.0, ge=0)


class CostResponse(BaseModel):
    """Wire shape for ``GET /projects/{id}/cost``.

    Aggregated from ``run_steps.cost_cents`` per ``runs.kind`` for the
    target month. M2 returns zeros if no integration calls have happened
    yet — the M5 integrations layer surfaces real ``cost.usd`` numbers
    via the ``runs.metadata_json`` payload.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "by_integration": {"dataforseo": 0.0, "firecrawl": 0.0},
                "total_usd": 0.0,
                "period_start": "2026-05-01T00:00:00",
                "period_end": "2026-06-01T00:00:00",
            }
        }
    )

    by_integration: dict[str, float]
    total_usd: float
    period_start: str
    period_end: str


# ---------------------------------------------------------------------------
# Project CRUD.
# ---------------------------------------------------------------------------


@router.get("", response_model=PageResponse[ProjectOut])
async def list_projects(
    page: PaginationParams = Depends(pagination_params),
    active_only: bool = Query(False),
    session: Session = Depends(get_session),
) -> PageResponse[ProjectOut]:
    """List projects with optional ``?active_only=true`` filter."""
    repo = ProjectRepository(session)
    return page_response(repo.list(active_only=active_only, limit=page.limit, after_id=page.after))


@router.post(
    "",
    response_model=WriteResponse[ProjectOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    body: ProjectCreateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ProjectOut]:
    """Create a project; transactionally seeds 80 EEAT criteria per D7."""
    repo = ProjectRepository(session)
    env = repo.create(
        slug=body.slug,
        name=body.name,
        domain=body.domain,
        niche=body.niche,
        locale=body.locale,
        schedule_json=body.schedule_json,
    )
    return write_response(env)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: int, session: Session = Depends(get_session)) -> ProjectOut:
    """Fetch a single project by id."""
    return ProjectRepository(session).get(project_id)


@router.patch("/{project_id}", response_model=WriteResponse[ProjectOut])
async def update_project(
    project_id: int,
    body: ProjectUpdateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ProjectOut]:
    """UI-permissive PATCH; the repo refuses ``slug`` per audit B-27."""
    patch = body.model_dump(exclude_unset=True)
    return write_response(ProjectRepository(session).update(project_id, **patch))


@router.post("/{project_id}/activate", response_model=WriteResponse[ProjectOut])
async def activate_project(
    project_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[ProjectOut]:
    """Make ``project_id`` the only ``is_active=true`` project (E1)."""
    return write_response(ProjectRepository(session).set_active(project_id))


@router.delete("/{project_id}", response_model=WriteResponse[ProjectOut])
async def delete_project(
    project_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[ProjectOut]:
    """Soft-delete: flips ``is_active=false``. Hard cascade is M9."""
    return write_response(ProjectRepository(session).delete(project_id))


# ---------------------------------------------------------------------------
# Voice profiles.
# ---------------------------------------------------------------------------


@router.get("/{project_id}/voice", response_model=VoiceProfileOut | None)
async def get_voice(
    project_id: int,
    session: Session = Depends(get_session),
) -> VoiceProfileOut | None:
    """Return the active (``is_default=true``) voice profile or null."""
    repo = VoiceProfileRepository(session)
    page = repo.list_variants(project_id, limit=200)
    for v in page.items:
        if v.is_default:
            return v
    return None


@router.put(
    "/{project_id}/voice",
    response_model=WriteResponse[VoiceProfileOut],
    status_code=status.HTTP_200_OK,
)
async def put_voice(
    project_id: int,
    body: VoiceUpsertRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[VoiceProfileOut]:
    """Create-or-replace the active voice profile."""
    repo = VoiceProfileRepository(session)
    env = repo.set(
        project_id=project_id,
        name=body.name,
        voice_md=body.voice_md,
        is_default=True,
    )
    return write_response(env)


@router.get("/{project_id}/voice/variants", response_model=PageResponse[VoiceProfileOut])
async def list_voice_variants(
    project_id: int,
    page: PaginationParams = Depends(pagination_params),
    session: Session = Depends(get_session),
) -> PageResponse[VoiceProfileOut]:
    """List all voice variants for a project."""
    return page_response(
        VoiceProfileRepository(session).list_variants(
            project_id, limit=page.limit, after_id=page.after
        )
    )


@router.post(
    "/{project_id}/voice/variants",
    response_model=WriteResponse[VoiceProfileOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_voice_variant(
    project_id: int,
    body: VoiceUpsertRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[VoiceProfileOut]:
    """Insert a new voice variant (does not auto-activate unless ``is_default=true``)."""
    return write_response(
        VoiceProfileRepository(session).set(
            project_id=project_id,
            name=body.name,
            voice_md=body.voice_md,
            is_default=body.is_default,
        )
    )


@router.post(
    "/{project_id}/voice/{voice_id}/activate",
    response_model=WriteResponse[VoiceProfileOut],
)
async def activate_voice(
    project_id: int,
    voice_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[VoiceProfileOut]:
    """Mark ``voice_id`` active and clear the default on every other variant."""
    _ = project_id  # repo derives project_id from the row
    return write_response(VoiceProfileRepository(session).set_active(voice_id))


# ---------------------------------------------------------------------------
# Compliance rules.
# ---------------------------------------------------------------------------


@router.get("/{project_id}/compliance", response_model=list[ComplianceRuleOut])
async def list_compliance(
    project_id: int,
    session: Session = Depends(get_session),
) -> list[ComplianceRuleOut]:
    """List compliance rules ordered by position then id."""
    return ComplianceRuleRepository(session).list(project_id)


@router.post(
    "/{project_id}/compliance",
    response_model=WriteResponse[ComplianceRuleOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_compliance(
    project_id: int,
    body: ComplianceCreateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ComplianceRuleOut]:
    """Add a compliance rule for the project."""
    env = ComplianceRuleRepository(session).add(
        project_id=project_id,
        kind=body.kind,
        title=body.title,
        body_md=body.body_md,
        jurisdictions=body.jurisdictions,
        position=body.position,
        params_json=body.params_json,
        validator=body.validator,
        is_active=body.is_active,
    )
    return write_response(env)


@router.patch(
    "/{project_id}/compliance/{rule_id}",
    response_model=WriteResponse[ComplianceRuleOut],
)
async def update_compliance(
    project_id: int,
    rule_id: int,
    body: ComplianceUpdateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ComplianceRuleOut]:
    """Patch a compliance rule (ownership of ``project_id`` enforced by FK)."""
    _ = project_id  # repo derives from row
    patch = body.model_dump(exclude_unset=True)
    return write_response(ComplianceRuleRepository(session).update(rule_id, **patch))


@router.delete(
    "/{project_id}/compliance/{rule_id}",
    response_model=WriteResponse[ComplianceRuleOut],
)
async def delete_compliance(
    project_id: int,
    rule_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[ComplianceRuleOut]:
    """Hard-delete a compliance rule."""
    _ = project_id
    return write_response(ComplianceRuleRepository(session).remove(rule_id))


# ---------------------------------------------------------------------------
# EEAT criteria.
# ---------------------------------------------------------------------------


@router.get("/{project_id}/eeat", response_model=list[EeatCriterionOut])
async def list_eeat(
    project_id: int,
    session: Session = Depends(get_session),
) -> list[EeatCriterionOut]:
    """List EEAT criteria ordered by category + code."""
    return EeatCriteriaRepository(session).list(project_id)


@router.put(
    "/{project_id}/eeat",
    response_model=WriteResponse[list[EeatCriterionOut]],
)
async def bulk_set_eeat(
    project_id: int,
    body: EeatBulkSetRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[list[EeatCriterionOut]]:
    """Bulk update ``required``/``active``/``weight`` per criterion id.

    Repo enforces D7 ``tier='core'`` floor; whole batch rolls back if any
    item violates.
    """
    return write_response(EeatCriteriaRepository(session).bulk_set(project_id, body.items))


@router.patch(
    "/{project_id}/eeat/{criterion_id}",
    response_model=WriteResponse[EeatCriterionOut],
)
async def patch_eeat_criterion(
    project_id: int,
    criterion_id: int,
    body: EeatTogglePatch,
    session: Session = Depends(get_session),
) -> WriteResponse[EeatCriterionOut]:
    """Toggle ``required``/``active`` or set ``weight`` on a single criterion.

    D7: ``tier='core'`` rows refuse ``required=False`` / ``active=False``.
    The repo raises ``ConflictError`` which surfaces as 409.
    """
    _ = project_id
    repo = EeatCriteriaRepository(session)
    if body.required is None and body.active is None and body.weight is None:
        # No-op patch — refetch the row through ``toggle`` (no flags) so the
        # caller still gets the canonical envelope shape rather than a 422.
        return write_response(repo.toggle(criterion_id))
    if body.weight is not None:
        # Apply weight first so a combined patch lands atomically.
        weight_env = repo.score(criterion_id, weight=body.weight)
        if body.required is None and body.active is None:
            return write_response(weight_env)
    return write_response(repo.toggle(criterion_id, required=body.required, active=body.active))


# ---------------------------------------------------------------------------
# Publish targets.
# ---------------------------------------------------------------------------


@router.get("/{project_id}/publish-targets", response_model=list[PublishTargetOut])
async def list_publish_targets(
    project_id: int,
    session: Session = Depends(get_session),
) -> list[PublishTargetOut]:
    """List publish targets for a project."""
    return PublishTargetRepository(session).list(project_id)


@router.post(
    "/{project_id}/publish-targets",
    response_model=WriteResponse[PublishTargetOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_publish_target(
    project_id: int,
    body: PublishTargetCreateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[PublishTargetOut]:
    """Add a publish target; ``is_primary=true`` clears any other primary."""
    return write_response(
        PublishTargetRepository(session).add(
            project_id=project_id,
            kind=body.kind,
            config_json=body.config_json,
            is_primary=body.is_primary,
            is_active=body.is_active,
        )
    )


@router.patch(
    "/{project_id}/publish-targets/{target_id}",
    response_model=WriteResponse[PublishTargetOut],
)
async def update_publish_target(
    project_id: int,
    target_id: int,
    body: PublishTargetUpdateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[PublishTargetOut]:
    """Patch a publish target."""
    _ = project_id
    patch = body.model_dump(exclude_unset=True)
    return write_response(PublishTargetRepository(session).update(target_id, **patch))


@router.delete(
    "/{project_id}/publish-targets/{target_id}",
    response_model=WriteResponse[PublishTargetOut],
)
async def delete_publish_target(
    project_id: int,
    target_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[PublishTargetOut]:
    """Hard-delete a publish target."""
    _ = project_id
    return write_response(PublishTargetRepository(session).remove(target_id))


@router.post(
    "/{project_id}/publish-targets/{target_id}/set-primary",
    response_model=WriteResponse[PublishTargetOut],
)
async def set_primary_publish_target(
    project_id: int,
    target_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[PublishTargetOut]:
    """Make ``target_id`` the project's primary; clear every other primary."""
    _ = project_id
    return write_response(PublishTargetRepository(session).set_primary(target_id))


# ---------------------------------------------------------------------------
# Integrations.
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/integrations",
    response_model=list[IntegrationCredentialOut],
)
async def list_integrations(
    project_id: int,
    session: Session = Depends(get_session),
) -> list[IntegrationCredentialOut]:
    """List project credentials plus global credentials (payload is never returned)."""
    repo = IntegrationCredentialRepository(session)
    return [*repo.list(project_id), *repo.list(None)]


@router.post(
    "/{project_id}/integrations",
    response_model=WriteResponse[IntegrationCredentialOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_integration(
    project_id: int,
    body: IntegrationCreateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[IntegrationCredentialOut]:
    """Upsert an integration credential.

    M4: ``IntegrationCredentialRepository.set`` encrypts the plaintext
    payload via AES-256-GCM at rest (PLAN.md L1106-L1124).
    """
    return write_response(
        IntegrationCredentialRepository(session).set(
            project_id=project_id,
            kind=body.kind,
            plaintext_payload=body.plaintext_payload.encode("utf-8"),
            config_json=body.config_json,
            expires_at=body.expires_at,
        )
    )


@router.patch(
    "/{project_id}/integrations/{credential_id}",
    response_model=WriteResponse[IntegrationCredentialOut],
)
async def update_integration(
    project_id: int,
    credential_id: int,
    body: IntegrationUpdateRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[IntegrationCredentialOut]:
    """Patch an integration credential row.

    The repo's ``set`` upserts on ``(project_id, kind)``; we read the
    existing row to preserve ``kind`` if the body omits it, then re-set.
    """
    repo = IntegrationCredentialRepository(session)
    rows = [c for c in repo.list(project_id) if c.id == credential_id]
    if not rows:
        raise HTTPException(
            status_code=404,
            detail={"detail": f"credential {credential_id} not found", "code": -32004},
        )
    current = rows[0]
    if body.plaintext_payload is None:
        # We can't safely re-encrypt without the plaintext; refuse rotations
        # that would otherwise zero out the existing payload.
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "plaintext_payload is required to rotate a credential",
                "code": -32602,
                "hint": (
                    "Send the plaintext payload again — config-only patches "
                    "are not supported (rotation safety)."
                ),
            },
        )
    new_kind = body.kind if body.kind is not None else current.kind
    new_payload = body.plaintext_payload.encode("utf-8")
    new_config = body.config_json if body.config_json is not None else current.config_json
    new_expires = body.expires_at if body.expires_at is not None else current.expires_at
    return write_response(
        repo.set(
            project_id=project_id,
            kind=new_kind,
            plaintext_payload=new_payload,
            config_json=new_config,
            expires_at=new_expires,
        )
    )


@router.delete(
    "/{project_id}/integrations/{credential_id}",
    response_model=WriteResponse[IntegrationCredentialOut],
)
async def delete_integration(
    project_id: int,
    credential_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[IntegrationCredentialOut]:
    """Hard-delete an integration credential row."""
    _ = project_id
    return write_response(IntegrationCredentialRepository(session).remove(credential_id))


@router.post("/{project_id}/integrations/{credential_id}/test")
async def test_integration(
    project_id: int,
    credential_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Probe vendor health by dispatching to the per-kind wrapper.

    Resolves the credential row, looks up the integration class via
    ``content_stack.integrations.REGISTRY``, instantiates it with the
    decrypted payload + config, and calls ``test_credentials()``.
    Returns the wrapper's status dict on success; raises
    ``IntegrationDownError`` (502) or ``RateLimitedError`` (429) on
    failure (the typed-error map handles the HTTP shape).
    """
    import httpx

    from content_stack.integrations import integration_class_for
    from content_stack.repositories.base import NotFoundError

    repo = IntegrationCredentialRepository(session)
    row = repo.fetch_row(credential_id)
    if row.project_id is not None and row.project_id != project_id:
        raise NotFoundError(f"credential {credential_id} not in project {project_id}")
    integration_cls = integration_class_for(row.kind)
    if integration_cls is None:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": (
                    f"integration kind {row.kind!r} has no test wrapper; "
                    "it may be a runtime LLM key (no health probe)"
                ),
                "code": -32602,
                "hint": "Only DataForSEO/Firecrawl/GSC/OpenAI/Reddit/Jina/Ahrefs/PAA expose tests.",
            },
        )
    plaintext = repo.get_decrypted(credential_id)
    extra: dict[str, Any] = {}
    # DataForSEO needs the login; everyone else takes only the payload.
    if row.kind == "dataforseo":
        config = row.config_json or {}
        login = config.get("login")
        if not login:
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": "dataforseo credential missing config_json.login",
                    "code": -32602,
                },
            )
        extra["login"] = login
    async with httpx.AsyncClient(timeout=30.0) as client:
        integration = integration_cls(
            payload=plaintext,
            project_id=project_id,
            http=client,
            **extra,
        )
        return await integration.test_credentials()


# ---------------------------------------------------------------------------
# Sitemap-fetch helper for skill #5 (competitor-sitemap-shortcut).
# ---------------------------------------------------------------------------


class SitemapFetchRequest(BaseModel):
    """Body for ``POST /projects/{id}/sitemap-fetch``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "urls": [
                    "https://competitor.example/sitemap.xml",
                ],
                "max_entries": 500,
            }
        }
    )

    urls: list[str] = Field(min_length=1, max_length=20)
    timeout_s: float = Field(default=15.0, gt=0, le=60)
    max_index_depth: int = Field(default=2, ge=0, le=4)
    max_entries: int = Field(default=5_000, ge=1, le=20_000)


class SitemapFetchEntryResponse(BaseModel):
    """One URL row in the sitemap-fetch response."""

    url: str
    lastmod: str | None = None
    changefreq: str | None = None
    priority: str | None = None
    source_sitemap: str | None = None


class SitemapFetchErrorResponse(BaseModel):
    """One per-URL fetch failure in the sitemap-fetch response."""

    url: str
    error: str


class SitemapFetchResponse(BaseModel):
    """Top-level shape of the sitemap-fetch response."""

    entries: list[SitemapFetchEntryResponse]
    errors: list[SitemapFetchErrorResponse]


@router.post(
    "/{project_id}/sitemap-fetch",
    response_model=SitemapFetchResponse,
)
async def fetch_project_sitemap(
    project_id: int,
    body: SitemapFetchRequest,
    session: Session = Depends(get_session),
) -> SitemapFetchResponse:
    """Fetch a list of competitor sitemap URLs and return parsed entries.

    Companion to MCP ``sitemap.fetch`` — same payload, same response
    shape; the REST endpoint exists so the UI can show a project-scoped
    sitemap browser without going through MCP. We resolve the project
    only to validate the path (the helper itself doesn't read project
    rows).
    """
    import httpx as _httpx

    from content_stack.integrations.sitemap import fetch_sitemap_entries

    # Validate the project exists; the helper itself is project-agnostic.
    ProjectRepository(session).get(project_id)

    async with _httpx.AsyncClient(
        timeout=body.timeout_s,
        follow_redirects=True,
    ) as client:
        result = await fetch_sitemap_entries(
            body.urls,
            client=client,
            timeout_s=body.timeout_s,
            max_index_depth=body.max_index_depth,
            max_entries=body.max_entries,
        )

    return SitemapFetchResponse(
        entries=[
            SitemapFetchEntryResponse(
                url=e.url,
                lastmod=e.lastmod,
                changefreq=e.changefreq,
                priority=e.priority,
                source_sitemap=e.source_sitemap,
            )
            for e in result.entries
        ],
        errors=[SitemapFetchErrorResponse(url=err.url, error=err.error) for err in result.errors],
    )


# ---------------------------------------------------------------------------
# GSC OAuth flow (PLAN.md L1069-L1080).
# ---------------------------------------------------------------------------


# Module-level routers so the OAuth routes are *not* nested under
# ``/projects/{project_id}/...`` — Google's redirect URI is shared
# across projects, so the callback path must be flat. We add the
# routes to a separate router then re-export through the same module.

oauth_router = APIRouter(prefix="/api/v1/integrations/gsc", tags=["integrations"])


class GscAuthorizeRequest(BaseModel):
    """Body for ``POST /integrations/gsc/oauth/authorize``."""

    model_config = ConfigDict(json_schema_extra={"example": {"project_id": 1}})

    project_id: int
    redirect_uri: str = Field(
        default="http://localhost:5180/api/v1/integrations/gsc/oauth/callback",
        description="Must match the redirect URI registered in Google Cloud Console.",
    )


@oauth_router.post("/oauth/authorize")
async def gsc_oauth_authorize(
    body: GscAuthorizeRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return the Google OAuth consent URL the operator opens in their browser.

    Stores the random ``state`` nonce in
    ``integration_credentials.config_json.oauth_state`` so the callback
    can validate it.
    """
    import secrets

    from content_stack.integrations.gsc import build_authorize_url

    state = secrets.token_urlsafe(32)
    # Persist the nonce on a placeholder row so the callback can find
    # the project + state pair by state value alone.
    repo = IntegrationCredentialRepository(session)
    config = {
        "oauth_state": state,
        "redirect_uri": body.redirect_uri,
    }
    # Empty plaintext is fine — the row is a placeholder until the
    # callback fills it in. AAD is bound to ``(project_id, kind)`` so
    # the row can't be moved between projects.
    repo.set(
        project_id=body.project_id,
        kind="gsc",
        plaintext_payload=b"{}",
        config_json=config,
    )
    url = build_authorize_url(state=state, redirect_uri=body.redirect_uri)
    return {"authorization_url": url, "state": state}


@oauth_router.get("/oauth/callback", response_class=HTMLResponse)
async def gsc_oauth_callback(
    code: str,
    state: str,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Exchange the OAuth code for tokens and store them encrypted.

    Returns a tiny "you can close this tab" HTML page so the operator
    sees confirmation in the browser they opened the consent URL in.
    """
    import json

    from sqlmodel import select

    from content_stack.db.models import IntegrationCredential
    from content_stack.integrations.gsc import exchange_code

    # Locate the placeholder row by state. The state nonce lives in
    # ``config_json.oauth_state``; we filter at the DB level on
    # ``kind='gsc'`` and post-filter on the JSON column (SQLite's JSON
    # functions are too version-dependent to rely on at the ORM layer).
    candidates = session.exec(
        select(IntegrationCredential).where(IntegrationCredential.kind == "gsc")
    ).all()
    matched = next(
        (r for r in candidates if (r.config_json or {}).get("oauth_state") == state),
        None,
    )
    if matched is None:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "OAuth state mismatch — start the authorize flow again",
                "code": -32602,
            },
        )
    redirect_uri = (matched.config_json or {}).get(
        "redirect_uri",
        "http://localhost:5180/api/v1/integrations/gsc/oauth/callback",
    )
    tokens = await exchange_code(code=code, redirect_uri=redirect_uri)
    payload_bytes = json.dumps(tokens).encode("utf-8")
    config = {k: v for k, v in (matched.config_json or {}).items() if k != "oauth_state"}
    expires_at: datetime | None = None
    if "expires_at" in tokens:
        try:
            expires_at = datetime.fromisoformat(str(tokens["expires_at"]).rstrip("Z"))
        except ValueError:
            expires_at = None
    repo = IntegrationCredentialRepository(session)
    repo.set(
        project_id=matched.project_id,
        kind="gsc",
        plaintext_payload=payload_bytes,
        config_json=config,
        expires_at=expires_at,
    )
    body = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>GSC connected</title></head><body>"
        "<h1>Google Search Console connected</h1>"
        "<p>You can close this tab.</p>"
        "</body></html>"
    )
    return HTMLResponse(body, status_code=200)


# ---------------------------------------------------------------------------
# Schedules.
# ---------------------------------------------------------------------------


@router.get("/{project_id}/schedules", response_model=list[ScheduledJobOut])
async def list_schedules(
    project_id: int,
    session: Session = Depends(get_session),
) -> list[ScheduledJobOut]:
    """List scheduled jobs for a project."""
    return ScheduledJobRepository(session).list(project_id)


@router.post(
    "/{project_id}/schedules",
    response_model=WriteResponse[ScheduledJobOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    project_id: int,
    body: ScheduleUpsertRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ScheduledJobOut]:
    """Upsert a scheduled job for the project."""
    return write_response(
        ScheduledJobRepository(session).set(
            project_id=project_id,
            kind=body.kind,
            cron_expr=body.cron_expr,
            enabled=body.enabled,
        )
    )


@router.patch(
    "/{project_id}/schedules/{job_id}",
    response_model=WriteResponse[ScheduledJobOut],
)
async def update_schedule(
    project_id: int,
    job_id: int,
    body: ScheduleUpsertRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[ScheduledJobOut]:
    """Replace a scheduled job by id (kind/cron/enabled).

    The repo's ``set`` is upsert-on-``(project_id, kind)``; the id form is
    only used by the toggle helper below.
    """
    _ = project_id, job_id
    return write_response(
        ScheduledJobRepository(session).set(
            project_id=project_id,
            kind=body.kind,
            cron_expr=body.cron_expr,
            enabled=body.enabled,
        )
    )


@router.delete(
    "/{project_id}/schedules/{job_id}",
    response_model=WriteResponse[ScheduledJobOut],
)
async def delete_schedule(
    project_id: int,
    job_id: int,
    session: Session = Depends(get_session),
) -> WriteResponse[ScheduledJobOut]:
    """Disable (toggle off) a scheduled job. Hard-delete is M9 maintenance work."""
    _ = project_id
    return write_response(ScheduledJobRepository(session).toggle(job_id, enabled=False))


# ---------------------------------------------------------------------------
# Budgets (M-25).
# ---------------------------------------------------------------------------


def _canonical_budget_kind(kind: str) -> str:
    """Normalize legacy UI aliases to integration wrapper keys."""
    if kind == "paa":
        return "google-paa"
    return kind


@router.get(
    "/{project_id}/budgets/{kind}",
    response_model=IntegrationBudgetOut,
)
async def get_budget(
    project_id: int,
    kind: str,
    session: Session = Depends(get_session),
) -> IntegrationBudgetOut:
    """Read the current month's budget + spend for ``(project_id, kind)``."""
    return IntegrationBudgetRepository(session).get(project_id, _canonical_budget_kind(kind))


@router.post(
    "/{project_id}/budgets",
    response_model=WriteResponse[IntegrationBudgetOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_budget(
    project_id: int,
    body: BudgetUpsertRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[IntegrationBudgetOut]:
    """Upsert a budget row (``monthly_budget_usd`` + ``alert_threshold_pct``)."""
    return write_response(
        IntegrationBudgetRepository(session).set(
            project_id=project_id,
            kind=_canonical_budget_kind(body.kind),
            monthly_budget_usd=body.monthly_budget_usd,
            alert_threshold_pct=body.alert_threshold_pct,
            qps=body.qps,
        )
    )


@router.patch(
    "/{project_id}/budgets/{kind}",
    response_model=WriteResponse[IntegrationBudgetOut],
)
async def update_budget(
    project_id: int,
    kind: str,
    body: BudgetUpsertRequest,
    session: Session = Depends(get_session),
) -> WriteResponse[IntegrationBudgetOut]:
    """Update an existing budget; the body's ``kind`` is ignored — path wins."""
    _ = body.kind
    return write_response(
        IntegrationBudgetRepository(session).set(
            project_id=project_id,
            kind=_canonical_budget_kind(kind),
            monthly_budget_usd=body.monthly_budget_usd,
            alert_threshold_pct=body.alert_threshold_pct,
            qps=body.qps,
        )
    )


# ---------------------------------------------------------------------------
# Cost summary.
# ---------------------------------------------------------------------------


@router.get("/{project_id}/cost", response_model=CostResponse)
async def get_project_cost(
    project_id: int,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    session: Session = Depends(get_session),
) -> CostResponse:
    """Aggregate per-integration cost for ``project_id`` in ``month`` (YYYY-MM).

    M2 returns zeros across the board if no integration calls have
    happened yet — the M5 integrations layer surfaces real ``cost.usd``
    via ``runs.metadata_json``. We sum from ``run_steps.cost_cents`` for
    accuracy and divide by 100 to land on USD.
    """
    cost = RunRepository(session).cost(project_id, month=month)
    by_kind_cents: dict[str, int] = cost["by_kind_cents"]
    by_integration = {k: round(v / 100.0, 4) for k, v in by_kind_cents.items()}
    return CostResponse(
        by_integration=by_integration,
        total_usd=round(cost["total_cents"] / 100.0, 4),
        period_start=cost["period_start"],
        period_end=cost["period_end"],
    )


# ---------------------------------------------------------------------------
# Body-only routes that need a separate annotation.
# ---------------------------------------------------------------------------

# (Reserved hook for future operator-only routes: e.g. `/seal-immutables`.)
_ = Body  # keep imported name visible in docs


__all__ = ["router"]
