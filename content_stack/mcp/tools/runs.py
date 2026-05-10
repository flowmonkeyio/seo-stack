"""``run.*`` and ``procedure.*`` tools.

Exposes the audit-trail layer (``RunRepository`` + ``RunStepRepository``
+ ``RunStepCallRepository`` + ``ProcedureRunStepRepository``) plus the
procedure-orchestration seam.

The primary procedure surface is agent-led. ``procedure.run`` opens the
durable run + step skeleton, then the current MCP client calls
``procedure.claimStep`` / executes the step itself / ``procedure.recordStep``.
The daemon does not spawn hidden writer sessions for MCP callers.

M8: ``run.resume`` / ``run.fork`` now route through the runner the same
way the ``procedure.*`` variants do. The two pairs are subtly different:

- ``procedure.resume`` / ``procedure.fork`` use the procedure-step
  index (an integer step position).
- ``run.resume`` / ``run.fork`` use a **named step id** because the
  RunRepository view is per-skill (``run_steps``) rather than
  per-procedure-step (``procedure_run_steps``). For consistency with
  M8 behaviour we map ``run.fork(from_step=<step_id>)`` to the
  procedure-step index, then use the same fork path as
  ``procedure.fork``. ``run.resume`` resolves to the procedure-resume
  path.
"""

from __future__ import annotations

import secrets
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from content_stack.db.models import ProcedureRunStepStatus, RunKind, RunStatus
from content_stack.mcp.context import MCPContext
from content_stack.mcp.contract import MCPInput, MCPOutput, WriteEnvelope
from content_stack.mcp.permissions import INVALID_SKILL, SYSTEM_SKILL, TEST_SKILL
from content_stack.mcp.server import ToolRegistry, ToolSpec
from content_stack.mcp.streaming import ProgressEmitter
from content_stack.procedures.runner import ProcedureRunner
from content_stack.repositories.base import (
    NotFoundError,
    Page,
    ValidationError,
)
from content_stack.repositories.runs import (
    ProcedureRunStepOut,
    ProcedureRunStepRepository,
    RunOut,
    RunRepository,
    RunStepCallOut,
    RunStepCallRepository,
    RunStepOut,
    RunStepRepository,
)

# ---------------------------------------------------------------------------
# run.* inputs.
# ---------------------------------------------------------------------------


class RunStartInput(MCPInput):
    """Insert a fresh run + return ``(run_id, run_token)``.

    The ``run_token`` is the run's ``client_session_id`` — every
    subsequent tool call within this run echoes the token so the server
    correlates calls to the run for audit + tool-grant enforcement
    (audit B-10).
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "project_id": 1,
                "kind": "procedure",
                "procedure_slug": "topic-to-published",
            }
        },
    )

    project_id: int | None = None
    kind: RunKind
    parent_run_id: int | None = None
    procedure_slug: str | None = None
    skill_name: str | None = None
    metadata_json: dict[str, Any] | None = None


class RunStartOutput(BaseModel):
    """Wire shape for ``run.start`` — exposes ``run_token`` so the caller
    can echo it on subsequent calls."""

    run: RunOut
    run_token: str
    run_id: int


class RunFinishInput(MCPInput):
    """Move a run to a terminal status."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"run_id": 1, "status": "success"}}
    )

    run_id: int
    status: RunStatus
    error: str | None = None
    metadata_json: dict[str, Any] | None = None


class RunHeartbeatInput(MCPInput):
    """Update heartbeat_at to now."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"run_id": 1}})

    run_id: int


class RunAbortInput(MCPInput):
    """Abort a run, optionally cascading to children."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"run_id": 1, "cascade": True}}
    )

    run_id: int
    cascade: bool = False


class RunListInput(MCPInput):
    """List runs with filters."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int | None = None
    kind: RunKind | None = None
    status: RunStatus | None = None
    parent_run_id: int | None = None
    limit: int | None = None
    after_id: int | None = None


class RunGetInput(MCPInput):
    """Fetch one run by id."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"run_id": 1}})

    run_id: int


class RunChildrenInput(MCPInput):
    """List direct children of a parent run."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"parent_run_id": 1}})

    parent_run_id: int


class RunCostInput(MCPInput):
    """Sum cost_cents per run kind for a project + month."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"project_id": 1, "month": "2026-05"}}
    )

    project_id: int
    month: str | None = None


