"""``interlink.*`` tools — internal-link CRUD + state-machine + repair.

``interlink.suggest`` is one of the four streaming tools per audit M-21:
when more than 10 candidates are submitted, the handler emits a progress
notification every 10 inserts so the calling LLM gets feedback on long
suggest passes.
"""

from __future__ import annotations

from pydantic import ConfigDict

from content_stack.db.models import InternalLinkStatus
from content_stack.mcp.context import MCPContext
from content_stack.mcp.contract import MCPInput, WriteEnvelope
from content_stack.mcp.server import ToolRegistry, ToolSpec
from content_stack.mcp.streaming import ProgressEmitter
from content_stack.repositories.base import Page
from content_stack.repositories.interlinks import (
    InterlinkRepository,
    InterlinkSuggestion,
    InternalLinkOut,
)

# ---------------------------------------------------------------------------
# Inputs.
# ---------------------------------------------------------------------------


class InterlinkSuggestInput(MCPInput):
    """Insert N suggested links; streams progress every 10 entries."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "project_id": 1,
                "suggestions": [
                    {"from_article_id": 1, "to_article_id": 2, "anchor_text": "see also"}
                ],
            }
        },
    )

    project_id: int
    suggestions: list[InterlinkSuggestion]


class InterlinkApplyInput(MCPInput):
    """Move a link suggested → applied."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"link_id": 1}})

    link_id: int


class InterlinkDismissInput(MCPInput):
    """Move a link to dismissed (terminal)."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"link_id": 1}})

    link_id: int


class InterlinkRepairInput(MCPInput):
    """Mark all live applied links pointing at the article as broken."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"article_id": 1}})

    article_id: int


class InterlinkBulkApplyInput(MCPInput):
    """Apply many suggestions in one transaction (all-or-nothing)."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"ids": [1, 2, 3]}})

    ids: list[int]


class InterlinkListInput(MCPInput):
    """List internal links with filters."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int
    status: InternalLinkStatus | None = None
    from_article_id: int | None = None
    to_article_id: int | None = None
    limit: int | None = None
    after_id: int | None = None


# ---------------------------------------------------------------------------
# Handlers.
# ---------------------------------------------------------------------------


_SUGGEST_PROGRESS_INTERVAL = 10


async def _interlink_suggest(
    inp: InterlinkSuggestInput, ctx: MCPContext, emit: ProgressEmitter
) -> WriteEnvelope[list[InternalLinkOut]]:
    """Insert N suggested links; streams progress every 10."""
    repo = InterlinkRepository(ctx.session)
    suggestions = list(inp.suggestions)
    total = len(suggestions)
    if total > _SUGGEST_PROGRESS_INTERVAL and emit.is_active:
        all_rows: list[InternalLinkOut] = []
        for batch_start in range(0, total, _SUGGEST_PROGRESS_INTERVAL):
            batch = suggestions[batch_start : batch_start + _SUGGEST_PROGRESS_INTERVAL]
            env = repo.suggest(inp.project_id, batch)
            all_rows.extend(env.data)
            await emit.emit(
                step=batch_start + len(batch),
                total=total,
                message=f"suggested {batch_start + len(batch)}/{total} links",
            )
        await emit.done("suggest complete")
        return WriteEnvelope[list[InternalLinkOut]](
            data=all_rows, run_id=ctx.run_id, project_id=inp.project_id
        )
    env = repo.suggest(inp.project_id, suggestions)
    return WriteEnvelope[list[InternalLinkOut]](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _interlink_apply(
    inp: InterlinkApplyInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[InternalLinkOut]:
    env = InterlinkRepository(ctx.session).apply(inp.link_id)
    return WriteEnvelope[InternalLinkOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _interlink_dismiss(
    inp: InterlinkDismissInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[InternalLinkOut]:
    env = InterlinkRepository(ctx.session).dismiss(inp.link_id)
    return WriteEnvelope[InternalLinkOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _interlink_repair(
    inp: InterlinkRepairInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[list[InternalLinkOut]]:
    env = InterlinkRepository(ctx.session).repair(inp.article_id)
    return WriteEnvelope[list[InternalLinkOut]](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _interlink_bulk_apply(
    inp: InterlinkBulkApplyInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[list[InternalLinkOut]]:
    env = InterlinkRepository(ctx.session).bulk_apply(inp.ids)
    return WriteEnvelope[list[InternalLinkOut]](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _interlink_list(
    inp: InterlinkListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> Page[InternalLinkOut]:
    return InterlinkRepository(ctx.session).list(
        inp.project_id,
        status=inp.status,
        from_article_id=inp.from_article_id,
        to_article_id=inp.to_article_id,
        limit=inp.limit,
        after_id=inp.after_id,
    )


# ---------------------------------------------------------------------------
# Registration.
# ---------------------------------------------------------------------------


def register(registry: ToolRegistry) -> None:
    """Register every interlink.* tool."""
    registry.register(
        ToolSpec(
            name="interlink.suggest",
            description="Insert N suggested links; streams progress every 10 entries.",
            input_model=InterlinkSuggestInput,
            output_model=WriteEnvelope[list[InternalLinkOut]],
            handler=_interlink_suggest,
            streaming=True,
        )
    )
    registry.register(
        ToolSpec(
            "interlink.apply",
            "Move a link suggested → applied.",
            InterlinkApplyInput,
            WriteEnvelope[InternalLinkOut],
            _interlink_apply,
        )
    )
    registry.register(
        ToolSpec(
            "interlink.dismiss",
            "Move a link to dismissed (terminal).",
            InterlinkDismissInput,
            WriteEnvelope[InternalLinkOut],
            _interlink_dismiss,
        )
    )
    registry.register(
        ToolSpec(
            "interlink.repair",
            "Mark all live applied links pointing at the article as broken.",
            InterlinkRepairInput,
            WriteEnvelope[list[InternalLinkOut]],
            _interlink_repair,
        )
    )
    registry.register(
        ToolSpec(
            "interlink.bulkApply",
            "Apply many suggestions atomically (all-or-nothing).",
            InterlinkBulkApplyInput,
            WriteEnvelope[list[InternalLinkOut]],
            _interlink_bulk_apply,
        )
    )
    registry.register(
        ToolSpec(
            "interlink.list",
            "List internal links with filters.",
            InterlinkListInput,
            Page[InternalLinkOut],
            _interlink_list,
        )
    )


__all__ = ["register"]
