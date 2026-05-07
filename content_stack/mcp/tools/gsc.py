"""``gsc.*``, ``drift.*``, ``redirect.*`` tools.

``gsc.bulkIngest`` is one of the four streaming tools per audit M-21 —
when the input row count exceeds 1000 the handler emits a progress
notification every 1000 rows so multi-tens-of-thousand-row imports give
the caller continuous feedback.

``drift.diff`` is M5 work (Firecrawl + drift-watch skill); the M3 tool
returns ``MilestoneDeferralError`` with the M5 hint.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import ConfigDict

from content_stack.db.models import RedirectKind
from content_stack.mcp.context import MCPContext
from content_stack.mcp.contract import MCPInput, WriteEnvelope
from content_stack.mcp.errors import MilestoneDeferralError
from content_stack.mcp.server import ToolRegistry, ToolSpec
from content_stack.mcp.streaming import ProgressEmitter
from content_stack.repositories.base import Page
from content_stack.repositories.gsc import (
    DriftBaselineOut,
    DriftBaselineRepository,
    GscMetricDailyOut,
    GscMetricOut,
    GscMetricRepository,
    GscMetricsDailyRepository,
    GscRow,
    RedirectOut,
    RedirectRepository,
)

# ---------------------------------------------------------------------------
# gsc.* inputs.
# ---------------------------------------------------------------------------


class GscBulkIngestInput(MCPInput):
    """Insert N raw GSC metric rows; streams progress every 1000."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "rows": []}},
    )

    project_id: int
    rows: list[GscRow]


class GscQueryProjectInput(MCPInput):
    """Read raw rows for a project in [since, until)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "project_id": 1,
                "since": "2026-04-01T00:00:00",
                "until": "2026-05-01T00:00:00",
            }
        },
    )

    project_id: int
    since: datetime
    until: datetime


class GscQueryArticleInput(MCPInput):
    """Read raw rows for an article in [since, until)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "article_id": 1,
                "since": "2026-04-01T00:00:00",
                "until": "2026-05-01T00:00:00",
            }
        },
    )

    article_id: int
    since: datetime
    until: datetime


class GscRollupInput(MCPInput):
    """Aggregate daily rows for a project + day."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"project_id": 1, "day": "2026-05-01"}}
    )

    project_id: int
    day: date


class GscListDailyInput(MCPInput):
    """List daily rollup rows."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int
    article_id: int | None = None
    limit: int | None = None
    after_id: int | None = None


# ---------------------------------------------------------------------------
# gsc.* handlers.
# ---------------------------------------------------------------------------


_INGEST_PROGRESS_INTERVAL = 1000


