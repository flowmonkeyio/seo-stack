"""EEAT three-verdict branch coverage (audit BLOCKER-09).

Procedure 4's ``eeat-gate`` step is the only step the runner branches
on a verdict for:

- ``SHIP`` advances.
- ``FIX`` loops back to ``editor``; capped at 3 iterations.
- ``BLOCK`` aborts the run with ``runs.status='aborted'`` (and would
  flip the article status to ``aborted-publish`` if we tracked an
  article in the runner — covered separately).
"""

from __future__ import annotations

from sqlmodel import Session

from content_stack.db.models import (
    ProcedureRunStepStatus,
    Run,
    RunStatus,
)
from content_stack.procedures.llm import StepDispatch, StubDispatcher
from content_stack.procedures.runner import ProcedureRunner
from content_stack.repositories.runs import ProcedureRunStepRepository


async def test_block_verdict_aborts_run(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
    engine: object,
) -> None:
    """``verdict='BLOCK'`` aborts immediately with ``runs.status='aborted'``."""

    def block_handler(_payload: StepDispatch) -> dict:
        return {
            "verdict": "BLOCK",
            "vetoes_failed": ["T04"],
            "fix_required": [],
        }

    dispatcher.set_handler("02-content/eeat-gate", block_handler)
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        assert run.status == RunStatus.ABORTED
        assert run.error is not None
        assert "BLOCK" in run.error
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    # Steps after eeat-gate should still be 'pending' (never executed).
    publish = next(s for s in steps if s.step_id == "publish")
    assert publish.status == ProcedureRunStepStatus.PENDING


async def test_fix_verdict_loops_back_to_editor_until_ship(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
    engine: object,
) -> None:
    """First ``FIX`` loops back to editor; the second pass returns SHIP."""

    state = {"calls": 0}

    def fix_then_ship(_payload: StepDispatch) -> dict:
        state["calls"] += 1
        if state["calls"] == 1:
            return {
                "verdict": "FIX",
                "fix_required": [{"criterion_id": "C04", "finding": "X", "severity": "med"}],
            }
        return {
            "verdict": "SHIP",
            "fix_required": [],
        }

    dispatcher.set_handler("02-content/eeat-gate", fix_then_ship)
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
    # eeat-gate dispatcher fired twice (FIX, then SHIP).
    assert dispatcher.calls.get("02-content/eeat-gate", 0) == 2
    # Editor fired twice as well — once on the original walk + once after the loop.
    assert dispatcher.calls.get("02-content/editor", 0) == 2


async def test_fix_loop_exceeds_cap_aborts(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
    engine: object,
) -> None:
    """When ``FIX`` keeps coming, the runner aborts after the configured cap."""

    def always_fix(_payload: StepDispatch) -> dict:
        return {
            "verdict": "FIX",
            "fix_required": [{"criterion_id": "C04", "finding": "X", "severity": "med"}],
        }

    dispatcher.set_handler("02-content/eeat-gate", always_fix)
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        assert run.status == RunStatus.FAILED
        assert run.error is not None
        assert "loop-back limit exceeded" in run.error
    # The runner caps the editor at ``procedure_runner_max_loop_iterations``
    # (default 3) — we expect the original editor + 3 loop-back replays = 4.
    assert dispatcher.calls.get("02-content/editor", 0) == 4
