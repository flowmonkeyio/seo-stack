"""Per-handler unit-style tests for the M8 ``_programmatic/`` registry."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from content_stack.procedures.programmatic import (
    HumanReviewPause,
    ProgrammaticStepRegistry,
    StepContext,
)
from content_stack.procedures.runner import ProcedureRunner
from content_stack.repositories.projects import ProjectRepository


def _ctx(
    *,
    runner: ProcedureRunner,
    project_id: int,
    args: dict,
    run_id: int = 1,
    step_id: str = "test-step",
    previous_outputs: dict | None = None,
) -> StepContext:
    return StepContext(
        runner=runner,
        run_id=run_id,
        step_id=step_id,
        project_id=project_id,
        args=args,
        previous_outputs=dict(previous_outputs or {}),
    )


async def test_project_create_handler_creates_project(
    runner: ProcedureRunner, scenario: dict
) -> None:
    """``project-create`` writes a new project row + returns its id."""
    handler = ProgrammaticStepRegistry.get("project-create")
    assert handler is not None
    out = await handler(
        _ctx(
            runner=runner,
            project_id=scenario["project_id"],
            args={
                "slug": "handler-test",
                "name": "Handler Test",
                "domain": "handler.example.com",
                "locale": "en-US",
                "niche": "saas",
            },
        )
    )
    assert out["created"] is True
    assert isinstance(out["project_id"], int)


async def test_project_create_validates_required_args(
    runner: ProcedureRunner, scenario: dict
) -> None:
    """Missing slug/name/domain/locale → ValueError."""
    handler = ProgrammaticStepRegistry.get("project-create")
    assert handler is not None
    with pytest.raises(ValueError, match="missing required args"):
        await handler(
            _ctx(
                runner=runner,
                project_id=scenario["project_id"],
                args={"slug": "x"},  # missing name/domain/locale
            )
        )


async def test_voice_profile_prompt_raises_human_review(
    runner: ProcedureRunner, scenario: dict
) -> None:
    """The voice-profile-prompt handler always pauses for human input."""
    handler = ProgrammaticStepRegistry.get("voice-profile-prompt")
    assert handler is not None
    with pytest.raises(HumanReviewPause):
        await handler(_ctx(runner=runner, project_id=scenario["project_id"], args={}))


async def test_publish_target_prompt_raises_human_review(
    runner: ProcedureRunner, scenario: dict
) -> None:
    handler = ProgrammaticStepRegistry.get("publish-target-prompt")
    assert handler is not None
    with pytest.raises(HumanReviewPause):
        await handler(_ctx(runner=runner, project_id=scenario["project_id"], args={}))


async def test_topic_approval_pause_handler_raises_human_review(
    runner: ProcedureRunner, scenario: dict
) -> None:
    """Procedures 2 + 3 use this to wait for the operator's queue approval."""
    handler = ProgrammaticStepRegistry.get("topic-approval-pause")
    assert handler is not None
    with pytest.raises(HumanReviewPause):
        await handler(_ctx(runner=runner, project_id=scenario["project_id"], args={}))


async def test_compliance_seed_returns_template_for_known_niche(
    runner: ProcedureRunner, engine: object
) -> None:
    """The ``igaming`` niche seeds responsible-gambling + affiliate-disclosure."""
    with Session(engine) as s:
        repo = ProjectRepository(s)
        env = repo.create(
            slug="igaming-test",
            name="igaming",
            domain="igaming.example.com",
            locale="en-US",
            niche="igaming",
        )
        new_pid = env.data.id
        assert new_pid is not None
    handler = ProgrammaticStepRegistry.get("compliance-seed")
    assert handler is not None
    out = await handler(_ctx(runner=runner, project_id=new_pid, args={}))
    assert out["seed_count"] == 2
    assert "responsible-gambling" in out["seeded_kinds"]


async def test_compliance_seed_no_op_for_unknown_niche(
    runner: ProcedureRunner, engine: object
) -> None:
    """Unknown niche → empty template (operator authors manually)."""
    with Session(engine) as s:
        repo = ProjectRepository(s)
        env = repo.create(
            slug="weird-niche",
            name="weird",
            domain="weird.example.com",
            locale="en-US",
            niche="nft-soccer",
        )
        new_pid = env.data.id
        assert new_pid is not None
    handler = ProgrammaticStepRegistry.get("compliance-seed")
    assert handler is not None
    out = await handler(_ctx(runner=runner, project_id=new_pid, args={}))
    assert out["seed_count"] == 0


