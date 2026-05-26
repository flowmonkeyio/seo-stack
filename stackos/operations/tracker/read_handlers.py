"""Read operation handlers for the tracker operation surface."""

from __future__ import annotations

from typing import Any

from stackos.agent_responses import (
    compact_tracker_brief,
    compact_tracker_changed,
    compact_tracker_history_page,
    compact_tracker_next,
    compact_tracker_search,
    compact_tracker_status,
    compact_tracker_verify,
)
from stackos.mcp.context import MCPContext
from stackos.mcp.streaming import ProgressEmitter
from stackos.operations.tracker.schemas import (
    TrackerChangedInput,
    TrackerGetInput,
    TrackerHistoryInput,
    TrackerNextInput,
    TrackerProjectInput,
    TrackerResponseMode,
    TrackerSearchInput,
    TrackerTicketInput,
)
from stackos.repositories.base import Page
from stackos.repositories.tracker import (
    TrackerBriefOut,
    TrackerChangedOut,
    TrackerHistoryOut,
    TrackerNextOut,
    TrackerRepository,
    TrackerSearchOut,
    TrackerSnapshotOut,
    TrackerStatusOut,
    TrackerVerifyOut,
)


async def tracker_status(
    inp: TrackerProjectInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> TrackerStatusOut | dict[str, Any]:
    status = TrackerRepository(ctx.session).status(project_id=inp.project_id)
    if inp.response_mode == "compact":
        return compact_tracker_status(status)
    return status


async def tracker_get(
    inp: TrackerGetInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> TrackerSnapshotOut:
    return TrackerRepository(ctx.session).get(
        project_id=inp.project_id,
        statuses=inp.statuses,
        task_key=inp.task_key,
        ticket_keys=inp.ticket_keys,
        ticket_ids=inp.ticket_ids,
        block_state=inp.block_state,
        dependency_ticket_key=inp.dependency_ticket_key,
        workflow_key=inp.workflow_key,
        run_plan_id=inp.run_plan_id,
        assignee=inp.assignee,
        include_graph=inp.include_graph,
    )


async def tracker_next(
    inp: TrackerNextInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> TrackerNextOut | dict[str, Any]:
    next_work = TrackerRepository(ctx.session).next(
        project_id=inp.project_id,
        limit=inp.limit,
        assignee=inp.assignee,
        include_blocked=inp.include_blocked,
    )
    if inp.response_mode == "compact":
        return compact_tracker_next(next_work)
    return next_work


async def tracker_blockers(
    inp: TrackerProjectInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> TrackerNextOut | dict[str, Any]:
    blockers = TrackerRepository(ctx.session).blockers(project_id=inp.project_id)
    if inp.response_mode == "compact":
        return compact_tracker_next(blockers)
    return blockers


async def tracker_brief(
    inp: TrackerTicketInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> TrackerBriefOut | dict[str, Any]:
    return _brief_response(
        TrackerRepository(ctx.session).brief(
            project_id=inp.project_id,
            ticket_key=inp.ticket_key,
        ),
        response_mode=inp.response_mode,
    )


def _brief_response(
    brief: TrackerBriefOut,
    *,
    response_mode: TrackerResponseMode,
) -> TrackerBriefOut | dict[str, Any]:
    if response_mode == "compact":
        return compact_tracker_brief(brief)
    return brief


async def tracker_why(
    inp: TrackerTicketInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> TrackerBriefOut | dict[str, Any]:
    return _brief_response(
        TrackerRepository(ctx.session).brief(
            project_id=inp.project_id,
            ticket_key=inp.ticket_key,
        ),
        response_mode=inp.response_mode,
    )


async def tracker_execute(
    inp: TrackerTicketInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> TrackerBriefOut | dict[str, Any]:
    return _brief_response(
        TrackerRepository(ctx.session).brief(
            project_id=inp.project_id,
            ticket_key=inp.ticket_key,
        ),
        response_mode=inp.response_mode,
    )


async def tracker_verify(
    inp: TrackerTicketInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> TrackerVerifyOut | dict[str, Any]:
    verification = TrackerRepository(ctx.session).verify(
        project_id=inp.project_id,
        ticket_key=inp.ticket_key,
    )
    if inp.response_mode == "compact":
        return compact_tracker_verify(verification)
    return verification


async def tracker_history(
    inp: TrackerHistoryInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> Page[TrackerHistoryOut] | dict[str, Any]:
    history = TrackerRepository(ctx.session).history(
        project_id=inp.project_id,
        limit=inp.limit,
        after_id=inp.after_id,
    )
    if inp.response_mode == "compact":
        return compact_tracker_history_page(history)
    return history


async def tracker_changed(
    inp: TrackerChangedInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> TrackerChangedOut | dict[str, Any]:
    changed = TrackerRepository(ctx.session).changed(
        project_id=inp.project_id,
        since_rev=inp.since_rev,
        limit=inp.limit,
    )
    if inp.response_mode == "compact":
        return compact_tracker_changed(changed)
    return changed


async def tracker_search(
    inp: TrackerSearchInput,
    ctx: MCPContext,
    _emitter: ProgressEmitter,
) -> TrackerSearchOut | dict[str, Any]:
    search = TrackerRepository(ctx.session).search(
        project_id=inp.project_id,
        query=inp.query,
        limit=inp.limit,
    )
    if inp.response_mode == "compact":
        return compact_tracker_search(search)
    return search


__all__ = [
    "_brief_response",
    "tracker_blockers",
    "tracker_brief",
    "tracker_changed",
    "tracker_execute",
    "tracker_get",
    "tracker_history",
    "tracker_next",
    "tracker_search",
    "tracker_status",
    "tracker_verify",
    "tracker_why",
]
