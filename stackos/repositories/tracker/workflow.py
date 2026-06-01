"""Workflow tracker identity helpers."""

from __future__ import annotations

from stackos.db.models import RunPlanStep, TrackerSourceKind, TrackerTicket
from stackos.repositories.tracker.utils import _slug


def workflow_step_ticket_key(run_plan_id: int, step_id: str) -> str:
    return f"workflow-{run_plan_id}-{_slug(step_id, fallback='step', max_length=80)}"


def is_workflow_step_mirror_ticket(ticket: TrackerTicket, step: RunPlanStep | None) -> bool:
    if ticket.run_plan_id is None or step is None:
        return False
    return (
        ticket.source_kind == TrackerSourceKind.WORKFLOW
        and ticket.parent_ticket_id is None
        and ticket.key == workflow_step_ticket_key(ticket.run_plan_id, step.step_id)
        and ticket.run_plan_step_id == step.id
    )


__all__ = ["is_workflow_step_mirror_ticket", "workflow_step_ticket_key"]
