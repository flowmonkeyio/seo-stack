"""Shared run-plan dependency helpers."""

from __future__ import annotations

from stackos.db.models import RunPlanStep, RunPlanStepStatus

COMPLETED_DEPENDENCY_STATUSES = {
    RunPlanStepStatus.SUCCESS,
    RunPlanStepStatus.SKIPPED,
}


def completed_dependency_step_ids(rows: list[RunPlanStep]) -> set[str]:
    return {item.step_id for item in rows if item.status in COMPLETED_DEPENDENCY_STATUSES}


def transitive_step_dependencies(
    rows: list[RunPlanStep],
    step: RunPlanStep,
) -> list[str]:
    by_id = {item.step_id: item for item in rows}
    ordered: list[str] = []
    seen: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in seen:
            return
        seen.add(step_id)
        dependency_step = by_id.get(step_id)
        if dependency_step is not None:
            for parent_id in dependency_step.depends_on_json or []:
                visit(str(parent_id))
        ordered.append(step_id)

    for dependency_id in step.depends_on_json or []:
        visit(str(dependency_id))
    return ordered


def incomplete_step_dependencies(
    rows: list[RunPlanStep],
    step: RunPlanStep,
) -> list[str]:
    completed = completed_dependency_step_ids(rows)
    return [dep for dep in transitive_step_dependencies(rows, step) if dep not in completed]
