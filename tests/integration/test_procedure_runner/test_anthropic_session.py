"""``AnthropicSession`` smoke + credential-resolution coverage.

The production dispatcher is **not exercised against real Anthropic
endpoints** in CI (no real credentials, no real cost). This test file
only verifies:

1. The class is importable + constructs cleanly.
2. ``MissingDaemonLlmCredential`` fires when no daemon-side anthropic
   credential exists.
3. The resolver consumes the JSON-shaped credential payload
   (``{"api_key": "..."}``).

Production end-to-end coverage lands in M7 follow-up alongside the
``settings.procedure_runner_llm='anthropic'`` switch.
"""

from __future__ import annotations

from sqlmodel import Session

from content_stack.procedures.llm import (
    AnthropicSession,
    MissingDaemonLlmCredential,
)
from content_stack.repositories.projects import IntegrationCredentialRepository


async def test_anthropic_session_constructs() -> None:
    """The class imports + builds without touching the network."""

    async def _noop_executor(_name: str, _args: dict) -> dict:
        return {}

    sess = AnthropicSession(engine=None, tool_executor=_noop_executor)
    assert sess._model == "claude-sonnet-4-6"


async def test_missing_anthropic_credential_raises_typed_error(engine: object) -> None:
    """Without a daemon-side anthropic row, ``_resolve_credential`` raises."""

    async def _noop_executor(_name: str, _args: dict) -> dict:
        return {}

    sess = AnthropicSession(engine=engine, tool_executor=_noop_executor)
    import pytest

    with pytest.raises(MissingDaemonLlmCredential):
        sess._resolve_credential()


async def test_resolves_json_credential_payload(engine: object) -> None:
    """A ``{"api_key": "..."}`` payload round-trips through the resolver."""
    with Session(engine) as s:
        repo = IntegrationCredentialRepository(s)
        # Set a global (project_id=None) anthropic credential.
        repo.set(
            project_id=None,
            kind="anthropic",
            plaintext_payload=b'{"api_key": "sk-ant-test-stub"}',
        )

    async def _noop_executor(_name: str, _args: dict) -> dict:
        return {}

    sess = AnthropicSession(engine=engine, tool_executor=_noop_executor)
    api_key = sess._resolve_credential()
    assert api_key == "sk-ant-test-stub"
