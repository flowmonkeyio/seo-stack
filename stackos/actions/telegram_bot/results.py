"""Telegram action result shaping."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from stackos.actions.connectors import ActionConnectorRequest, ActionConnectorResult
from stackos.actions.provider_utils import result

from .refs import _provider_chat_ref, _provider_message_ref


def _telegram_result(
    request: ActionConnectorRequest,
    *,
    status_code: int,
    body: Any,
    headers: Mapping[str, str] | None,
    telegram_method: str,
    metadata: dict[str, Any] | None = None,
) -> ActionConnectorResult:
    base = result(
        provider="telegram-bot",
        operation=request.operation,
        status_code=status_code,
        body=body,
        headers=headers,
        metadata={
            "telegram_method": telegram_method,
            **(metadata or {}),
        },
    )
    result_body = body.get("result") if isinstance(body, Mapping) else None
    message_ref = _provider_message_ref(result_body)
    chat_ref = _provider_chat_ref(result_body)
    if message_ref is None and chat_ref is None:
        return base

    output = dict(base.output_json)
    output["status"] = "sent"
    if chat_ref is not None:
        output["chat_ref"] = chat_ref
        output["channel_ref"] = chat_ref
    if message_ref is not None:
        output["message_ref"] = message_ref
    thread_ref = request.input_json.get("thread_ref")
    if isinstance(thread_ref, str) and thread_ref:
        output["thread_ref"] = thread_ref
    if isinstance(result_body, Mapping) and result_body.get("message_id") is not None:
        output["provider_message_id"] = str(result_body["message_id"])
    return ActionConnectorResult(
        output_json=output,
        metadata_json=base.metadata_json,
        cost_cents=base.cost_cents,
    )


def _telegram_reaction_result(
    request: ActionConnectorRequest,
    *,
    status_code: int,
    body: Any,
    headers: Mapping[str, str] | None,
) -> ActionConnectorResult:
    base = result(
        provider="telegram-bot",
        operation=request.operation,
        status_code=status_code,
        body=body,
        headers=headers,
        metadata={"telegram_method": "setMessageReaction"},
    )
    output = dict(base.output_json)
    output.update(
        {
            "status": "reacted",
            "message_ref": request.input_json.get("message_ref"),
            "reaction_emoji": request.input_json.get("emoji"),
        }
    )
    return ActionConnectorResult(
        output_json=output,
        metadata_json=base.metadata_json,
        cost_cents=base.cost_cents,
    )


def _telegram_delete_result(
    request: ActionConnectorRequest,
    *,
    status_code: int,
    body: Any,
    headers: Mapping[str, str] | None,
) -> ActionConnectorResult:
    base = result(
        provider="telegram-bot",
        operation=request.operation,
        status_code=status_code,
        body=body,
        headers=headers,
        metadata={"telegram_method": "deleteMessage"},
    )
    output = dict(base.output_json)
    output.update(
        {
            "status": "deleted",
            "message_ref": request.input_json.get("message_ref"),
        }
    )
    return ActionConnectorResult(
        output_json=output,
        metadata_json=base.metadata_json,
        cost_cents=base.cost_cents,
    )
