"""Slack action result shaping."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from stackos.actions.connectors import ActionConnectorRequest, ActionConnectorResult

from .refs import (
    _channel_from_body,
    _channel_id_from_obj,
    _message_ref,
    _nested,
    _next_cursor,
    _safe_channel,
    _surface_ref,
    _thread_ref,
)


def _identity_result(
    request: ActionConnectorRequest,
    status: int,
    body: Any,
    headers: httpx.Headers,
) -> ActionConnectorResult:
    data = body if isinstance(body, Mapping) else {}
    return ActionConnectorResult(
        output_json={
            "provider": "slack-bot",
            "operation": request.operation,
            "status": "ok",
            "team_id": data.get("team_id"),
            "team": data.get("team"),
            "user_id": data.get("user_id"),
            "user": data.get("user"),
            "bot_id": data.get("bot_id"),
            "url": data.get("url"),
        },
        metadata_json=_metadata("auth.test", request.operation, status, body, headers),
    )


def _message_result(
    request: ActionConnectorRequest,
    status: int,
    body: Any,
    headers: httpx.Headers,
    sent_payload: Mapping[str, Any],
) -> ActionConnectorResult:
    data = body if isinstance(body, Mapping) else {}
    channel = str(data.get("channel") or sent_payload.get("channel") or "")
    ts = str(data.get("ts") or _nested(data, "message.ts") or "")
    thread_ts = str(sent_payload.get("thread_ts") or ts) if ts else None
    return ActionConnectorResult(
        output_json={
            "provider": "slack-bot",
            "operation": request.operation,
            "status": "sent",
            "channel_ref": _surface_ref(channel) if channel else None,
            "thread_ref": _thread_ref(channel, thread_ts) if channel and thread_ts else None,
            "message_ref": _message_ref(channel, ts) if channel and ts else None,
            "provider_message_ts": ts or None,
        },
        metadata_json=_metadata("chat.postMessage", request.operation, status, body, headers),
    )


def _conversation_open_result(
    request: ActionConnectorRequest,
    status: int,
    body: Any,
    headers: httpx.Headers,
) -> ActionConnectorResult:
    channel = _channel_from_body(body)
    channel_id = _channel_id_from_obj(channel)
    return ActionConnectorResult(
        output_json={
            "provider": "slack-bot",
            "operation": request.operation,
            "status": "ok",
            "channel_ref": _surface_ref(channel_id) if channel_id else None,
            "channel": _safe_channel(channel),
        },
        metadata_json=_metadata("conversations.open", request.operation, status, body, headers),
    )


def _conversation_info_result(
    request: ActionConnectorRequest,
    status: int,
    body: Any,
    headers: httpx.Headers,
) -> ActionConnectorResult:
    channel = _channel_from_body(body)
    return ActionConnectorResult(
        output_json={
            "provider": "slack-bot",
            "operation": request.operation,
            "status": "ok",
            "channel": _safe_channel(channel),
        },
        metadata_json=_metadata("conversations.info", request.operation, status, body, headers),
    )


def _conversation_list_result(
    request: ActionConnectorRequest,
    status: int,
    body: Any,
    headers: httpx.Headers,
) -> ActionConnectorResult:
    data = body if isinstance(body, Mapping) else {}
    raw_channels = data.get("channels")
    channels: list[Any] = raw_channels if isinstance(raw_channels, list) else []
    return ActionConnectorResult(
        output_json={
            "provider": "slack-bot",
            "operation": request.operation,
            "status": "ok",
            "channel_refs": [
                _surface_ref(str(item.get("id")))
                for item in channels
                if isinstance(item, Mapping) and item.get("id")
            ],
            "count": len(channels),
            "next_cursor": _next_cursor(body),
        },
        metadata_json=_metadata("conversations.list", request.operation, status, body, headers),
    )


def _conversation_members_result(
    request: ActionConnectorRequest,
    status: int,
    body: Any,
    headers: httpx.Headers,
) -> ActionConnectorResult:
    data = body if isinstance(body, Mapping) else {}
    raw_members = data.get("members")
    members: list[Any] = raw_members if isinstance(raw_members, list) else []
    return ActionConnectorResult(
        output_json={
            "provider": "slack-bot",
            "operation": request.operation,
            "status": "ok",
            "member_refs": [f"slack-user:{member}" for member in members],
            "count": len(members),
            "next_cursor": _next_cursor(body),
        },
        metadata_json=_metadata("conversations.members", request.operation, status, body, headers),
    )


def _metadata(
    slack_method: str,
    operation: str,
    status: int,
    body: Any,
    headers: httpx.Headers,
) -> dict[str, Any]:
    data = body if isinstance(body, Mapping) else {}
    meta = {
        "vendor": "slack-bot",
        "operation": operation,
        "slack_method": slack_method,
        "status_code": status,
    }
    retry_after = headers.get("retry-after")
    if retry_after:
        meta["retry_after"] = retry_after
    next_cursor = _next_cursor(data)
    if next_cursor:
        meta["next_cursor"] = next_cursor
    if data.get("warning"):
        meta["warning"] = data.get("warning")
    if isinstance(data.get("response_metadata"), Mapping) and data["response_metadata"].get(
        "warnings"
    ):
        meta["warnings"] = data["response_metadata"].get("warnings")
    return meta
