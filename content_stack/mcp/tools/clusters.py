"""``cluster.*`` and ``topic.*`` tools.

``topic.bulkCreate`` is one of the four streaming tools per audit M-21.
When the input list exceeds 50 items, the handler emits a progress
notification every 50 inserts so a long topical-cluster import doesn't
look frozen to the calling LLM client.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict

from content_stack.db.models import (
    ClusterType,
    TopicIntent,
    TopicSource,
    TopicStatus,
)
from content_stack.mcp.context import MCPContext
from content_stack.mcp.contract import MCPInput, WriteEnvelope
from content_stack.mcp.server import ToolRegistry, ToolSpec
from content_stack.mcp.streaming import ProgressEmitter
from content_stack.repositories.base import Page
from content_stack.repositories.clusters import (
    ClusterOut,
    ClusterRepository,
    TopicCreate,
    TopicOut,
    TopicRepository,
)

# ---------------------------------------------------------------------------
# cluster.* inputs.
# ---------------------------------------------------------------------------


class ClusterCreateInput(MCPInput):
    """Insert a cluster (topical map node)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "name": "betting-101", "type": "topical"}},
    )

    project_id: int
    name: str
    type: ClusterType
    parent_id: int | None = None


class ClusterListInput(MCPInput):
    """List clusters for a project."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int
    limit: int | None = None
    after_id: int | None = None


class ClusterGetInput(MCPInput):
    """Fetch a cluster by id."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"cluster_id": 1}})

    cluster_id: int


# ---------------------------------------------------------------------------
# topic.* inputs.
# ---------------------------------------------------------------------------


class TopicCreateInput(MCPInput):
    """Insert one topic."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "title": "Best parlay strategies"}},
    )

    project_id: int
    title: str
    primary_kw: str = ""
    secondary_kws: list[str] | None = None
    intent: TopicIntent = TopicIntent.INFORMATIONAL
    status: TopicStatus = TopicStatus.QUEUED
    priority: int | None = None
    source: TopicSource = TopicSource.MANUAL
    cluster_id: int | None = None


class TopicBulkCreateInput(MCPInput):
    """Insert N topics in one transaction. Streaming when len>50."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "items": [{"title": "Topic 1"}]}},
    )

    project_id: int
    items: list[TopicCreate]


class TopicListInput(MCPInput):
    """List topics with filters + tiebreaker sort."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"project_id": 1, "status": "queued"}}
    )

    project_id: int
    status: TopicStatus | None = None
    source: TopicSource | None = None
    cluster_id: int | None = None
    sort: Literal["priority", "-priority", "id", "-id"] = "priority"
    limit: int | None = None
    after_id: int | None = None


class TopicGetInput(MCPInput):
    """Fetch a topic by id."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"topic_id": 1}})

    topic_id: int


class TopicApproveInput(MCPInput):
    """Set status='approved'."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"topic_id": 1}})

    topic_id: int


class TopicRejectInput(MCPInput):
    """Set status='rejected'."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"topic_id": 1}})

    topic_id: int


