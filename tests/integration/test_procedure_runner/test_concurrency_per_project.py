"""Per-project concurrency — different projects run in parallel.

M8 changes the semaphore key from ``procedure-{slug}`` (system-wide) to
``procedure-{slug}-{project_id}`` (per-project) per PLAN.md L1361.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlmodel import Session

from content_stack.config import Settings
from content_stack.db.models import Run, RunStatus
from content_stack.procedures.llm import StubDispatcher
from content_stack.procedures.runner import ProcedureRunner
from content_stack.repositories.projects import ProjectRepository


@pytest.fixture
def settings_p(tmp_path: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=5180,
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
    )


def _make_runner(
    *,
    engine: object,
    settings: Settings,
    dispatcher: StubDispatcher,
) -> ProcedureRunner:
    repo_root = Path(__file__).resolve().parents[3]
    return ProcedureRunner(
        settings=settings,
        engine=engine,  # type: ignore[arg-type]
        dispatcher=dispatcher,
        procedures_dir=repo_root / "procedures",
    )


async def test_two_projects_same_procedure_run_in_parallel(
    engine: object, settings_p: Settings, scenario: dict
) -> None:
    """Different project_id values share no semaphore — concurrent runs."""
    dispatcher = StubDispatcher()
    runner = _make_runner(engine=engine, settings=settings_p, dispatcher=dispatcher)

    # Create a second project with its own publish target so procedure 4 can run.
    from content_stack.db.models import (
        PublishTarget,
        PublishTargetKind,
        Topic,
        TopicIntent,
        TopicSource,
        TopicStatus,
    )

    with Session(engine) as s:  # type: ignore[arg-type]
        repo = ProjectRepository(s)
        env = repo.create(
            slug="parallel-2",
            name="Parallel 2",
            domain="parallel-2.example",
            locale="en-US",
        )
        pid2 = env.data.id
        assert pid2 is not None
        topic2 = Topic(
            project_id=pid2,
            title="Second project topic",
            primary_kw="parallel topic",
            intent=TopicIntent.INFORMATIONAL,
            source=TopicSource.MANUAL,
            status=TopicStatus.APPROVED,
        )
        s.add(topic2)
        s.commit()
        s.refresh(topic2)
        topic2_id = topic2.id
        target2 = PublishTarget(
            project_id=pid2,
            kind=PublishTargetKind.NUXT_CONTENT,
            config_json={"repo": "test/site2"},
            is_primary=True,
            is_active=True,
        )
        s.add(target2)
        s.commit()

    # Fire both runs concurrently.
    env1, env2 = await asyncio.gather(
        runner.start(
            slug="04-topic-to-published",
            args={"topic_id": scenario["topic_id"]},
            project_id=scenario["project_id"],
        ),
        runner.start(
            slug="04-topic-to-published",
            args={"topic_id": topic2_id},
            project_id=pid2,
        ),
    )
    await asyncio.gather(
        runner.wait_for(env1["run_id"]),
        runner.wait_for(env2["run_id"]),
    )
    with Session(engine) as s:  # type: ignore[arg-type]
        run1 = s.get(Run, env1["run_id"])
        run2 = s.get(Run, env2["run_id"])
        assert run1 is not None and run2 is not None
        assert run1.status == RunStatus.SUCCESS
        assert run2.status == RunStatus.SUCCESS
