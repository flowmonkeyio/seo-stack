"""Cron-procedure registrar — one job per active project per scheduled procedure."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlmodel import Session

from content_stack.config import Settings
from content_stack.db.models import Project
from content_stack.jobs.cron_procedures import (
    _job_id,
    _resolve_timezone,
    register_cron_procedures,
)
from content_stack.jobs.scheduler import (
    PROCEDURE_CRON_JOB_PREFIX,
    build_scheduler,
)
from content_stack.procedures.runner import ProcedureRunner


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=5180,
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
    )


@pytest.fixture
def runner(engine: object, settings: Settings) -> ProcedureRunner:
    repo_root = Path(__file__).resolve().parents[3]
    return ProcedureRunner(
        settings=settings,
        engine=engine,  # type: ignore[arg-type]
        procedures_dir=repo_root / "procedures",
    )


@pytest.fixture
def two_projects(engine: object) -> Iterator[list[int]]:
    """Two active projects + one inactive (filter sanity)."""
    ids: list[int] = []
    with Session(engine) as s:  # type: ignore[arg-type]
        for slug, active in (
            ("active-1", True),
            ("active-2", True),
            ("inactive-1", False),
        ):
            row = Project(
                slug=slug,
                name=slug,
                domain=f"{slug}.example.com",
                locale="en-US",
                is_active=active,
                schedule_json={"timezone": "America/Los_Angeles"} if active else None,
            )
            s.add(row)
            s.commit()
            s.refresh(row)
            assert row.id is not None
            ids.append(row.id)
    yield ids


async def test_register_cron_creates_one_job_per_active_project(
    engine: object, settings: Settings, runner: ProcedureRunner, two_projects: list[int]
) -> None:
    """Procedures 6 + 7 each register one job per active project."""
    scheduler = build_scheduler(settings, engine)  # type: ignore[arg-type]
    scheduler.start(paused=True)  # don't fire crons in tests
    try:
        with Session(engine) as s:  # type: ignore[arg-type]
            registered = register_cron_procedures(scheduler=scheduler, runner=runner, session=s)
        # 2 active projects * 2 scheduled procedures (06, 07) = 4 jobs
        assert len(registered) == 4
        assert all(jid.startswith(PROCEDURE_CRON_JOB_PREFIX) for jid in registered)
        # Format: procedure-{slug}-{project_id}
        for jid in registered:
            jobs = scheduler.get_jobs(jobstore="memory")
            assert any(j.id == jid for j in jobs)
    finally:
        scheduler.shutdown(wait=False)


def test_job_id_format() -> None:
    """``_job_id`` returns ``procedure-<slug>-<project_id>``."""
    assert _job_id("06-weekly-gsc-review", 42) == "procedure-06-weekly-gsc-review-42"


def test_resolve_timezone_reads_schedule_json(engine: object) -> None:
    """Default field ``projects.schedule_json.timezone`` returns the configured tz."""
    project = Project(
        slug="tz-test",
        name="tz",
        domain="tz.example.com",
        locale="en-US",
        is_active=True,
        schedule_json={"timezone": "Europe/Berlin"},
    )
    assert _resolve_timezone(project, "projects.schedule_json.timezone") == "Europe/Berlin"


def test_resolve_timezone_falls_back_to_utc_when_missing(engine: object) -> None:
    """Missing schedule_json → UTC."""
    project = Project(
        slug="no-tz",
        name="no-tz",
        domain="no-tz.example.com",
        locale="en-US",
        is_active=True,
        schedule_json=None,
    )
    assert _resolve_timezone(project, "projects.schedule_json.timezone") == "UTC"


async def test_no_jobs_when_no_active_projects(
    engine: object, settings: Settings, runner: ProcedureRunner
) -> None:
    """Empty active projects = no jobs registered."""
    scheduler = build_scheduler(settings, engine)  # type: ignore[arg-type]
    scheduler.start(paused=True)
    try:
        with Session(engine) as s:  # type: ignore[arg-type]
            registered = register_cron_procedures(scheduler=scheduler, runner=runner, session=s)
        assert registered == []
    finally:
        scheduler.shutdown(wait=False)
