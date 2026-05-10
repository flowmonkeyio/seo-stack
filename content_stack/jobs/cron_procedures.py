"""Cron-triggered procedures registrar — M8.

Procedures 6 (``weekly-gsc-review``) and 7 (``monthly-humanize-pass``)
declare ``schedule.cron`` blocks in their PROCEDURE.md frontmatter
(parsed in M7.B as ``ProcedureSchedule``). M8's lifespan walks the
runner's procedure registry, finds the procedures with a non-None
schedule, and registers one APScheduler job per active project per
procedure.

Job_id pattern: ``procedure-{slug}-{project_id}``. The body is a tiny
async wrapper that opens an agent-led run via
``runner.start(slug, args={"project_id": p.id}, project_id=p.id)``.
Cron prepares the work queue; the current operator agent still owns the
writing / SEO judgment when it picks the run up.

Per-procedure timezone resolution:

- The schedule block's ``timezone_field`` is a dotted path like
  ``projects.schedule_json.timezone`` (default).
- We resolve the value at registration time from the project row.
- Fallback to ``UTC`` when the field is absent / null — operators who
  haven't yet set a timezone get a sensible default rather than a hard
  error.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from content_stack.db.models import Project
from content_stack.jobs.scheduler import (
    PROCEDURE_CRON_JOB_PREFIX,
)
from content_stack.logging import get_logger
from content_stack.procedures.parser import ProcedureSchedule, ProcedureSpec
from content_stack.procedures.runner import ProcedureRunner

_log = get_logger(__name__)


def _resolve_timezone(project: Project, field: str) -> str:
    """Walk the dotted path from ``schedule.timezone_field`` to a string.

    Default field is ``projects.schedule_json.timezone``. Returns ``UTC``
    when the path resolves to ``None``.
    """
    parts = field.split(".")
    if not parts:
        return "UTC"
    # First part should be ``projects`` — sanity check + skip.
    if parts[0] != "projects":
        return "UTC"
    cursor: Any = project
    for part in parts[1:]:
        if cursor is None:
            return "UTC"
        cursor = cursor.get(part) if isinstance(cursor, dict) else getattr(cursor, part, None)
    if isinstance(cursor, str) and cursor:
        return cursor
    return "UTC"


def _job_id(slug: str, project_id: int) -> str:
    """Stable id pattern — kept narrow so tests + cancels are predictable."""
    return f"{PROCEDURE_CRON_JOB_PREFIX}{slug}-{project_id}"


def make_cron_procedure_runner(
    *,
    runner: ProcedureRunner,
    slug: str,
    project_id: int,
) -> Callable[[], Awaitable[None]]:
    """Build the job body that fires the runner for one (slug, project_id).

    APScheduler invokes this on each cron tick. The body is async and
    closes over the runner + slug + project_id so the registration loop
    can produce one closure per job_id.

    Note: APScheduler's SQLAlchemyJobStore *cannot* persist a closure —
    only top-level functions are serialisable. We work around this by
    NOT using the SQL jobstore for cron-procedure jobs (they're
    reconstructed at every lifespan startup from the procedure registry),
    so the closure-over-instance is safe.
    """

    async def _fire() -> None:
        _log.info(
            "jobs.cron_procedures.fire",
            slug=slug,
            project_id=project_id,
        )
        try:
            await runner.start(
                slug=slug,
                args={"project_id": project_id},
                project_id=project_id,
            )
        except Exception as exc:  # pragma: no cover — defensive
            _log.warning(
                "jobs.cron_procedures.fire_failed",
                slug=slug,
                project_id=project_id,
                error=str(exc),
            )

    return _fire


def register_cron_procedures(
    *,
    scheduler: AsyncIOScheduler,
    runner: ProcedureRunner,
    session: Session,
) -> list[str]:
    """Walk the registry + register one cron job per active project per scheduled procedure.

    Returns the list of registered job_ids. Idempotent — re-registering
    a job_id replaces the prior trigger (used by tests).
    """
    registered: list[str] = []
    procedures: dict[str, ProcedureSpec] = {
        slug: spec
        for slug, spec in (runner.list_procedures_with_specs() or {}).items()
        if spec.schedule is not None
    }
    if not procedures:
        return registered
    projects = session.exec(
        select(Project).where(Project.is_active.is_(True))  # type: ignore[union-attr,attr-defined]
    ).all()
    for slug, spec in procedures.items():
        sched: ProcedureSchedule = spec.schedule  # type: ignore[assignment]
        for project in projects:
            if project.id is None:
                continue
            tz = _resolve_timezone(project, sched.timezone_field)
            try:
                trigger = CronTrigger.from_crontab(sched.cron, timezone=tz)
            except Exception as exc:
                _log.warning(
                    "jobs.cron_procedures.invalid_cron",
                    slug=slug,
                    project_id=project.id,
                    cron=sched.cron,
                    timezone=tz,
                    error=str(exc),
                )
                continue
            job_id = _job_id(slug, project.id)
            scheduler.add_job(
                make_cron_procedure_runner(
                    runner=runner,
                    slug=slug,
                    project_id=project.id,
                ),
                trigger=trigger,
                id=job_id,
                name=f"procedure {slug} for project {project.id}",
                replace_existing=True,
                jobstore="memory",  # closure cannot be pickled
            )
            registered.append(job_id)
    return registered


__all__ = [
    "make_cron_procedure_runner",
    "register_cron_procedures",
]