class TopicBulkUpdateStatusInput(MCPInput):
    """Move N topics to a new status (validated all-or-nothing)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "ids": [1, 2, 3], "status": "approved"}},
    )

    project_id: int
    ids: list[int]
    status: TopicStatus


# ---------------------------------------------------------------------------
# Handlers.
# ---------------------------------------------------------------------------


async def _cluster_create(
    inp: ClusterCreateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[ClusterOut]:
    env = ClusterRepository(ctx.session).create(
        project_id=inp.project_id,
        name=inp.name,
        type=inp.type,
        parent_id=inp.parent_id,
    )
    return WriteEnvelope[ClusterOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _cluster_list(
    inp: ClusterListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> Page[ClusterOut]:
    return ClusterRepository(ctx.session).list(
        inp.project_id, limit=inp.limit, after_id=inp.after_id
    )


async def _cluster_get(inp: ClusterGetInput, ctx: MCPContext, _emit: ProgressEmitter) -> ClusterOut:
    return ClusterRepository(ctx.session).get(inp.cluster_id)


async def _topic_create(
    inp: TopicCreateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[TopicOut]:
    item = TopicCreate(
        title=inp.title,
        primary_kw=inp.primary_kw,
        secondary_kws=inp.secondary_kws,
        intent=inp.intent,
        status=inp.status,
        priority=inp.priority,
        source=inp.source,
        cluster_id=inp.cluster_id,
    )
    env = TopicRepository(ctx.session).create(inp.project_id, item)
    return WriteEnvelope[TopicOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


# Streaming threshold for topic.bulkCreate per audit M-21.
_BULK_CREATE_PROGRESS_INTERVAL = 50


async def _topic_bulk_create(
    inp: TopicBulkCreateInput, ctx: MCPContext, emit: ProgressEmitter
) -> WriteEnvelope[list[TopicOut]]:
    """Insert N topics; emit progress every 50 when N>50."""
    repo = TopicRepository(ctx.session)
    items = list(inp.items)
    total = len(items)
    if total > _BULK_CREATE_PROGRESS_INTERVAL and emit.is_active:
        # Insert in batches of 50 so we can emit progress between batches.
        all_rows: list[TopicOut] = []
        for batch_start in range(0, total, _BULK_CREATE_PROGRESS_INTERVAL):
            batch = items[batch_start : batch_start + _BULK_CREATE_PROGRESS_INTERVAL]
            env = repo.bulk_create(inp.project_id, batch)
            all_rows.extend(env.data)
            await emit.emit(
                step=batch_start + len(batch),
                total=total,
                message=f"inserted {batch_start + len(batch)}/{total} topics",
            )
        await emit.done("bulkCreate complete")
        return WriteEnvelope[list[TopicOut]](
            data=all_rows,
            run_id=ctx.run_id,
            project_id=inp.project_id,
        )
    # Non-streaming path.
    env = repo.bulk_create(inp.project_id, items)
    return WriteEnvelope[list[TopicOut]](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _topic_list(
    inp: TopicListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> Page[TopicOut]:
    return TopicRepository(ctx.session).list(
        inp.project_id,
        status=inp.status,
        source=inp.source,
        cluster_id=inp.cluster_id,
        sort=inp.sort,
        limit=inp.limit,
        after_id=inp.after_id,
    )


async def _topic_get(inp: TopicGetInput, ctx: MCPContext, _emit: ProgressEmitter) -> TopicOut:
    return TopicRepository(ctx.session).get(inp.topic_id)


async def _topic_approve(
    inp: TopicApproveInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[TopicOut]:
    env = TopicRepository(ctx.session).approve(inp.topic_id)
    return WriteEnvelope[TopicOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _topic_reject(
    inp: TopicRejectInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[TopicOut]:
    env = TopicRepository(ctx.session).reject(inp.topic_id)
    return WriteEnvelope[TopicOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _topic_bulk_update_status(
    inp: TopicBulkUpdateStatusInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[list[TopicOut]]:
    env = TopicRepository(ctx.session).bulk_update_status(inp.project_id, inp.ids, inp.status)
    return WriteEnvelope[list[TopicOut]](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


# ---------------------------------------------------------------------------
# Registration.
# ---------------------------------------------------------------------------


def register(registry: ToolRegistry) -> None:
    """Register every cluster.* / topic.* tool."""
    registry.register(
        ToolSpec(
            "cluster.create",
            "Insert a cluster (topical map node).",
            ClusterCreateInput,
            WriteEnvelope[ClusterOut],
            _cluster_create,
        )
    )
    registry.register(
        ToolSpec(
            "cluster.list",
            "List clusters for a project.",
            ClusterListInput,
            Page[ClusterOut],
            _cluster_list,
        )
    )
    registry.register(
        ToolSpec("cluster.get", "Fetch a cluster by id.", ClusterGetInput, ClusterOut, _cluster_get)
    )

    registry.register(
        ToolSpec(
            "topic.create",
            "Insert one topic.",
            TopicCreateInput,
            WriteEnvelope[TopicOut],
            _topic_create,
        )
    )
    registry.register(
        ToolSpec(
            name="topic.bulkCreate",
            description="Insert N topics; streams progress every 50 when N>50.",
            input_model=TopicBulkCreateInput,
            output_model=WriteEnvelope[list[TopicOut]],
            handler=_topic_bulk_create,
            streaming=True,
        )
    )
    registry.register(
        ToolSpec(
            "topic.list",
            "List topics with filters + queue tiebreaker.",
            TopicListInput,
            Page[TopicOut],
            _topic_list,
        )
    )
    registry.register(
        ToolSpec("topic.get", "Fetch a topic by id.", TopicGetInput, TopicOut, _topic_get)
    )
    registry.register(
        ToolSpec(
            "topic.approve",
            "Set topic status='approved'.",
            TopicApproveInput,
            WriteEnvelope[TopicOut],
            _topic_approve,
        )
    )
    registry.register(
        ToolSpec(
            "topic.reject",
            "Set topic status='rejected'.",
            TopicRejectInput,
            WriteEnvelope[TopicOut],
            _topic_reject,
        )
    )
    registry.register(
        ToolSpec(
            "topic.bulkUpdateStatus",
            "Move N topics to a new status (all-or-nothing).",
            TopicBulkUpdateStatusInput,
            WriteEnvelope[list[TopicOut]],
            _topic_bulk_update_status,
        )
    )


__all__ = ["register"]
