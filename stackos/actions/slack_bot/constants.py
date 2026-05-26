"""Slack Web API connector constants."""

from __future__ import annotations

import re

_BASE_URL = "https://slack.com/api"
_MAX_TEXT_CHARS = 40_000
_RECOMMENDED_TEXT_CHARS = 4_000
_MAX_BLOCKS = 50
_MAX_ACTION_BLOCK_ELEMENTS = 25
_MAX_BUTTON_TEXT_CHARS = 75
_MAX_BUTTON_VALUE_CHARS = 2_000
_MAX_BUTTON_ACTION_ID_CHARS = 255
_MAX_BUTTON_URL_CHARS = 3_000
_MAX_CONVERSATION_LIMIT = 1_000
_MAX_OPEN_USERS = 8
_CONVERSATION_TYPES = {"public_channel", "private_channel", "mpim", "im"}
_SECRETISH_BUTTON_RE = re.compile(
    r"(?i)(bearer\s+|xox[baprs]-|sk-[a-z0-9]|api[_-]?key|client[_-]?secret|"
    r"refresh[_-]?token|access[_-]?token|password|secret)"
)
_SLACK_TOKEN_RE = re.compile(r"(?i)xox[baprs]-[A-Za-z0-9-]+")
