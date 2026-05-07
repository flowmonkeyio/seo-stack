"""Variant application + publish-skill swap + step args + heartbeat coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from content_stack.db.models import (
    ProcedureRunStepStatus,
    PublishTarget,
    PublishTargetKind,
    Run,
    RunStatus,
)
from content_stack.procedures.llm import StepDispatch, StubDispatcher
from content_stack.procedures.runner import ProcedureRunner
from content_stack.repositories.runs import ProcedureRunStepRepository


async def test_short_form_variant_omits_image_steps(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """``variant='short-form'`` drops image-generator + alt-text-auditor."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
        variant="short-form",
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        assert run.status == RunStatus.SUCCESS
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    assert "image-generator" not in [s.step_id for s in steps]
    assert "alt-text-auditor" not in [s.step_id for s in steps]


async def test_pillar_variant_pushes_brief_args(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
) -> None:
    """``variant='pillar'`` injects ``depth_tier=heavy`` + 4000 word target into brief.args."""
    captured: dict[str, dict] = {}

    def capture_brief(payload: StepDispatch) -> dict:
        captured["brief"] = dict(payload.args)
        return {"brief_set": True, "target_word_count": 4000}

    dispatcher.set_handler("01-research/content-brief", capture_brief)
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
        variant="pillar",
    )
    await runner.wait_for(envelope["run_id"])
    assert captured["brief"].get("depth_tier") == "heavy"
    assert captured["brief"].get("target_word_count") == 4000


async def test_publish_skill_swaps_for_wordpress_target(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
    engine: object,
) -> None:
    """When the project's primary target is WordPress, the runner dispatches WP."""

    # Replace the seeded NUXT target with WordPress.
    with Session(engine) as s:
        from sqlmodel import select

        existing = s.exec(
            select(PublishTarget).where(PublishTarget.project_id == scenario["project_id"])
        ).all()
        for row in existing:
            row.is_primary = False
            row.is_active = False
            s.add(row)
        wp = PublishTarget(
            project_id=scenario["project_id"],
            kind=PublishTargetKind.WORDPRESS,
            config_json={"endpoint": "https://example.com/wp-json"},
            is_primary=True,
            is_active=True,
        )
        s.add(wp)
        s.commit()

    # Track which publish skill the dispatcher saw.
    seen_skill: dict[str, str] = {}

    def record_publish(payload: StepDispatch) -> dict:
        seen_skill["actual"] = payload.skill
        return {"published_url": "https://example.com/wp/post-1", "marked_published": True}

    dispatcher.set_handler("04-publishing/wordpress-publish", record_publish)
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    assert seen_skill.get("actual") == "04-publishing/wordpress-publish"


async def test_step_args_carry_topic_id_through_chain(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
) -> None:
    """Procedure-level ``args`` (topic_id) flow into every dispatch payload."""
    captured: dict[str, dict] = {}

    def capture_args(payload: StepDispatch) -> dict:
        captured[payload.skill] = dict(payload.args)
        return {"acked": True}

    for skill in (
        "01-research/content-brief",
        "02-content/outline",
        "02-content/editor",
    ):
        dispatcher.set_handler(skill, capture_args)

    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    for skill, args in captured.items():
        assert args.get("topic_id") == scenario["topic_id"], (skill, args)


async def test_heartbeat_advances_during_run(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """The runner's heartbeat is fresh after the run completes."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        assert run.heartbeat_at is not None
        # Heartbeat should be fresh (within the last minute).
        # Use timezone-aware; cross compare with utcnow.
        beat = run.heartbeat_at
        if beat.tzinfo is None:
            beat = beat.replace(tzinfo=UTC)
        assert datetime.now(tz=UTC) - beat < timedelta(minutes=2)


async def test_step_context_carries_previous_outputs(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
) -> None:
    """Each dispatch payload's ``context.previous_outputs`` reflects prior steps."""
    seen_contexts: dict[str, dict] = {}

    def record(payload: StepDispatch) -> dict:
        seen_contexts[payload.step_id] = dict(payload.context)
        return {"acked": True}

    for skill in ("02-content/outline", "02-content/editor"):
        dispatcher.set_handler(skill, record)
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    # Outline runs after brief — sees brief's output but not its own.
    outline_ctx = seen_contexts.get("outline", {})
    assert "brief" in outline_ctx.get("previous_outputs", {})
    assert "outline" not in outline_ctx.get("previous_outputs", {})
    # Editor runs after outline + drafts.
    editor_ctx = seen_contexts.get("editor", {})
    for prior in (
        "brief",
        "outline",
        "draft-intro",
        "draft-body",
        "draft-conclusion",
    ):
        assert prior in editor_ctx.get("previous_outputs", {}), (prior, editor_ctx)


async def test_allowed_tools_in_dispatch_payload_match_grants(
    runner: ProcedureRunner,
    dispatcher: StubDispatcher,
    scenario: dict,
) -> None:
    """Each dispatch sees the per-skill ``allowed_tools`` lifted from SKILL_TOOL_GRANTS."""
    from content_stack.mcp.permissions import SKILL_TOOL_GRANTS

    captured: dict[str, list[str]] = {}

    def record(payload: StepDispatch) -> dict:
        captured[payload.skill] = list(payload.context.get("allowed_tools", []))
        return {"acked": True}

    for skill_key in (
        "02-content/eeat-gate",
        "04-publishing/schema-emitter",
    ):
        dispatcher.set_handler(skill_key, record)

    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    for skill_key in (
        "02-content/eeat-gate",
        "04-publishing/schema-emitter",
    ):
        expected = sorted(SKILL_TOOL_GRANTS.get(skill_key, frozenset()))
        actual = captured.get(skill_key, [])
        assert actual == expected, (skill_key, actual, expected)


async def test_run_step_records_match_skeleton(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """Every step row carries a non-null started_at + ended_at after success."""
    envelope = await runner.start(
        slug="04-topic-to-published",
        args={"topic_id": scenario["topic_id"]},
        project_id=scenario["project_id"],
    )
    await runner.wait_for(envelope["run_id"])
    with Session(engine) as s:
        steps = ProcedureRunStepRepository(s).list_steps(envelope["run_id"])
    for step in steps:
        if step.status == ProcedureRunStepStatus.SUCCESS:
            assert step.started_at is not None, step.step_id
            assert step.ended_at is not None, step.step_id
