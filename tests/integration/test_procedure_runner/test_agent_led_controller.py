"""Agent-led procedure controller coverage."""

from __future__ import annotations

from sqlmodel import Session, select

from content_stack.db.models import (
    ProcedureRunStepStatus,
    PublishTarget,
    PublishTargetKind,
    Run,
    RunStatus,
)
from content_stack.procedures.runner import ProcedureRunner
from content_stack.repositories.runs import ProcedureRunStepRepository


def _record_successes_until(runner: ProcedureRunner, run_id: int, stop_before: str) -> None:
    for step_id in (
        "brief",
        "outline",
        "draft-intro",
        "draft-body",
        "draft-conclusion",
        "editor",
        "humanizer",
        "eeat-gate",
        "image-generator",
        "alt-text-auditor",
        "schema-emitter",
        "interlinker",
        "publish",
    ):
        if step_id == stop_before:
            return
        runner.record_step(
            run_id=run_id,
            step_id=step_id,
            status=ProcedureRunStepStatus.SUCCESS,
            output_json={"step_id": step_id, "article_id": 42},
        )


async def test_start_opens_skeleton_without_executing_steps(
    runner: ProcedureRunner,
    scenario: dict[str, int],
) -> None:
    """``start`` creates durable state and leaves execution to the caller."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )

    assert envelope["slug"] == "04-topic-to-published"
    assert envelope["orchestration_mode"] == "agent-led"
    assert envelope["run_token"]

    current = runner.current_step(run_id=envelope["run_id"])
    assert current["next_action"] == "claim_step"
    assert current["current_step"]["step_id"] == "brief"
    assert current["current_step"]["status"] == ProcedureRunStepStatus.PENDING
    assert current["current_step"]["skill"] == "01-research/content-brief"
    assert current["current_step"]["skill_body"]
    assert "article.create" in current["current_step"]["allowed_tools"]


async def test_claim_and_record_advance_agent_led_step(
    runner: ProcedureRunner,
    scenario: dict[str, int],
    engine: object,
) -> None:
    """Claim binds the skill grant; record stores output and returns the next step."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    run_id = envelope["run_id"]

    claimed = runner.claim_step(run_id=run_id, step_id="brief")
    assert claimed["next_action"] == "execute_step"
    assert claimed["current_step"]["status"] == ProcedureRunStepStatus.RUNNING

    with Session(engine) as session:
        row = session.get(Run, run_id)
        assert row is not None
        assert (row.metadata_json or {})["skill_name"] == "01-research/content-brief"

    recorded = runner.record_step(
        run_id=run_id,
        step_id="brief",
        status=ProcedureRunStepStatus.SUCCESS,
        output_json={"article_id": 42, "brief_set": True},
    )
    assert recorded["next_action"] == "claim_step"
    assert recorded["current_step"]["step_id"] == "outline"
    assert recorded["previous_outputs"]["brief"]["article_id"] == 42

    with Session(engine) as session:
        row = session.get(Run, run_id)
        assert row is not None
        assert (row.metadata_json or {})["skill_name"] == "04-topic-to-published"


