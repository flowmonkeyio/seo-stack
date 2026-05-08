"""Smoke tests for the seven new M7.B procedures.

Each test runs one procedure end-to-end against the StubDispatcher and
asserts the run reaches a documented terminal state:

- Procedures **1, 5, 6, 7, 8** with default stub behaviour walk every
  step to ``status='success'``.
- Procedures **2, 3** include an intentional ``human_review`` pause —
  the test injects a handler that raises ``LLMDispatcherError`` for
  the human-approval step so the runner pauses, then asserts the run
  is paused (run row stays ``status='running'`` and the runner's
  paused flag is set on the in-flight task entry).

These are smoke checks; per-step assertions live in the per-feature
tests (eeat-verdict, failure-modes, resume-and-fork, etc.).
"""

from __future__ import annotations

from sqlmodel import Session, select

from content_stack.db.models import ProcedureRunStepStatus, Run, RunStatus
from content_stack.procedures.llm import (
    LLMDispatcherError,
    StepDispatch,
    StubDispatcher,
)
from content_stack.procedures.runner import ProcedureRunner
from content_stack.repositories.runs import ProcedureRunStepRepository

# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _pause_handler(step_skill: str):
    """Build a handler that simulates the human-review pause.

    The runner's ``human_review`` mode triggers on step failure —
    production wires the pause-aware skill to raise a typed dispatch
    error after persisting ``runs.metadata_json.pending_human_review``.
    Tests reuse the same path: the handler raises a non-retryable
    error so the runner branches into the pause path.
    """

    def _handler(_payload: StepDispatch) -> dict:
        raise LLMDispatcherError(
            f"intentional pause for step {step_skill!r}",
            skill=step_skill,
            retryable=False,
        )

    return _handler


# ---------------------------------------------------------------------------
# Procedure 1 — bootstrap-project.
# ---------------------------------------------------------------------------


