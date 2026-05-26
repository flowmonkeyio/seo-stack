"""Telegram safe provider reference helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from stackos.repositories.base import ValidationError


def _provider_chat_ref(result_body: Any) -> str | None:
    chat_id = _provider_chat_id(result_body)
    if chat_id is None:
        return None
    return f"telegram-chat:{chat_id}"


def _provider_message_ref(result_body: Any) -> str | None:
    chat_id = _provider_chat_id(result_body)
    message_id = result_body.get("message_id") if isinstance(result_body, Mapping) else None
    if chat_id is None or message_id is None:
        return None
    return f"telegram-message:{chat_id}:{message_id}"


def _provider_chat_id(result_body: Any) -> Any:
    if not isinstance(result_body, Mapping):
        return None
    chat = result_body.get("chat")
    return chat.get("id") if isinstance(chat, Mapping) else None


def _message_ref_parts(value: Any) -> tuple[int, int]:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Telegram message_ref is required")
    text = value.strip()
    if text.startswith("telegram-message:"):
        parts = text.split(":")
        if len(parts) == 3:
            chat_id = _int_text(parts[1])
            message_id = _int_text(parts[2])
            if chat_id is not None and message_id is not None:
                return chat_id, message_id
    raise ValidationError("Telegram message_ref must be telegram-message:<chat_id>:<message_id>")


def _resolve_message_ref(profile: Mapping[str, Any], value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    for map_key in ("message_refs", "refs"):
        mapping = profile.get(map_key)
        if isinstance(mapping, Mapping) and value in mapping:
            return mapping[value]
    return value


def _int_text(value: str) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None