async def test_only_final_publish_step_is_target_resolved(
    runner: ProcedureRunner,
    scenario: dict[str, int],
) -> None:
    """Schema and interlink steps keep their authored skills before publish."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    run_id = envelope["run_id"]

    for step_id in (
        "brief",
        "outline",
        "draft-intro",
        "draft-body",
        "draft-conclusion",
        "editor",
        "humanizer",
        "eeat-gate",
        "image-generator",
        "alt-text-auditor",
    ):
        runner.record_step(
            run_id=run_id,
            step_id=step_id,
            status=ProcedureRunStepStatus.SUCCESS,
            output_json={"step_id": step_id, "article_id": 42},
        )

    current = runner.current_step(run_id=run_id)["current_step"]
    assert current["step_id"] == "schema-emitter"
    assert current["skill"] == "04-publishing/schema-emitter"
    assert "schema.set" in current["allowed_tools"]
    assert "publish.recordPublish" not in current["allowed_tools"]
    assert "target_id" not in current["args"]

    runner.record_step(
        run_id=run_id,
        step_id="schema-emitter",
        status=ProcedureRunStepStatus.SUCCESS,
        output_json={"step_id": "schema-emitter", "article_id": 42},
    )
    current = runner.current_step(run_id=run_id)["current_step"]
    assert current["step_id"] == "interlinker"
    assert current["skill"] == "04-publishing/interlinker"
    assert "publish.recordPublish" not in current["allowed_tools"]
    assert "target_id" not in current["args"]

    runner.record_step(
        run_id=run_id,
        step_id="interlinker",
        status=ProcedureRunStepStatus.SUCCESS,
        output_json={"step_id": "interlinker", "article_id": 42},
    )
    current = runner.current_step(run_id=run_id)["current_step"]
    assert current["step_id"] == "publish"
    assert current["skill"] == "04-publishing/nuxt-content-publish"
    assert "publish.recordPublish" in current["allowed_tools"]
    assert current["args"]["target_id"] > 0


async def test_publish_step_without_primary_target_uses_agent_publish(
    runner: ProcedureRunner,
    scenario: dict[str, int],
    engine: object,
) -> None:
    """Procedure 4 can publish without binding a target to the project."""
    with Session(engine) as session:
        targets = session.exec(
            select(PublishTarget).where(PublishTarget.project_id == scenario["project_id"])
        ).all()
        for target in targets:
            target.is_active = False
            session.add(target)
        session.commit()

    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    run_id = envelope["run_id"]
    _record_successes_until(runner, run_id, "publish")

    current = runner.current_step(run_id=run_id)["current_step"]
    assert current["step_id"] == "publish"
    assert current["skill"] == "04-publishing/agent-publish"
    assert "publish.recordExternal" in current["allowed_tools"]
    assert "publish.recordPublish" not in current["allowed_tools"]
    assert "target_id" not in current["args"]


async def test_unsupported_primary_publish_target_falls_back_to_agent_publish(
    runner: ProcedureRunner,
    scenario: dict[str, int],
    engine: object,
) -> None:
    """Unsupported target kinds stay targetless instead of pretending to be Nuxt."""
    with Session(engine) as session:
        target = session.exec(
            select(PublishTarget).where(
                PublishTarget.project_id == scenario["project_id"],
                PublishTarget.is_primary.is_(True),  # type: ignore[union-attr,attr-defined]
            )
        ).one()
        target.kind = PublishTargetKind.HUGO
        session.add(target)
        session.commit()

    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    run_id = envelope["run_id"]
    _record_successes_until(runner, run_id, "interlinker")

    after = runner.record_step(
        run_id=run_id,
        step_id="interlinker",
        status=ProcedureRunStepStatus.SUCCESS,
        output_json={"step_id": "interlinker", "article_id": 42},
    )
    current = after["current_step"]
    assert current["step_id"] == "publish"
    assert current["skill"] == "04-publishing/agent-publish"
    assert "publish.recordExternal" in current["allowed_tools"]
    assert "target_id" not in current["args"]


async def test_recording_all_steps_success_marks_run_success(
    runner: ProcedureRunner,
    scenario: dict[str, int],
    engine: object,
) -> None:
    """The controller closes the run once every procedure step is terminal."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    run_id = envelope["run_id"]

    for step_id in (
        "brief",
        "outline",
        "draft-intro",
        "draft-body",
        "draft-conclusion",
        "editor",
        "humanizer",
        "eeat-gate",
        "image-generator",
        "alt-text-auditor",
        "schema-emitter",
        "interlinker",
        "publish",
    ):
        runner.claim_step(run_id=run_id, step_id=step_id)
        runner.record_step(
            run_id=run_id,
            step_id=step_id,
            status=ProcedureRunStepStatus.SUCCESS,
            output_json={"step_id": step_id, "article_id": 42},
        )

    final = runner.current_step(run_id=run_id)
    assert final["next_action"] == "run_success"
    assert final["current_step"] is None
    with Session(engine) as session:
        row = session.get(Run, run_id)
        assert row is not None
        assert row.status == RunStatus.SUCCESS


async def test_resume_reopens_aborted_run_without_dispatching(
    runner: ProcedureRunner,
    scenario: dict[str, int],
    engine: object,
) -> None:
    """``resume`` returns the run to caller-managed running state."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    run_id = envelope["run_id"]
    await runner.abort(run_id=run_id)

    resumed = await runner.resume(run_id=run_id)
    assert resumed["run_id"] == run_id
    assert resumed["orchestration_mode"] == "agent-led"
    with Session(engine) as session:
        row = session.get(Run, run_id)
        assert row is not None
        assert row.status == RunStatus.RUNNING
        assert (row.metadata_json or {})["agent_control"]["state"] == "waiting_for_agent"


async def test_fork_copies_prior_outputs_and_starts_from_requested_step(
    runner: ProcedureRunner,
    scenario: dict[str, int],
    engine: object,
) -> None:
    """Forking preserves prior successful outputs and leaves later steps pending."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    run_id = envelope["run_id"]
    runner.claim_step(run_id=run_id, step_id="brief")
    runner.record_step(
        run_id=run_id,
        step_id="brief",
        status=ProcedureRunStepStatus.SUCCESS,
        output_json={"article_id": 99},
    )

    forked = await runner.fork(run_id=run_id, from_step_index=1)
    with Session(engine) as session:
        fork_steps = ProcedureRunStepRepository(session).list_steps(forked["run_id"])
    assert fork_steps[0].step_id == "brief"
    assert fork_steps[0].status == ProcedureRunStepStatus.SKIPPED
    assert fork_steps[0].output_json == {"article_id": 99}

    current = runner.current_step(run_id=forked["run_id"])
    assert current["current_step"]["step_id"] == "outline"
    assert current["previous_outputs"]["brief"]["article_id"] == 99


