from __future__ import annotations

import pytest
from sqlmodel import Session, select

from stackos.db.models import RunPlanStepStatus, TaskTracker, TrackerItemStatus
from stackos.repositories.base import ValidationError
from stackos.repositories.run_plans import RunPlanRepository
from stackos.repositories.tracker import TrackerRepository


def test_tracker_reads_do_not_create_default_tracker(session: Session, project_id: int) -> None:
    repo = TrackerRepository(session)

    status = repo.status(project_id=project_id)
    snapshot = repo.get(project_id=project_id)
    next_work = repo.next(project_id=project_id)

    assert status.rev == 0
    assert snapshot.tracker.id == 0
    assert snapshot.tasks == []
    assert snapshot.graph is not None
    assert next_work.tickets == []
    row = session.exec(select(TaskTracker).where(TaskTracker.project_id == project_id)).first()
    assert row is None


def test_manual_task_ticket_lifecycle_and_graph(session: Session, project_id: int) -> None:
    repo = TrackerRepository(session)

    task_env = repo.create_task(
        project_id=project_id,
        key="manual-comms",
        title="Manual communications work",
        goal="Track a direct agent task with child tickets.",
        created_by="codex",
    )
    repo.create_ticket(
        project_id=project_id,
        task_key="manual-comms",
        key="manual-discovery",
        title="Discovery",
        definition_of_done_json=["Constraints are written down."],
        created_by="codex",
    )
    repo.create_ticket(
        project_id=project_id,
        task_key="manual-comms",
        key="manual-delivery",
        title="Delivery",
        dependency_keys=["manual-discovery"],
        definition_of_done_json=["Delivery is verified."],
        created_by="codex",
    )

    next_before = repo.next(project_id=project_id)
    assert [ticket.key for ticket in next_before.tickets] == ["manual-discovery"]
    assert next_before.blocked[0].key == "manual-delivery"
    assert repo.status(project_id=project_id).blocked_ticket_count == 1

    picked = repo.pick(project_id=project_id, ticket_key="manual-discovery", assignee="codex").data
    assert picked.ticket is not None
    assert picked.ticket.status == TrackerItemStatus.IN_PROGRESS

    repo.update_ticket(
        project_id=project_id,
        ticket_key="manual-discovery",
        patch_json={"status": "complete", "outcome": "Discovery complete."},
        actor="codex",
    )
    after_first_ticket = repo.brief(project_id=project_id, ticket_key="manual-delivery")
    assert after_first_ticket.task.status == TrackerItemStatus.IN_PROGRESS
    next_after = repo.next(project_id=project_id)
    assert [ticket.key for ticket in next_after.tickets] == ["manual-delivery"]

    repo.pick(project_id=project_id, ticket_key="manual-delivery", assignee="codex")
    completed = repo.update_ticket(
        project_id=project_id,
        ticket_key="manual-delivery",
        patch_json={"status": "complete", "outcome": "Delivery complete."},
        actor="codex",
    ).data
    assert completed.task is not None
    assert completed.task.status == TrackerItemStatus.COMPLETE
    assert completed.task.completed_at is not None
    assert completed.ticket is not None
    assert completed.ticket.completed_at is not None

    reopened = repo.update_ticket(
        project_id=project_id,
        ticket_key="manual-delivery",
        patch_json={"status": "in-progress"},
        actor="codex",
    ).data
    assert reopened.task is not None
    assert reopened.task.status == TrackerItemStatus.IN_PROGRESS
    assert reopened.task.completed_at is None
    assert reopened.ticket is not None
    assert reopened.ticket.status == TrackerItemStatus.IN_PROGRESS
    assert reopened.ticket.completed_at is None

    completed = repo.update_ticket(
        project_id=project_id,
        ticket_key="manual-delivery",
        patch_json={"status": "complete", "outcome": "Delivery complete again."},
        actor="codex",
    ).data
    assert completed.task is not None
    assert completed.task.status == TrackerItemStatus.COMPLETE

    snapshot = repo.get(project_id=project_id)
    assert task_env.data.task is not None
    assert snapshot.graph is not None
    assert {node.id for node in snapshot.graph.nodes} >= {
        "task:manual-comms",
        "ticket:manual-discovery",
        "ticket:manual-delivery",
    }
    assert any(edge.type == "dependency" for edge in snapshot.graph.edges)