class RunResumeInput(MCPInput):
    """Resume a paused procedure run via the runner (M8)."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"run_id": 1}})

    run_id: int


class RunForkInput(MCPInput):
    """Fork a procedure run from a named step (M8).

    ``from_step`` names a procedure step id (matches
    ``procedure_run_steps.step_id``). The runner resolves it to the step
    index and opens a fork — same path as ``procedure.fork`` but
    keyed by step id rather than index for the per-skill
    audit-trail surface.
    """

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"run_id": 1, "from_step": "editor"}}
    )

    run_id: int
    from_step: str


# ---------------------------------------------------------------------------
# run.* handlers.
# ---------------------------------------------------------------------------


def _generate_run_token() -> str:
    """Return a 32-byte URL-safe token used as ``runs.client_session_id``."""
    return secrets.token_urlsafe(32)


async def _run_start(
    inp: RunStartInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[RunStartOutput]:
    """Open a new run row + return a fresh ``run_token``.

    The run's ``client_session_id`` IS the token — we mint a
    cryptographically-random URL-safe value here so every run has a
    distinct correlation handle. The ``metadata_json`` carries the
    skill name when caller specifies one, so ``permissions.resolve_run_token``
    can resolve the token back to a skill on subsequent calls.
    """
    token = _generate_run_token()
    metadata = dict(inp.metadata_json or {})
    if inp.skill_name is not None:
        if inp.skill_name in {SYSTEM_SKILL, TEST_SKILL, INVALID_SKILL}:
            raise ValidationError(
                "reserved skill_name cannot be bound to a run",
                data={"skill_name": inp.skill_name},
            )
        metadata["skill_name"] = inp.skill_name
    env = RunRepository(ctx.session).start(
        project_id=inp.project_id,
        kind=inp.kind,
        parent_run_id=inp.parent_run_id,
        procedure_slug=inp.procedure_slug,
        client_session_id=token,
        metadata_json=metadata if metadata else None,
    )
    assert env.data.id is not None
    payload = RunStartOutput(run=env.data, run_token=token, run_id=env.data.id)
    return WriteEnvelope[RunStartOutput](
        data=payload, run_id=env.data.id, project_id=env.project_id
    )


async def _run_finish(
    inp: RunFinishInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[RunOut]:
    env = RunRepository(ctx.session).finish(
        inp.run_id, status=inp.status, error=inp.error, metadata_json=inp.metadata_json
    )
    return WriteEnvelope[RunOut](data=env.data, run_id=env.run_id, project_id=env.project_id)


async def _run_heartbeat(
    inp: RunHeartbeatInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[RunOut | None]:
    env = RunRepository(ctx.session).heartbeat(inp.run_id)
    return WriteEnvelope[RunOut | None](data=env.data, run_id=env.run_id, project_id=env.project_id)


async def _run_abort(
    inp: RunAbortInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[RunOut]:
    env = RunRepository(ctx.session).abort(inp.run_id, cascade=inp.cascade)
    return WriteEnvelope[RunOut](data=env.data, run_id=env.run_id, project_id=env.project_id)


async def _run_list(inp: RunListInput, ctx: MCPContext, _emit: ProgressEmitter) -> Page[RunOut]:
    return RunRepository(ctx.session).list(
        project_id=inp.project_id,
        kind=inp.kind,
        status=inp.status,
        parent_run_id=inp.parent_run_id,
        limit=inp.limit,
        after_id=inp.after_id,
    )


async def _run_get(inp: RunGetInput, ctx: MCPContext, _emit: ProgressEmitter) -> RunOut:
    return RunRepository(ctx.session).get(inp.run_id)


async def _run_children(
    inp: RunChildrenInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[RunOut]:
    return RunRepository(ctx.session).children(inp.parent_run_id)


async def _run_cost(inp: RunCostInput, ctx: MCPContext, _emit: ProgressEmitter) -> dict[str, Any]:
    return RunRepository(ctx.session).cost(inp.project_id, month=inp.month)


async def _run_resume(
    inp: RunResumeInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[RunOut]:
    """Resume a procedure run without executing hidden writer work."""
    runner = _resolve_runner(ctx)
    envelope = await runner.resume(run_id=inp.run_id)
    run = RunRepository(ctx.session).get(envelope["run_id"])
    return WriteEnvelope[RunOut](
        data=run, run_id=envelope["run_id"], project_id=envelope["project_id"]
    )


async def _run_fork(
    inp: RunForkInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[RunOut]:
    """Fork a caller-managed procedure run from a named step."""
    runner = _resolve_runner(ctx)
    # Resolve the named step to an index in the procedure's spec.
    step_repo = ProcedureRunStepRepository(ctx.session)
    steps = step_repo.list_steps(inp.run_id)
    if not steps:
        raise NotFoundError(
            f"run {inp.run_id} has no procedure steps recorded",
            data={"run_id": inp.run_id},
        )
    target_idx = next((s.step_index for s in steps if s.step_id == inp.from_step), None)
    if target_idx is None:
        raise NotFoundError(
            f"step {inp.from_step!r} not found on run {inp.run_id}",
            data={
                "run_id": inp.run_id,
                "from_step": inp.from_step,
                "known_step_ids": [s.step_id for s in steps],
            },
        )
    envelope = await runner.fork(run_id=inp.run_id, from_step_index=target_idx)
    run = RunRepository(ctx.session).get(envelope["run_id"])
    return WriteEnvelope[RunOut](
        data=run, run_id=envelope["run_id"], project_id=envelope["project_id"]
    )


# ---------------------------------------------------------------------------
# Run-step audit-grain tools.
# ---------------------------------------------------------------------------


class RunStepInsertInput(MCPInput):
    """Insert a ``run_steps`` row — M8 procedure runner uses this."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"run_id": 1, "step_index": 0, "skill_name": "outline"}},
    )

    run_id: int
    step_index: int
    skill_name: str
    input_snapshot_json: dict[str, Any] | None = None


