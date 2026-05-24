"""Agent-facing communication delivery operations.

These operations sit above provider actions. Agents express actor, destination,
content, and context; StackOS resolves target/profile/action/credential details,
validates capabilities, executes the provider action, and records audit.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from stackos.actions import ActionRepository
from stackos.artifacts import redact_secrets
from stackos.auth_providers.repository import AuthRepository
from stackos.communications import (
    communication_profile_ref,
    communication_record_by_external_id,
    merged_provider_profile,
)
from stackos.db.models import Credential, ResourceRecord
from stackos.mcp.context import MCPContext
from stackos.mcp.contract import MCPInput, WriteEnvelope
from stackos.mcp.streaming import ProgressEmitter
from stackos.operations.communication_platform import (
    CommunicationTargetOut,
    _communication_target_out,
    _default_action_ref,
    _string_list,
    _target_action_defaults,
    _target_policy_allowed,
)
from stackos.operations.spec import (
    OperationExample,
    OperationSpec,
    OperationSurface,
    OperationSurfaces,
)
from stackos.repositories.agent_requests import AgentRequestOut, AgentRequestRepository
from stackos.repositories.base import ValidationError
from stackos.repositories.projects import ProjectRepository

_DEFAULT_FALLBACK_MODE: Literal["reject"] = "reject"
_COMMUNICATION_ERROR_DETAIL = "communication request rejected"


class CommunicationAttachmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["image", "document", "file"]
    artifact_ref: str | None = None
    url: str | None = None
    file_id: str | None = None
    caption: str | None = None
    filename: str | None = None
    mime_type: str | None = None


class CommunicationControlInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["button"] = "button"
    label: str
    action: str | None = None
    value: str | None = None
    callback_data: str | None = None
    url: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    style: Literal["default", "primary", "danger"] = "default"


class CommunicationContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    subject: str | None = None
    html: str | None = None
    format: Literal["auto", "plain", "markdown", "mrkdwn", "html"] = "auto"
    attachments: list[CommunicationAttachmentInput] = Field(default_factory=list)
    controls: list[CommunicationControlInput] = Field(default_factory=list)


class CommunicationContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_request_id: int | None = None
    reply_to: str | None = None
    thread: str | None = None
    thread_ref: str | None = None
    source_surface_ref: str | None = None
    invoker_ref: str | None = None


class CommunicationDeliveryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visibility: Literal["channel", "private", "origin"] = "channel"
    reply_mode: Literal["default", "same_thread", "new_thread", "message_reply", "none"] = "default"
    disable_notification: bool | None = None
    reply_broadcast: bool | None = None


class CommunicationFallbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["reject"] = _DEFAULT_FALLBACK_MODE


class CommunicationSendInput(MCPInput):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "project_id": 1,
                "from": "ops-bot",
                "to": "slack-roadmap",
                "text": "Done. The fix shipped.",
                "context": {"source_request_id": 5},
            }
        },
    )

    project_id: int | None = None
    to: str
    from_ref: str | None = Field(default=None, alias="from")
    text: str | None = None
    content: CommunicationContentInput | None = None
    attachments: list[CommunicationAttachmentInput] = Field(default_factory=list)
    controls: list[CommunicationControlInput] = Field(default_factory=list)
    context: CommunicationContextInput = Field(default_factory=CommunicationContextInput)
    delivery: CommunicationDeliveryInput = Field(default_factory=CommunicationDeliveryInput)
    fallback: CommunicationFallbackInput = Field(default_factory=CommunicationFallbackInput)
    intent_id: str | None = None
    intent_summary: str | None = None
    dry_run: bool = False


class CommunicationReplyInput(MCPInput):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "project_id": 1,
                "request_id": 42,
                "text": "I checked it. Routing is fixed.",
            }
        },
    )

    project_id: int | None = None
    request_id: int
    from_ref: str | None = Field(default=None, alias="from")
    text: str | None = None
    content: CommunicationContentInput | None = None
    attachments: list[CommunicationAttachmentInput] = Field(default_factory=list)
    controls: list[CommunicationControlInput] = Field(default_factory=list)
    delivery: CommunicationDeliveryInput = Field(default_factory=CommunicationDeliveryInput)
    fallback: CommunicationFallbackInput = Field(default_factory=CommunicationFallbackInput)
    intent_id: str | None = None
    intent_summary: str | None = None
    dry_run: bool = False


class CommunicationSendOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    status: str
    action_call_id: int | None = None
    action_ref: str
    provider_key: str
    target_ref: str | None = None
    actor_ref: str | None = None
    surface_ref: str | None = None
    thread_ref: str | None = None
    message_ref: str | None = None
    dry_run: bool = False
    resolved: dict[str, Any] = Field(default_factory=dict)


async def communication_send(
    inp: CommunicationSendInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> WriteEnvelope[CommunicationSendOut]:
    project_id = _resolve_project_id(inp.project_id, ctx)
    _require_project(ctx.session, project_id)
    content = _normalize_content(
        text=inp.text,
        content=inp.content,
        attachments=inp.attachments,
        controls=inp.controls,
    )
    source = _source_context(ctx.session, project_id=project_id, context=inp.context)
    target = _require_target(ctx.session, project_id=project_id, to=inp.to)
    actor = _resolve_actor(
        ctx.session,
        project_id=project_id,
        provider_key=target.provider_key,
        target=target,
        requested_from=inp.from_ref,
        source_actor_ref=source.get("profile_ref") or source.get("profile_key"),
    )
    _ensure_target_policy(
        policy=target.send_policy,
        target=target,
        actor_ref=actor["profile_ref"],
        source_surface_ref=source.get("source_surface_ref"),
        invoker_ref=source.get("invoker_ref"),
        resolved={
            "operation": "communication.send",
            "to": inp.to,
            "from": actor["profile_ref"],
            "provider": target.provider_key,
            "surface_ref": target.surface_ref,
        },
    )
    surface = _surface_data(ctx.session, project_id=project_id, surface_ref=target.surface_ref)
    payload = _build_provider_payload(
        session=ctx.session,
        project_id=project_id,
        provider_key=target.provider_key,
        action_ref=target.action_ref or _default_action_ref(target.provider_key),
        actor=actor,
        target=target,
        content=content,
        delivery=inp.delivery,
        context=inp.context,
        source=source,
        surface=surface,
        operation="communication.send",
    )
    return await _execute_delivery(
        ctx,
        project_id=project_id,
        operation="communication.send",
        action_ref=payload["action_ref"],
        input_json=payload["input_json"],
        credential_ref=actor["credential_ref"],
        idempotency_key=inp.idempotency_key
        or _derive_idempotency_key(
            project_id=project_id,
            operation="communication.send",
            action_ref=payload["action_ref"],
            actor_ref=actor["profile_ref"],
            destination_ref=target.target_ref,
            content=content,
            source_request_id=source.get("source_request_id"),
            intent_id=inp.intent_id,
            request_id=ctx.request_id,
        ),
        dry_run=inp.dry_run,
        metadata_json={
            "operation": "communication.send",
            "target_ref": target.target_ref,
            "actor_ref": actor["profile_ref"],
            "source_request_id": source.get("source_request_id"),
            "intent_summary": inp.intent_summary,
        },
        resolved={
            "operation": "communication.send",
            "to": inp.to,
            "from": actor["profile_ref"],
            "target_ref": target.target_ref,
            "provider_key": target.provider_key,
            "surface_ref": target.surface_ref,
        },
        target_ref=target.target_ref,
        actor_ref=actor["profile_ref"],
        surface_ref=target.surface_ref,
        fallback=inp.fallback,
    )


async def communication_reply(
    inp: CommunicationReplyInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> WriteEnvelope[CommunicationSendOut]:
    project_id = _resolve_project_id(inp.project_id, ctx)
    _require_project(ctx.session, project_id)
    request = AgentRequestRepository(ctx.session).get(
        project_id=project_id,
        request_id=inp.request_id,
    )
    source = _request_origin(ctx.session, project_id=project_id, request=request)
    content = _normalize_content(
        text=inp.text,
        content=inp.content,
        attachments=inp.attachments,
        controls=inp.controls,
    )
    provider_key = str(source.get("provider_key") or request.source_provider or "")
    if provider_key not in {"slack-bot", "telegram-bot"}:
        _reject(
            code="COMM_UNSUPPORTED_PROVIDER",
            category="provider",
            message=f"Request origin provider {provider_key or '<missing>'} is not reply-capable.",
            resolved={
                "operation": "communication.reply",
                "request_id": inp.request_id,
                "provider": provider_key or None,
            },
            failed_paths=[
                {
                    "path": "/request_id",
                    "requested": "reply.origin",
                    "target_supports": ["slack-bot", "telegram-bot"],
                    "target_does_not_support": [provider_key or "missing_provider"],
                }
            ],
            repair_options=[
                {
                    "id": "choose_explicit_target",
                    "description": "Use communication.send with an explicit named target.",
                }
            ],
        )
    target = _origin_target(source, project_id=project_id, provider_key=provider_key)
    actor = _resolve_actor(
        ctx.session,
        project_id=project_id,
        provider_key=provider_key,
        target=target,
        requested_from=inp.from_ref or source.get("profile_ref") or source.get("profile_key"),
        source_actor_ref=None,
    )
    _ensure_reply_policy(
        operation="communication.reply",
        provider_key=provider_key,
        actor=actor,
        source=source,
        target=target,
    )
    payload = _build_provider_payload(
        session=ctx.session,
        project_id=project_id,
        provider_key=provider_key,
        action_ref=target.action_ref or _default_action_ref(provider_key),
        actor=actor,
        target=target,
        content=content,
        delivery=_reply_delivery(inp.delivery),
        context=CommunicationContextInput(
            source_request_id=inp.request_id,
            reply_to=source.get("message_ref"),
            thread_ref=source.get("thread_ref"),
            source_surface_ref=source.get("source_surface_ref"),
            invoker_ref=source.get("invoker_ref"),
        ),
        source=source,
        surface=_surface_data(
            ctx.session,
            project_id=project_id,
            surface_ref=str(source.get("source_surface_ref") or ""),
        ),
        operation="communication.reply",
    )
    return await _execute_delivery(
        ctx,
        project_id=project_id,
        operation="communication.reply",
        action_ref=payload["action_ref"],
        input_json=payload["input_json"],
        credential_ref=actor["credential_ref"],
        idempotency_key=inp.idempotency_key
        or _derive_idempotency_key(
            project_id=project_id,
            operation="communication.reply",
            action_ref=payload["action_ref"],
            actor_ref=actor["profile_ref"],
            destination_ref=str(source.get("source_surface_ref") or ""),
            content=content,
            source_request_id=inp.request_id,
            intent_id=inp.intent_id,
            request_id=ctx.request_id,
        ),
        dry_run=inp.dry_run,
        metadata_json={
            "operation": "communication.reply",
            "actor_ref": actor["profile_ref"],
            "source_request_id": inp.request_id,
            "intent_summary": inp.intent_summary,
        },
        resolved={
            "operation": "communication.reply",
            "request_id": inp.request_id,
            "from": actor["profile_ref"],
            "provider_key": provider_key,
            "surface_ref": source.get("source_surface_ref"),
        },
        target_ref=None,
        actor_ref=actor["profile_ref"],
        surface_ref=source.get("source_surface_ref"),
        fallback=inp.fallback,
    )


def _resolve_project_id(project_id: int | None, ctx: MCPContext) -> int:
    resolved = project_id if project_id is not None else ctx.project_id
    if resolved is None:
        raise ValidationError(
            "project_id is required unless the agent bridge resolved the workspace project"
        )
    return int(resolved)


def _require_project(session: Session, project_id: int) -> None:
    ProjectRepository(session).get(project_id)


def _normalize_content(
    *,
    text: str | None,
    content: CommunicationContentInput | None,
    attachments: list[CommunicationAttachmentInput],
    controls: list[CommunicationControlInput],
) -> CommunicationContentInput:
    if content is None:
        content = CommunicationContentInput(text=text)
    elif text is not None and content.text is not None and text.strip() != content.text.strip():
        _reject(
            code="COMM_INPUT_AMBIGUOUS",
            category="input",
            message="Pass text either at the top level or inside content.text, not both.",
            failed_paths=[
                {"path": "/text", "requested": "message.text"},
                {"path": "/content/text", "requested": "message.text"},
            ],
            repair_options=[
                {
                    "id": "use_one_text_field",
                    "description": "Retry with only content.text or only top-level text.",
                }
            ],
        )
    elif text is not None and content.text is None:
        content.text = text
    content.attachments.extend(attachments)
    content.controls.extend(controls)
    if (
        not _has_text(content.text)
        and not _has_text(content.html)
        and not content.attachments
        and not content.controls
    ):
        _reject(
            code="COMM_CONTENT_REQUIRED",
            category="input",
            message="Communication delivery requires text, html, an attachment, or controls.",
            failed_paths=[{"path": "/content", "requested": "deliverable_content"}],
            repair_options=[
                {
                    "id": "add_content",
                    "description": "Retry with text, html, attachments, or controls.",
                }
            ],
        )
    return content


def _source_context(
    session: Session,
    *,
    project_id: int,
    context: CommunicationContextInput,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "source_request_id": context.source_request_id,
        "source_surface_ref": context.source_surface_ref,
        "invoker_ref": context.invoker_ref,
    }
    if context.source_request_id is None:
        return data
    request = AgentRequestRepository(session).get(
        project_id=project_id,
        request_id=context.source_request_id,
    )
    data.update(_request_origin(session, project_id=project_id, request=request))
    if context.source_surface_ref:
        data["source_surface_ref"] = context.source_surface_ref
    if context.invoker_ref:
        data["invoker_ref"] = context.invoker_ref
    return data


def _request_origin(
    session: Session,
    *,
    project_id: int,
    request: AgentRequestOut,
) -> dict[str, Any]:
    metadata = dict(request.metadata_json or {})
    message_data: dict[str, Any] = {}
    if request.source_resource_record_id is not None:
        record = session.get(ResourceRecord, request.source_resource_record_id)
        if record is not None and record.project_id == project_id:
            message_data = dict(record.data_json or {})
    provider_key = (
        request.source_provider
        or message_data.get("provider_key")
        or metadata.get("provider_key")
        or ""
    )
    surface_ref = (
        message_data.get("surface_ref")
        or message_data.get("channel_ref")
        or message_data.get("chat_ref")
        or metadata.get("surface_ref")
        or metadata.get("channel_ref")
        or metadata.get("chat_ref")
    )
    return {
        "source_request_id": request.id,
        "provider_key": provider_key,
        "profile_ref": metadata.get("profile_ref") or message_data.get("profile_ref"),
        "profile_key": metadata.get("profile_key") or message_data.get("profile_key"),
        "source_surface_ref": surface_ref,
        "thread_ref": message_data.get("thread_ref") or metadata.get("thread_ref"),
        "message_ref": request.source_message_ref or message_data.get("message_ref"),
        "invoker_ref": metadata.get("invoker_ref") or message_data.get("sender_ref"),
    }


def _require_target(session: Session, *, project_id: int, to: str) -> CommunicationTargetOut:
    key = to.strip()
    external_id = key if key.startswith("communication-target:") else f"communication-target:{key}"
    record = communication_record_by_external_id(
        session,
        project_id=project_id,
        resource_key="communication-target",
        external_id=external_id,
    )
    if record is None:
        _reject(
            code="COMM_TARGET_NOT_FOUND",
            category="routing",
            message=f"Communication target {to!r} was not found.",
            resolved={"operation": "communication.send", "to": to},
            failed_paths=[{"path": "/to", "requested": to}],
            repair_options=[
                {
                    "id": "list_targets",
                    "description": "Call communicationTarget.list and choose a configured target.",
                },
                {
                    "id": "create_target",
                    "description": "Create a communicationTarget before sending.",
                },
            ],
        )
    assert record is not None
    return _communication_target_out(record.id, record.project_id, record.data_json or {})


def _origin_target(
    source: dict[str, Any],
    *,
    project_id: int,
    provider_key: str,
) -> CommunicationTargetOut:
    surface_ref = str(source.get("source_surface_ref") or "")
    return CommunicationTargetOut(
        record_id=0,
        project_id=project_id,
        target_ref=f"request-origin:{source.get('source_request_id')}",
        key=f"request-origin-{source.get('source_request_id')}",
        provider_key=provider_key,
        surface_ref=surface_ref,
        profile_ref=(
            str(source.get("profile_ref")) if isinstance(source.get("profile_ref"), str) else None
        ),
        thread_ref=str(source.get("thread_ref"))
        if isinstance(source.get("thread_ref"), str)
        else None,
        enabled=True,
        action_ref=_default_action_ref(provider_key),
        action_input_defaults={},
        send_policy={"mode": "explicit-target", "allowed_profile_refs": []},
        metadata_json={},
    )


def _resolve_actor(
    session: Session,
    *,
    project_id: int,
    provider_key: str,
    target: CommunicationTargetOut,
    requested_from: str | None,
    source_actor_ref: Any = None,
) -> dict[str, Any]:
    actor_ref = _choose_actor_ref(
        target=target,
        requested_from=requested_from,
        source_actor_ref=source_actor_ref,
    )
    if actor_ref is None:
        candidates = _candidate_actor_refs(target)
        _reject(
            code="COMM_AMBIGUOUS_ACTOR" if candidates else "COMM_ACTOR_REQUIRED",
            category="routing",
            message=(
                "Multiple communication profiles could send this message; pass from."
                if candidates
                else "No communication profile could be resolved for this message; pass from."
            ),
            resolved={
                "provider": provider_key,
                "target_ref": target.target_ref,
                "candidate_actor_refs": candidates,
            },
            failed_paths=[{"path": "/from", "requested": "communication-profile"}],
            repair_options=[
                {
                    "id": "pass_from",
                    "description": "Retry with from set to a communication profile key or ref.",
                }
            ],
        )
    assert actor_ref is not None
    actor_ref = _normalize_profile_ref(actor_ref)
    record = communication_record_by_external_id(
        session,
        project_id=project_id,
        resource_key="communication-profile",
        external_id=actor_ref,
    )
    if record is None:
        _reject(
            code="COMM_ACTOR_NOT_FOUND",
            category="routing",
            message=f"Communication profile {actor_ref!r} was not found.",
            resolved={"provider": provider_key, "actor_ref": actor_ref},
            failed_paths=[{"path": "/from", "requested": actor_ref}],
            repair_options=[
                {
                    "id": "list_profiles",
                    "description": "Call communicationProfile.list and choose an existing profile.",
                }
            ],
        )
    assert record is not None
    profile = dict(record.data_json or {})
    provider_profile = merged_provider_profile(profile, provider_key)
    if provider_key not in dict(profile.get("provider_facets") or {}):
        _reject(
            code="COMM_ACTOR_PROVIDER_UNSUPPORTED",
            category="routing",
            message=f"Profile {actor_ref} has no {provider_key} provider facet.",
            resolved={"provider": provider_key, "actor_ref": actor_ref},
            failed_paths=[{"path": "/from", "requested": actor_ref}],
            repair_options=[
                {
                    "id": "choose_profile_with_provider",
                    "description": f"Retry with a profile that has a {provider_key} facet.",
                }
            ],
        )
    auth_profile_key = str(provider_profile.get("auth_profile_key") or "default")
    credential_ref = _credential_ref_for_profile(
        session,
        project_id=project_id,
        provider_key=provider_key,
        profile_key=auth_profile_key,
    )
    if credential_ref is None:
        _reject(
            code="COMM_CREDENTIAL_REQUIRED",
            category="setup",
            message=(
                f"No connected {provider_key} credential exists for profile {auth_profile_key!r}."
            ),
            resolved={
                "provider": provider_key,
                "actor_ref": actor_ref,
                "auth_profile_key": auth_profile_key,
            },
            failed_paths=[{"path": "/from", "requested": actor_ref}],
            repair_options=[
                {
                    "id": "connect_provider",
                    "description": (
                        "Connect or repair the provider credential in StackOS connections."
                    ),
                }
            ],
        )
    return {
        "profile_ref": actor_ref,
        "profile_key": actor_ref.split(":", 1)[1],
        "auth_profile_key": auth_profile_key,
        "credential_ref": credential_ref,
        "profile": profile,
        "provider_profile": provider_profile,
    }


def _choose_actor_ref(
    *,
    target: CommunicationTargetOut,
    requested_from: str | None,
    source_actor_ref: Any = None,
) -> str | None:
    if requested_from and requested_from.strip():
        return requested_from.strip()
    if target.profile_ref:
        return target.profile_ref
    policy = dict(target.send_policy or {})
    for key in ("default_actor_ref", "default_profile_ref"):
        value = policy.get(key) or target.metadata_json.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    candidates = _candidate_actor_refs(target)
    if len(candidates) == 1:
        return candidates[0]
    if isinstance(source_actor_ref, str) and source_actor_ref.strip():
        source_ref = _normalize_profile_ref(source_actor_ref)
        if not candidates or source_ref in candidates:
            return source_ref
    return None


def _candidate_actor_refs(target: CommunicationTargetOut) -> list[str]:
    policy = dict(target.send_policy or {})
    refs = _string_list(policy.get("allowed_profile_refs"))
    return [_normalize_profile_ref(item) for item in refs]


def _normalize_profile_ref(value: str) -> str:
    raw = value.strip()
    if raw.startswith("communication-profile:"):
        return raw
    return communication_profile_ref(raw)


def _credential_ref_for_profile(
    session: Session,
    *,
    project_id: int,
    provider_key: str,
    profile_key: str,
) -> str | None:
    from sqlmodel import col, select

    AuthRepository(session).status(project_id=project_id, provider_key=provider_key)
    row = session.exec(
        select(Credential).where(
            col(Credential.project_id) == project_id,
            col(Credential.provider_key) == provider_key,
            col(Credential.profile_key) == profile_key,
            col(Credential.revoked_at).is_(None),
        )
    ).first()
    return row.credential_ref if row is not None else None


def _ensure_target_policy(
    *,
    policy: dict[str, Any],
    target: CommunicationTargetOut,
    actor_ref: str,
    source_surface_ref: str | None,
    invoker_ref: str | None,
    resolved: dict[str, Any],
) -> None:
    allowed, reason = _target_policy_allowed(
        policy,
        target_ref=target.target_ref,
        profile_ref=actor_ref,
        source_surface_ref=source_surface_ref,
        invoker_ref=invoker_ref,
    )
    if target.enabled and allowed:
        return
    if not target.enabled:
        reason = "target_disabled"
    _reject(
        code="COMM_TARGET_NOT_ALLOWED",
        category="policy",
        message=f"Communication target policy rejected send: {reason}.",
        resolved=resolved,
        failed_paths=[
            {
                "path": "/to",
                "requested": target.target_ref,
                "policy_reason": reason,
            }
        ],
        repair_options=[
            {
                "id": "choose_allowed_target_or_actor",
                "description": (
                    "Retry with an allowed target/from pair or update communicationTarget policy."
                ),
            }
        ],
    )


def _surface_data(session: Session, *, project_id: int, surface_ref: str) -> dict[str, Any]:
    if not surface_ref:
        return {}
    record = communication_record_by_external_id(
        session,
        project_id=project_id,
        resource_key="communication-channel",
        external_id=f"communication-surface:{surface_ref}",
    )
    return dict(record.data_json or {}) if record is not None else {}


def _ensure_reply_policy(
    *,
    operation: str,
    provider_key: str,
    actor: dict[str, Any],
    source: dict[str, Any],
    target: CommunicationTargetOut,
) -> None:
    profile = dict(actor.get("profile") or {})
    response_policy = dict(profile.get("response_policy") or {})
    mode = str(response_policy.get("mode") or "origin").strip()
    if mode in {"disabled", "deny"}:
        _reject(
            code="COMM_REPLY_NOT_ALLOWED",
            category="policy",
            message="Profile response_policy disables replies to request origins.",
            resolved={
                "operation": operation,
                "provider": provider_key,
                "from": actor["profile_ref"],
                "source_request_id": source.get("source_request_id"),
            },
            failed_paths=[{"path": "/request_id", "policy_reason": "response_policy_disabled"}],
        )
    _ensure_ref_policy(
        policy=response_policy,
        allowed_key="allowed_source_surface_refs",
        denied_key="denied_source_surface_refs",
        value=source.get("source_surface_ref"),
        path="/request_id",
        requested="origin.surface",
        denial_code="COMM_REPLY_NOT_ALLOWED",
        resolved={
            "operation": operation,
            "provider": provider_key,
            "from": actor["profile_ref"],
            "surface_ref": source.get("source_surface_ref"),
        },
    )
    _ensure_ref_policy(
        policy=response_policy,
        allowed_key="allowed_invoker_refs",
        denied_key="denied_invoker_refs",
        value=source.get("invoker_ref"),
        path="/request_id",
        requested="origin.invoker",
        denial_code="COMM_REPLY_NOT_ALLOWED",
        resolved={
            "operation": operation,
            "provider": provider_key,
            "from": actor["profile_ref"],
            "invoker_ref": source.get("invoker_ref"),
        },
    )
    access = dict(profile.get("access_policy") or {})
    invoker_ref = source.get("invoker_ref")
    if not isinstance(invoker_ref, str) or not invoker_ref:
        if access.get("user_mode") in {"allowlist", "denylist", "all"}:
            _reject(
                code="COMM_REPLY_INVOKER_UNKNOWN",
                category="policy",
                message=(
                    "Reply origin has no invoker_ref, so user response policy cannot be verified."
                ),
                resolved={
                    "operation": operation,
                    "provider": provider_key,
                    "from": actor["profile_ref"],
                    "surface_ref": target.surface_ref,
                },
                failed_paths=[{"path": "/request_id", "requested": "origin.invoker_ref"}],
            )
        return
    user_mode = access.get("user_mode")
    denied = set(_string_list(access.get("denied_user_refs")))
    if invoker_ref in denied:
        _reject(
            code="COMM_REPLY_NOT_ALLOWED",
            category="policy",
            message=f"Profile access_policy denies replies to invoker {invoker_ref}.",
            resolved={
                "operation": operation,
                "provider": provider_key,
                "from": actor["profile_ref"],
                "invoker_ref": invoker_ref,
            },
            failed_paths=[{"path": "/request_id", "policy_reason": "invoker_denied"}],
        )
    if user_mode == "allowlist":
        allowed = set(_string_list(access.get("allowed_user_refs")))
        if invoker_ref not in allowed:
            _reject(
                code="COMM_REPLY_NOT_ALLOWED",
                category="policy",
                message=f"Profile access_policy does not allow replies to invoker {invoker_ref}.",
                resolved={
                    "operation": operation,
                    "provider": provider_key,
                    "from": actor["profile_ref"],
                    "invoker_ref": invoker_ref,
                },
                failed_paths=[{"path": "/request_id", "policy_reason": "invoker_not_allowed"}],
            )


def _ensure_ref_policy(
    *,
    policy: dict[str, Any],
    allowed_key: str,
    denied_key: str,
    value: Any,
    path: str,
    requested: str,
    denial_code: str,
    resolved: dict[str, Any],
) -> None:
    if not isinstance(value, str) or not value:
        return
    denied = set(_string_list(policy.get(denied_key)))
    if value in denied:
        _reject(
            code=denial_code,
            category="policy",
            message=f"Response policy denies {value}.",
            resolved=resolved,
            failed_paths=[{"path": path, "requested": requested, "policy_reason": "denied"}],
        )
    allowed = set(_string_list(policy.get(allowed_key)))
    if allowed and value not in allowed:
        _reject(
            code=denial_code,
            category="policy",
            message=f"Response policy does not allow {value}.",
            resolved=resolved,
            failed_paths=[{"path": path, "requested": requested, "policy_reason": "not_allowed"}],
        )


def _build_provider_payload(
    *,
    session: Session,
    project_id: int,
    provider_key: str,
    action_ref: str | None,
    actor: dict[str, Any],
    target: CommunicationTargetOut,
    content: CommunicationContentInput,
    delivery: CommunicationDeliveryInput,
    context: CommunicationContextInput,
    source: dict[str, Any],
    surface: dict[str, Any],
    operation: str,
) -> dict[str, Any]:
    if action_ref is None:
        _reject(
            code="COMM_PROVIDER_ACTION_MISSING",
            category="provider",
            message=f"Provider {provider_key} has no configured message send action.",
            resolved={"operation": operation, "provider": provider_key},
            failed_paths=[{"path": "/to", "requested": target.target_ref}],
        )
    assert action_ref is not None
    capabilities = _effective_capabilities(provider_key, surface)
    _validate_delivery_options(
        operation=operation,
        provider_key=provider_key,
        target=target,
        delivery=delivery,
    )
    _validate_content_shape(
        operation=operation,
        provider_key=provider_key,
        target=target,
        content=content,
    )
    required = _required_capabilities(content, delivery=delivery, provider_key=provider_key)
    unsupported = [item for item in required if item["capability"] not in capabilities]
    if unsupported:
        _reject_unsupported_capability(
            operation=operation,
            provider_key=provider_key,
            target=target,
            actor_ref=actor["profile_ref"],
            requested=unsupported,
            capabilities=capabilities,
        )
    if not bool(surface.get("send_enabled", True)):
        _reject(
            code="COMM_SURFACE_SEND_DISABLED",
            category="policy",
            message=f"Surface {target.surface_ref} is not enabled for sends.",
            resolved={
                "operation": operation,
                "provider": provider_key,
                "surface_ref": target.surface_ref,
            },
            failed_paths=[{"path": "/to", "requested": target.target_ref}],
        )

    defaults = _target_action_defaults(session, target)
    source_request_id = (
        context.source_request_id
        if context.source_request_id is not None
        else source.get("source_request_id")
    )
    _ensure_delivery_context(
        operation=operation,
        provider_key=provider_key,
        target=target,
        delivery=delivery,
        context=context,
        source=source,
    )
    if provider_key == "slack-bot":
        _ensure_provider_action_ref(
            operation=operation,
            provider_key=provider_key,
            action_ref=action_ref,
            allowed={"communications.slack-bot.message.send"},
            target=target,
        )
        input_json = {
            **defaults,
            "profile_ref": actor["profile_ref"],
            "surface_ref": target.surface_ref,
        }
        if _has_text(content.text):
            input_json["text"] = content.text
        blocks = _slack_blocks(content)
        if blocks:
            input_json["blocks"] = blocks
        thread_ref = _delivery_thread_ref(delivery, context, target=target, source=source)
        if thread_ref:
            input_json["thread_ref"] = thread_ref
        if delivery.reply_broadcast is not None:
            input_json["reply_broadcast"] = delivery.reply_broadcast
        if source_request_id is not None:
            input_json["source_agent_request_id"] = source_request_id
        control_metadata = _control_metadata(content)
        if control_metadata:
            input_json["control_metadata"] = control_metadata
        return {"action_ref": action_ref, "input_json": input_json}

    if provider_key == "telegram-bot":
        image = _single_image_attachment(content)
        resolved_action_ref = (
            "communications.telegram-bot.photo.send"
            if image is not None
            else "communications.telegram-bot.message.send"
        )
        _ensure_provider_action_ref(
            operation=operation,
            provider_key=provider_key,
            action_ref=action_ref,
            allowed={
                "communications.telegram-bot.message.send",
                "communications.telegram-bot.photo.send",
            },
            target=target,
        )
        _ensure_target_allows_resolved_action_ref(
            operation=operation,
            provider_key=provider_key,
            configured_action_ref=action_ref,
            resolved_action_ref=resolved_action_ref,
            target=target,
        )
        input_json = {
            **defaults,
            "profile_key": actor["profile_key"],
            "chat_ref": target.surface_ref,
        }
        if delivery.disable_notification is not None:
            input_json["disable_notification"] = delivery.disable_notification
        if source_request_id is not None:
            input_json["source_agent_request_id"] = source_request_id
        thread_ref = _delivery_thread_ref(delivery, context, target=target, source=source)
        if thread_ref:
            input_json["thread_ref"] = thread_ref
        if delivery.reply_mode == "message_reply" and (
            context.reply_to or source.get("message_ref")
        ):
            input_json["reply_to_message_ref"] = context.reply_to or source.get("message_ref")
        reply_markup = _telegram_reply_markup(content)
        if reply_markup:
            input_json["reply_markup"] = reply_markup
        parse_mode = _telegram_parse_mode(content.format)
        if parse_mode:
            input_json["parse_mode"] = parse_mode
        control_metadata = _control_metadata(content, max_token_bytes=64)
        if control_metadata:
            input_json["control_metadata"] = control_metadata
        if image is not None:
            input_json["photo"] = {
                key: value
                for key, value in {
                    "artifact_ref": image.artifact_ref,
                    "url": image.url,
                    "file_id": image.file_id,
                }.items()
                if value
            }
            caption = image.caption or content.text
            if caption:
                input_json["caption"] = caption
            return {"action_ref": resolved_action_ref, "input_json": input_json}
        input_json["text"] = content.text or ""
        return {"action_ref": resolved_action_ref, "input_json": input_json}

    if provider_key == "smtp":
        _ensure_provider_action_ref(
            operation=operation,
            provider_key=provider_key,
            action_ref=action_ref,
            allowed={"communications.smtp.email.send"},
            target=target,
        )
        input_json = {**defaults}
        if _has_text(content.subject):
            input_json["subject"] = content.subject
        if _has_text(content.html):
            input_json["html"] = content.html
        if _has_text(content.text):
            input_json["text"] = content.text
        if source_request_id is not None:
            input_json["source_agent_request_id"] = source_request_id
        missing = [key for key in ("recipients", "subject") if key not in input_json]
        if missing:
            _reject(
                code="COMM_EMAIL_FIELD_REQUIRED",
                category="input",
                message=f"SMTP target requires {', '.join(missing)} before sending.",
                resolved={
                    "operation": operation,
                    "provider": provider_key,
                    "target_ref": target.target_ref,
                },
                failed_paths=[
                    {"path": f"/content/{key}", "requested": key}
                    for key in missing
                    if key == "subject"
                ]
                + [
                    {"path": "/to", "requested": "target.action_input_defaults.recipients"}
                    for key in missing
                    if key == "recipients"
                ],
                repair_options=[
                    {
                        "id": "provide_email_fields",
                        "description": (
                            "Add subject and configure recipients on the communication target."
                        ),
                    }
                ],
            )
        return {"action_ref": action_ref, "input_json": input_json}

    _reject(
        code="COMM_UNSUPPORTED_PROVIDER",
        category="provider",
        message=f"Provider {provider_key!r} is not supported by communication.send.",
        resolved={"operation": operation, "provider": provider_key},
        failed_paths=[{"path": "/to", "requested": target.target_ref}],
    )
    raise AssertionError("unreachable")


async def _execute_delivery(
    ctx: MCPContext,
    *,
    project_id: int,
    operation: str,
    action_ref: str,
    input_json: dict[str, Any],
    credential_ref: str,
    idempotency_key: str,
    dry_run: bool,
    metadata_json: dict[str, Any],
    resolved: dict[str, Any],
    target_ref: str | None,
    actor_ref: str | None,
    surface_ref: str | None,
    fallback: CommunicationFallbackInput,
) -> WriteEnvelope[CommunicationSendOut]:
    if fallback.mode != "reject":
        _reject(
            code="COMM_FALLBACK_UNSUPPORTED",
            category="input",
            message="Only fallback.mode=reject is currently supported.",
            resolved={**resolved, "fallback_mode": fallback.mode},
            failed_paths=[{"path": "/fallback/mode", "requested": fallback.mode}],
        )
    settings = ctx.extras.get("settings")
    asset_dir = getattr(settings, "generated_assets_dir", None)
    env = await ActionRepository(ctx.session, asset_dir=asset_dir).execute(
        project_id=project_id,
        action_ref=action_ref,
        input_json=input_json,
        credential_ref=credential_ref,
        run_id=ctx.run_id,
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        metadata_json={
            **metadata_json,
            "dedupe_source": "communication-operation",
        },
    )
    output = env.data.output_json or {}
    out = CommunicationSendOut(
        status="validated" if dry_run else str(output.get("status") or "sent"),
        action_call_id=env.data.action_call.id,
        action_ref=action_ref,
        provider_key=str(env.data.action_call.provider_key or resolved.get("provider_key") or ""),
        target_ref=target_ref,
        actor_ref=actor_ref,
        surface_ref=surface_ref or _first_str(output, "channel_ref", "chat_ref", "surface_ref"),
        thread_ref=_first_str(output, "thread_ref"),
        message_ref=_first_str(output, "message_ref"),
        dry_run=dry_run,
        resolved=resolved,
    )
    return WriteEnvelope(data=out, run_id=env.run_id, project_id=env.project_id)


def _effective_capabilities(provider_key: str, surface: dict[str, Any]) -> set[str]:
    caps = set(_provider_capabilities(provider_key))
    raw = dict(surface.get("capabilities") or {})
    mapping = {
        "can_write": "text",
        "can_thread": "thread",
        "buttons": "control.button.callback",
        "callback_buttons": "control.button.callback",
        "url_buttons": "control.button.url",
        "images": "attachment.image",
        "image": "attachment.image",
        "html": "html",
        "threads": "thread",
        "reactions": "reaction",
    }
    for key, cap in mapping.items():
        if raw.get(key) is True:
            caps.add(cap)
        elif raw.get(key) is False and cap in caps:
            caps.remove(cap)
    explicit = raw.get("supported")
    if isinstance(explicit, list):
        caps.update(str(item) for item in explicit if str(item).strip())
    unsupported = raw.get("unsupported")
    if isinstance(unsupported, list):
        caps.difference_update(str(item) for item in unsupported if str(item).strip())
    return caps


def _validate_delivery_options(
    *,
    operation: str,
    provider_key: str,
    target: CommunicationTargetOut,
    delivery: CommunicationDeliveryInput,
) -> None:
    failed: list[dict[str, Any]] = []
    if operation == "communication.send" and delivery.visibility != "channel":
        failed.append(
            {
                "path": "/delivery/visibility",
                "requested": delivery.visibility,
                "required_capability": f"visibility.{delivery.visibility}",
                "target_supports": ["channel"],
            }
        )
    if operation == "communication.reply" and delivery.visibility == "private":
        failed.append(
            {
                "path": "/delivery/visibility",
                "requested": delivery.visibility,
                "required_capability": "visibility.private",
                "target_supports": ["channel", "origin"],
            }
        )
    if delivery.reply_mode == "new_thread":
        failed.append(
            {
                "path": "/delivery/reply_mode",
                "requested": "new_thread",
                "required_capability": "thread.create",
                "target_supports": ["default", "same_thread", "message_reply", "none"],
            }
        )
    if delivery.disable_notification is not None and provider_key != "telegram-bot":
        failed.append(
            {
                "path": "/delivery/disable_notification",
                "requested": "disable_notification",
                "required_capability": "notification.silent",
                "target_supports": ["telegram-bot"],
            }
        )
    if delivery.reply_broadcast is not None and provider_key != "slack-bot":
        failed.append(
            {
                "path": "/delivery/reply_broadcast",
                "requested": "reply_broadcast",
                "required_capability": "thread.reply_broadcast",
                "target_supports": ["slack-bot"],
            }
        )
    if failed:
        _reject(
            code="COMM_UNSUPPORTED_DELIVERY_OPTION",
            category="capability",
            message="Target provider does not support one or more requested delivery options.",
            resolved={
                "operation": operation,
                "provider": provider_key,
                "target_ref": target.target_ref,
                "surface_ref": target.surface_ref,
            },
            failed_paths=failed,
            repair_options=[
                {
                    "id": "change_delivery",
                    "description": (
                        "Retry with only supported delivery options. This is semantic and "
                        "requires agent decision."
                    ),
                    "requires_agent_decision": True,
                }
            ],
        )


def _validate_content_shape(
    *,
    operation: str,
    provider_key: str,
    target: CommunicationTargetOut,
    content: CommunicationContentInput,
) -> None:
    if provider_key == "telegram-bot":
        if (
            content.controls
            and not _has_text(content.text)
            and _single_image_attachment(content) is None
        ):
            _reject(
                code="COMM_TEXT_OR_ATTACHMENT_REQUIRED",
                category="input",
                message="Telegram inline controls must be attached to a text or photo message.",
                resolved={
                    "operation": operation,
                    "provider": provider_key,
                    "target_ref": target.target_ref,
                },
                failed_paths=[
                    {
                        "path": "/content/controls",
                        "requested": "controls_without_message",
                        "required_capability": "message.container",
                    }
                ],
                repair_options=[
                    {
                        "id": "add_text_or_image",
                        "description": (
                            "Add content.text or one image attachment for Telegram controls."
                        ),
                    }
                ],
            )
        if len(content.attachments) > 1:
            _reject(
                code="COMM_UNSUPPORTED_CONTENT_SHAPE",
                category="capability",
                message="Telegram high-level delivery supports one attachment per message.",
                resolved={
                    "operation": operation,
                    "provider": provider_key,
                    "target_ref": target.target_ref,
                },
                failed_paths=[
                    {
                        "path": "/content/attachments/1",
                        "requested": "multiple_attachments",
                        "required_capability": "attachment.multiple",
                    }
                ],
                repair_options=[
                    {
                        "id": "send_separate_messages",
                        "description": (
                            "Send separate communication.send calls for each attachment."
                        ),
                    }
                ],
            )


def _ensure_provider_action_ref(
    *,
    operation: str,
    provider_key: str,
    action_ref: str,
    allowed: set[str],
    target: CommunicationTargetOut,
) -> None:
    if action_ref in allowed:
        return
    _reject(
        code="COMM_UNSUPPORTED_PROVIDER_ACTION",
        category="provider",
        message=f"{provider_key} target action {action_ref!r} is not supported by {operation}.",
        resolved={
            "operation": operation,
            "provider": provider_key,
            "target_ref": target.target_ref,
            "action_ref": action_ref,
        },
        failed_paths=[
            {
                "path": "/to",
                "requested": action_ref,
                "target_supports": sorted(allowed),
            }
        ],
        repair_options=[
            {
                "id": "use_provider_action_escape_hatch",
                "description": (
                    "Call action.run directly only when the agent intentionally needs a "
                    "provider-specific custom action."
                ),
            }
        ],
    )


def _ensure_target_allows_resolved_action_ref(
    *,
    operation: str,
    provider_key: str,
    configured_action_ref: str,
    resolved_action_ref: str,
    target: CommunicationTargetOut,
) -> None:
    if resolved_action_ref == configured_action_ref:
        return
    metadata = dict(target.metadata_json or {})
    if metadata.get("action_mode") == "auto":
        return
    allowed = set(_string_list(metadata.get("allowed_action_refs")))
    if resolved_action_ref in allowed:
        return
    _reject(
        code="COMM_TARGET_ACTION_VARIANT_NOT_ALLOWED",
        category="provider",
        message=(
            f"Target {target.key} resolves to {configured_action_ref}, but this content "
            f"requires {resolved_action_ref}."
        ),
        resolved={
            "operation": operation,
            "provider": provider_key,
            "target_ref": target.target_ref,
            "configured_action_ref": configured_action_ref,
            "required_action_ref": resolved_action_ref,
        },
        failed_paths=[
            {
                "path": "/content/attachments",
                "requested": resolved_action_ref,
                "target_supports": sorted({configured_action_ref, *allowed}),
            }
        ],
        repair_options=[
            {
                "id": "allow_target_action_variant",
                "description": (
                    "Configure target metadata action_mode=auto or allowed_action_refs "
                    "for this provider action variant."
                ),
            }
        ],
    )


def _provider_capabilities(provider_key: str) -> set[str]:
    if provider_key == "slack-bot":
        return {
            "text",
            "markdown",
            "mrkdwn",
            "control.button.callback",
            "control.button.url",
            "thread",
        }
    if provider_key == "telegram-bot":
        return {
            "text",
            "markdown",
            "html",
            "control.button.callback",
            "control.button.url",
            "attachment.image",
            "thread",
            "message_reply",
        }
    if provider_key == "smtp":
        return {"text", "html"}
    return set()


def _required_capabilities(
    content: CommunicationContentInput,
    *,
    delivery: CommunicationDeliveryInput,
    provider_key: str,
) -> list[dict[str, str]]:
    required: list[dict[str, str]] = []

    def add(capability: str, path: str, requested: str | None = None) -> None:
        if any(item["capability"] == capability for item in required):
            return
        required.append(
            {
                "capability": capability,
                "path": path,
                "requested": requested or capability,
            }
        )

    if _has_text(content.text):
        add("text", "/content/text")
    if _has_text(content.html) or content.format == "html":
        add("html", "/content/html")
    if content.format in {"markdown", "mrkdwn"}:
        add("markdown" if provider_key != "slack-bot" else "mrkdwn", "/content/format")
    for index, attachment in enumerate(content.attachments):
        if attachment.type == "image":
            add("attachment.image", f"/content/attachments/{index}")
        else:
            add(f"attachment.{attachment.type}", f"/content/attachments/{index}")
        if not (attachment.artifact_ref or attachment.url or attachment.file_id):
            _reject(
                code="COMM_ATTACHMENT_SOURCE_REQUIRED",
                category="input",
                message=f"Attachment {index} requires artifact_ref, url, or file_id.",
                failed_paths=[
                    {
                        "path": f"/content/attachments/{index}",
                        "requested": f"attachment.{attachment.type}",
                    }
                ],
            )
    for index, control in enumerate(content.controls):
        if control.type != "button":
            add(f"control.{control.type}", f"/content/controls/{index}")
            continue
        if control.url:
            add("control.button.url", f"/content/controls/{index}")
        else:
            add("control.button.callback", f"/content/controls/{index}")
        if control.payload and not (control.value or control.callback_data or control.action):
            _reject(
                code="COMM_CONTROL_TOKEN_REQUIRED",
                category="input",
                message=(
                    "Button payload requires value, callback_data, or action so "
                    "callbacks stay routable."
                ),
                failed_paths=[
                    {
                        "path": f"/content/controls/{index}",
                        "requested": "control.button.callback",
                    }
                ],
                repair_options=[
                    {
                        "id": "add_callback_token",
                        "description": "Add value, callback_data, or action to the button.",
                    }
                ],
            )
    if delivery.reply_mode == "same_thread":
        add("thread", "/delivery/reply_mode", "same_thread")
    if delivery.reply_mode == "message_reply":
        add("message_reply", "/delivery/reply_mode", "message_reply")
    return required


def _reject_unsupported_capability(
    *,
    operation: str,
    provider_key: str,
    target: CommunicationTargetOut,
    actor_ref: str,
    requested: list[dict[str, str]],
    capabilities: set[str],
) -> None:
    _reject(
        code="COMM_UNSUPPORTED_CAPABILITY",
        category="capability",
        message=(
            f"Target {target.key} does not support: "
            f"{', '.join(item['capability'] for item in requested)}."
        ),
        resolved={
            "operation": operation,
            "to": target.key,
            "from": actor_ref,
            "provider": provider_key,
            "surface_ref": target.surface_ref,
        },
        failed_paths=[
            {
                "path": item["path"],
                "requested": item["requested"],
                "required_capability": item["capability"],
                "target_supports": sorted(capabilities),
                "target_does_not_support": sorted(
                    {unsupported["capability"] for unsupported in requested}
                ),
            }
            for item in requested
        ],
        repair_options=[
            {
                "id": "choose_different_target",
                "description": (
                    "Use a target whose provider/surface supports the requested capability."
                ),
            },
            {
                "id": "change_content",
                "description": (
                    "Change the requested content. This is semantic and requires agent decision."
                ),
                "requires_agent_decision": True,
            },
        ],
    )


def _slack_blocks(content: CommunicationContentInput) -> list[dict[str, Any]]:
    if not content.controls:
        return []
    elements = []
    for control in content.controls:
        token = _control_token(control)
        element: dict[str, Any] = {
            "type": "button",
            "text": {"type": "plain_text", "text": control.label},
            "action_id": control.action or token,
        }
        if control.url:
            element["url"] = control.url
        else:
            element["value"] = token
        elements.append(element)
    return [{"type": "actions", "block_id": "stackos-controls", "elements": elements}]


def _telegram_reply_markup(content: CommunicationContentInput) -> dict[str, Any] | None:
    if not content.controls:
        return None
    row = []
    for control in content.controls:
        item: dict[str, Any] = {"text": control.label}
        if control.url:
            item["url"] = control.url
        else:
            item["callback_data"] = _control_token(control, max_bytes=64)
        row.append(item)
    return {"inline_keyboard": [row]}


def _control_token(control: CommunicationControlInput, *, max_bytes: int | None = None) -> str:
    token = control.callback_data or control.value or control.action
    if not token:
        token = (
            f"control:{_stable_digest({'label': control.label, 'payload': control.payload})[:16]}"
        )
    if max_bytes is not None and len(token.encode("utf-8")) > max_bytes:
        token = f"c:{_stable_digest({'token': token, 'payload': control.payload})[:20]}"
    return token


def _control_metadata(
    content: CommunicationContentInput,
    *,
    max_token_bytes: int | None = None,
) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for control in content.controls:
        token = _control_token(control)
        bounded_token = _control_token(control, max_bytes=max_token_bytes)
        item = {
            "type": control.type,
            "label": control.label,
            "action": control.action,
            "value": control.value,
            "callback_data": control.callback_data,
            "url": control.url,
            "payload": control.payload,
            "style": control.style,
        }
        clean = redact_secrets(
            {key: value for key, value in item.items() if value not in (None, {}, [])}
        )
        if clean:
            metadata[token] = clean
            metadata[bounded_token] = clean
        if control.action and control.action != token:
            metadata[control.action] = clean
    return metadata


def _single_image_attachment(
    content: CommunicationContentInput,
) -> CommunicationAttachmentInput | None:
    if not content.attachments:
        return None
    if len(content.attachments) == 1 and content.attachments[0].type == "image":
        return content.attachments[0]
    return None


def _telegram_parse_mode(format_value: str) -> str | None:
    if format_value == "html":
        return "HTML"
    if format_value == "markdown":
        return "Markdown"
    return None


def _delivery_thread_ref(
    delivery: CommunicationDeliveryInput,
    context: CommunicationContextInput,
    *,
    target: CommunicationTargetOut,
    source: dict[str, Any],
) -> str | None:
    if delivery.reply_mode == "none":
        return None
    if context.thread_ref:
        return context.thread_ref
    if context.thread == "same" or delivery.reply_mode == "same_thread":
        return str(source.get("thread_ref") or target.thread_ref or "") or None
    if delivery.reply_mode == "default":
        return target.thread_ref
    return None


def _ensure_delivery_context(
    *,
    operation: str,
    provider_key: str,
    target: CommunicationTargetOut,
    delivery: CommunicationDeliveryInput,
    context: CommunicationContextInput,
    source: dict[str, Any],
) -> None:
    if (delivery.reply_mode == "same_thread" or context.thread == "same") and not (
        context.thread_ref or source.get("thread_ref") or target.thread_ref
    ):
        _reject(
            code="COMM_DELIVERY_CONTEXT_REQUIRED",
            category="input",
            message="same_thread delivery requires a resolvable thread_ref.",
            resolved={
                "operation": operation,
                "provider": provider_key,
                "target_ref": target.target_ref,
                "surface_ref": target.surface_ref,
            },
            failed_paths=[
                {
                    "path": "/delivery/reply_mode",
                    "requested": "same_thread",
                    "required_context": "thread_ref",
                }
            ],
            repair_options=[
                {
                    "id": "provide_thread_ref",
                    "description": (
                        "Pass context.thread_ref or choose a non-threaded delivery mode."
                    ),
                }
            ],
        )
    if delivery.reply_mode == "message_reply" and not (
        context.reply_to or source.get("message_ref")
    ):
        _reject(
            code="COMM_DELIVERY_CONTEXT_REQUIRED",
            category="input",
            message="message_reply delivery requires a resolvable source message ref.",
            resolved={
                "operation": operation,
                "provider": provider_key,
                "target_ref": target.target_ref,
                "surface_ref": target.surface_ref,
            },
            failed_paths=[
                {
                    "path": "/delivery/reply_mode",
                    "requested": "message_reply",
                    "required_context": "reply_to",
                }
            ],
            repair_options=[
                {
                    "id": "provide_reply_to",
                    "description": "Pass context.reply_to or choose a non-message-reply mode.",
                }
            ],
        )


def _reply_delivery(delivery: CommunicationDeliveryInput) -> CommunicationDeliveryInput:
    return delivery


def _derive_idempotency_key(
    *,
    project_id: int,
    operation: str,
    action_ref: str,
    actor_ref: str | None,
    destination_ref: str,
    content: CommunicationContentInput,
    source_request_id: int | None,
    intent_id: str | None,
    request_id: str,
) -> str:
    source = {
        "scope": "communication",
        "project_id": project_id,
        "operation": operation,
        "action_ref": action_ref,
        "actor_ref": actor_ref,
        "destination_ref": destination_ref,
        "content": content.model_dump(mode="json"),
        "source_request_id": source_request_id,
        "intent_id": (intent_id or "").strip() or None,
        "request_id": None if intent_id else request_id,
    }
    return f"communication:{_stable_digest(source)}"


def _stable_digest(value: dict[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _first_str(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _has_text(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _reject(
    *,
    code: str,
    category: str,
    message: str,
    resolved: dict[str, Any] | None = None,
    failed_paths: list[dict[str, Any]] | None = None,
    repair_options: list[dict[str, Any]] | None = None,
    terminal: bool = True,
    retryable: bool = False,
) -> None:
    raise ValidationError(
        _COMMUNICATION_ERROR_DETAIL,
        data={
            "ok": False,
            "error": {
                "code": code,
                "category": category,
                "message": message,
                "effect": "none",
                "terminal": terminal,
                "retryable": retryable,
                "same_input_will_fail": terminal and not retryable,
                "requires_agent_decision": True,
                "failed_paths": failed_paths or [],
                "resolved": resolved or {},
                "repair": {
                    "next_action": "choose_one",
                    "options": repair_options or [],
                    "do_not": [
                        "Do not retry the same input unchanged.",
                        "Do not assume provider capabilities that are not listed.",
                        "Do not change communication semantics without an explicit agent decision.",
                    ],
                },
            },
        },
    )


def _surfaces(name: str, command: str) -> OperationSurfaces:
    return OperationSurfaces(
        mcp=OperationSurface(enabled=True),
        rest=OperationSurface(enabled=True, path=f"/api/v1/operations/{name}/call"),
        cli=OperationSurface(enabled=True, command=command),
    )


def operation_specs() -> list[OperationSpec]:
    return [
        OperationSpec(
            name="communication.send",
            summary="Send a provider-neutral message to a named communication target.",
            input_model=CommunicationSendInput,
            output_model=WriteEnvelope[CommunicationSendOut],
            handler=communication_send,
            surfaces=_surfaces("communication.send", "ops call communication.send"),
            purpose=(
                "Use this as the normal agent path for Slack, Telegram, email, and future "
                "communication sends. The agent provides actor/destination/content/context; "
                "StackOS resolves profile, target, provider action, credential, policy, "
                "capabilities, idempotency, and audit."
            ),
            prerequisites=(
                "Pass to as a configured communication target key/ref.",
                "Pass from only when multiple profiles could send; otherwise StackOS resolves it.",
                "Unsupported rich features reject by default with model-readable repair context.",
            ),
            returns=("A compact sent/validated result with message_ref and action_call_id.",),
            examples=(
                OperationExample(
                    title="Send update to roadmap",
                    arguments={
                        "project_id": 1,
                        "from": "ops-bot",
                        "to": "slack-roadmap",
                        "text": "Done. The fix shipped.",
                    },
                ),
            ),
            grant_policy="direct-communication-send",
        ),
        OperationSpec(
            name="communication.reply",
            summary="Reply to the origin of one agent request.",
            input_model=CommunicationReplyInput,
            output_model=WriteEnvelope[CommunicationSendOut],
            handler=communication_reply,
            surfaces=_surfaces("communication.reply", "ops call communication.reply"),
            purpose=(
                "Use this when an inbound Telegram or Slack agent request should receive "
                "a response in its origin surface/thread without manually reconstructing "
                "provider ids or credentials."
            ),
            prerequisites=(
                "Pass request_id for a stored agent request.",
                "StackOS resolves origin provider, surface, thread, actor profile, credential, "
                "provider payload, and idempotency.",
            ),
            returns=("A compact sent/validated result with message_ref and action_call_id.",),
            examples=(
                OperationExample(
                    title="Reply to inbound request",
                    arguments={"project_id": 1, "request_id": 42, "text": "Done."},
                ),
            ),
            grant_policy="direct-communication-send",
        ),
    ]


__all__ = [
    "CommunicationReplyInput",
    "CommunicationSendInput",
    "CommunicationSendOut",
    "communication_reply",
    "communication_send",
    "operation_specs",
]
