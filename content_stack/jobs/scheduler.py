"""APScheduler configuration for the daemon — M8.

Per PLAN.md L1344-L1364 (audit MAJOR-23) the scheduler is built once at
daemon startup and held on ``app.state.scheduler``. Job sources:

1. **Procedure runs** (``runner.start`` → ``add_job(..., trigger='date')``).
   The job_id pattern ``run-{run_id}`` makes in-flight runs observable
   and cancellable while the daemon is alive. The actual execution state
   is persisted in the application's ``runs`` / ``run_steps`` tables;
   APScheduler's memory marker is re-created by the runner and is not a
   durable mid-step resume mechanism.
2. **Cron-triggered procedures** (procedure 6 + 7's ``schedule.cron``).
   One job per active project, registered at lifespan startup. Job_id
   ``procedure-{slug}-{project_id}``.
3. **Background ops jobs** — runs reaper, OAuth refresh, GSC pull,
   drift rollup. Each registered explicitly in the lifespan hook.

The two jobstore tables are deliberately distinct:

- ``apscheduler_jobs`` — the SDK's own pickle-blob persistence, managed
  end-to-end by SQLAlchemyJobStore. Schema is *not* tracked by Alembic;
  the SDK creates it idempotently on first use. We never query this
  table from application code.
- ``scheduled_jobs`` — our operator-facing per-project cron metadata
  (PLAN.md L379). The UI's "Schedules" tab toggles ``enabled``. M8's
  cron-procedure registrar consults this table to decide which projects
  to register; APScheduler itself doesn't know about it.

Per audit MAJOR-23 the executor map is:

- ``default`` — ``AsyncIOExecutor`` for the runner + short jobs.
- ``long`` — ``ThreadPoolExecutor(max_workers=2)`` for genuinely
  blocking calls (e.g. a future synchronous backup tool).

Job defaults:

- ``coalesce=True`` so a daemon that was offline for a week
  collapses missed cron firings into one (PLAN.md L1362).
- ``max_instances=1`` per ``job_id`` — APScheduler refuses to start a
  second instance while one is in-flight. The runner uses a separate
  per-procedure ``asyncio.Semaphore`` for in-process parallelism caps.
- ``misfire_grace_time=3600`` (1 h) — the daemon will still fire a job
  that drifted up to an hour from its scheduled time.

Timezone is ``UTC`` for the scheduler globally; per-procedure cron jobs
resolve the project's local timezone at registration time (audit M-23).
"""

from __future__ import annotations

from typing import Any

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.engine import Engine

from content_stack.config import Settings

# Stable job_id prefixes — used by the runner + lifespan registration so
# operators (and tests) can find / cancel jobs by predictable ids.
RUNNER_JOB_PREFIX = "run-"
PROCEDURE_CRON_JOB_PREFIX = "procedure-"
RUNS_REAPER_JOB_ID = "background-runs-reaper"
OAUTH_REFRESH_JOB_ID = "background-oauth-refresh"
GSC_PULL_JOB_ID = "background-gsc-pull"
DRIFT_ROLLUP_JOB_ID = "background-drift-rollup"

# Misfire grace times — kept here so all jobs read the same numbers.
JOB_DEFAULT_MISFIRE_GRACE_SECONDS = 3600  # 1h — generous default
REAPER_MISFIRE_GRACE_SECONDS = 600  # 10 min — reaper should run promptly
RUNNER_MISFIRE_GRACE_SECONDS = 7200  # 2h — long-running procedure tail
OAUTH_MISFIRE_GRACE_SECONDS = 1800  # 30 min — refresh budget is forgiving
GSC_PULL_MISFIRE_GRACE_SECONDS = 7200  # 2h
DRIFT_ROLLUP_MISFIRE_GRACE_SECONDS = 7200  # 2h


def build_scheduler(settings: Settings, engine: Engine) -> AsyncIOScheduler:
    """Return an ``AsyncIOScheduler`` wired against the daemon's engine.

    Per PLAN.md L1346-L1358 the executor + jobstore + job_defaults are
    fixed; per audit MAJOR-23 we assert this layout in tests so an
    accidental drift surfaces during release validation.

    Note ``settings`` is currently unused but accepted for symmetry —
    the lifespan hook always has both available, and a future tightening
    (``settings.scheduler_misfire_grace_seconds`` etc.) lands here
    without changing call sites.
    """
    _ = settings
    executors: dict[str, Any] = {
        "default": AsyncIOExecutor(),
        "long": ThreadPoolExecutor(max_workers=2),
    }
    jobstores: dict[str, Any] = {
        # Kept available for simple picklable jobs. Procedure execution
        # state is stored in our own runs/run_steps tables instead; the
        # runner's live markers use the memory jobstore because they
        # close over asyncio tasks and cannot be resumed by unpickling an
        # APScheduler job.
        "default": SQLAlchemyJobStore(
            engine=engine,
            tablename="apscheduler_jobs",
        ),
        # Cron-procedure jobs + ops jobs (reaper / oauth-refresh /
        # gsc-pull / drift-rollup) rely on closures over the daemon's
        # live runner / engine and therefore cannot be pickled into the
        # SQL store. They live in memory and the lifespan re-registers
        # them on every boot, which matches PLAN.md L1357's directive
        # ("its own table prefix" — separate-store layer of the same
        # idea).
        "memory": MemoryJobStore(),
    }
    job_defaults: dict[str, Any] = {
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": JOB_DEFAULT_MISFIRE_GRACE_SECONDS,
    }
    return AsyncIOScheduler(
        executors=executors,
        jobstores=jobstores,
        job_defaults=job_defaults,
        timezone="UTC",
    )


__all__ = [
    "DRIFT_ROLLUP_JOB_ID",
    "DRIFT_ROLLUP_MISFIRE_GRACE_SECONDS",
    "GSC_PULL_JOB_ID",
    "GSC_PULL_MISFIRE_GRACE_SECONDS",
    "JOB_DEFAULT_MISFIRE_GRACE_SECONDS",
    "OAUTH_MISFIRE_GRACE_SECONDS",
    "OAUTH_REFRESH_JOB_ID",
    "PROCEDURE_CRON_JOB_PREFIX",
    "REAPER_MISFIRE_GRACE_SECONDS",
    "RUNNER_JOB_PREFIX",
    "RUNNER_MISFIRE_GRACE_SECONDS",
    "RUNS_REAPER_JOB_ID",
    "build_scheduler",
]