class RunStepListInput(MCPInput):
    """List per-skill steps for a run."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"run_id": 1}})

    run_id: int


class RunStepCallRecordInput(MCPInput):
    """Record a per-MCP-tool call inside a run step."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"run_step_id": 1, "mcp_tool": "article.get"}}
    )

    run_step_id: int
    mcp_tool: str
    request_json: dict[str, Any] | None = None
    response_json: dict[str, Any] | None = None
    duration_ms: int | None = None
    error: str | None = None
    cost_cents: int = 0


class RunStepCallListInput(MCPInput):
    """List recorded MCP-tool calls for a run step."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"run_step_id": 1}})

    run_step_id: int


async def _run_step_insert(
    inp: RunStepInsertInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[RunStepOut]:
    env = RunStepRepository(ctx.session).insert_step(
        run_id=inp.run_id,
        step_index=inp.step_index,
        skill_name=inp.skill_name,
        input_snapshot_json=inp.input_snapshot_json,
    )
    return WriteEnvelope[RunStepOut](data=env.data, run_id=env.run_id, project_id=env.project_id)


async def _run_step_list(
    inp: RunStepListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[RunStepOut]:
    return RunStepRepository(ctx.session).list_steps(inp.run_id)


async def _run_step_call_record(
    inp: RunStepCallRecordInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[RunStepCallOut]:
    env = RunStepCallRepository(ctx.session).record_call(
        run_step_id=inp.run_step_id,
        mcp_tool=inp.mcp_tool,
        request_json=inp.request_json,
        response_json=inp.response_json,
        duration_ms=inp.duration_ms,
        error=inp.error,
        cost_cents=inp.cost_cents,
    )
    return WriteEnvelope[RunStepCallOut](
        data=env.data, run_id=env.run_id, project_id=env.project_id
    )


async def _run_step_call_list(
    inp: RunStepCallListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[RunStepCallOut]:
    return RunStepCallRepository(ctx.session).list(inp.run_step_id)


# ---------------------------------------------------------------------------
# procedure.* tools.
# ---------------------------------------------------------------------------


class ProcedureListInput(MCPInput):
    """List registered procedure slugs."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {}})


class ProcedureRunInput(MCPInput):
    """Start a caller-managed procedure run.

    The daemon pre-writes a ``runs`` row + the procedure's
    ``procedure_run_steps`` skeleton and returns
    ``{run_id, run_token, status_url}``. The current agent then claims
    each step, follows the returned skill prompt, calls tools directly,
    and records the step result.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"slug": "04-topic-to-published", "project_id": 1, "args": {"topic_id": 1}}
        },
    )

    slug: str
    project_id: int
    # ``Field(default_factory=dict)`` avoids the mutable-default class-attribute
    # pitfall (RUF012) while still letting the JSON wire shape default to {}.
    args: dict[str, Any] = Field(default_factory=dict)
    parent_run_id: int | None = None
    variant: str | None = None


class ProcedureRunOutput(BaseModel):
    """Wire shape for ``procedure.run``."""

    run_id: int
    run_token: str
    status_url: str
    slug: str
    project_id: int
    started: bool
    orchestration_mode: str = "agent-led"


class ProcedureStatusInput(MCPInput):
    """Read the procedure-step rows for a given run."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"run_id": 1}})

    run_id: int


