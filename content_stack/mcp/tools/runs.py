"""``run.*`` and ``procedure.*`` tools.

Exposes the audit-trail layer (``RunRepository`` + ``RunStepRepository``
+ ``RunStepCallRepository`` + ``ProcedureRunStepRepository``) plus the
procedure-orchestration seam.

**Procedure runner is M8** — ``procedure.run`` validates the slug
exists in the (M3-empty) registry and otherwise raises
``MilestoneDeferralError`` so the tool is discoverable but documents
the deferral cleanly. ``procedure.list`` returns ``[]`` (the registry is
empty at M3); ``procedure.status`` works today and reads the
``ProcedureRunStep`` rows for any existing run.
"""

from __future__ import annotations

import secrets
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from content_stack.db.models import RunKind, RunStatus
from content_stack.mcp.context import MCPContext
from content_stack.mcp.contract import MCPInput, MCPOutput, WriteEnvelope
from content_stack.mcp.errors import MilestoneDeferralError
from content_stack.mcp.server import ToolRegistry, ToolSpec
from content_stack.mcp.streaming import ProgressEmitter
from content_stack.repositories.base import Page
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
    """Resume a paused procedure run — M9 deferral."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"run_id": 1}})

    run_id: int


class RunForkInput(MCPInput):
    """Fork a procedure run from a named step — M9 deferral."""

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
    inp: RunResumeInput, _ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[RunOut]:
    """Resume a paused procedure run — M8 deferral (jobs + scheduling)."""
    raise MilestoneDeferralError(
        "run.resume requires the M8 jobs/scheduling subsystem",
        data={
            "milestone": "M8",
            "hint": "Lands with APScheduler + the procedure runner driver",
            "run_id": inp.run_id,
        },
    )


async def _run_fork(
    inp: RunForkInput, _ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[RunOut]:
    """Fork a procedure run from a named step — M8 deferral."""
    raise MilestoneDeferralError(
        "run.fork requires the M8 jobs/scheduling subsystem",
        data={
            "milestone": "M8",
            "hint": "Lands with APScheduler + the procedure runner driver",
            "run_id": inp.run_id,
            "from_step": inp.from_step,
        },
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
    """List registered procedure slugs (M3 returns [] — registry empty)."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {}})


class ProcedureRunInput(MCPInput):
    """Enqueue a procedure run — M8 deferral.

    M3 documents the seam: validates the slug exists in the registry
    (currently empty) and raises ``MilestoneDeferralError`` with the
    M8 hint. M8 will create the ``runs`` row, return ``(run_id,
    run_token, status_url)``, and dispatch the runner asynchronously.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"slug": "topic-to-published", "project_id": 1, "args": {"topic_id": 1}}
        },
    )

    slug: str
    project_id: int
    # ``Field(default_factory=dict)`` avoids the mutable-default class-attribute
    # pitfall (RUF012) while still letting the JSON wire shape default to {}.
    args: dict[str, Any] = Field(default_factory=dict)


class ProcedureStatusInput(MCPInput):
    """Read the procedure-step rows for a given run."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"run_id": 1}})

    run_id: int


class ProcedureStatusOutput(MCPOutput):
    """Wire shape for ``procedure.status``."""

    run: RunOut
    steps: list[ProcedureRunStepOut]


class ProcedureResumeInput(MCPInput):
    """Resume a paused procedure run — M8/M9 deferral."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"run_id": 1}})

    run_id: int


class ProcedureForkInput(MCPInput):
    """Fork a procedure run — M8/M9 deferral."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"run_id": 1, "from_step": "editor"}}
    )

    run_id: int
    from_step: str


async def _procedure_list(
    _inp: ProcedureListInput, _ctx: MCPContext, _emit: ProgressEmitter
) -> list[str]:
    """Return the registered procedure slug list.

    M3 ships with an empty registry; the procedure-runner + slug-loader
    land in M8. We return ``[]`` rather than -32601 because the
    operation is well-defined ("list known procedures") even when the
    list is empty — this matches the deliverable brief.
    """
    return []


async def _procedure_run(
    inp: ProcedureRunInput, _ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[Any]:
    """Enqueue a procedure run — M7 deferral.

    The slug is validated against the (empty) registry; the deferral
    error carries ``data.milestone='M7'`` and a hint pointing at
    PLAN.md L880-L900 + decision D4. Procedure-runner work is
    step 8 (M7 in 0-indexed convention).
    """
    raise MilestoneDeferralError(
        "procedure.run requires the M7 procedure runner",
        data={
            "milestone": "M7",
            "hint": (
                "M3 exposes the tool seam; M7 implements the daemon-orchestrated runner per "
                "PLAN.md L880-L900 (decision D4). The runner creates a `runs` row with "
                "kind='procedure' and dispatches step-by-step LLM subprocesses."
            ),
            "slug": inp.slug,
            "project_id": inp.project_id,
        },
    )


async def _procedure_status(
    inp: ProcedureStatusInput, ctx: MCPContext, _emit: ProgressEmitter
) -> ProcedureStatusOutput:
    """Return the run header + every procedure-step row for a run.

    Works today — reads ``RunRepository.get`` plus
    ``ProcedureRunStepRepository.list_steps``. M8 will populate the
    ``ProcedureRunStep`` rows during runner execution; until then any
    rows pre-inserted by tests / ad-hoc fixtures show up here.
    """
    run = RunRepository(ctx.session).get(inp.run_id)
    steps = ProcedureRunStepRepository(ctx.session).list_steps(inp.run_id)
    return ProcedureStatusOutput(run=run, steps=steps)


async def _procedure_resume(
    inp: ProcedureResumeInput, _ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[Any]:
    raise MilestoneDeferralError(
        "procedure.resume requires the M7 procedure runner",
        data={"milestone": "M7", "hint": "Lands with the runner", "run_id": inp.run_id},
    )


async def _procedure_fork(
    inp: ProcedureForkInput, _ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[Any]:
    raise MilestoneDeferralError(
        "procedure.fork requires the M7 procedure runner",
        data={
            "milestone": "M7",
            "hint": "Lands with the runner",
            "run_id": inp.run_id,
            "from_step": inp.from_step,
        },
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
            description="Enqueue a procedure run (M8 deferral; documented seam).",
            input_model=ProcedureRunInput,
            output_model=WriteEnvelope[Any],
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
            "Resume a paused procedure run.",
            ProcedureResumeInput,
            WriteEnvelope[Any],
            _procedure_resume,
        )
    )
    registry.register(
        ToolSpec(
            "procedure.fork",
            "Fork a procedure run from a named step.",
            ProcedureForkInput,
            WriteEnvelope[Any],
            _procedure_fork,
        )
    )


__all__ = ["register"]