async def _gsc_bulk_ingest(
    inp: GscBulkIngestInput, ctx: MCPContext, emit: ProgressEmitter
) -> WriteEnvelope[int]:
    """Insert N raw GSC metric rows; streams progress every 1000."""
    repo = GscMetricRepository(ctx.session)
    rows = list(inp.rows)
    total = len(rows)
    if total > _INGEST_PROGRESS_INTERVAL and emit.is_active:
        inserted_total = 0
        for batch_start in range(0, total, _INGEST_PROGRESS_INTERVAL):
            batch = rows[batch_start : batch_start + _INGEST_PROGRESS_INTERVAL]
            env = repo.bulk_ingest(inp.project_id, batch)
            inserted_total += env.data
            await emit.emit(
                step=batch_start + len(batch),
                total=total,
                message=f"ingested {batch_start + len(batch)}/{total} rows",
            )
        await emit.done("bulkIngest complete")
        return WriteEnvelope[int](data=inserted_total, run_id=ctx.run_id, project_id=inp.project_id)
    env = repo.bulk_ingest(inp.project_id, rows)
    return WriteEnvelope[int](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _gsc_query_project(
    inp: GscQueryProjectInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[GscMetricOut]:
    return GscMetricRepository(ctx.session).query_project(
        inp.project_id, since=inp.since, until=inp.until
    )


async def _gsc_query_article(
    inp: GscQueryArticleInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[GscMetricOut]:
    return GscMetricRepository(ctx.session).query_article(
        inp.article_id, since=inp.since, until=inp.until
    )


async def _gsc_rollup(
    inp: GscRollupInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[int]:
    env = GscMetricsDailyRepository(ctx.session).rollup(inp.project_id, day=inp.day)
    return WriteEnvelope[int](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _gsc_list_daily(
    inp: GscListDailyInput, ctx: MCPContext, _emit: ProgressEmitter
) -> Page[GscMetricDailyOut]:
    return GscMetricsDailyRepository(ctx.session).list(
        inp.project_id, article_id=inp.article_id, limit=inp.limit, after_id=inp.after_id
    )


# ---------------------------------------------------------------------------
# drift.* tools.
# ---------------------------------------------------------------------------


class DriftSnapshotInput(MCPInput):
    """Insert a baseline row for content drift detection."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"article_id": 1, "baseline_md": "..."}}
    )

    article_id: int
    baseline_md: str


class DriftListInput(MCPInput):
    """List baselines for an article."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"article_id": 1}})

    article_id: int


class DriftGetInput(MCPInput):
    """Fetch one baseline."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"baseline_id": 1}})

    baseline_id: int


class DriftDiffInput(MCPInput):
    """Compare a baseline to current content — M5 deferral."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"baseline_id": 1, "current_md": "..."}}
    )

    baseline_id: int
    current_md: str


async def _drift_snapshot(
    inp: DriftSnapshotInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[DriftBaselineOut]:
    env = DriftBaselineRepository(ctx.session).snapshot(
        article_id=inp.article_id, baseline_md=inp.baseline_md
    )
    return WriteEnvelope[DriftBaselineOut](
        data=env.data, run_id=ctx.run_id, project_id=env.project_id
    )


async def _drift_list(
    inp: DriftListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> list[DriftBaselineOut]:
    return DriftBaselineRepository(ctx.session).list(inp.article_id)


async def _drift_get(
    inp: DriftGetInput, ctx: MCPContext, _emit: ProgressEmitter
) -> DriftBaselineOut:
    return DriftBaselineRepository(ctx.session).get(inp.baseline_id)


async def _drift_diff(
    inp: DriftDiffInput, _ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[Any]:
    """M5 deferral — drift comparison engine."""
    raise MilestoneDeferralError(
        "drift.diff requires the M5 drift-watch skill",
        data={
            "milestone": "M5",
            "hint": "Lands with the Firecrawl integration + drift-watch skill",
            "baseline_id": inp.baseline_id,
        },
    )


# ---------------------------------------------------------------------------
# redirect.* tools.
# ---------------------------------------------------------------------------


class RedirectCreateInput(MCPInput):
    """Insert a 301/302 redirect record."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "from_url": "/old", "to_article_id": 1}},
    )

    project_id: int
    from_url: str
    to_article_id: int | None = None
    kind: RedirectKind = RedirectKind.R301


class RedirectListInput(MCPInput):
    """List redirects for a project."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"project_id": 1}})

    project_id: int
    limit: int | None = None
    after_id: int | None = None


class RedirectLookupInput(MCPInput):
    """Look up a redirect by from_url."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"example": {"project_id": 1, "from_url": "/old"}}
    )

    project_id: int
    from_url: str


async def _redirect_create(
    inp: RedirectCreateInput, ctx: MCPContext, _emit: ProgressEmitter
) -> WriteEnvelope[RedirectOut]:
    env = RedirectRepository(ctx.session).create(
        project_id=inp.project_id,
        from_url=inp.from_url,
        to_article_id=inp.to_article_id,
        kind=inp.kind,
    )
    return WriteEnvelope[RedirectOut](data=env.data, run_id=ctx.run_id, project_id=env.project_id)


async def _redirect_list(
    inp: RedirectListInput, ctx: MCPContext, _emit: ProgressEmitter
) -> Page[RedirectOut]:
    return RedirectRepository(ctx.session).list(
        inp.project_id, limit=inp.limit, after_id=inp.after_id
    )


async def _redirect_lookup(
    inp: RedirectLookupInput, ctx: MCPContext, _emit: ProgressEmitter
) -> RedirectOut | None:
    return RedirectRepository(ctx.session).lookup(project_id=inp.project_id, from_url=inp.from_url)


# ---------------------------------------------------------------------------
# Registration.
# ---------------------------------------------------------------------------


def register(registry: ToolRegistry) -> None:
    """Register every gsc.* / drift.* / redirect.* tool."""
    # gsc.*
    registry.register(
        ToolSpec(
            name="gsc.bulkIngest",
            description="Insert N raw GSC metric rows; streams progress every 1000.",
            input_model=GscBulkIngestInput,
            output_model=WriteEnvelope[int],
            handler=_gsc_bulk_ingest,
            streaming=True,
        )
    )
    registry.register(
        ToolSpec(
            "gsc.queryProject",
            "Read raw rows for a project in [since, until).",
            GscQueryProjectInput,
            list[GscMetricOut],
            _gsc_query_project,
        )
    )
    registry.register(
        ToolSpec(
            "gsc.queryArticle",
            "Read raw rows for an article in [since, until).",
            GscQueryArticleInput,
            list[GscMetricOut],
            _gsc_query_article,
        )
    )
    registry.register(
        ToolSpec(
            "gsc.rollup",
            "Aggregate daily rows for a project + day.",
            GscRollupInput,
            WriteEnvelope[int],
            _gsc_rollup,
        )
    )
    registry.register(
        ToolSpec(
            "gsc.listDaily",
            "List daily rollup rows.",
            GscListDailyInput,
            Page[GscMetricDailyOut],
            _gsc_list_daily,
        )
    )

    # drift.*
    registry.register(
        ToolSpec(
            "drift.snapshot",
            "Insert a baseline for content drift detection.",
            DriftSnapshotInput,
            WriteEnvelope[DriftBaselineOut],
            _drift_snapshot,
        )
    )
    registry.register(
        ToolSpec(
            "drift.list",
            "List baselines for an article.",
            DriftListInput,
            list[DriftBaselineOut],
            _drift_list,
        )
    )
    registry.register(
        ToolSpec("drift.get", "Fetch one baseline.", DriftGetInput, DriftBaselineOut, _drift_get)
    )
    registry.register(
        ToolSpec(
            "drift.diff",
            "Compare a baseline to current content (M5 deferral).",
            DriftDiffInput,
            WriteEnvelope[Any],
            _drift_diff,
        )
    )

    # redirect.*
    registry.register(
        ToolSpec(
            "redirect.create",
            "Insert a 301/302 redirect record.",
            RedirectCreateInput,
            WriteEnvelope[RedirectOut],
            _redirect_create,
        )
    )
    registry.register(
        ToolSpec(
            "redirect.list",
            "List redirects for a project.",
            RedirectListInput,
            Page[RedirectOut],
            _redirect_list,
        )
    )
    registry.register(
        ToolSpec(
            "redirect.lookup",
            "Look up a redirect by from_url.",
            RedirectLookupInput,
            RedirectOut,
            _redirect_lookup,
        )
    )


__all__ = ["register"]
