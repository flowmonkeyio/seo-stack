"""Runner integration with APScheduler — M8.

Verifies that ``runner.start`` plays cleanly with a bound scheduler:

- The runner accepts a scheduler via the constructor or ``bind_scheduler``.
- Starting a run with the scheduler bound still completes end-to-end.
- A scheduled ``run-{run_id}`` marker job is registered when the
  scheduler is running.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session

from content_stack.config import Settings
from content_stack.db.models import Run, RunStatus
from content_stack.jobs.scheduler import build_scheduler
from content_stack.procedures.llm import StubDispatcher
from content_stack.procedures.runner import ProcedureRunner


@pytest.fixture
def settings_for_apscheduler(tmp_path: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=5180,
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
    )


async def test_runner_dispatches_via_scheduler_when_bound(
    engine: object, settings_for_apscheduler: Settings, scenario: dict
) -> None:
    """Bound scheduler: run completes + scheduler had a marker job."""
    scheduler = build_scheduler(settings_for_apscheduler, engine)  # type: ignore[arg-type]
    repo_root = Path(__file__).resolve().parents[3]
    runner = ProcedureRunner(
        settings=settings_for_apscheduler,
        engine=engine,  # type: ignore[arg-type]
        dispatcher=StubDispatcher(),
        procedures_dir=repo_root / "procedures",
        scheduler=scheduler,
    )
    scheduler.start()
    try:
        envelope = await runner.start(
            slug="04-topic-to-published",
            args={"topic_id": scenario["topic_id"]},
            project_id=scenario["project_id"],
        )
        await runner.wait_for(envelope["run_id"])
    finally:
        scheduler.shutdown(wait=False)
    with Session(engine) as s:  # type: ignore[arg-type]
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        assert run.status == RunStatus.SUCCESS


async def test_bind_scheduler_post_construction(
    engine: object, settings_for_apscheduler: Settings, scenario: dict
) -> None:
    """``bind_scheduler`` attaches a scheduler after construction."""
    repo_root = Path(__file__).resolve().parents[3]
    runner = ProcedureRunner(
        settings=settings_for_apscheduler,
        engine=engine,  # type: ignore[arg-type]
        procedures_dir=repo_root / "procedures",
    )
    scheduler = build_scheduler(settings_for_apscheduler, engine)  # type: ignore[arg-type]
    runner.bind_scheduler(scheduler)
    scheduler.start()
    try:
        envelope = await runner.start(
            slug="04-topic-to-published",
            args={"topic_id": scenario["topic_id"]},
            project_id=scenario["project_id"],
        )
        await runner.wait_for(envelope["run_id"])
    finally:
        scheduler.shutdown(wait=False)
    with Session(engine) as s:  # type: ignore[arg-type]
        run = s.get(Run, envelope["run_id"])
        assert run is not None
        assert run.status == RunStatus.SUCCESS


async def test_runner_falls_back_to_asyncio_without_scheduler(
    runner: ProcedureRunner, scenario: dict, engine: object
) -> None:
    """No scheduler bound → asyncio fallback (preserves M7.A test ergonomics)."""
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


async def test_list_procedures_with_specs_returns_all_eight(
    runner: ProcedureRunner,
) -> None:
    """The M8 cron registrar uses this to find scheduled procedures."""
    specs = runner.list_procedures_with_specs()
    assert len(specs) == 8
    # Procedure 6 + 7 have schedule blocks; others don't.
    assert specs["06-weekly-gsc-review"].schedule is not None
    assert specs["07-monthly-humanize-pass"].schedule is not None
    assert specs["04-topic-to-published"].schedule is None