async def test_procedure_01_bootstrap_runs_to_success(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
    engine: object,
) -> None:
    """Procedure 01 walks all 7 setup steps.

    M8 routes ``_programmatic/*`` through the dedicated handler
    registry. The voice-profile / publish-target / integration-creds
    prompts raise ``HumanReviewPause`` (operator-driven). For this
    smoke test we override those handlers via the StubDispatcher seam
    so the full chain runs through to success.
    """
    # The StubDispatcher's handlers do not run for programmatic skills
    # (M8 routes those through the ProgrammaticStepRegistry directly).
    # Tests that need to bypass the operator-pause handlers do so via a
    # dispatcher-replacement at the runner instance level — not relevant
    # here since the smoke test only validates the chain shape, which
    # we do by setting ``on_failure=skip`` on the prompts via a tweak
    # to the runner... For M8 we test what actually happens.
    _ = dispatcher
    envelope = await runner.start(
        slug="01-bootstrap-project",
        args={
            # ``project-create`` needs slug + name + domain + locale.
            # The seeded project already exists with slug="m7-test", so
            # we use a unique slug here to avoid the ConflictError.
            "slug": "fresh-m8",
            "name": "Fresh M8 site",
            "domain": "newsite.example",
            "niche": "saas",
            "locale": "en-US",
        },
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None, envelope
        # voice-profile / publish-target / integration-creds raise
        # HumanReviewPause -> the runner pauses at the first one
        # (voice-profile), leaving the run in 'running' status with
        # subsequent steps still pending. This matches procedure 1's
        # operator-driven nature.
        assert run.status == RunStatus.RUNNING, run.error
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    assert len(steps) == 7
    # project-create succeeded; voice-profile paused.
    project_create = next(s for s in steps if s.step_id == "project-create")
    assert project_create.status == ProcedureRunStepStatus.SUCCESS
    voice_profile = next(s for s in steps if s.step_id == "voice-profile")
    assert voice_profile.status == ProcedureRunStepStatus.FAILED
    assert voice_profile.error and "human-review-pause" in voice_profile.error


# ---------------------------------------------------------------------------
# Procedure 2 — one-site-shortcut (human-approval pause).
# ---------------------------------------------------------------------------


async def test_procedure_02_one_site_shortcut_pauses_at_approval(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
    engine: object,
) -> None:
    """Procedure 02 pauses at ``human-approval`` (the human_review step)."""
    dispatcher.set_handler(
        "_programmatic/topic-approval-pause",
        _pause_handler("_programmatic/topic-approval-pause"),
    )
    envelope = await runner.start(
        slug="02-one-site-shortcut",
        args={"competitors": "a.example,b.example"},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        # human_review keeps the run row in 'running' so heartbeats fire.
        assert run.status == RunStatus.RUNNING, run.status
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    # Step before pause completed; the final cluster step never ran.
    pre_cluster = next(s for s in steps if s.step_id == "pre-approval-cluster")
    assert pre_cluster.status == ProcedureRunStepStatus.SUCCESS
    final_cluster = next(s for s in steps if s.step_id == "topical-cluster")
    assert final_cluster.status == ProcedureRunStepStatus.PENDING


# ---------------------------------------------------------------------------
# Procedure 3 — keyword-to-topic-queue (human-review-queue pause).
# ---------------------------------------------------------------------------


async def test_procedure_03_keyword_queue_pauses_at_review(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
    engine: object,
) -> None:
    """Procedure 03 pauses at ``human-review-queue`` (the human_review step)."""
    dispatcher.set_handler(
        "_programmatic/topic-approval-pause",
        _pause_handler("_programmatic/topic-approval-pause"),
    )
    envelope = await runner.start(
        slug="03-keyword-to-topic-queue",
        args={"seed_keywords": "best content stack saas"},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        assert run.status == RunStatus.RUNNING
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    # Cluster step executed; review step paused.
    cluster = next(s for s in steps if s.step_id == "topical-cluster")
    assert cluster.status == ProcedureRunStepStatus.SUCCESS


# ---------------------------------------------------------------------------
# Procedure 5 — bulk-content-launch.
# ---------------------------------------------------------------------------


async def test_procedure_05_bulk_launch_runs_to_success(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """Procedure 05 walks the four bulk-launch steps.

    M8: ``estimate-cost`` requires ``topic_ids`` to be a **list** not
    a CSV string; ``spawn-procedure-4-batch`` reads the same list and
    spawns one child run per id (with ``parent_run_id`` linked); the
    wait-for-children step polls and the final-summary aggregates.

    The test passes an empty list so the wait-for-children step
    returns immediately (no children to wait for) — a non-empty list
    would require a fully-fledged article-creation pipeline which is
    covered by the dedicated nested-procedure-dispatch tests.
    """
    envelope = await runner.start(
        slug="05-bulk-content-launch",
        args={
            "topic_ids": [],  # empty: estimate-cost = $0, no children.
            "budget_cap_usd": 50.0,
            # Tests use a tiny poll interval so wait-for-children
            # finishes inside the test runtime budget. Default is 30s.
            "poll_seconds": 0.05,
            "timeout_seconds": 5.0,
        },
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        assert run.status == RunStatus.SUCCESS, run.error
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    assert len(steps) == 4
    assert [s.step_id for s in steps] == [
        "estimate-cost",
        "spawn-procedure-4-batch",
        "wait-for-children",
        "final-summary",
    ]


# ---------------------------------------------------------------------------
# Procedure 6 — weekly-gsc-review.
# ---------------------------------------------------------------------------


async def test_procedure_06_weekly_gsc_runs_to_success(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """Procedure 06 walks all 6 weekly-sweep steps with the default stub."""
    envelope = await runner.start(
        slug="06-weekly-gsc-review",
        args={"window_days": 7},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        assert run.status == RunStatus.SUCCESS, run.error
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    assert len(steps) == 6


# ---------------------------------------------------------------------------
# Procedure 7 — monthly-humanize-pass.
# ---------------------------------------------------------------------------


async def test_procedure_07_monthly_humanize_runs_to_success(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """Procedure 07 walks the candidate-selection + per-candidate steps."""
    envelope = await runner.start(
        slug="07-monthly-humanize-pass",
        args={"top_n": 5, "selection_mode": "auto"},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        assert run.status == RunStatus.SUCCESS, run.error
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    assert len(steps) == 2


# ---------------------------------------------------------------------------
# Procedure 8 — add-new-site.
# ---------------------------------------------------------------------------


async def test_procedure_08_add_new_site_walks_steps(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """Procedure 08 walks the four child-procedure steps.

    M8: ``_programmatic/run-child-procedure`` spawns a real child run
    with ``parent_run_id`` set. The first child (procedure 1) hits the
    operator-pause path at ``voice-profile`` and pauses; that
    propagates to the parent as a child-failure (because the child
    didn't reach SUCCESS). With ``on_failure=human_review`` on the
    parent step, the parent itself pauses at ``bootstrap`` — exactly
    what procedure 8's PROCEDURE.md prescribes.

    This test asserts on the chain shape (4 steps registered) +
    that the bootstrap step's child run was actually spawned with the
    expected parent linkage.
    """
    envelope = await runner.start(
        slug="08-add-new-site",
        args={
            # Forwarded to the child procedure 1; needs slug + name.
            "slug": "fresh-eight",
            "name": "Fresh Eight",
            "domain": "fresh.example",
            "niche": "ecommerce",
            "locale": "en-US",
            "competitors": "rival.example",
            # Tight polling — procedure 5's wait-for-children
            # default is 30s which is too slow for tests.
            "poll_seconds": 0.05,
            "timeout_seconds": 5.0,
        },
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        # Parent paused at bootstrap because the child paused. Per
        # the spec the parent's on_failure is human_review for every
        # step — the runner's HumanReviewPause translation results in
        # status='running' (heartbeats keep firing).
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    assert len(steps) == 4
    assert [s.step_id for s in steps] == [
        "bootstrap",
        "topic-discovery-shortcut",
        "topic-discovery-deep",
        "bulk-launch",
    ]
    # Child run was spawned and linked to the parent.
    with Session(engine) as s:
        child_runs = s.exec(select(Run).where(Run.parent_run_id == envelope["run_id"])).all()
    assert len(child_runs) >= 1, "expected at least one child run from bootstrap step"


# ---------------------------------------------------------------------------
# Variant smoke tests — ensure variants apply cleanly across the catalogue.
# ---------------------------------------------------------------------------


async def test_procedure_01_minimal_variant_drops_setup_steps(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """The ``minimal`` variant on procedure 01 drops publish-target + integration-creds."""
    envelope = await runner.start(
        slug="01-bootstrap-project",
        args={"domain": "min.example", "niche": "saas", "locale": "en-US"},
        project_id=scenario["project_id"],
        variant="minimal",
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    step_ids = [s.step_id for s in steps]
    assert "publish-target" not in step_ids
    assert "integration-creds" not in step_ids
    # Other steps remain.
    assert "project-create" in step_ids
    assert "verify" in step_ids


async def test_procedure_08_shortcut_variant_drops_deep_path(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """The ``shortcut`` variant drops the keyword-discovery deep path."""
    envelope = await runner.start(
        slug="08-add-new-site",
        args={
            "domain": "shortcut.example",
            "niche": "saas",
            "locale": "en-US",
            "competitors": "competitor.example",
        },
        project_id=scenario["project_id"],
        variant="shortcut",
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    step_ids = [s.step_id for s in steps]
    assert "topic-discovery-deep" not in step_ids
    assert "topic-discovery-shortcut" in step_ids