async def test_bulk_cost_estimator_raises_on_budget_breach(
    runner: ProcedureRunner, scenario: dict
) -> None:
    """Per audit M-25: budget breach raises before fanning out."""
    handler = ProgrammaticStepRegistry.get("bulk-cost-estimator")
    assert handler is not None
    # 10 topics * $0.50 = $5; budget cap $1 → breach.
    with pytest.raises(ValueError, match="exceeds budget cap"):
        await handler(
            _ctx(
                runner=runner,
                project_id=scenario["project_id"],
                args={"topic_ids": list(range(1, 11)), "budget_cap_usd": 1.0},
            )
        )


async def test_bulk_cost_estimator_passes_under_cap(
    runner: ProcedureRunner, scenario: dict
) -> None:
    """Budget cap exceeds the estimate → returns the summary cleanly."""
    handler = ProgrammaticStepRegistry.get("bulk-cost-estimator")
    assert handler is not None
    out = await handler(
        _ctx(
            runner=runner,
            project_id=scenario["project_id"],
            args={"topic_ids": [1, 2], "budget_cap_usd": 100.0},
        )
    )
    assert out["n_topics"] == 2
    assert out["estimated_total_usd"] == pytest.approx(1.0)


async def test_bulk_cost_estimator_accepts_csv_topic_ids(
    runner: ProcedureRunner, scenario: dict
) -> None:
    """Procedure 5 accepts the documented comma-separated topic id input."""
    handler = ProgrammaticStepRegistry.get("bulk-cost-estimator")
    assert handler is not None
    out = await handler(
        _ctx(
            runner=runner,
            project_id=scenario["project_id"],
            args={"topic_ids": "1, 2,3", "budget_cap_usd": 100.0},
        )
    )
    assert out["n_topics"] == 3
    assert out["estimated_total_usd"] == pytest.approx(1.5)


async def test_bulk_cost_estimator_all_approved_selects_project_topics(
    runner: ProcedureRunner, scenario: dict
) -> None:
    """Procedure 5's all-approved flag pulls approved topics for the project."""
    handler = ProgrammaticStepRegistry.get("bulk-cost-estimator")
    assert handler is not None
    out = await handler(
        _ctx(
            runner=runner,
            project_id=scenario["project_id"],
            args={"all_approved": True, "budget_cap_usd": 100.0},
        )
    )
    assert out["n_topics"] == 1


async def test_select_refresh_candidates_top_n_mode(
    runner: ProcedureRunner, scenario: dict
) -> None:
    """``selection_mode=top-n`` reads the candidate_ids arg directly."""
    handler = ProgrammaticStepRegistry.get("select-refresh-candidates")
    assert handler is not None
    out = await handler(
        _ctx(
            runner=runner,
            project_id=scenario["project_id"],
            args={
                "selection_mode": "top-n",
                "candidate_ids": "10, 20, 30",
                "top_n": 2,
            },
        )
    )
    assert out["candidate_ids"] == [10, 20]


async def test_select_refresh_candidates_auto_mode(runner: ProcedureRunner, scenario: dict) -> None:
    """``selection_mode=auto`` queries ``ArticleRepository.list_due_for_refresh``."""
    handler = ProgrammaticStepRegistry.get("select-refresh-candidates")
    assert handler is not None
    out = await handler(
        _ctx(
            runner=runner,
            project_id=scenario["project_id"],
            args={"selection_mode": "auto", "top_n": 5},
        )
    )
    # No published articles in the seeded scenario → empty list.
    assert out["candidate_ids"] == []


async def test_bulk_final_summary_aggregates_wait_step(
    runner: ProcedureRunner, scenario: dict
) -> None:
    """``bulk-final-summary`` reads from previous_outputs['wait-for-children']."""
    handler = ProgrammaticStepRegistry.get("bulk-final-summary")
    assert handler is not None
    out = await handler(
        _ctx(
            runner=runner,
            project_id=scenario["project_id"],
            args={},
            previous_outputs={
                "wait-for-children": {
                    "success": [1, 2],
                    "failed": [3],
                    "aborted": [],
                }
            },
        )
    )
    assert out == {"success_count": 2, "failed_count": 1, "aborted_count": 0}
