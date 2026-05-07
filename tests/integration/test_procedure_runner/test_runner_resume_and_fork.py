"""Resume + fork + crash-recovery coverage (audit B-13).

The runner is **resumable**: an aborted run picks up from the next
pending step on ``resume()``. ``fork()`` clones a run from a chosen
step index, copying the source's prior outputs as the new run's
``output_json``.

Crash recovery: ``RunRepository.reap_stale`` detects orphans whose
``heartbeat_at`` is older than the configured threshold; the runner's
``resume`` API picks them back up.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from content_stack.db.models import (
    ProcedureRunStep,
    ProcedureRunStepStatus,
    Run,
    RunStatus,
)
from content_stack.procedures.llm import (
    LLMDispatcherError,
    StepDispatch,
    StubDispatcher,
)
from content_stack.procedures.runner import ProcedureRunner
from content_stack.repositories.runs import (
    ProcedureRunStepRepository,
    RunRepository,
)


async def test_resume_after_failure_picks_up_from_failed_step(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
    engine: object,
) -> None:
    """A run that aborts mid-chain resumes from the failed step."""

    state = {"first_pass": True}

    def conditional_outline(_payload: StepDispatch) -> dict:
        if state["first_pass"]:
            raise LLMDispatcherError("first try fails", skill="02-content/outline", retryable=False)
        return {"outline_md": "# Outline\n\n## A\n## B", "section_count": 2}

    dispatcher.set_handler("02-content/outline", conditional_outline)

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

    # Flip the conditional + resume.
    state["first_pass"] = False
    resume_envelope = await runner.resume(run_id=envelope["run_id"])
    assert resume_envelope["run_id"] == envelope["run_id"]
    assert resume_envelope["started"] is True
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        assert run.status == RunStatus.SUCCESS


async def test_resume_already_finished_is_noop(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """``resume`` on a successfully-finished run is a clean no-op."""
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
    no_op = await runner.resume(run_id=envelope["run_id"])
    assert no_op["started"] is False


async def test_fork_copies_prior_outputs(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """``fork`` creates a fresh run that starts from a chosen step."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    fork_envelope = await runner.fork(
        run_id=envelope["run_id"],
        from_step_index=5,  # editor onward
    )
    await runner.wait_for(fork_envelope["run_id"])
    assert fork_envelope["run_id"] != envelope["run_id"]
    assert fork_envelope["parent_run_id"] == envelope["run_id"]
    with Session(engine) as s:
        steps = ProcedureRunStepRepository(s).list_steps(fork_envelope["run_id"])
    # Steps 0..4 should be 'skipped' in the fork (carried over from source).
    skipped = [s for s in steps if s.step_index < 5]
    assert all(s.status == ProcedureRunStepStatus.SKIPPED for s in skipped), skipped
    # Steps 5..11 ran fresh.
    fresh = [s for s in steps if s.step_index >= 5]
    assert all(s.status == ProcedureRunStepStatus.SUCCESS for s in fresh), fresh


async def test_reap_stale_detects_heartbeat_drift_then_runner_resumes(
    runner: ProcedureRunner,
    scenario: dict,
    engine: object,
) -> None:
    """A run with a stale heartbeat is reaped + resumes successfully.

    Simulates the daemon-crash recovery path: kill the runner mid-step
    (we mark a step in-progress and rewind the heartbeat); on the next
    daemon boot ``RunRepository.reap_stale`` flips it to FAILED;
    ``runner.resume`` walks forward from where the kill landed.
    """

    # Open a run + pre-write the step skeleton without dispatching.
    spec = runner.get_spec("04-topic-to-published")
    _token, run_id = runner._open_run(  # type: ignore[attr-defined]
        slug=spec.slug,
        project_id=scenario["project_id"],
        parent_run_id=None,
        args={"topic_id": scenario["topic_id"]},
        spec=spec,
        client_session_id=None,
    )

    # Flip first step to RUNNING with a stale heartbeat in the past.
    with Session(engine) as s:
        run = s.get(Run, run_id)
        assert run is not None
        run.heartbeat_at = datetime.now(tz=UTC) - timedelta(minutes=15)
        s.add(run)
        # Mark the first step as 'running' so reap_stale has something
        # to flip.
        from sqlmodel import select

        first_step = s.exec(
            select(ProcedureRunStep)
            .where(ProcedureRunStep.run_id == run_id)
            .order_by(ProcedureRunStep.step_index.asc())  # type: ignore[union-attr,attr-defined]
        ).first()
        assert first_step is not None
        first_step.status = ProcedureRunStepStatus.RUNNING
        s.add(first_step)
        s.commit()

    # Reap.
    with Session(engine) as s:
        reaped = RunRepository(s).reap_stale(stale_after_seconds=60)
    assert reaped == 1

    # Resume — the runner picks up from the failed step.
    resume_envelope = await runner.resume(run_id=run_id)
    assert resume_envelope["started"] is True
    await runner.wait_for(run_id)
    with Session(engine) as s:
        run = s.get(Run, run_id)
        assert run is not None
        assert run.status == RunStatus.SUCCESS


async def test_in_flight_count_tracks_active_tasks(runner: ProcedureRunner, scenario: dict) -> None:
    """``in_flight_count`` returns 0 once tasks complete."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    # Give asyncio a tick to drain the done-callback registry cleanup.
    await asyncio.sleep(0.05)
    assert runner.in_flight_count(slug="04-topic-to-published") == 0
