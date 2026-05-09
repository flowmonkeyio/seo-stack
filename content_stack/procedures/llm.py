"""LLM dispatcher seam for the procedure runner.

Per locked decision D4 (PLAN.md L884-L900): the daemon holds its own
LLM credentials separate from the user runtime. The procedure runner
dispatches each step as a fresh per-skill LLM session via the
``LLMDispatcher`` protocol below.

For M7.A the **StubDispatcher is the only implementation** — it lets
us prove the runner end-to-end without burning OpenAI / Anthropic
tokens, and gives every test in
``tests/integration/test_procedure_runner/`` a deterministic surface.

Real provider dispatchers (OpenAI Responses API, Anthropic Messages
API) are a follow-up M7 mini-milestone:

- ``OpenAIDispatcher`` — reads the ``openai-procedure-runner`` row
  from ``integration_credentials`` (kind), separate from the
  ``openai-images`` credential per audit M-11. Calls the Responses
  API with the skill body as the system prompt + the run context as
  the user message + the skill's allowed tools as the function
  catalogue. Each function call from the model is dispatched back
  through the daemon's MCP shim with the run_token so the per-skill
  tool-grant matrix enforces.
- ``AnthropicDispatcher`` — same shape against the Anthropic Messages
  API. Uses the ``anthropic-procedure-runner`` integration row.

The dispatcher selection is driven by ``settings.procedure_runner_llm``
(``"stub"`` is the M7.A default; production switches to ``"openai"`` or
``"anthropic"``). The runner reads the setting at construction time
and binds a single dispatcher for the lifetime of the daemon.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class StepDispatch:
    """Per-step dispatch payload handed to the LLM dispatcher.

    Wrap the things every dispatcher implementation needs without
    leaking the runner's internals. The dispatcher returns whatever
    its implementation produced; the runner persists it verbatim into
    ``procedure_run_steps.output_json``.
    """

    skill: str
    """The skill key (e.g. ``02-content/editor``) — looks up the
    SKILL.md body, the per-step tool grants, and the ``allowed_tools``
    catalogue."""

    skill_body: str
    """The SKILL.md prose loaded from disk. Implementations pass this
    as the system prompt to the LLM. The stub dispatcher ignores it
    (it returns scripted outputs)."""

    step_id: str
    """Stable identifier for the procedure_run_steps row."""

    args: dict[str, Any]
    """Step-level args (from ``ProcedureStep.args`` plus runtime
    context like ``article_id`` injected by the runner)."""

    run_id: int
    run_token: str
    project_id: int
    """Run + project correlation. The dispatcher passes these through
    to whatever per-step persistence it does (e.g. ``run.recordStepCall``
    via the MCP shim)."""

    context: dict[str, Any] = field(default_factory=dict)
    """Free-form context (article state snapshot, prior step outputs).
    Dispatchers that build a real LLM prompt fold these into the user
    message; the stub passes them as-is to the script."""


class LLMDispatcher(Protocol):
    """The seam between the runner and the LLM session.

    A ``dispatch`` call must:

    1. Run the skill's prose against the LLM (or, for the stub, run the
       scripted handler).
    2. Return a dict that becomes ``procedure_run_steps.output_json``.

    Errors raise ``LLMDispatcherError`` so the runner's per-step
    failure handling (``on_failure`` modes) can branch on a typed
    signal rather than a bare ``Exception``.
    """

    async def dispatch(self, payload: StepDispatch) -> dict[str, Any]:
        """Run the step; return its output_json shape."""
        ...


class LLMDispatcherError(RuntimeError):
    """Raised when an LLM dispatcher cannot produce a step output.

    The runner catches this and runs the step's ``on_failure`` mode
    (``abort`` / ``retry`` / ``skip`` / ``loop_back`` / ``human_review``).
    """

    def __init__(
        self,
        message: str,
        *,
        skill: str,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.skill = skill
        self.retryable = retryable


# ---------------------------------------------------------------------------
# StubDispatcher — the M7.A primary.
# ---------------------------------------------------------------------------


# A scripted handler function: ``(payload) -> dict`` produces the
# ``output_json`` for a step. Synchronous because most stubs are tiny;
# async stubs can ``await`` inside the body. Returning ``None`` from
# the handler is treated as "no scripted match"; the runner then uses
# the default script for the skill.
ScriptedHandler = Callable[[StepDispatch], dict[str, Any]]


_DEFAULT_OUTPUTS: dict[str, dict[str, Any]] = {
    "01-research/content-brief": {
        "brief_set": True,
        "target_word_count": 1500,
        "primary_angle": "stub-brief",
        "sources_planned": 3,
    },
    "02-content/outline": {
        "outline_md": "# Outline\n\n## Section 1\n## Section 2\n## Section 3",
        "section_count": 3,
    },
    "02-content/draft-intro": {
        "section": "intro",
        "words_added": 280,
        "draft_appended": True,
    },
    "02-content/draft-body": {
        "section": "body",
        "words_added": 900,
        "draft_appended": True,
    },
    "02-content/draft-conclusion": {
        "section": "conclusion",
        "words_added": 220,
        "draft_appended": True,
        "marked_drafted": True,
    },
    "02-content/editor": {
        "edited_md_set": True,
        "edits_applied": 14,
        "voice_consistency_score": 92,
    },
    "02-content/eeat-gate": {
        "verdict": "SHIP",
        "dimension_scores": {
            "C": 88,
            "O": 85,
            "R": 84,
            "E": 79,
            "Exp": 82,
            "Ept": 90,
            "A": 86,
            "T": 91,
        },
        "system_scores": {"GEO": 84, "SEO": 87},
        "vetoes_failed": [],
        "top_issues": [],
        "fix_required": [],
    },
    "03-assets/image-generator": {
        "image_url": "https://stub.example.com/article-hero.png",
        "asset_id": None,
        "generated": True,
    },
    "03-assets/alt-text-auditor": {
        "alt_texts_generated": 1,
        "audited": True,
    },
    "04-publishing/schema-emitter": {
        "schema_set": True,
        "schema_type": "Article",
        "validated": True,
    },
    "04-publishing/interlinker": {
        "suggestions_count": 3,
        "applied_count": 2,
    },
    "04-publishing/nuxt-content-publish": {
        "published_url": "https://stub.example.com/articles/stub-slug",
        "target_kind": "nuxt-content",
        "marked_published": True,
    },
    "04-publishing/wordpress-publish": {
        "published_url": "https://stub.example.com/wordpress/stub-slug",
        "target_kind": "wordpress",
        "marked_published": True,
    },
    "04-publishing/ghost-publish": {
        "published_url": "https://stub.example.com/ghost/stub-slug",
        "target_kind": "ghost",
        "marked_published": True,
    },
}


class StubDispatcher:
    """Deterministic dispatcher for tests + M7.A end-to-end runs.

    Returns scripted outputs per skill name. Tests can supply
    ``handlers`` to override per-skill behaviour (e.g. force the
    eeat-gate to return ``verdict='FIX'`` for the FIX-loop test).

    Handlers can also raise ``LLMDispatcherError`` to simulate a
    transient or permanent LLM failure; the runner branches per the
    step's ``on_failure`` mode in response.
    """

    def __init__(
        self,
        *,
        handlers: dict[str, ScriptedHandler] | None = None,
        default_outputs: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._handlers: dict[str, ScriptedHandler] = dict(handlers or {})
        self._defaults: dict[str, dict[str, Any]] = (
            default_outputs if default_outputs is not None else dict(_DEFAULT_OUTPUTS)
        )
        # Per-skill call counter — handlers can branch on this to
        # simulate "first time fail, second time succeed" patterns
        # used in retry / FIX-loop tests.
        self.calls: dict[str, int] = {}

    def set_handler(self, skill: str, handler: ScriptedHandler) -> None:
        """Register / replace a handler for a skill."""
        self._handlers[skill] = handler

    def set_default_output(self, skill: str, output: dict[str, Any]) -> None:
        """Override the default output for a skill (round-trip safe)."""
        self._defaults[skill] = dict(output)

    async def dispatch(self, payload: StepDispatch) -> dict[str, Any]:
        """Look up + run the scripted handler for ``payload.skill``."""
        self.calls[payload.skill] = self.calls.get(payload.skill, 0) + 1
        handler = self._handlers.get(payload.skill)
        if handler is not None:
            scripted = handler(payload)
            if scripted is not None:
                return scripted
        default = self._defaults.get(payload.skill)
        if default is not None:
            return dict(default)  # copy so mutation by the caller is safe
        # Unknown skill — return a permissive ack so downstream tests
        # exercising "the runner walked the chain" still pass without
        # needing every skill's default. Tests that care about a
        # specific shape supply a default explicitly.
        return {"acked": True, "skill": payload.skill, "step_id": payload.step_id}


# ---------------------------------------------------------------------------
# AnthropicSession — production dispatcher.
# ---------------------------------------------------------------------------


class MissingDaemonLlmCredential(LLMDispatcherError):
    """Raised when the daemon has no ``kind='anthropic'`` row to drive a step.

    Per locked decision D4 the daemon holds its own LLM credentials,
    distinct from any user-runtime credentials. When the operator has not
    yet wired an ``integration_credentials`` row with ``kind='anthropic'``
    (project-scoped or global), the runner can't dispatch the step.

    The dispatcher raises this typed error so the runner can map it onto
    JSON-RPC code -32010 (IntegrationDown) at the MCP boundary instead of
    bubbling a generic 500 with no actionable hint.
    """

    def __init__(self, *, kind: str = "anthropic") -> None:
        super().__init__(
            f"daemon has no integration_credentials row with kind={kind!r}",
            skill="<setup>",
            retryable=False,
        )
        self.kind = kind


class AnthropicSession:
    """Production dispatcher driving real Anthropic Messages API turns.

    Per locked decision D4 (PLAN.md L884-L900): the daemon holds its own
    LLM credentials in ``integration_credentials`` with ``kind='anthropic'``
    (separate from any user runtime). This dispatcher reads that row,
    calls the Messages API with the skill body as the system prompt and
    the runner-supplied step context as the user message, and loops on
    tool-use blocks until the model returns ``stop_reason='end_turn'`` or
    we hit ``max_iterations``.

    **Model choice.** The daemon defaults to ``claude-sonnet-4-6`` — the
    runtime knowledge cutoff (Jan 2026) names this as the production
    Sonnet checkpoint. Operators can override via ``model=...`` at
    dispatcher construction without code changes (settings reload + edit
    of the daemon's LLM config row).

    **Tool execution.** The dispatcher receives a ``tool_executor``
    callable from the runner that maps tool-name → coroutine. Each
    ``tool_use`` block from the model is dispatched through that
    callable (which the runner wires to the MCP shim with a run_token
    bound, so the per-skill tool-grant matrix double-enforces). The
    returned ``tool_result`` is appended to the next turn's messages.

    For M7.A this class is **not exercised by tests** — every test uses
    the ``StubDispatcher`` to keep CI deterministic and free. Production
    deployments wire ``AnthropicSession`` via the
    ``settings.procedure_runner_llm='anthropic'`` flag (the runner reads
    the setting at construction time).
    """

    def __init__(
        self,
        *,
        engine: Any,
        tool_executor: Callable[[str, dict[str, Any]], Any],
        model: str = "claude-sonnet-4-6",
        max_iterations: int = 30,
    ) -> None:
        self._engine = engine
        self._tool_executor = tool_executor
        self._model = model
        self._max_iterations = max_iterations
        # Lazy-init the SDK client so importing this module doesn't fail
        # on a daemon install that lacks the ``anthropic`` package (the
        # M7.A install only requires it when the operator switches the
        # ``procedure_runner_llm`` setting).
        self._client: Any = None

    def _ensure_client(self, api_key: str) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=api_key)
        return self._client

    def _resolve_credential(self) -> str:
        """Pull the daemon's ``kind='anthropic'`` credential.

        Falls back from project-scoped to global per
        ``IntegrationCredentialRepository.get_decrypted_for`` semantics.
        Procedure runs always use the global row because the runner is
        a daemon-side actor, not a per-project actor; project-scoped
        Anthropic creds are reserved for future per-project hooks.
        """
        from sqlmodel import Session

        from content_stack.repositories.base import NotFoundError as _NotFoundError
        from content_stack.repositories.projects import (
            IntegrationCredentialRepository,
        )

        with Session(self._engine) as s:
            repo = IntegrationCredentialRepository(s)
            try:
                _, payload = repo.get_decrypted_for(project_id=None, kind="anthropic")
            except _NotFoundError as exc:
                raise MissingDaemonLlmCredential() from exc
        text = payload.decode("utf-8")
        # Stored shape is `{"api_key": "..."}` (JSON) per the integration
        # convention; tolerate a bare-string fallback for legacy installs.
        try:
            import json

            data = json.loads(text)
            if isinstance(data, dict) and "api_key" in data:
                return str(data["api_key"])
        except json.JSONDecodeError:
            pass
        return text

    async def dispatch(self, payload: StepDispatch) -> dict[str, Any]:
        """Drive a real Messages API turn loop for the step."""
        api_key = self._resolve_credential()
        client = self._ensure_client(api_key)

        # Build the catalog of tools the skill is allowed to call.
        allowed_tools = sorted(payload.context.get("allowed_tools", []) or [])
        tool_specs = [
            {
                "name": tool_name,
                "description": f"MCP tool {tool_name}",
                # We don't have a per-tool input schema readily available here;
                # the dispatcher accepts a permissive object schema, and the
                # tool handler validates downstream via its pydantic Input.
                "input_schema": {"type": "object", "additionalProperties": True},
            }
            for tool_name in allowed_tools
        ]

        system_prompt = payload.skill_body or f"Run skill {payload.skill}."
        user_prompt = (
            f"Procedure step `{payload.step_id}` (skill `{payload.skill}`).\n"
            f"Inputs: {payload.args}\n"
            f"Run context: {payload.context}\n\n"
            "Use the tools provided to read/write state. Stop when the step "
            "is complete and emit a one-sentence summary of what changed."
        )

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
        tool_calls: list[dict[str, Any]] = []
        final_text: str | None = None
        iterations = 0

        while iterations < self._max_iterations:
            iterations += 1
            response = await client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=tool_specs or None,
            )
            assistant_blocks: list[dict[str, Any]] = []
            tool_uses: list[dict[str, Any]] = []
            for block in response.content:
                btype = getattr(block, "type", None)
                if btype == "text":
                    final_text = getattr(block, "text", None)
                    assistant_blocks.append({"type": "text", "text": final_text or ""})
                elif btype == "tool_use":
                    tool_uses.append(
                        {
                            "id": block.id,
                            "name": block.name,
                            "input": dict(block.input or {}),
                        }
                    )
                    assistant_blocks.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": dict(block.input or {}),
                        }
                    )
            messages.append({"role": "assistant", "content": assistant_blocks})

            if response.stop_reason == "end_turn" and not tool_uses:
                break

            if not tool_uses:
                # No tool use + stop_reason != end_turn → bail to avoid an
                # infinite loop on a malformed response.
                break

            tool_result_blocks: list[dict[str, Any]] = []
            for tu in tool_uses:
                try:
                    tool_output = await self._tool_executor(tu["name"], tu["input"])
                    tool_calls.append(
                        {"name": tu["name"], "input": tu["input"], "output": tool_output}
                    )
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": [{"type": "text", "text": str(tool_output)}],
                        }
                    )
                except Exception as exc:
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": [{"type": "text", "text": f"error: {exc}"}],
                            "is_error": True,
                        }
                    )
                    raise LLMDispatcherError(
                        f"tool {tu['name']!r} failed: {exc}",
                        skill=payload.skill,
                        retryable=False,
                    ) from exc
            messages.append({"role": "user", "content": tool_result_blocks})

        usage = (
            {
                "input_tokens": getattr(response.usage, "input_tokens", 0),
                "output_tokens": getattr(response.usage, "output_tokens", 0),
            }
            if response is not None
            else {}
        )
        return {
            "final_text": final_text,
            "tool_calls": tool_calls,
            "iterations": iterations,
            "usage": usage,
            "skill": payload.skill,
            "step_id": payload.step_id,
        }


__all__ = [
    "AnthropicSession",
    "LLMDispatcher",
    "LLMDispatcherError",
    "MissingDaemonLlmCredential",
    "ScriptedHandler",
    "StepDispatch",
    "StubDispatcher",
]
