"""Per-step ``on_failure`` mode coverage.

Procedure 4 declares all five failure modes across its 12 steps:

- ``abort`` (brief / outline / editor / schema-emitter / publish)
- ``retry`` (draft-intro / draft-body / draft-conclusion, max_retries=1)
- ``loop_back`` (eeat-gate)
- ``skip`` (image-generator / alt-text-auditor / interlinker)

These tests exercise abort + retry + skip paths with explicit
``LLMDispatcherError`` raises from the StubDispatcher.
"""

from __future__ import annotations

from sqlmodel import Session

from content_stack.db.models import (
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
from content_stack.repositories.runs import ProcedureRunStepRepository


async def test_abort_step_terminates_run(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
    engine: object,
) -> None:
    """A failed ``abort``-mode step terminates the run with FAILED."""

    def fail(_payload: StepDispatch) -> dict:
        raise LLMDispatcherError("outline failed", skill="02-content/outline", retryable=False)

    dispatcher.set_handler("02-content/outline", fail)
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
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    outline = next(s for s in steps if s.step_id == "outline")
    assert outline.status == ProcedureRunStepStatus.FAILED
    assert outline.error is not None
    assert "outline failed" in outline.error
    # Steps after outline never ran.
    editor = next(s for s in steps if s.step_id == "editor")
    assert editor.status == ProcedureRunStepStatus.PENDING


async def test_retry_recovers_after_first_failure(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
    engine: object,
) -> None:
    """A ``retry`` step that fails once + succeeds on the second attempt finishes."""
    state = {"calls": 0}

    def flaky(_payload: StepDispatch) -> dict:
        state["calls"] += 1
        if state["calls"] == 1:
            raise LLMDispatcherError("transient", skill="02-content/draft-intro", retryable=True)
        return {"section": "intro", "draft_appended": True}

    dispatcher.set_handler("02-content/draft-intro", flaky)
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
    assert state["calls"] == 2


async def test_retry_exhaustion_aborts(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
    engine: object,
) -> None:
    """A ``retry`` step that exhausts ``max_retries`` aborts the run."""

    def always_fail(_payload: StepDispatch) -> dict:
        raise LLMDispatcherError("always", skill="02-content/draft-intro", retryable=True)

    dispatcher.set_handler("02-content/draft-intro", always_fail)
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


async def test_skip_advances_through_failed_step(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
    engine: object,
) -> None:
    """A ``skip``-mode step that raises is recorded skipped + the chain continues."""

    def kaboom(_payload: StepDispatch) -> dict:
        raise LLMDispatcherError(
            "image gen unavailable",
            skill="03-assets/image-generator",
            retryable=False,
        )

    dispatcher.set_handler("03-assets/image-generator", kaboom)
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
    image_step = next(s for s in steps if s.step_id == "image-generator")
    assert image_step.status == ProcedureRunStepStatus.SKIPPED
    publish_step = next(s for s in steps if s.step_id == "publish")
    assert publish_step.status == ProcedureRunStepStatus.SUCCESS


async def test_abort_method_terminates_in_flight_run(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
    engine: object,
) -> None:
    """``runner.abort`` flips the row to ABORTED + cancels the asyncio task."""
    import asyncio

    async def slow(_payload: StepDispatch) -> dict:
        # Sleep long enough for the test to land an abort while the
        # task is in-flight.
        await asyncio.sleep(0.5)
        return {"finished": True}

    # Wrap the async handler with the synchronous ScriptedHandler API.
    # The dispatcher handler signature is sync; sleeping needs an async
    # workaround. Use a dedicated dispatcher subclass for this test.
    class SlowStub(StubDispatcher):
        async def dispatch(self, payload: StepDispatch) -> dict:
            await slow(payload)
            return {"acked": True}

    runner._dispatcher = SlowStub()  # type: ignore[attr-defined]
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    # Give the task a moment to start before aborting.
    await asyncio.sleep(0.05)
    await runner.abort(run_id=envelope["run_id"])
    # Wait briefly for the abort + task cleanup to settle.
    await asyncio.sleep(0.05)
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        assert run.status == RunStatus.ABORTED
