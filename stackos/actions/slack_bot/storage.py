"""Slack conversation, message, membership, and button storage."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from stackos.actions.connectors import ActionConnectorRequest
from stackos.repositories.agent_requests import AgentRequestRepository
from stackos.repositories.resources import ResourceRepository

from .constants import _RECOMMENDED_TEXT_CHARS
from .profile import _communication_profile_key, _credential_profile_key
from .refs import (
    _button_specs,
    _channel_display_name,
    _channel_from_body,
    _channel_id,
    _channel_id_from_obj,
    _channel_kind,
    _message_ref,
    _nested,
    _outbound_button_external_id,
    _surface_ref,
    _team_id,
    _thread_ref,
)


def _store_outbound_message(
    request: ActionConnectorRequest,
    provider_body: Any,
    sent_payload: Mapping[str, Any],
) -> None:
    if request.session is None or not isinstance(provider_body, Mapping):
        return
    channel = str(provider_body.get("channel") or sent_payload.get("channel") or "")
    ts = str(provider_body.get("ts") or _nested(provider_body, "message.ts") or "")
    if not channel or not ts:
        return
    profile_key = _communication_profile_key(request)
    auth_profile_key = _credential_profile_key(request)
    team_id = _team_id(request, provider_body)
    text = str(sent_payload.get("text") or _nested(provider_body, "message.text") or "")
    thread_ts = str(sent_payload.get("thread_ts") or ts)
    resources = ResourceRepository(request.session)
    _upsert_channel(
        resources,
        request.project_id,
        profile_key=profile_key,
        auth_profile_key=auth_profile_key,
        team_id=team_id,
        channel_obj={"id": channel, "name": channel},
        source="slack-bot-action",
    )
    message_ref = _message_ref(channel, ts)
    resources.upsert_record(
        project_id=request.project_id,
        plugin_slug="communications",
        resource_key="communication-message",
        external_id=f"slack-message:{profile_key}:{channel}:{ts}",
        title="Slack outbound message",
        data_json={
            "provider_key": "slack-bot",
            "profile_key": profile_key,
            "auth_profile_key": auth_profile_key,
            "team_id": team_id,
            "direction": "outbound",
            "surface_ref": _surface_ref(channel),
            "channel_ref": _surface_ref(channel),
            "thread_ref": _thread_ref(channel, thread_ts),
            "message_ref": message_ref,
            "provider_message_ts": ts,
            "content_type": "blocks" if isinstance(sent_payload.get("blocks"), list) else "text",
            "text_preview": text[:_RECOMMENDED_TEXT_CHARS],
            "transport_status": "accepted",
            "attention_status": "sent",
            "source_agent_request_id": request.input_json.get("source_agent_request_id"),
            "action_ref": request.action_ref,
        },
        provenance_json={"source": "slack-bot-action"},
    )
    _store_outbound_buttons(request, resources, message_ref=message_ref, channel=channel)


def _store_outbound_buttons(
    request: ActionConnectorRequest,
    resources: ResourceRepository,
    *,
    message_ref: str,
    channel: str,
) -> None:
    blocks = request.input_json.get("blocks")
    if not isinstance(blocks, list):
        return
    control_metadata = (
        request.input_json.get("control_metadata")
        if isinstance(request.input_json.get("control_metadata"), Mapping)
        else {}
    )
    profile_key = _communication_profile_key(request)
    auth_profile_key = _credential_profile_key(request)
    source_scope = _source_button_scope(request, fallback_channel_ref=_surface_ref(channel))
    for button in _button_specs(blocks):
        action_id = str(button.get("action_id") or "")
        value = str(button.get("value") or "")
        metadata = _button_metadata(control_metadata, action_id=action_id, value=value)
        interaction_external_id = _outbound_button_external_id(
            profile_key=profile_key,
            message_ref=message_ref,
            action_id=action_id,
            value=value,
            block_id=str(button.get("block_id") or ""),
        )
        resources.upsert_record(
            project_id=request.project_id,
            plugin_slug="communications",
            resource_key="communication-interaction",
            external_id=interaction_external_id,
            title=str(button.get("text") or action_id or "Slack button"),
            data_json={
                "provider_key": "slack-bot",
                "profile_key": profile_key,
                "auth_profile_key": auth_profile_key,
                "interaction_type": "outbound_block_button",
                "surface_ref": _surface_ref(channel),
                "channel_ref": _surface_ref(channel),
                "message_ref": message_ref,
                "block_id": button.get("block_id"),
                "action_id": action_id,
                "button_value": value or None,
                "control_action": metadata.get("action"),
                "control_payload": metadata.get("payload"),
                "control_metadata": metadata or None,
                "url_button": bool(button.get("url")),
                "status": "active",
                "source_agent_request_id": request.input_json.get("source_agent_request_id"),
                "allowed_user_refs": source_scope.get("allowed_user_refs", []),
                "allowed_channel_refs": source_scope.get("allowed_channel_refs", []),
            },
            provenance_json={"source": "slack-bot-action"},
        )


def _button_metadata(
    control_metadata: Any,
    *,
    action_id: str,
    value: str,
) -> dict[str, Any]:
    if not isinstance(control_metadata, Mapping):
        return {}
    for key in (value, action_id):
        item = control_metadata.get(key)
        if isinstance(item, Mapping):
            return dict(item)
    return {}


def _source_button_scope(
    request: ActionConnectorRequest,
    *,
    fallback_channel_ref: str,
) -> dict[str, list[str]]:
    scope: dict[str, list[str]] = {"allowed_channel_refs": [fallback_channel_ref]}
    if request.session is None:
        return scope
    request_id = request.input_json.get("source_agent_request_id")
    if not isinstance(request_id, int) or isinstance(request_id, bool):
        return scope
    source = AgentRequestRepository(request.session).get(
        project_id=request.project_id,
        request_id=request_id,
    )
    metadata = source.metadata_json or {}
    invoker_ref = metadata.get("invoker_ref")
    if isinstance(invoker_ref, str) and invoker_ref:
        scope["allowed_user_refs"] = [invoker_ref]
    surface_ref = metadata.get("surface_ref") or metadata.get("channel_ref")
    if isinstance(surface_ref, str) and surface_ref:
        scope["allowed_channel_refs"] = [surface_ref]
    return scope


def _store_conversation_from_body(request: ActionConnectorRequest, provider_body: Any) -> None:
    if request.session is None:
        return
    channel = _channel_from_body(provider_body)
    if not channel:
        return
    _upsert_channel(
        ResourceRepository(request.session),
        request.project_id,
        profile_key=_communication_profile_key(request),
        auth_profile_key=_credential_profile_key(request),
        team_id=_team_id(request, provider_body),
        channel_obj=channel,
        source="slack-bot-action",
    )


def _store_conversation_list(request: ActionConnectorRequest, provider_body: Any) -> None:
    if request.session is None or not isinstance(provider_body, Mapping):
        return
    channels = provider_body.get("channels")
    if not isinstance(channels, list):
        return
    resources = ResourceRepository(request.session)
    profile_key = _communication_profile_key(request)
    auth_profile_key = _credential_profile_key(request)
    for channel in channels:
        if isinstance(channel, Mapping):
            _upsert_channel(
                resources,
                request.project_id,
                profile_key=profile_key,
                auth_profile_key=auth_profile_key,
                team_id=_team_id(request, provider_body),
                channel_obj=channel,
                source="slack-bot-action",
            )


def _store_memberships_from_body(request: ActionConnectorRequest, provider_body: Any) -> None:
    if request.session is None or not isinstance(provider_body, Mapping):
        return
    members = provider_body.get("members")
    if not isinstance(members, list):
        return
    channel_ref = request.input_json.get("channel_ref") or request.input_json.get("surface_ref")
    channel = _channel_id(request, channel_ref)
    resources = ResourceRepository(request.session)
    profile_key = _communication_profile_key(request)
    auth_profile_key = _credential_profile_key(request)
    for member in members:
        if not isinstance(member, str) or not member:
            continue
        resources.upsert_record(
            project_id=request.project_id,
            plugin_slug="communications",
            resource_key="communication-membership",
            external_id=f"slack-membership:{profile_key}:{channel}:{member}",
            title=f"{member} in {channel}",
            data_json={
                "provider_key": "slack-bot",
                "profile_key": profile_key,
                "auth_profile_key": auth_profile_key,
                "surface_ref": _surface_ref(channel),
                "member_ref": f"slack-user:{member}",
                "membership_kind": "user",
                "status": "joined",
                "roles": [],
                "permissions": {},
                "scope_status": {},
            },
            provenance_json={"source": "slack-bot-action"},
        )


def _upsert_channel(
    resources: ResourceRepository,
    project_id: int,
    *,
    profile_key: str,
    auth_profile_key: str,
    team_id: str | None,
    channel_obj: Mapping[str, Any],
    source: str,
) -> None:
    channel_id = _channel_id_from_obj(channel_obj)
    if not channel_id:
        return
    display = _channel_display_name(channel_obj)
    resources.upsert_record(
        project_id=project_id,
        plugin_slug="communications",
        resource_key="communication-channel",
        external_id=f"slack-channel:{profile_key}:{channel_id}",
        title=display,
        data_json={
            "provider_key": "slack-bot",
            "profile_key": profile_key,
            "auth_profile_key": auth_profile_key,
            "team_id": team_id,
            "surface_ref": _surface_ref(channel_id),
            "channel_ref": _surface_ref(channel_id),
            "provider_channel_id": channel_id,
            "kind": _channel_kind(channel_obj),
            "display_name": display,
            "safe_external_ref": f"slack-team:{team_id}:channel:{channel_id}"
            if team_id
            else f"slack-channel:{channel_id}",
            "send_enabled": True,
            "ingest_enabled": True,
            "capabilities": {
                "can_read": True,
                "can_write": bool(channel_obj.get("is_member", True)),
                "can_thread": True,
            },
            "metadata_json": {
                "is_private": channel_obj.get("is_private"),
                "is_archived": channel_obj.get("is_archived"),
                "is_member": channel_obj.get("is_member"),
                "user": channel_obj.get("user"),
            },
        },
        provenance_json={"source": source},
    )