class ProcedureStatusOutput(MCPOutput):
    """Wire shape for ``procedure.status``."""

    run: RunOut
    steps: list[ProcedureRunStepOut]


class ProcedureResumeInput(MCPInput):
    """Resume an aborted / paused procedure run from the next pending step."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"run_id": 1}})

    run_id: int


class ProcedureForkInput(MCPInput):
    """Fork a procedure run from a step index, copying prior outputs.

    Forking is the canonical "redo from step N onward" pattern — used
    by the content-refresher chain to roll a published article back
    through the editor + EEAT-gate + publish steps without losing the
    versions baked into the source run's audit trail.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"run_id": 1, "from_step_index": 5}},
    )

    run_id: int
    from_step_index: int


class ProcedureCurrentStepInput(MCPInput):
    """Return the current agent-managed procedure step package."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"run_id": 1}})

    run_id: int


class ProcedureClaimStepInput(MCPInput):
    """Claim the current step and bind the run token to its skill grant."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"run_id": 1, "step_id": "outline"}}
    )

    run_id: int
    step_id: str | None = None


class ProcedureRecordStepInput(MCPInput):
    """Record the current agent's procedure-step result."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "run_id": 1,
                "step_id": "outline",
                "status": "success",
                "output_json": {"outline_id": 12},
            }
        },
    )

    run_id: int
    step_id: str
    status: ProcedureRunStepStatus
    output_json: dict[str, Any] | None = None
    error: str | None = None


class ProcedureExecuteProgrammaticStepInput(MCPInput):
    """Execute the current deterministic ``_programmatic/*`` step."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"run_id": 1, "step_id": "generate-topic-plan"}},
    )

    run_id: int
    step_id: str | None = None


class ProcedureStepContextOutput(MCPOutput):
    """Agent-facing package for the next procedure step."""

    run: RunOut
    steps: list[ProcedureRunStepOut]
    run_id: int
    run_token: str
    slug: str
    project_id: int | None
    orchestration_mode: str
    procedure_args: dict[str, Any]
    previous_outputs: dict[str, Any]
    current_step: dict[str, Any] | None
    next_action: str


def _resolve_runner(ctx: MCPContext) -> ProcedureRunner:
    """Pull the bound runner off the context, raising a typed error if missing."""
    runner = ctx.procedure_runner
    if runner is None:
        raise ValidationError(
            "procedure_runner not initialised — daemon lifespan did not run",
            data={"hint": "this should never happen in production; tests must inject a runner"},
        )
    if not isinstance(runner, ProcedureRunner):
        # Defensive — keeps mypy + tests honest if someone monkey-patches.
        raise ValidationError(
            f"procedure_runner is the wrong type: {type(runner).__name__}",
            data={"hint": "ctx.procedure_runner must be a ProcedureRunner instance"},
        )
    return runner


async def _procedure_list(
    _inp: ProcedureListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[str]:
    """Return the registered procedure slug list.

    M7.A: the runner exposes the slug catalogue; we proxy it.
    """
    runner = _resolve_runner(ctx)
    return runner.list_procedures()


async def _procedure_run(
    inp: ProcedureRunInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ProcedureRunOutput]:
    """Open a procedure run for the current agent to manage."""
    runner = _resolve_runner(ctx)
    try:
        envelope = await runner.start(
            slug=inp.slug,
            args=inp.args,
            project_id=inp.project_id,
            parent_run_id=inp.parent_run_id,
            variant=inp.variant,
        )
    except NotFoundError:
        raise
    payload = ProcedureRunOutput(
        run_id=envelope["run_id"],
        run_token=envelope["run_token"],
        status_url=envelope["status_url"],
        slug=envelope["slug"],
        project_id=envelope["project_id"],
        started=envelope["started"],
    )
    return WriteEnvelope[ProcedureRunOutput](
        data=payload, run_id=envelope["run_id"], project_id=envelope["project_id"]
    )


async def _procedure_status(
    inp: ProcedureStatusInput, ctx: MCPContext, _emit: ProgressEmitter
) -> ProcedureStatusOutput:
    """Return the run header + every procedure-step row for a run."""
    run = RunRepository(ctx.session).get(inp.run_id)
    steps = ProcedureRunStepRepository(ctx.session).list_steps(inp.run_id)
    return ProcedureStatusOutput(run=run, steps=steps)


async def _procedure_resume(
    inp: ProcedureResumeInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ProcedureRunOutput]:
    """Resume an aborted / paused procedure run."""
    runner = _resolve_runner(ctx)
    envelope = await runner.resume(run_id=inp.run_id)
    payload = ProcedureRunOutput(
        run_id=envelope["run_id"],
        run_token=envelope["run_token"],
        status_url=envelope["status_url"],
        slug=envelope["slug"],
        project_id=envelope["project_id"],
        started=envelope["started"],
    )
    return WriteEnvelope[ProcedureRunOutput](
        data=payload, run_id=envelope["run_id"], project_id=envelope["project_id"]
    )


async def _procedure_fork(
    inp: ProcedureForkInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ProcedureRunOutput]:
    """Fork a procedure run from a step index, copying prior outputs."""
    runner = _resolve_runner(ctx)
    envelope = await runner.fork(run_id=inp.run_id, from_step_index=inp.from_step_index)
    payload = ProcedureRunOutput(
        run_id=envelope["run_id"],
        run_token=envelope["run_token"],
        status_url=envelope["status_url"],
        slug=envelope["slug"],
        project_id=envelope["project_id"],
        started=envelope["started"],
    )
    return WriteEnvelope[ProcedureRunOutput](
        data=payload, run_id=envelope["run_id"], project_id=envelope["project_id"]
    )


async def _procedure_current_step(
    inp: ProcedureCurrentStepInput, ctx: MCPContext, _emit: ProgressEmitter
) -> ProcedureStepContextOutput:
    """Return the next step package without claiming it."""
    runner = _resolve_runner(ctx)
    return ProcedureStepContextOutput.model_validate(runner.current_step(run_id=inp.run_id))


async def _procedure_claim_step(
    inp: ProcedureClaimStepInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ProcedureStepContextOutput]:
    """Claim the next procedure step for caller-owned execution."""
    runner = _resolve_runner(ctx)
    payload = ProcedureStepContextOutput.model_validate(
        runner.claim_step(run_id=inp.run_id, step_id=inp.step_id)
    )
    return WriteEnvelope[ProcedureStepContextOutput](
        data=payload, run_id=payload.run_id, project_id=payload.project_id
    )


async def _procedure_record_step(
    inp: ProcedureRecordStepInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ProcedureStepContextOutput]:
    """Persist a caller-owned step result and return the next package."""
    runner = _resolve_runner(ctx)
    payload = ProcedureStepContextOutput.model_validate(
        runner.record_step(
            run_id=inp.run_id,
            step_id=inp.step_id,
            status=inp.status,
            output_json=inp.output_json,
            error=inp.error,
        )
    )
    return WriteEnvelope[ProcedureStepContextOutput](
        data=payload, run_id=payload.run_id, project_id=payload.project_id
    )


async def _procedure_execute_programmatic_step(
    inp: ProcedureExecuteProgrammaticStepInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ProcedureStepContextOutput]:
    """Execute a deterministic programmatic step on behalf of the current agent."""
    runner = _resolve_runner(ctx)
    payload = ProcedureStepContextOutput.model_validate(
        await runner.execute_programmatic_step(run_id=inp.run_id, step_id=inp.step_id)
    )
    return WriteEnvelope[ProcedureStepContextOutput](
        data=payload, run_id=payload.run_id, project_id=payload.project_id
    )


# ---------------------------------------------------------------------------
# Registration.
# ---------------------------------------------------------------------------


def register(registry: ToolRegistry) -> None:
    """Register every run.* / procedure.* tool."""
    # run.*
    registry.register(
        ToolSpec(
            "run.start",
            "Open a run; returns (run_id, run_token).",
            RunStartInput,
            WriteEnvelope[RunStartOutput],
            _run_start,
        )
    )
    registry.register(
        ToolSpec(
            "run.finish",
            "Move a run to a terminal status.",
            RunFinishInput,
            WriteEnvelope[RunOut],
            _run_finish,
        )
    )
    registry.register(
        ToolSpec(
            "run.heartbeat",
            "Update heartbeat_at to now.",
            RunHeartbeatInput,
            WriteEnvelope[RunOut | None],
            _run_heartbeat,
        )
    )
    registry.register(
        ToolSpec(
            "run.abort",
            "Abort a run (optionally cascading to children).",
            RunAbortInput,
            WriteEnvelope[RunOut],
            _run_abort,
        )
    )
    registry.register(
        ToolSpec("run.list", "List runs with filters.", RunListInput, Page[RunOut], _run_list)
    )
    registry.register(ToolSpec("run.get", "Fetch one run by id.", RunGetInput, RunOut, _run_get))
    registry.register(
        ToolSpec(
            "run.children",
            "List direct children of a parent run.",
            RunChildrenInput,
            list[RunOut],
            _run_children,
        )
    )
    registry.register(
        ToolSpec(
            "run.cost",
            "Sum cost_cents per run kind for a project + month.",
            RunCostInput,
            dict[str, Any],
            _run_cost,
        )
    )
    registry.register(
        ToolSpec(
            "run.resume",
            "Resume a paused procedure run.",
            RunResumeInput,
            WriteEnvelope[RunOut],
            _run_resume,
        )
    )
    registry.register(
        ToolSpec(
            "run.fork",
            "Fork a procedure run from a named step.",
            RunForkInput,
            WriteEnvelope[RunOut],
            _run_fork,
        )
    )

    # Run-step audit grain.
    registry.register(
        ToolSpec(
            "run.insertStep",
            "Insert a per-skill run_step row.",
            RunStepInsertInput,
            WriteEnvelope[RunStepOut],
            _run_step_insert,
        )
    )
    registry.register(
        ToolSpec(
            "run.listSteps",
            "List per-skill steps for a run.",
            RunStepListInput,
            list[RunStepOut],
            _run_step_list,
        )
    )
    registry.register(
        ToolSpec(
            "run.recordStepCall",
            "Record a per-MCP-tool call inside a run step.",
            RunStepCallRecordInput,
            WriteEnvelope[RunStepCallOut],
            _run_step_call_record,
        )
    )
    registry.register(
        ToolSpec(
            "run.listStepCalls",
            "List recorded MCP-tool calls for a run step.",
            RunStepCallListInput,
            list[RunStepCallOut],
            _run_step_call_list,
        )
    )

    # procedure.*
    registry.register(
        ToolSpec(
            "procedure.list",
            "List registered procedure slugs (empty at M3).",
            ProcedureListInput,
            list[str],
            _procedure_list,
        )
    )
    registry.register(
        ToolSpec(
            name="procedure.run",
            description=(
                "Open an agent-led procedure run; returns {run_id, run_token, status_url}."
            ),
            input_model=ProcedureRunInput,
            output_model=WriteEnvelope[ProcedureRunOutput],
            handler=_procedure_run,
            streaming=True,
        )
    )
    registry.register(
        ToolSpec(
            "procedure.status",
            "Read run header + procedure-step rows for a run.",
            ProcedureStatusInput,
            ProcedureStatusOutput,
            _procedure_status,
        )
    )
    registry.register(
        ToolSpec(
            "procedure.resume",
            "Resume an aborted/paused procedure run from the next pending step.",
            ProcedureResumeInput,
            WriteEnvelope[ProcedureRunOutput],
            _procedure_resume,
        )
    )
    registry.register(
        ToolSpec(
            "procedure.fork",
            "Fork a procedure run from a step index, copying prior outputs.",
            ProcedureForkInput,
            WriteEnvelope[ProcedureRunOutput],
            _procedure_fork,
        )
    )
    registry.register(
        ToolSpec(
            "procedure.currentStep",
            "Return the next agent-led procedure step package without claiming it.",
            ProcedureCurrentStepInput,
            ProcedureStepContextOutput,
            _procedure_current_step,
        )
    )
    registry.register(
        ToolSpec(
            "procedure.claimStep",
            "Claim the next procedure step and bind the run token to its skill grant.",
            ProcedureClaimStepInput,
            WriteEnvelope[ProcedureStepContextOutput],
            _procedure_claim_step,
        )
    )
    registry.register(
        ToolSpec(
            "procedure.recordStep",
            "Record the current agent's step result and return the next step package.",
            ProcedureRecordStepInput,
            WriteEnvelope[ProcedureStepContextOutput],
            _procedure_record_step,
        )
    )
    registry.register(
        ToolSpec(
            "procedure.executeProgrammaticStep",
            "Execute the current deterministic _programmatic/* step.",
            ProcedureExecuteProgrammaticStepInput,
            WriteEnvelope[ProcedureStepContextOutput],
            _procedure_execute_programmatic_step,
        )
    )


__all__ = ["register"]
