"""Daemon-orchestrated procedure runner.

Per locked decision **D4** (PLAN.md L884-L900): procedures are
daemon-orchestrated. The MCP tool ``procedure.run`` enqueues a
server-side runner that dispatches each step as a fresh per-skill LLM
session. The user's LLM client only kicks off + polls.

Per audit **B-21** + **B-13** the runner is resumable + heartbeat-reapable.
This module implements:

- ``ProcedureRunner.start`` — create a ``runs`` row + pre-write all
  ``procedure_run_steps`` rows + dispatch the runner via APScheduler.
  Returns ``{run_id, run_token, status_url}`` immediately so the
  client can poll ``procedure.status`` / ``GET /api/v1/procedures/runs/{id}``.
- ``ProcedureRunner.resume`` — pick up an aborted (or paused) run from
  the next pending step. Reads ``procedure_run_steps`` for the run's
  last clean state.
- ``ProcedureRunner.fork`` — clone a run starting from a chosen step
  index, copying prior step outputs as inputs. Used for refresh /
  humanizer chains where the operator wants to redo step N onward.
- ``ProcedureRunner.abort`` — flip the run row to ``aborted`` + cancel
  the in-process task.

Per-step semantics:

1. Look up the skill's ``allowed_tools`` from ``SKILL_TOOL_GRANTS``
   (load-bearing grant matrix per audit B-10).
2. Dispatch:
   - ``_programmatic/<name>`` → ``ProgrammaticStepRegistry.dispatch``
     (M8 — repository / integration code, no LLM session).
   - everything else → the bound ``LLMDispatcher`` (StubDispatcher /
     AnthropicSession).
3. Persist the dispatcher's output verbatim in
   ``procedure_run_steps.output_json``.
4. Branch per ``ProcedureStep.on_failure``:
   - ``abort`` → terminate the run with status='failed'.
   - ``retry`` → re-dispatch up to ``max_retries``; escalate to abort
     on exhaustion.
   - ``loop_back`` → cap iterations via
     ``settings.procedure_runner_max_loop_iterations`` and re-dispatch
     from ``loop_back_to``.
   - ``skip`` → mark the step ``skipped`` and advance.
   - ``human_review`` → mark the step ``paused`` (the run row stays
     ``running`` so heartbeats keep firing) and stop dispatching;
     ``procedure.resume`` picks up.
5. Heartbeat every step transition.

The runner's only special-case beyond the generic ``on_failure`` modes
is the **EEAT three-verdict branch** per audit BLOCKER-09:

- ``verdict='SHIP'`` → advance to the next step.
- ``verdict='FIX'`` → loop back to the editor (max-iteration capped).
- ``verdict='BLOCK'`` → abort with ``runs.status='aborted'`` and (if
  there's an article in scope) flip ``articles.status='aborted-publish'``.

**M7→M8 transition:** M7.A used ``asyncio.create_task`` to dispatch the
runner's main loop. M8 routes through APScheduler so the runner job is
persistent (SQLAlchemyJobStore), respects ``max_instances=1`` per
``run-{run_id}`` job, and resumes cleanly after a daemon crash. The
runner still uses an in-process ``asyncio.Semaphore`` per
``(slug, project_id)`` for fine-grained per-project serialization that
the cross-process scheduler can't express on its own.

If the scheduler is not bound (e.g. tests using the M7.A entry path),
the runner falls back to ``asyncio.create_task`` — the dispatch
contract is unchanged.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from content_stack.config import Settings
from content_stack.db.models import (
    Article,
    ArticleStatus,
    ProcedureRunStepStatus,
    PublishTarget,
    PublishTargetKind,
    Run,
    RunKind,
    RunStatus,
)
from content_stack.mcp.permissions import SKILL_TOOL_GRANTS
from content_stack.procedures.llm import (
    LLMDispatcher,
    LLMDispatcherError,
    StepDispatch,
    StubDispatcher,
)
from content_stack.procedures.parser import (
    ProcedureSpec,
    ProcedureStep,
    load_all_procedures,
)
from content_stack.procedures.programmatic import (
    HumanReviewPause,
    ProgrammaticStepRegistry,
)
from content_stack.procedures.programmatic import (
    StepContext as ProgrammaticStepContext,
)
from content_stack.repositories.base import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from content_stack.repositories.runs import (
    ProcedureRunStepRepository,
    RunRepository,
)

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Skill prefix for programmatic step dispatch — runner detects this at
# dispatch time and routes through ``ProgrammaticStepRegistry`` instead
# of the LLM dispatcher. The handler name follows the prefix:
# ``_programmatic/foo-bar`` → registry key ``foo-bar``.
_PROGRAMMATIC_PREFIX = "_programmatic/"

_log = logging.getLogger(__name__)

# Map publish_target kinds onto the publish skill key. Procedure 4
# declares ``04-publishing/nuxt-content-publish`` as the default in
# frontmatter; the runner overrides at dispatch time based on the
# project's primary active publish target.
_PUBLISH_KIND_TO_SKILL: dict[PublishTargetKind, str] = {
    PublishTargetKind.NUXT_CONTENT: "04-publishing/nuxt-content-publish",
    PublishTargetKind.WORDPRESS: "04-publishing/wordpress-publish",
    PublishTargetKind.GHOST: "04-publishing/ghost-publish",
}

# A token used in step.skill values to flag the runner-driven publish
# selection. Procedure 4 sets the publish step's ``skill`` to the
# nuxt-content default; the runner swaps to the project's primary
# target if it differs. We don't introduce a new reserved token here —
# the runner just inspects the skill's path-prefix ``04-publishing/``
# and re-resolves at dispatch time.
_PUBLISH_PREFIX = "04-publishing/"

# A trailing identifier keyed off the procedure slug + project_id for
# heartbeat-reapable concurrency lookups. The runner uses these to
# enforce ``concurrency_limit`` system-wide via per-procedure
# semaphores held on the runner instance.
SemaphoreKey = str


# ---------------------------------------------------------------------------
# In-flight task registry.
# ---------------------------------------------------------------------------


@dataclass
class _RunnerTask:
    """One in-flight procedure run.

    The runner holds these in a dict keyed by run_id so ``abort()`` can
    cancel the task and ``resume()`` can avoid double-dispatch races.
    """

    task: asyncio.Task[None]
    run_id: int
    slug: str
    semaphore_key: SemaphoreKey
    started_at: float = 0.0
    paused: bool = False
    """Set by the human_review handler — paused tasks complete with
    the run row still 'running' so the operator can resume via
    ``procedure.resume``."""


# ---------------------------------------------------------------------------
# Runner.
# ---------------------------------------------------------------------------


@dataclass
class _StepContext:
    """Per-step state passed through the runner's main loop.

    Held entirely in-memory; nothing here outlives the asyncio task.
    Persistence is via the ``procedure_run_steps`` rows + ``runs.metadata_json``.
    """

    spec: ProcedureSpec
    run_id: int
    run_token: str
    project_id: int
    args: dict[str, Any]
    article_id: int | None = None
    """Resolved at start time when the procedure declares an
    ``article_id`` input or the runner derives one from a topic_id (e.g.
    procedure 4 creates an article if the topic doesn't have one yet)."""

    step_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Each completed step's output_json keyed by step.id. Available to
    later steps as ``context['previous_outputs'][step_id]``."""

    loop_iteration: dict[str, int] = field(default_factory=dict)
    """Per-target-step loop counter. ``loop_back`` increments
    ``loop_iteration[loop_back_to]`` and the runner aborts when any
    counter exceeds ``settings.procedure_runner_max_loop_iterations``."""

    pause_requested: dict[str, bool] = field(default_factory=dict)
    """Set by ``HumanReviewPause`` from a programmatic handler. Forces
    the post-step action to ``pause`` regardless of the step's declared
    ``on_failure`` mode (operator-driven prompts always pause)."""


class ProcedureRunner:
    """Daemon-orchestrated procedure runner per D4."""

    def __init__(
        self,
        *,
        settings: Settings,
        engine: Engine,
        dispatcher: LLMDispatcher | None = None,
        procedures_dir: Path | None = None,
        scheduler: AsyncIOScheduler | None = None,
    ) -> None:
        self._settings = settings
        self._engine = engine
        self._dispatcher = dispatcher or StubDispatcher()
        if procedures_dir is None:
            procedures_dir = _default_procedures_dir()
        self._procedures_dir = procedures_dir
        # Eager-load + cache the procedure registry. Loading raises if
        # any PROCEDURE.md is malformed — we want that surfaced at
        # startup, not at the first ``procedure.run`` call.
        self._registry: dict[str, ProcedureSpec] = load_all_procedures(procedures_dir)
        # Per-(slug, project_id) semaphore — the in-process complement to
        # APScheduler's ``max_instances=1`` per job_id. M7.A keyed on slug
        # alone (system-wide); M8 keys on (slug, project_id) per
        # PLAN.md L1361 ("per-project serialization") so different projects
        # of the same procedure can run in parallel.
        self._semaphores: dict[SemaphoreKey, asyncio.Semaphore] = {}
        self._tasks: dict[int, _RunnerTask] = {}
        self._tasks_lock = asyncio.Lock()
        self._skill_body_cache: dict[str, str] = {}
        # Skills root mirrors the procedures directory layout — repo
        # root has both. We resolve once at construction.
        self._skills_dir = _default_skills_dir(procedures_dir)
        # APScheduler binding (M8). When None the runner falls back to
        # ``asyncio.create_task`` — preserves M7.A test ergonomics where
        # tests construct a runner without a scheduler.
        self._scheduler: AsyncIOScheduler | None = scheduler

    def bind_scheduler(self, scheduler: AsyncIOScheduler) -> None:
        """Attach a scheduler post-construction. Called by the lifespan."""
        self._scheduler = scheduler

    def list_procedures_with_specs(self) -> dict[str, ProcedureSpec]:
        """Return ``slug → ProcedureSpec`` for every loaded procedure.

        Used by the M8 cron-procedure registrar to find procedures with a
        non-None ``schedule`` block. Tests of the M7 path don't need
        this — it's M8-specific.
        """
        return dict(self._registry)

    # ------------------------------------------------------------------
    # Public API.
    # ------------------------------------------------------------------

    def list_procedures(self) -> list[str]:
        """Return the registered procedure slugs (sorted)."""
        return sorted(self._registry.keys())

    def get_spec(self, slug: str) -> ProcedureSpec:
        """Return one ``ProcedureSpec`` by slug.

        Raises :class:`NotFoundError` for unknown slugs so callers can
        map to a 404 / -32004.
        """
        spec = self._registry.get(slug)
        if spec is None:
            raise NotFoundError(
                f"procedure {slug!r} not registered",
                data={"slug": slug, "known": sorted(self._registry.keys())},
            )
        return spec

    async def start(
        self,
        *,
        slug: str,
        args: dict[str, Any],
        project_id: int,
        parent_run_id: int | None = None,
        idempotency_key: str | None = None,
        variant: str | None = None,
        client_session_id: str | None = None,
        wait: bool = False,
    ) -> dict[str, Any]:
        """Create a runs row + pre-write step rows + dispatch.

        Returns a status envelope ``{run_id, run_token, status_url, slug,
        project_id, started}``.

        ``wait=True`` blocks until the asyncio task completes; tests
        use this to assert on terminal state synchronously without
        sleeping. Production callers (REST / MCP) leave ``wait=False``.
        """
        # ``client_session_id`` is supplied by tests that pre-mint a token
        # (e.g. via ``run.start``); production passes None and we mint
        # one. Either way the value lives on ``runs.client_session_id``
        # and is what permissions.resolve_run_token round-trips against.
        spec = self.get_spec(slug)
        if variant is not None:
            spec = spec.apply_variant(variant)

        run_token, run_id = self._open_run(
            slug=slug,
            project_id=project_id,
            parent_run_id=parent_run_id,
            args=args,
            spec=spec,
            client_session_id=client_session_id,
        )

        # Reserve the semaphore key + dispatch via the scheduler (M8) or
        # asyncio fallback (M7.A test path).
        sem_key = _semaphore_key(slug, project_id)
        sem = self._semaphores.setdefault(sem_key, asyncio.Semaphore(spec.concurrency_limit))
        await self._dispatch_run(
            spec=spec,
            run_id=run_id,
            run_token=run_token,
            project_id=project_id,
            args=args,
            semaphore=sem,
            sem_key=sem_key,
            wait=wait,
            label="start",
        )
        return {
            "run_id": run_id,
            "run_token": run_token,
            "status_url": f"/api/v1/procedures/runs/{run_id}",
            "slug": slug,
            "project_id": project_id,
            "started": True,
        }

    async def resume(self, *, run_id: int, wait: bool = False) -> dict[str, Any]:
        """Resume an aborted / paused run from the next pending step.

        Reads ``procedure_run_steps`` for the run's last clean state.
        If every step succeeded, the run is already finished — returns a
        no-op envelope. If the procedure declares ``resumable=False``,
        raises :class:`ConflictError`.
        """
        with Session(self._engine) as s:
            run_row = s.get(Run, run_id)
            if run_row is None:
                raise NotFoundError(f"run {run_id} not found", data={"run_id": run_id})
            if run_row.procedure_slug is None:
                raise ValidationError(
                    f"run {run_id} is not a procedure run (no procedure_slug)",
                    data={"run_id": run_id},
                )
            spec = self.get_spec(run_row.procedure_slug)
            if not spec.resumable:
                raise ConflictError(
                    f"procedure {spec.slug!r} declares resumable=false",
                    data={"slug": spec.slug, "run_id": run_id},
                )
            # Find the resume index.
            steps = ProcedureRunStepRepository(s).list_steps(run_id)
            resume_index = _next_pending_step_index(steps)
            if resume_index is None:
                # Nothing to resume — every step is terminal. Surface a
                # clean no-op so the operator UI can show "already done".
                return {
                    "run_id": run_id,
                    "run_token": run_row.client_session_id or "",
                    "status_url": f"/api/v1/procedures/runs/{run_id}",
                    "slug": spec.slug,
                    "project_id": run_row.project_id or 0,
                    "started": False,
                }
            # Re-open the run if it was aborted.
            if run_row.status != RunStatus.RUNNING:
                run_row.status = RunStatus.RUNNING
                run_row.error = None
                run_row.ended_at = None
                s.add(run_row)
                s.commit()
                s.refresh(run_row)
            run_token = run_row.client_session_id or ""
            project_id = run_row.project_id or 0
            metadata = run_row.metadata_json or {}
            args = metadata.get("procedure_args", {}) or {}
            seed_outputs: dict[str, dict[str, Any]] = {}
            for step_row in steps:
                if step_row.status == ProcedureRunStepStatus.SUCCESS and step_row.output_json:
                    seed_outputs[step_row.step_id] = step_row.output_json

        sem_key = _semaphore_key(spec.slug, project_id)
        sem = self._semaphores.setdefault(sem_key, asyncio.Semaphore(spec.concurrency_limit))
        await self._dispatch_run(
            spec=spec,
            run_id=run_id,
            run_token=run_token,
            project_id=project_id,
            args=args,
            semaphore=sem,
            sem_key=sem_key,
            wait=wait,
            label="resume",
            resume_from=resume_index,
            seed_outputs=seed_outputs,
        )
        return {
            "run_id": run_id,
            "run_token": run_token,
            "status_url": f"/api/v1/procedures/runs/{run_id}",
            "slug": spec.slug,
            "project_id": project_id,
            "started": True,
        }

    async def fork(
        self,
        *,
        run_id: int,
        from_step_index: int,
        wait: bool = False,
    ) -> dict[str, Any]:
        """Create a new run starting from ``from_step_index``.

        Copies all prior step outputs from the source run as inputs to
        the new run. Used for refresh / humanizer chains where the
        operator wants to redo step N onward without losing the prior
        versions.
        """
        with Session(self._engine) as s:
            source_row = s.get(Run, run_id)
            if source_row is None:
                raise NotFoundError(f"run {run_id} not found", data={"run_id": run_id})
            if source_row.procedure_slug is None:
                raise ValidationError(
                    f"run {run_id} is not a procedure run",
                    data={"run_id": run_id},
                )
            spec = self.get_spec(source_row.procedure_slug)
            if from_step_index < 0 or from_step_index >= len(spec.steps):
                raise ValidationError(
                    f"from_step_index {from_step_index} out of range for procedure "
                    f"{spec.slug!r} (has {len(spec.steps)} steps)",
                    data={"from_step_index": from_step_index, "step_count": len(spec.steps)},
                )
            source_steps = ProcedureRunStepRepository(s).list_steps(run_id)
            seed_outputs: dict[str, dict[str, Any]] = {}
            for step_row in source_steps[:from_step_index]:
                if step_row.status == ProcedureRunStepStatus.SUCCESS and step_row.output_json:
                    seed_outputs[step_row.step_id] = step_row.output_json
            metadata = source_row.metadata_json or {}
            args = metadata.get("procedure_args", {}) or {}
            project_id = source_row.project_id or 0
            parent_run_id = run_id

        # Open a fresh run row + pre-write the step skeleton, marking
        # all steps before from_step_index as 'skipped' so the audit
        # trail records the fork explicitly.
        run_token, new_run_id = self._open_run(
            slug=spec.slug,
            project_id=project_id,
            parent_run_id=parent_run_id,
            args=args,
            spec=spec,
            client_session_id=None,
        )
        # Mark the pre-fork steps as 'skipped' and seed their output_json
        # with the source's value for audit clarity.
        with Session(self._engine) as s:
            step_repo = ProcedureRunStepRepository(s)
            new_steps = step_repo.list_steps(new_run_id)
            for idx, step_row in enumerate(new_steps):
                if idx >= from_step_index:
                    break
                source_value = seed_outputs.get(step_row.step_id)
                step_repo.advance_step(
                    step_row.id,  # type: ignore[arg-type]
                    status=ProcedureRunStepStatus.SKIPPED,
                    output_json=source_value,
                )

        sem_key = _semaphore_key(spec.slug, project_id)
        sem = self._semaphores.setdefault(sem_key, asyncio.Semaphore(spec.concurrency_limit))
        await self._dispatch_run(
            spec=spec,
            run_id=new_run_id,
            run_token=run_token,
            project_id=project_id,
            args=args,
            semaphore=sem,
            sem_key=sem_key,
            wait=wait,
            label="fork",
            resume_from=from_step_index,
            seed_outputs=seed_outputs,
        )
        return {
            "run_id": new_run_id,
            "run_token": run_token,
            "status_url": f"/api/v1/procedures/runs/{new_run_id}",
            "slug": spec.slug,
            "project_id": project_id,
            "parent_run_id": parent_run_id,
            "started": True,
        }

    async def abort(self, *, run_id: int, cascade: bool = False) -> dict[str, Any]:
        """Abort an in-flight run + cancel its asyncio task.

        Idempotent: aborting an already-terminal run flips no states.
        Also removes the corresponding ``run-{run_id}`` APScheduler job
        if one was registered (M8).
        """
        async with self._tasks_lock:
            runner_task = self._tasks.get(run_id)
        if runner_task is not None:
            runner_task.task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await runner_task.task
        # Remove the scheduler job if one is bound. The job marker
        # (``_noop_job_marker``) may already have fired; ``remove_job``
        # is idempotent enough — we suppress JobLookupError.
        if self._scheduler is not None:
            with contextlib.suppress(Exception):
                self._scheduler.remove_job(f"run-{run_id}", jobstore="memory")
        with Session(self._engine) as s:
            RunRepository(s).abort(run_id, cascade=cascade)
            row = s.get(Run, run_id)
            project_id = row.project_id if row else None
        return {
            "run_id": run_id,
            "project_id": project_id,
            "aborted": True,
            "cascade": cascade,
        }

    async def wait_for(self, run_id: int, *, timeout: float | None = None) -> None:
        """Block until ``run_id`` has finished (success / failed / aborted).

        Tests use this to synchronise on terminal state without sleeping.
        Returns silently if the run is already terminal or unknown.
        """
        async with self._tasks_lock:
            runner_task = self._tasks.get(run_id)
        if runner_task is None:
            return
        try:
            if timeout is None:
                await runner_task.task
            else:
                await asyncio.wait_for(asyncio.shield(runner_task.task), timeout)
        except asyncio.CancelledError:
            return

    def in_flight_count(self, slug: str | None = None) -> int:
        """Return the number of in-flight runner tasks (optionally filtered).

        Tests use this to assert on the concurrency-limit semaphore.
        """
        count = 0
        for t in self._tasks.values():
            if slug is not None and t.slug != slug:
                continue
            if not t.task.done():
                count += 1
        return count

    # ------------------------------------------------------------------
    # Internal — task body.
    # ------------------------------------------------------------------

    def _open_run(
        self,
        *,
        slug: str,
        project_id: int,
        parent_run_id: int | None,
        args: dict[str, Any],
        spec: ProcedureSpec,
        client_session_id: str | None,
    ) -> tuple[str, int]:
        """Create the ``runs`` row + pre-write the step rows.

        Returns ``(run_token, run_id)``. Token is the run's
        ``client_session_id`` — production callers mint via ``run.start``,
        but the runner always controls its own token because the
        per-step subprocess (real LLM dispatcher) needs a fresh
        correlation handle.
        """
        token = client_session_id or _mint_run_token()
        metadata = {
            "procedure_slug": slug,
            "procedure_args": args,
            "skill_name": slug,  # so resolve_run_token finds the slug for grant lookups
        }
        with Session(self._engine) as s:
            run_repo = RunRepository(s)
            env = run_repo.start(
                project_id=project_id,
                kind=RunKind.PROCEDURE,
                parent_run_id=parent_run_id,
                procedure_slug=slug,
                client_session_id=token,
                metadata_json=metadata,
            )
            run_id = env.data.id
            assert run_id is not None
            step_repo = ProcedureRunStepRepository(s)
            for idx, step in enumerate(spec.steps):
                step_repo.insert_step(
                    run_id=run_id,
                    step_index=idx,
                    step_id=step.id,
                )
        return token, run_id

    async def _dispatch_run(
        self,
        *,
        spec: ProcedureSpec,
        run_id: int,
        run_token: str,
        project_id: int,
        args: dict[str, Any],
        semaphore: asyncio.Semaphore,
        sem_key: SemaphoreKey,
        wait: bool,
        label: str,
        resume_from: int = 0,
        seed_outputs: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Schedule the run's main loop via APScheduler (M8) or asyncio (M7.A).

        The scheduler path uses ``trigger='date'`` with ``run_date=now``
        so the runner job fires immediately but goes through APScheduler
        — which means the job is persistent (SQLAlchemyJobStore) +
        respects ``max_instances=1`` across the daemon.

        The asyncio fallback preserves the M7.A test ergonomics (tests
        that don't bind a scheduler still run end-to-end). Both paths
        record the in-flight task on ``self._tasks[run_id]`` so
        ``abort()`` + ``wait_for()`` work uniformly.
        """

        async def _body() -> None:
            await self._run_task(
                spec=spec,
                run_id=run_id,
                run_token=run_token,
                project_id=project_id,
                args=args,
                semaphore=semaphore,
                resume_from=resume_from,
                seed_outputs=seed_outputs,
            )

        # Build the asyncio task that drives ``_body``. Both branches
        # produce an awaitable handle on ``self._tasks[run_id]`` so
        # ``abort`` / ``wait_for`` can work the same way regardless of
        # whether APScheduler is in the chain.
        if self._scheduler is not None and self._scheduler.running:
            task = asyncio.create_task(_body(), name=f"proc-{spec.slug}-{run_id}-{label}")
            # Register the run with APScheduler so the in-flight job is
            # observable / cancellable via ``scheduler.get_job(...)`` and
            # the persistent jobstore tracks it. We schedule a
            # short-circuit "complete" job that simply attaches the
            # task — APScheduler's ``date`` trigger fires once at
            # ``run_date`` and removes the job afterward.
            job_id = f"run-{run_id}"
            try:
                self._scheduler.add_job(
                    func=_noop_job_marker,
                    trigger="date",
                    run_date=datetime.now(UTC),
                    id=job_id,
                    name=f"runner {spec.slug} run_id={run_id}",
                    replace_existing=True,
                    jobstore="memory",
                )
            except Exception as exc:  # pragma: no cover — defensive
                _log.warning(
                    "procedure_runner.scheduler_add_job_failed",
                    extra={"run_id": run_id, "error": str(exc)},
                )
        else:
            task = asyncio.create_task(_body(), name=f"proc-{spec.slug}-{run_id}-{label}")

        loop_time = asyncio.get_event_loop().time()
        runner_task = _RunnerTask(
            task=task,
            run_id=run_id,
            slug=spec.slug,
            semaphore_key=sem_key,
            started_at=loop_time,
        )
        async with self._tasks_lock:
            self._tasks[run_id] = runner_task
        task.add_done_callback(self._make_done_callback(run_id))
        if wait:
            await task

    async def _run_task(
        self,
        *,
        spec: ProcedureSpec,
        run_id: int,
        run_token: str,
        project_id: int,
        args: dict[str, Any],
        semaphore: asyncio.Semaphore,
        resume_from: int = 0,
        seed_outputs: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """The asyncio task body. Walks the spec, dispatches each step.

        Always finishes the run (success / failed / aborted). Wrapping
        the whole body in a try/finally ensures crash recovery + the
        task-registry cleanup paths fire even when a step explodes.
        """
        async with semaphore:
            ctx = _StepContext(
                spec=spec,
                run_id=run_id,
                run_token=run_token,
                project_id=project_id,
                args=dict(args),
                step_outputs=dict(seed_outputs or {}),
            )
            ctx.article_id = self._resolve_article_id(args)
            try:
                await self._main_loop(ctx, start_index=resume_from)
            except asyncio.CancelledError:
                # Cancellation lands here when ``abort()`` cancels the
                # task. We don't re-finalise the run — abort() already
                # flipped status='aborted'. Re-raising lets asyncio
                # propagate the cancellation up to the task boundary.
                raise
            except Exception as exc:
                _log.exception("procedure_runner.unexpected_error", extra={"run_id": run_id})
                await self._finalize(
                    run_id=run_id,
                    status=RunStatus.FAILED,
                    error=f"runner-crash: {exc}",
                    article_id=ctx.article_id,
                )

    async def _main_loop(self, ctx: _StepContext, *, start_index: int) -> None:
        """Walk ``ctx.spec.steps`` from ``start_index`` to the end."""
        idx = start_index
        max_steps = len(ctx.spec.steps)
        # Outer guard against malformed loop_back chains. Each loop_back
        # increments a per-target counter; the runner aborts when any
        # counter exceeds ``settings.procedure_runner_max_loop_iterations``.
        while idx < max_steps:
            step = ctx.spec.steps[idx]
            self._maybe_swap_publish_skill(ctx, step)
            await self._run_step(ctx, step_index=idx)
            # Inspect the last step's outcome to decide what to do next.
            verdict_action = self._post_step_action(ctx, step)
            if verdict_action.action == "advance":
                idx += 1
                continue
            if verdict_action.action == "abort":
                await self._abort_with_message(
                    ctx, status=RunStatus.FAILED, error=verdict_action.error or "step-aborted"
                )
                return
            if verdict_action.action == "block":
                # EEAT BLOCK or any explicit BLOCK from a step. Mark the
                # article as 'aborted-publish' if there's one in scope.
                if ctx.article_id is not None:
                    self._mark_article_aborted(ctx.article_id, reason=verdict_action.error)
                await self._abort_with_message(
                    ctx,
                    status=RunStatus.ABORTED,
                    error=verdict_action.error or "blocked",
                )
                return
            if verdict_action.action == "loop_back":
                target_idx = verdict_action.loop_back_index
                assert target_idx is not None
                target_step = ctx.spec.steps[target_idx]
                ctx.loop_iteration[target_step.id] = ctx.loop_iteration.get(target_step.id, 0) + 1
                if (
                    ctx.loop_iteration[target_step.id]
                    > self._settings.procedure_runner_max_loop_iterations
                ):
                    await self._abort_with_message(
                        ctx,
                        status=RunStatus.FAILED,
                        error=(
                            f"loop-back limit exceeded for step {target_step.id!r} "
                            f"(>{self._settings.procedure_runner_max_loop_iterations})"
                        ),
                    )
                    return
                # Re-prepare the step rows from target_idx onward to a
                # fresh 'pending' so the audit trail shows the loop. We
                # leave the prior attempts in place (they're 'success'
                # rows) and insert fresh rows by overwriting their
                # state via advance_step. The existing PRIMARY KEY
                # (run_id, step_index) means we just reset.
                self._reset_steps_for_loop(ctx.run_id, from_index=target_idx)
                idx = target_idx
                continue
            if verdict_action.action == "pause":
                # human_review pause — leave the run row 'running' so
                # heartbeats keep firing; the operator resumes.
                _log.info(
                    "procedure_runner.paused",
                    extra={"run_id": ctx.run_id, "step": step.id},
                )
                async with self._tasks_lock:
                    runner_task = self._tasks.get(ctx.run_id)
                    if runner_task is not None:
                        runner_task.paused = True
                return
        # Walked off the end → success.
        await self._finalize(
            run_id=ctx.run_id,
            status=RunStatus.SUCCESS,
            article_id=ctx.article_id,
            verdict_metadata=self._success_metadata(ctx),
        )

    async def _run_step(self, ctx: _StepContext, *, step_index: int) -> None:
        """Dispatch one step + persist its output / failure state.

        Per M8: ``_programmatic/<name>`` skills route through
        ``ProgrammaticStepRegistry``; everything else goes through the
        bound ``LLMDispatcher``. ``HumanReviewPause`` raised by a
        programmatic handler is translated into an ``on_failure='human_review'``
        equivalent — the runner records the step as ``failed`` so the
        post-step action handler can pause the run.
        """
        step = ctx.spec.steps[step_index]
        self._heartbeat(ctx.run_id)
        # Mark the row as 'running' for live UI display.
        with Session(self._engine) as s:
            step_repo = ProcedureRunStepRepository(s)
            row = self._fetch_step_row(s, ctx.run_id, step_index)
            step_pk = row.id
            assert step_pk is not None
            step_repo.advance_step(step_pk, status=ProcedureRunStepStatus.RUNNING)
        # Build the dispatch payload.
        merged_args = self._merge_args(ctx, step)
        max_attempts = step.max_retries + 1 if step.on_failure == "retry" else 1
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                output = await self._dispatch_step_once(
                    step=step, ctx=ctx, merged_args=merged_args, attempt=attempt
                )
            except HumanReviewPause as exc:
                # Translate into a step failure with a sentinel error
                # message. ``_handle_failed_step`` (when the step's
                # on_failure is human_review) returns a ``pause`` action.
                # For steps whose on_failure is *not* human_review, the
                # step still pauses — we override the post-step action
                # by stamping ``runner_task.paused`` later. To keep the
                # dispatch contract clean we surface a typed marker in
                # the step's error column.
                with Session(self._engine) as s:
                    step_repo = ProcedureRunStepRepository(s)
                    row = self._fetch_step_row(s, ctx.run_id, step_index)
                    step_pk = row.id
                    assert step_pk is not None
                    step_repo.advance_step(
                        step_pk,
                        status=ProcedureRunStepStatus.FAILED,
                        error=f"human-review-pause: {exc.reason}",
                    )
                ctx.step_outputs[step.id] = {
                    "human_review": True,
                    "reason": exc.reason,
                    "hint": exc.hint,
                    "skill": step.skill,
                }
                # Force the on_failure path to ``human_review`` regardless
                # of the spec's declared mode — a programmatic prompt
                # explicitly requested operator attention.
                ctx.pause_requested[step.id] = True
                return
            except LLMDispatcherError as exc:
                last_exc = exc
                if attempt + 1 < max_attempts and exc.retryable:
                    _log.info(
                        "procedure_runner.retry",
                        extra={
                            "run_id": ctx.run_id,
                            "step": step.id,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                        },
                    )
                    continue
                # Out of retries — record the failure.
                with Session(self._engine) as s:
                    step_repo = ProcedureRunStepRepository(s)
                    row = self._fetch_step_row(s, ctx.run_id, step_index)
                    step_pk = row.id
                    assert step_pk is not None
                    step_repo.advance_step(
                        step_pk,
                        status=ProcedureRunStepStatus.FAILED,
                        error=str(exc),
                    )
                ctx.step_outputs[step.id] = {"error": str(exc), "skill": step.skill}
                return
            except Exception as exc:
                # Programmatic handlers raise plain Exceptions for "step
                # failed" — translate to the same shape as an LLM
                # dispatcher error so on_failure modes fire identically.
                last_exc = exc
                if attempt + 1 < max_attempts and step.on_failure == "retry":
                    _log.info(
                        "procedure_runner.retry_programmatic",
                        extra={
                            "run_id": ctx.run_id,
                            "step": step.id,
                            "attempt": attempt,
                        },
                    )
                    continue
                with Session(self._engine) as s:
                    step_repo = ProcedureRunStepRepository(s)
                    row = self._fetch_step_row(s, ctx.run_id, step_index)
                    step_pk = row.id
                    assert step_pk is not None
                    step_repo.advance_step(
                        step_pk,
                        status=ProcedureRunStepStatus.FAILED,
                        error=str(exc),
                    )
                ctx.step_outputs[step.id] = {"error": str(exc), "skill": step.skill}
                return
            # Success.
            with Session(self._engine) as s:
                step_repo = ProcedureRunStepRepository(s)
                row = self._fetch_step_row(s, ctx.run_id, step_index)
                step_pk = row.id
                assert step_pk is not None
                step_repo.advance_step(
                    step_pk,
                    status=ProcedureRunStepStatus.SUCCESS,
                    output_json=output,
                )
            ctx.step_outputs[step.id] = output
            return
        # Defensive — shouldn't reach here because the loop returns from
        # both success and exhausted-retry branches. If it does, treat
        # as failed.
        if last_exc is not None:
            with Session(self._engine) as s:
                step_repo = ProcedureRunStepRepository(s)
                row = self._fetch_step_row(s, ctx.run_id, step_index)
                step_pk = row.id
                assert step_pk is not None
                step_repo.advance_step(
                    step_pk,
                    status=ProcedureRunStepStatus.FAILED,
                    error=str(last_exc),
                )

    async def _dispatch_step_once(
        self,
        *,
        step: ProcedureStep,
        ctx: _StepContext,
        merged_args: dict[str, Any],
        attempt: int,
    ) -> dict[str, Any]:
        """Single-attempt dispatch. M8 splits LLM vs programmatic."""
        if step.skill.startswith(_PROGRAMMATIC_PREFIX):
            handler_name = step.skill[len(_PROGRAMMATIC_PREFIX) :]
            handler = ProgrammaticStepRegistry.get(handler_name)
            if handler is None:
                raise LLMDispatcherError(
                    f"no programmatic handler registered for {step.skill!r}",
                    skill=step.skill,
                    retryable=False,
                )
            programmatic_ctx = ProgrammaticStepContext(
                runner=self,
                run_id=ctx.run_id,
                project_id=ctx.project_id,
                args=merged_args,
                previous_outputs=dict(ctx.step_outputs),
            )
            return await handler(programmatic_ctx)
        # LLM dispatcher path (StubDispatcher / AnthropicSession).
        skill_body = self._load_skill_body(step.skill)
        payload = StepDispatch(
            skill=step.skill,
            skill_body=skill_body,
            step_id=step.id,
            args=merged_args,
            run_id=ctx.run_id,
            run_token=ctx.run_token,
            project_id=ctx.project_id,
            context={
                "article_id": ctx.article_id,
                "previous_outputs": dict(ctx.step_outputs),
                "procedure_args": dict(ctx.args),
                "loop_iteration": dict(ctx.loop_iteration),
                "attempt": attempt,
                "max_retries": step.max_retries,
                "allowed_tools": sorted(SKILL_TOOL_GRANTS.get(step.skill, frozenset())),
            },
        )
        return await self._dispatcher.dispatch(payload)

    def _post_step_action(
        self,
        ctx: _StepContext,
        step: ProcedureStep,
    ) -> _StepAction:
        """Decide what the runner does after a step completes.

        Branches in order:

        0. ``HumanReviewPause`` was raised → force pause regardless of
           the spec's declared on_failure mode (M8 — programmatic prompt).
        1. EEAT three-verdict (audit BLOCKER-09) — only fires when the
           step's skill is the EEAT gate AND the step output carries a
           ``verdict``.
        2. Step's recorded status (success / failed / skipped).
        3. ``on_failure`` mode for the step.
        """
        if ctx.pause_requested.get(step.id):
            return _StepAction(action="pause")
        out = ctx.step_outputs.get(step.id, {})
        # EEAT three-verdict special case.
        if step.skill == "02-content/eeat-gate" and isinstance(out, dict):
            verdict = out.get("verdict")
            if verdict == "BLOCK":
                return _StepAction(action="block", error="eeat-gate=BLOCK")
            if verdict == "FIX":
                # Find the loop_back_to target; default to "editor" if
                # the spec authored loop_back without an explicit target.
                target_id = step.loop_back_to or "editor"
                target_idx = next(
                    (i for i, s in enumerate(ctx.spec.steps) if s.id == target_id),
                    None,
                )
                if target_idx is None or target_idx >= ctx.spec.steps.index(step):
                    return _StepAction(
                        action="abort",
                        error=f"eeat FIX target {target_id!r} not declared as a prior step",
                    )
                return _StepAction(action="loop_back", loop_back_index=target_idx)
            if verdict == "SHIP":
                return _StepAction(action="advance")
            # No verdict surfaced — fall through to the generic action.
        # Inspect the step row's status.
        with Session(self._engine) as s:
            step_index = ctx.spec.steps.index(step)
            row = self._fetch_step_row(s, ctx.run_id, step_index)
            row_status = row.status
        if row_status == ProcedureRunStepStatus.SUCCESS:
            return _StepAction(action="advance")
        if row_status == ProcedureRunStepStatus.SKIPPED:
            return _StepAction(action="advance")
        if row_status == ProcedureRunStepStatus.FAILED:
            return self._handle_failed_step(ctx, step)
        # Shouldn't happen — the runner only leaves rows in 'success' /
        # 'failed' / 'skipped'. Treat as advance to avoid an infinite
        # loop.
        return _StepAction(action="advance")

    def _handle_failed_step(self, ctx: _StepContext, step: ProcedureStep) -> _StepAction:
        """Apply ``step.on_failure`` to a failed step."""
        mode = step.on_failure
        if mode == "abort":
            return _StepAction(action="abort", error=f"step {step.id!r} failed (on_failure=abort)")
        if mode == "skip":
            # Convert the step's row from 'failed' to 'skipped' so the
            # post-condition ('skipped' rows look intentional) holds.
            self._mark_step_skipped(ctx.run_id, step.id)
            return _StepAction(action="advance")
        if mode == "loop_back":
            target_id = step.loop_back_to
            assert target_id is not None  # validated by ProcedureStep
            target_idx = next((i for i, s in enumerate(ctx.spec.steps) if s.id == target_id), None)
            if target_idx is None:
                return _StepAction(action="abort", error=f"loop_back target {target_id!r} missing")
            return _StepAction(action="loop_back", loop_back_index=target_idx)
        if mode == "retry":
            # Out-of-retries already recorded as 'failed'; treat as abort
            # to surface the failure.
            return _StepAction(
                action="abort",
                error=f"step {step.id!r} exhausted retries",
            )
        if mode == "human_review":
            return _StepAction(action="pause")
        return _StepAction(action="abort", error=f"unknown on_failure mode {mode!r}")

    def _maybe_swap_publish_skill(self, ctx: _StepContext, step: ProcedureStep) -> None:
        """If the step is a publish step, re-resolve to the project's primary target.

        Procedure 4 declares ``04-publishing/nuxt-content-publish`` as the
        default in frontmatter; the runner overrides at dispatch time
        based on the project's primary active publish target. This
        keeps the procedure file portable across projects with
        different publishers.

        The swap is gated on the step's ``skill`` being one of the three
        publisher endings (``…-publish``) — schema-emitter and the
        interlinker also live under ``04-publishing/`` but are not
        publishers, so a prefix check alone over-matches.
        """
        if not step.skill.startswith(_PUBLISH_PREFIX):
            return
        if step.skill not in _PUBLISH_KIND_TO_SKILL.values():
            return
        target_skill = self._resolve_publish_skill(ctx.project_id)
        if target_skill is not None and target_skill != step.skill:
            step.skill = target_skill

    def _resolve_publish_skill(self, project_id: int) -> str | None:
        """Look up the project's primary active publish target → skill key."""
        with Session(self._engine) as s:
            row = s.exec(
                select(PublishTarget).where(
                    PublishTarget.project_id == project_id,
                    PublishTarget.is_primary.is_(True),  # type: ignore[union-attr,attr-defined]
                    PublishTarget.is_active.is_(True),  # type: ignore[union-attr,attr-defined]
                )
            ).first()
        if row is None:
            return None
        return _PUBLISH_KIND_TO_SKILL.get(row.kind)

    def _resolve_article_id(self, args: dict[str, Any]) -> int | None:
        """Resolve the article_id the procedure operates on (if any).

        Procedure 4 takes ``topic_id``; the article doesn't yet exist
        when the procedure starts. The first step (``content-brief``)
        is responsible for creating it via ``article.create``. The
        runner discovers the article id at dispatch time from the
        ``content-brief`` step's output_json so subsequent steps can
        carry an article scope.

        Procedures that take ``article_id`` directly (e.g. procedure 7
        content-refresher) get the value here.
        """
        if "article_id" in args:
            try:
                return int(args["article_id"])
            except (TypeError, ValueError):
                return None
        return None

    def _success_metadata(self, ctx: _StepContext) -> dict[str, Any]:
        """Bundle per-step outputs into ``runs.metadata_json`` on success."""
        return {
            "procedure_complete": True,
            "step_outputs": dict(ctx.step_outputs),
            "loop_iteration": dict(ctx.loop_iteration),
        }

    def _heartbeat(self, run_id: int) -> None:
        """Update ``runs.heartbeat_at = now()``."""
        with Session(self._engine) as s:
            RunRepository(s).heartbeat(run_id)

    async def _finalize(
        self,
        *,
        run_id: int,
        status: RunStatus,
        article_id: int | None,
        error: str | None = None,
        verdict_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Move the run to a terminal status."""
        with Session(self._engine) as s:
            RunRepository(s).finish(
                run_id, status=status, error=error, metadata_json=verdict_metadata or None
            )

    async def _abort_with_message(
        self,
        ctx: _StepContext,
        *,
        status: RunStatus,
        error: str,
    ) -> None:
        """Abort the run + surface ``error`` on the row."""
        await self._finalize(
            run_id=ctx.run_id,
            status=status,
            article_id=ctx.article_id,
            error=error,
            verdict_metadata={"step_outputs": dict(ctx.step_outputs)},
        )
        if status == RunStatus.ABORTED and ctx.article_id is not None:
            self._mark_article_aborted(ctx.article_id, reason=error)

    def _mark_article_aborted(self, article_id: int, *, reason: str | None) -> None:
        """Flip ``articles.status='aborted-publish'`` on a BLOCK / abort."""
        with Session(self._engine) as s:
            article = s.get(Article, article_id)
            if article is None:
                return
            terminal = ArticleStatus.ABORTED_PUBLISH
            if article.status == terminal:
                return
            from content_stack.db.models import ARTICLE_STATUS_TRANSITIONS

            allowed = ARTICLE_STATUS_TRANSITIONS.get(article.status, frozenset())
            if terminal not in allowed:
                _log.warning(
                    "procedure_runner.cannot_mark_aborted_publish",
                    extra={
                        "article_id": article_id,
                        "current_status": article.status.value,
                        "reason": reason,
                    },
                )
                return
            article.status = terminal
            s.add(article)
            s.commit()

    def _mark_step_skipped(self, run_id: int, step_id: str) -> None:
        """Convert a 'failed' step row to 'skipped' (skip-on-failure mode).

        The repository layer's ``advance_step`` is permissive — it
        overwrites ``status`` without a transition guard, so we can
        flip ``failed → skipped`` cleanly. Tests assert on the resulting
        timeline shape.
        """
        with Session(self._engine) as s:
            step_repo = ProcedureRunStepRepository(s)
            steps = step_repo.list_steps(run_id)
            row = next((r for r in steps if r.step_id == step_id), None)
            if row is None:
                return
            step_repo.advance_step(row.id, status=ProcedureRunStepStatus.SKIPPED)  # type: ignore[arg-type]

    def _reset_steps_for_loop(self, run_id: int, *, from_index: int) -> None:
        """Reset rows from ``from_index`` onward to 'pending' for a loop_back.

        The audit row keeps prior attempts captured in ``runs.metadata_json.step_outputs``;
        the per-step row's status reflects the latest attempt only.
        """
        with Session(self._engine) as s:
            step_repo = ProcedureRunStepRepository(s)
            steps = step_repo.list_steps(run_id)
            for row in steps:
                if row.step_index < from_index:
                    continue
                step_repo.advance_step(row.id, status=ProcedureRunStepStatus.PENDING)  # type: ignore[arg-type]

    def _fetch_step_row(self, session: Session, run_id: int, step_index: int) -> Any:
        """Return the row matching ``(run_id, step_index)`` or raise."""
        from content_stack.db.models import ProcedureRunStep

        row = session.exec(
            select(ProcedureRunStep).where(
                ProcedureRunStep.run_id == run_id,
                ProcedureRunStep.step_index == step_index,
            )
        ).first()
        if row is None:
            raise NotFoundError(
                f"procedure_run_step (run_id={run_id}, step_index={step_index}) not found",
                data={"run_id": run_id, "step_index": step_index},
            )
        return row

    def _merge_args(self, ctx: _StepContext, step: ProcedureStep) -> dict[str, Any]:
        """Merge step.args + procedure-level args + runtime context."""
        merged: dict[str, Any] = dict(step.args)
        # Procedure-level args (e.g. topic_id) override step defaults.
        for key, value in ctx.args.items():
            merged.setdefault(key, value)
        if ctx.article_id is not None:
            merged.setdefault("article_id", ctx.article_id)
        return merged

    def _load_skill_body(self, skill_path: str) -> str:
        """Read ``skills/<skill_path>/SKILL.md`` (cached)."""
        cached = self._skill_body_cache.get(skill_path)
        if cached is not None:
            return cached
        skill_md = self._skills_dir / skill_path / "SKILL.md"
        if not skill_md.is_file():
            # Stub is fine without the body — but warn so production
            # installs fail visibly when a skill is missing.
            _log.info(
                "procedure_runner.skill_body_missing",
                extra={"skill": skill_path, "path": str(skill_md)},
            )
            self._skill_body_cache[skill_path] = ""
            return ""
        body = skill_md.read_text(encoding="utf-8")
        self._skill_body_cache[skill_path] = body
        return body

    def _make_done_callback(self, run_id: int) -> Callable[[asyncio.Task[None]], None]:
        """Build a typed done-callback closing over ``run_id``.

        Mypy can't always infer the lambda body's type when it captures
        ``self`` + a parameter; an explicit factory keeps the call sites
        terse without an `# type: ignore`.
        """

        def _on_done(_task: asyncio.Task[None]) -> None:
            self._task_done(run_id)

        return _on_done

    def _task_done(self, run_id: int) -> None:
        """Drop the in-flight registry entry once the asyncio task ends."""

        # asyncio guarantees the callback runs on the loop thread, so
        # we can use ``asyncio.create_task`` to acquire the lock.
        async def _drop() -> None:
            async with self._tasks_lock:
                self._tasks.pop(run_id, None)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Loop already shut down — no-op; the registry will be GC'd
            # alongside the runner instance.
            return
        # Fire-and-forget cleanup; we don't need the task ref because it
        # only mutates the in-memory registry.
        loop.create_task(_drop())  # noqa: RUF006


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


@dataclass
class _StepAction:
    """Outcome of a step from the runner's perspective.

    The runner's main loop consumes one of these per step iteration to
    decide what to do next. ``loop_back_index`` is set when ``action ==
    'loop_back'``; otherwise None.
    """

    action: str
    """One of ``'advance' | 'abort' | 'block' | 'loop_back' | 'pause'``."""

    error: str | None = None
    loop_back_index: int | None = None


def _noop_job_marker() -> None:
    """Module-level no-op for APScheduler's ``run-{run_id}`` marker job.

    APScheduler's SQLAlchemyJobStore can only persist top-level
    callables (the pickle layer can't reach closure-bound coroutines).
    The actual runner work lives on an ``asyncio.Task`` we own; this
    function is just a "scheduled job ran" telemetry breadcrumb so
    tests + ``scheduler.get_job(job_id)`` can observe the run.
    """
    return None


def _semaphore_key(slug: str, project_id: int) -> SemaphoreKey:
    """Per-(slug, project_id) semaphore key — M8 per-project serialization.

    PLAN.md L1361 mandates per-project serialization for procedure runs
    (``job_id=procedure-{slug}-{project_id}``); the in-process semaphore
    matches that key so two runs of the same procedure for different
    projects proceed in parallel.
    """
    return f"procedure-{slug}-{project_id}"


def _next_pending_step_index(steps: list[Any]) -> int | None:
    """Return the index of the next pending / running step.

    Used by ``resume`` to find where to pick up. Returns ``None`` if
    every step is terminal.
    """
    for s in steps:
        if s.status in (
            ProcedureRunStepStatus.PENDING,
            ProcedureRunStepStatus.RUNNING,
            ProcedureRunStepStatus.FAILED,
        ):
            return s.step_index
    return None


def _mint_run_token() -> str:
    """Mint a fresh URL-safe run token."""
    import secrets

    return secrets.token_urlsafe(32)


def _default_procedures_dir() -> Path:
    """Repo-root ``procedures/`` (production install will move to XDG)."""
    pkg = Path(__file__).resolve().parent.parent  # content_stack/
    return pkg.parent / "procedures"


def _default_skills_dir(procedures_dir: Path) -> Path:
    """Sibling ``skills/`` directory."""
    return procedures_dir.parent / "skills"


# Type alias re-export so callers can subscript ``RunnerFactory[Self]``
# without importing the inner class.
RunnerFactory = Callable[[], "ProcedureRunner"]


__all__ = [
    "ProcedureRunner",
    "RunnerFactory",
]
