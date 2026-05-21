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

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from content_stack.api.deps import get_session, get_settings
from content_stack.api.envelopes import WriteResponse, write_response
from content_stack.api.pagination import (
    PageResponse,
    PaginationParams,
    page_response,
    pagination_params,
)
from content_stack.auth_providers import AuthRepository
from content_stack.config import Settings
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


class IntegrationTestResponse(BaseModel):
    """Normalized response for ``POST /projects/{id}/integrations/{cid}/test``."""

    ok: bool
    vendor: str
    status: str
    summary: str
    details: str | None = None
    checked_at: str
    retryable: bool = False
    next_action: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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
    config_json = normalize_publish_target_config(body.kind, body.config_json)
    validate_publish_target_config(body.kind, config_json)
    return write_response(
        PublishTargetRepository(session).add(
            project_id=project_id,
            kind=body.kind,
            config_json=config_json,
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
    repo = PublishTargetRepository(session)
    patch = body.model_dump(exclude_unset=True)
    if "config_json" in patch or "kind" in patch:
        current = next((target for target in repo.list(project_id) if target.id == target_id), None)
        effective_kind = body.kind
        if effective_kind is None and current is not None:
            effective_kind = current.kind
        effective_config = body.config_json
        if effective_config is None and current is not None:
            effective_config = current.config_json
        if effective_kind is not None:
            effective_config = normalize_publish_target_config(effective_kind, effective_config)
        if "config_json" in patch:
            patch["config_json"] = effective_config
        if effective_kind is not None:
            validate_publish_target_config(effective_kind, effective_config)
    return write_response(repo.update(target_id, **patch))


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


_TARGET_SECRET_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "admin_api_key",
    "authorization",
)


def normalize_publish_target_config(
    kind: PublishTargetKind | str,
    config_json: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Store file-target config with the keys consumed by publish skills."""
    if config_json is None:
        return None
    kind_value = kind.value if isinstance(kind, PublishTargetKind) else str(kind)
    config = dict(config_json)
    if kind_value in {"nuxt-content", "hugo", "astro"}:
        if "content_subdir" not in config and "content_dir" in config:
            config["content_subdir"] = config["content_dir"]
        if "public_subdir" not in config and "assets_dir" in config:
            config["public_subdir"] = config["assets_dir"]
        config.pop("content_dir", None)
        config.pop("assets_dir", None)
    return config


def validate_publish_target_config(
    kind: PublishTargetKind | str,
    config_json: dict[str, Any] | None,
) -> None:
    """Validate provider config and reject obvious secrets in target config."""
    kind_value = kind.value if isinstance(kind, PublishTargetKind) else str(kind)
    config = normalize_publish_target_config(kind_value, config_json) or {}
    secret_key = _find_secret_config_key(config)
    if secret_key is not None:
        _raise_target_config_error(
            "publish target config must not contain secrets",
            kind_value,
            secret_key=secret_key,
            hint=(
                "Store WordPress/Ghost/API secrets as integration credentials; "
                "target config should contain only routing metadata."
            ),
        )

    if kind_value in {"nuxt-content", "hugo", "astro"}:
        _require_config_string(config, kind_value, "repo_path")
        _require_config_string(config, kind_value, "content_subdir")
        return
    if kind_value == "wordpress":
        _require_config_string(config, kind_value, "wp_url")
        _validate_optional_number(config, kind_value, "category_id")
        _validate_optional_number_list(config, kind_value, "tag_ids")
        return
    if kind_value == "ghost":
        _require_config_string(config, kind_value, "ghost_url")
        _validate_optional_string_list(config, kind_value, "tags")
        _validate_optional_string_list(config, kind_value, "authors")
        return
    if kind_value == "custom-webhook":
        _require_config_string(config, kind_value, "webhook_url")
        method = config.get("method")
        if method is not None and method not in {"POST", "PUT", "PATCH"}:
            _raise_target_config_error("method must be POST, PUT, or PATCH", kind_value)
        headers = config.get("headers")
        if headers is not None and (
            not isinstance(headers, dict) or _find_secret_config_key(headers) is not None
        ):
            _raise_target_config_error(
                "headers must be an object without secrets",
                kind_value,
                hint="Use an integration credential for authenticated webhook calls.",
            )


def _find_secret_config_key(config: Mapping[str, Any]) -> str | None:
    for key, value in config.items():
        key_lower = str(key).lower()
        if any(part in key_lower for part in _TARGET_SECRET_KEY_PARTS):
            return str(key)
        if isinstance(value, dict):
            nested = _find_secret_config_key(value)
            if nested is not None:
                return f"{key}.{nested}"
    return None


def _require_config_string(config: Mapping[str, Any], kind: str, key: str) -> None:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        _raise_target_config_error(f"{key} is required", kind, field=key)


def _validate_optional_number(config: Mapping[str, Any], kind: str, key: str) -> None:
    value = config.get(key)
    if value is not None and not _is_json_number(value):
        _raise_target_config_error(f"{key} must be a number", kind, field=key)


def _validate_optional_number_list(config: Mapping[str, Any], kind: str, key: str) -> None:
    value = config.get(key)
    if value is None:
        return
    if not isinstance(value, list) or any(not _is_json_number(item) for item in value):
        _raise_target_config_error(f"{key} must be a list of numbers", kind, field=key)


def _validate_optional_string_list(config: Mapping[str, Any], kind: str, key: str) -> None:
    value = config.get(key)
    if value is None:
        return
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _raise_target_config_error(f"{key} must be a list of strings", kind, field=key)


def _is_json_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int | float)


def _raise_target_config_error(
    detail: str,
    kind: str,
    *,
    field: str | None = None,
    secret_key: str | None = None,
    hint: str | None = None,
) -> None:
    data: dict[str, Any] = {"kind": kind}
    if field is not None:
        data["field"] = field
    if secret_key is not None:
        data["secret_key"] = secret_key
    raise HTTPException(
        status_code=422,
        detail={
            "detail": detail,
            "code": -32602,
            "retryable": False,
            "data": data,
            "hint": hint,
        },
    )


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


@router.post(
    "/{project_id}/integrations/{credential_id}/test",
    response_model=IntegrationTestResponse,
)
async def test_integration(
    project_id: int,
    credential_id: int,
    session: Session = Depends(get_session),
) -> IntegrationTestResponse:
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
                "hint": (
                    "Only DataForSEO/Firecrawl/GSC/OpenAI/Reddit/Jina/Ahrefs/PAA/"
                    "WordPress/Ghost expose tests."
                ),
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
    elif row.kind == "wordpress":
        config = row.config_json or {}
        site_url = config.get("wp_url") or config.get("site_url") or config.get("base_url")
        if not site_url:
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": "wordpress credential missing config_json.wp_url",
                    "code": -32602,
                },
            )
        extra["site_url"] = str(site_url)
    elif row.kind == "ghost":
        config = row.config_json or {}
        site_url = config.get("ghost_url") or config.get("site_url") or config.get("base_url")
        if not site_url:
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": "ghost credential missing config_json.ghost_url",
                    "code": -32602,
                },
            )
        extra["site_url"] = str(site_url)
        if config.get("api_version"):
            extra["api_version"] = str(config["api_version"])
    async with httpx.AsyncClient(timeout=30.0) as client:
        integration = integration_cls(
            payload=plaintext,
            project_id=project_id,
            http=client,
            **extra,
        )
        raw_result = await integration.test_credentials()
        return _normalize_integration_test_result(row.kind, raw_result)


def _normalize_integration_test_result(
    kind: str,
    raw: Mapping[str, Any],
) -> IntegrationTestResponse:
    vendor = str(raw.get("vendor") or kind)
    ok = bool(raw.get("ok", raw.get("status") == "ok"))
    status_value = raw.get("status")
    status_text = str(status_value) if status_value else ("ok" if ok else "failed")
    summary_value = raw.get("summary") or raw.get("detail") or raw.get("message")
    summary = (
        str(summary_value)
        if summary_value
        else (f"{vendor} credentials are reachable" if ok else f"{vendor} credential test failed")
    )
    details = raw.get("details")
    retryable = raw.get("retryable")
    next_action = raw.get("next_action")
    passthrough_keys = {
        "ok",
        "vendor",
        "status",
        "summary",
        "detail",
        "message",
        "details",
        "checked_at",
        "retryable",
        "next_action",
        "metadata",
    }
    metadata = {key: value for key, value in raw.items() if key not in passthrough_keys}
    metadata_value = raw.get("metadata")
    if isinstance(metadata_value, dict):
        metadata.update(metadata_value)
    checked_at = raw.get("checked_at")
    return IntegrationTestResponse(
        ok=ok,
        vendor=vendor,
        status=status_text,
        summary=summary,
        details=str(details) if details else None,
        checked_at=str(checked_at) if checked_at else datetime.now(tz=UTC).isoformat(),
        retryable=bool(retryable) if isinstance(retryable, bool) else False,
        next_action=str(next_action) if next_action else None,
        metadata=metadata,
    )


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
_GSC_OAUTH_ENV_VARS = ("GSC_OAUTH_CLIENT_ID", "GSC_OAUTH_CLIENT_SECRET")


class GscAuthorizeRequest(BaseModel):
    """Body for ``POST /integrations/gsc/oauth/authorize``."""

    model_config = ConfigDict(json_schema_extra={"example": {"project_id": 1}})

    project_id: int
    redirect_uri: str | None = Field(
        default=None,
        description="Must match the redirect URI registered in Google Cloud Console.",
    )


class GscOAuthInfoResponse(BaseModel):
    """Local setup details for the GSC OAuth flow."""

    redirect_uri: str
    configured: bool
    missing: list[str] = Field(default_factory=list)
    hint: str | None = None


class GscAuthorizeResponse(BaseModel):
    """Consent URL plus the callback URI used to build it."""

    authorization_url: str
    state: str
    redirect_uri: str


@oauth_router.get("/oauth/info", response_model=GscOAuthInfoResponse)
async def gsc_oauth_info(
    settings: Settings = Depends(get_settings),
) -> GscOAuthInfoResponse:
    """Return local GSC OAuth setup details without creating an OAuth state."""
    missing = _missing_gsc_oauth_env_vars()
    return GscOAuthInfoResponse(
        redirect_uri=AuthRepository.default_gsc_redirect_uri(settings),
        configured=len(missing) == 0,
        missing=missing,
        hint=_gsc_oauth_setup_hint() if missing else None,
    )


@oauth_router.post("/oauth/authorize", response_model=GscAuthorizeResponse)
async def gsc_oauth_authorize(
    body: GscAuthorizeRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> GscAuthorizeResponse:
    """Return the Google OAuth consent URL the operator opens in their browser.

    Delegates to the generic auth-provider flow, which stores the state
    in ``oauth_states`` while preserving the legacy callback URL.
    """
    from content_stack.repositories.base import ValidationError

    try:
        env = AuthRepository(session).start(
            project_id=body.project_id,
            provider_key="gsc",
            settings=settings,
            redirect_uri=body.redirect_uri,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": exc.detail,
                "code": -32602,
                "retryable": False,
                "data": exc.data,
                "hint": exc.data.get("hint") or _gsc_oauth_setup_hint(),
            },
        ) from exc
    assert env.data.authorization_url is not None
    assert env.data.state is not None
    assert env.data.redirect_uri is not None
    return GscAuthorizeResponse(
        authorization_url=env.data.authorization_url,
        state=env.data.state,
        redirect_uri=env.data.redirect_uri,
    )


def _missing_gsc_oauth_env_vars() -> list[str]:
    return [name for name in _GSC_OAUTH_ENV_VARS if not os.environ.get(name)]


def _gsc_oauth_setup_hint() -> str:
    return "Set GSC_OAUTH_CLIENT_ID and GSC_OAUTH_CLIENT_SECRET, then restart the daemon."


@oauth_router.get("/oauth/callback", response_class=HTMLResponse)
async def gsc_oauth_callback(
    code: str,
    state: str,
    settings: Settings = Depends(get_settings),
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

    auth_repo = AuthRepository(session)
    oauth_state = auth_repo.consume_oauth_state(state=state, provider_key="gsc")
    matched = None
    if oauth_state is not None and oauth_state.integration_credential_id is not None:
        matched = session.get(IntegrationCredential, oauth_state.integration_credential_id)
    if matched is None:
        # Compatibility fallback for rows created before generic oauth_states.
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
        AuthRepository.default_gsc_redirect_uri(settings),
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
    if matched.id is not None:
        credential = auth_repo.sync_credential_for_integration(matched.id)
        auth_repo.record_refresh_event(
            credential=credential,
            provider_key="gsc",
            status="connected",
            metadata_json={"oauth_callback": True, "token_payload": tokens},
        )
        session.commit()
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
    "/{project_id}/budgets",
    response_model=list[IntegrationBudgetOut],
)
async def list_budgets(
    project_id: int,
    session: Session = Depends(get_session),
) -> list[IntegrationBudgetOut]:
    """List configured budget rows for a project."""
    return IntegrationBudgetRepository(session).list(project_id)


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
