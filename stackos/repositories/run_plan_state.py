"""Shared run/run-plan lifecycle state constants."""

from __future__ import annotations

from stackos.db.models import RunPlanStatus, RunPlanStepStatus, RunStatus

TERMINAL_RUN_STATUSES = {RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.ABORTED}
PLAN_TO_RUN_TERMINAL_STATUS = {
    RunPlanStatus.COMPLETED: RunStatus.SUCCESS,
    RunPlanStatus.FAILED: RunStatus.FAILED,
    RunPlanStatus.ABORTED: RunStatus.ABORTED,
}
TERMINAL_PLAN_STATUSES = frozenset(PLAN_TO_RUN_TERMINAL_STATUS)
TERMINAL_STEP_STATUSES = {
    RunPlanStepStatus.SUCCESS,
    RunPlanStepStatus.FAILED,
    RunPlanStepStatus.SKIPPED,
}

__all__ = [
    "PLAN_TO_RUN_TERMINAL_STATUS",
    "TERMINAL_PLAN_STATUSES",
    "TERMINAL_RUN_STATUSES",
    "TERMINAL_STEP_STATUSES",
]