def test_tracker_status_ignores_terminal_blocker_notes(
    session: Session,
    project_id: int,
) -> None:
    repo = TrackerRepository(session)
    repo.create_task(
        project_id=project_id,
        key="terminal-notes",
        title="Terminal blocker notes",
        created_by="codex",
    )
    repo.create_ticket(
        project_id=project_id,
        task_key="terminal-notes",
        key="terminal-open-blocked",
        title="Open blocked",
        blocker_reason="Waiting on input.",
        created_by="codex",
    )
    repo.create_ticket(
        project_id=project_id,
        task_key="terminal-notes",
        key="terminal-deferred-note",
        title="Deferred with historical note",
        blocker_reason="Deferred by product decision.",
        created_by="codex",
    )
    repo.update_ticket(
        project_id=project_id,
        ticket_key="terminal-deferred-note",
        patch_json={"status": "deferred"},
        actor="codex",
    )

    status = repo.status(project_id=project_id)
    blockers = repo.blockers(project_id=project_id)

    assert status.blocked_ticket_count == 1
    assert [ticket.key for ticket in blockers.blocked] == ["terminal-open-blocked"]


def test_tracker_patch_rejects_unsupported_shapes(
    session: Session,
    project_id: int,
) -> None:
    repo = TrackerRepository(session)
    repo.create_task(
        project_id=project_id,
        key="patch-shape",
        title="Patch shape",
        created_by="codex",
    )
    repo.create_ticket(
        project_id=project_id,
        task_key="patch-shape",
        key="patch-ticket",
        title="Patch ticket",
        created_by="codex",
    )

    with pytest.raises(ValidationError, match=r"patch_json\.tickets must be an object"):
        repo.patch(
            project_id=project_id,
            patch_json={
                "tickets": [
                    {"key": "patch-ticket", "status": "complete"},
                ],
            },
            actor="codex",
        )


def test_run_plan_lifecycle_mirrors_tracker(session: Session, project_id: int) -> None:
    plan = (
        RunPlanRepository(session)
        .create(
            project_id=project_id,
            run_plan_json={
                "schema_version": "stackos.run-plan.v1",
                "key": "tracker.workflow.run",
                "title": "Tracker Workflow",
                "steps": [
                    {"id": "prepare", "title": "Prepare", "success_criteria": ["Prepared"]},
                    {
                        "id": "deliver",
                        "title": "Deliver",
                        "depends_on": ["prepare"],
                        "success_criteria": ["Delivered"],
                    },
                ],
            },
            created_by="codex",
        )
        .data
    )

    tracker = TrackerRepository(session)
    snapshot = tracker.get(project_id=project_id, run_plan_id=plan.id)
    assert len(snapshot.tasks) == 1
    assert snapshot.tasks[0].key == f"workflow-{plan.id}"
    assert {ticket.key for ticket in snapshot.tickets} == {
        f"workflow-{plan.id}-prepare",
        f"workflow-{plan.id}-deliver",
    }
    assert snapshot.dependencies[0].depends_on_ticket_key == f"workflow-{plan.id}-prepare"

    started = RunPlanRepository(session).start(plan.id, project_id=project_id).data
    claimed = (
        RunPlanRepository(session)
        .claim_step(
            run_plan_id=plan.id,
            run_id=started.run_id,
            step_id="prepare",
            claimed_by="codex",
        )
        .data
    )
    assert claimed.status == "running"

    running_ticket = tracker.brief(
        project_id=project_id,
        ticket_key=f"workflow-{plan.id}-prepare",
    ).ticket
    assert running_ticket.status == TrackerItemStatus.IN_PROGRESS
    assert running_ticket.assignee == "codex"
    assert running_ticket.run_id == started.run_id

    RunPlanRepository(session).record_step(
        run_plan_id=plan.id,
        run_id=started.run_id,
        step_id="prepare",
        status=RunPlanStepStatus.SUCCESS,
        result_json={"summary": "Prepared"},
    )
    complete_ticket = tracker.brief(
        project_id=project_id,
        ticket_key=f"workflow-{plan.id}-prepare",
    ).ticket
    assert complete_ticket.status == TrackerItemStatus.COMPLETE
    assert complete_ticket.outcome == "Prepared"
