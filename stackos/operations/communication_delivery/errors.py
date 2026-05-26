"""Structured communication delivery rejection helpers."""

from __future__ import annotations

from typing import Any

from stackos.repositories.base import ValidationError

from .constants import _COMMUNICATION_ERROR_DETAIL


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