async def test_execute_programmatic_step_records_output(
    runner: ProcedureRunner,
    scenario: dict[str, int],
) -> None:
    """Programmatic steps execute only through the explicit agent tool path."""
    envelope = await runner.start(
        slug="05-bulk-content-launch",
        args={"topic_ids": [scenario["topic_id"]], "budget_cap_usd": 10.0},
        project_id=scenario["project_id"],
    )
    run_id = envelope["run_id"]

    current = runner.current_step(run_id=run_id)
    assert current["next_action"] == "execute_programmatic_step"
    assert current["current_step"]["step_type"] == "programmatic"
    assert "procedure.executeProgrammaticStep" in current["current_step"]["allowed_tools"]

    after = await runner.execute_programmatic_step(run_id=run_id, step_id="estimate-cost")
    assert after["previous_outputs"]["estimate-cost"]["n_topics"] == 1
    assert after["current_step"]["step_id"] == "spawn-procedure-4-batch"


async def test_retry_failure_policy_requeues_then_fails_after_cap(
    runner: ProcedureRunner,
    scenario: dict[str, int],
    engine: object,
) -> None:
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    run_id = envelope["run_id"]
    _record_successes_until(runner, run_id, "draft-intro")

    retry = runner.record_step(
        run_id=run_id,
        step_id="draft-intro",
        status=ProcedureRunStepStatus.FAILED,
        error="malformed draft",
    )
    assert retry["current_step"]["step_id"] == "draft-intro"
    assert retry["current_step"]["status"] == ProcedureRunStepStatus.PENDING
    assert retry["run"].status == RunStatus.RUNNING

    failed = runner.record_step(
        run_id=run_id,
        step_id="draft-intro",
        status=ProcedureRunStepStatus.FAILED,
        error="still malformed",
    )
    assert failed["next_action"] == "run_failed"
    assert failed["current_step"] is None
    with Session(engine) as session:
        row = session.get(Run, run_id)
        assert row is not None
        assert row.status == RunStatus.FAILED


async def test_skip_failure_policy_advances_to_next_step(
    runner: ProcedureRunner,
    scenario: dict[str, int],
    engine: object,
) -> None:
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    run_id = envelope["run_id"]
    _record_successes_until(runner, run_id, "image-generator")

    out = runner.record_step(
        run_id=run_id,
        step_id="image-generator",
        status=ProcedureRunStepStatus.FAILED,
        error="image vendor unavailable",
    )
    assert out["current_step"]["step_id"] == "alt-text-auditor"
    assert out["run"].status == RunStatus.RUNNING
    with Session(engine) as session:
        steps = ProcedureRunStepRepository(session).list_steps(run_id)
    image_step = next(step for step in steps if step.step_id == "image-generator")
    assert image_step.status == ProcedureRunStepStatus.SKIPPED


async def test_loop_back_policy_resets_prior_steps_on_fix(
    runner: ProcedureRunner,
    scenario: dict[str, int],
    engine: object,
) -> None:
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    run_id = envelope["run_id"]
    _record_successes_until(runner, run_id, "eeat-gate")

    out = runner.record_step(
        run_id=run_id,
        step_id="eeat-gate",
        status=ProcedureRunStepStatus.SUCCESS,
        output_json={"article_id": 42, "verdict": "FIX", "fix_required": ["add source"]},
    )
    assert out["current_step"]["step_id"] == "editor"
    with Session(engine) as session:
        steps = ProcedureRunStepRepository(session).list_steps(run_id)
    reset = {step.step_id: step.status for step in steps}
    assert reset["editor"] == ProcedureRunStepStatus.PENDING
    assert reset["humanizer"] == ProcedureRunStepStatus.PENDING
    assert reset["eeat-gate"] == ProcedureRunStepStatus.PENDING


async def test_loop_back_policy_aborts_on_block(
    runner: ProcedureRunner,
    scenario: dict[str, int],
    engine: object,
) -> None:
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    run_id = envelope["run_id"]
    _record_successes_until(runner, run_id, "eeat-gate")

    out = runner.record_step(
        run_id=run_id,
        step_id="eeat-gate",
        status=ProcedureRunStepStatus.SUCCESS,
        output_json={"article_id": 42, "verdict": "BLOCK"},
    )
    assert out["next_action"] == "run_aborted"
    assert out["current_step"] is None
    with Session(engine) as session:
        row = session.get(Run, run_id)
        assert row is not None
        assert row.status == RunStatus.ABORTED
