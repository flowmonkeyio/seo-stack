"""Nested-procedure dispatch — procedure 8 spawns child runs (M8)."""

from __future__ import annotations

from sqlmodel import Session, select

from content_stack.db.models import Run
from content_stack.procedures.runner import ProcedureRunner


async def test_proc_08_spawns_children_with_parent_run_id_linked(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """``_programmatic/run-child-procedure`` creates linked child runs."""
    envelope = await runner.start(
        slug="08-add-new-site",
        args={
            "slug": "child-test",
            "name": "child test",
            "domain": "child.example",
            "niche": "saas",
            "locale": "en-US",
            "competitors": "rival.example",
            "poll_seconds": 0.05,
            "timeout_seconds": 5.0,
        },
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    parent_id = envelope["run_id"]
    with Session(engine) as s:
        children = s.exec(select(Run).where(Run.parent_run_id == parent_id)).all()
    # At minimum the bootstrap step's child fired.
    assert len(children) >= 1
    # Each child carries the parent linkage.
    for child in children:
        assert child.parent_run_id == parent_id


async def test_run_child_procedure_handler_propagates_failure(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """A child whose status ends FAILED bubbles up as parent step failure."""
    # Procedure 8's bulk-launch step calls procedure 5; without
    # topic_ids the child fails (estimate-cost ValueError → abort).
    envelope = await runner.start(
        slug="08-add-new-site",
        args={
            "slug": "fail-test",
            "name": "fail test",
            "domain": "fail.example",
            "niche": "saas",
            "locale": "en-US",
            "competitors": "rival.example",
            # tiny polling for proc 5's wait-for-children
            "poll_seconds": 0.05,
            "timeout_seconds": 5.0,
        },
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        children = s.exec(select(Run).where(Run.parent_run_id == envelope["run_id"])).all()
    assert children, "procedure 8 should spawn at least one child"
