"""Smoke tests — start, walk, terminal-status transitions."""

from __future__ import annotations

from sqlmodel import Session

from content_stack.db.models import (
    ProcedureRunStepStatus,
    Run,
    RunStatus,
)
from content_stack.procedures.runner import ProcedureRunner
from content_stack.repositories.runs import ProcedureRunStepRepository


async def test_start_returns_envelope(runner: ProcedureRunner, scenario: dict) -> None:
    """``start`` returns a full envelope without blocking on execution."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    assert envelope["slug"] == "04-topic-to-published"
    assert envelope["started"] is True
    assert envelope["run_id"] >= 1
    assert len(envelope["run_token"]) > 16
    assert envelope["status_url"].endswith(f"/{envelope['run_id']}")
    # Wait for the asyncio task so the test is deterministic at teardown.
    await runner.wait_for(envelope["run_id"])


async def test_start_pre_writes_step_skeleton(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """Every declared step gets a ``procedure_run_steps`` row up front."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    assert len(steps) == 12
    assert [s.step_id for s in steps] == [
        "brief",
        "outline",
        "draft-intro",
        "draft-body",
        "draft-conclusion",
        "editor",
        "eeat-gate",
        "image-generator",
        "alt-text-auditor",
        "schema-emitter",
        "interlinker",
        "publish",
    ]


async def test_full_chain_reaches_success_with_stubs(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """The default StubDispatcher chain ends with ``runs.status='success''."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        assert run.status == RunStatus.SUCCESS
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    statuses = [step.status for step in steps]
    assert all(s == ProcedureRunStepStatus.SUCCESS for s in statuses), statuses


async def test_unknown_slug_raises_not_found(runner: ProcedureRunner) -> None:
    """``start`` with an unknown slug surfaces ``NotFoundError``."""
    import pytest

    from content_stack.repositories.base import NotFoundError

    with pytest.raises(NotFoundError):
        await runner.start(slug="ghost-procedure", args={}, project_id=1)


async def test_list_procedures_includes_workhorse(runner: ProcedureRunner) -> None:
    """``list_procedures`` advertises the M7.A procedure 04."""
    slugs = runner.list_procedures()
    assert "04-topic-to-published" in slugs


async def test_each_step_persists_output_json(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """Every step's StubDispatcher output lands in ``output_json``."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    for step in steps:
        assert step.output_json is not None, step.step_id
