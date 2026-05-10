"""Agent-led procedure controller coverage."""

from __future__ import annotations

from sqlmodel import Session

from content_stack.db.models import ProcedureRunStepStatus, Run, RunStatus
from content_stack.procedures.runner import ProcedureRunner
from content_stack.repositories.runs import ProcedureRunStepRepository


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
