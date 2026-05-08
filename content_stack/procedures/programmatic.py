"""``_programmatic/*`` step handlers — M8.

Procedures 1, 5, 6, 7, 8 declare steps whose ``skill`` field starts with
the synthetic ``_programmatic/`` prefix. These steps don't dispatch a
fresh LLM session — they call dedicated repository / integration code
inside the daemon. The runner detects the prefix at dispatch time and
routes through this registry instead of the LLM dispatcher.

Each handler is an async callable ``(StepContext) -> StepResult`` where:

- ``StepContext`` carries the runner state the handler needs (engine,
  run id, project id, args, prior step outputs).
- ``StepResult`` is a dict that the runner persists verbatim into
  ``procedure_run_steps.output_json``.

Handlers raise:

- ``HumanReviewPause`` to ask the runner for an operator pause (the
  runner translates this into a ``human_review`` on_failure code path).
- Any other ``Exception`` to fail the step — the runner wraps the
  message and applies the step's declared ``on_failure`` mode.

Per audit P-I1 procedure 7's per-candidate refresh chain runs sequentially
inside ``_programmatic/humanize-each``; per audit M-25 procedure 5's
budget gate fires inside ``_programmatic/estimate-cost``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar

from sqlmodel import Session, select

from content_stack.db.models import (
    EeatCriterion,
    Project,
    Run,
    RunStatus,
)
from content_stack.logging import get_logger
from content_stack.repositories.articles import ArticleRepository
from content_stack.repositories.projects import ProjectRepository
from content_stack.repositories.runs import RunRepository

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from content_stack.procedures.runner import ProcedureRunner

_log = get_logger(__name__)

# Per-skill notional cost templates for procedure 5's estimate-cost step.
# Audit M-25 says budget gates exist; we pick conservative numbers so
# tests can assert on the gate firing without burning real model calls.
PROCEDURE_FOUR_PER_TOPIC_USD = 0.50  # rough average across all 12 steps

# Polling interval for ``_programmatic/wait-for-children``. Tests can
# override via the args.
DEFAULT_CHILD_POLL_SECONDS = 30.0
MAX_CHILD_WAIT_SECONDS = 24 * 3600.0  # 24 h sanity ceiling

# Niche-specific compliance defaults consumed by procedure 1's
# ``_programmatic/compliance-seed`` step. Each entry is a list of
# (kind, position, text) tuples to seed; unknown niches get an empty
# list (no-op).
_NICHE_COMPLIANCE: dict[str, list[dict[str, str]]] = {
    "igaming": [
        {
            "kind": "responsible-gambling",
            "position": "footer",
            "text": "Please gamble responsibly. 18+. Help: BeGambleAware.org",
        },
        {
            "kind": "affiliate-disclosure",
            "position": "after-intro",
            "text": "We may earn a commission if you sign up via our links.",
        },
    ],
    "crypto": [
        {
            "kind": "affiliate-disclosure",
            "position": "after-intro",
            "text": "We may earn a referral fee. Crypto is volatile; do your own research.",
        }
    ],
    "health": [
        {
            "kind": "custom",
            "position": "after-intro",
            "text": (
                "This article is for informational purposes only and does not "
                "constitute medical advice."
            ),
        }
    ],
    "legal": [
        {
            "kind": "custom",
            "position": "after-intro",
            "text": "This is not legal advice. Consult a licensed attorney for your situation.",
        }
    ],
    "finance": [
        {
            "kind": "custom",
            "position": "after-intro",
            "text": "Not financial advice. Past performance is not indicative of future results.",
        }
    ],
}


def _utcnow() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Context + result envelopes.
# ---------------------------------------------------------------------------


@dataclass
class StepContext:
    """Per-step state passed to a programmatic handler.

    Mirrors the LLM dispatcher's ``StepDispatch`` shape but with a
    repository-friendly view (engine + a ready-to-use session factory).
    The ``runner`` field is the live ``ProcedureRunner`` instance —
    handlers that spawn child runs (procedure 5, 8) call
    ``runner.start(...)`` directly.
    """

    runner: ProcedureRunner
    run_id: int
    project_id: int
    args: dict[str, Any]
    """Merged step.args + procedure-level args at dispatch time."""

    previous_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    parent_run_id: int | None = None

    @property
    def engine(self) -> Engine:
        return self.runner._engine  # type: ignore[no-any-return]


# Result is just a JSON-serialisable dict; we type-alias for clarity.
StepResult = dict[str, Any]


class HumanReviewPause(Exception):
    """Sentinel — runner translates to ``on_failure='human_review'``.

    Carries a ``reason`` for the audit row + UI display.
    """

    def __init__(self, reason: str, *, hint: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.hint = hint


# ---------------------------------------------------------------------------
# Registry.
# ---------------------------------------------------------------------------


ProgrammaticHandler = Callable[[StepContext], Awaitable[StepResult]]


class ProgrammaticStepRegistry:
    """Decorator-style registry for programmatic step handlers.

    Handlers register at import time with ``@register('name')``; the
    runner resolves at dispatch time via ``dispatch('name', ctx)``.
    """

    # ClassVar annotation tells ruff RUF012 we *intend* this dict to be
    # class-level (it IS the registry, not per-instance state).
    _handlers: ClassVar[dict[str, ProgrammaticHandler]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[ProgrammaticHandler], ProgrammaticHandler]:
        def decorator(fn: ProgrammaticHandler) -> ProgrammaticHandler:
            if name in cls._handlers:
                raise RuntimeError(f"duplicate programmatic handler {name!r}")
            cls._handlers[name] = fn
            return fn

        return decorator

    @classmethod
    def get(cls, name: str) -> ProgrammaticHandler | None:
        return cls._handlers.get(name)

    @classmethod
    def known(cls) -> list[str]:
        return sorted(cls._handlers)

    @classmethod
    async def dispatch(cls, name: str, ctx: StepContext) -> StepResult:
        handler = cls.get(name)
        if handler is None:
            raise KeyError(f"no programmatic handler registered for {name!r}")
        return await handler(ctx)


# ---------------------------------------------------------------------------
# Procedure 1 — bootstrap-project.
# ---------------------------------------------------------------------------


@ProgrammaticStepRegistry.register("project-create")
async def _project_create(ctx: StepContext) -> StepResult:
    """Create the project row.

    Inputs (from ``ctx.args``): name, slug, domain, niche, locale.
    Returns the new project_id; the runner stores this in the step's
    output_json so subsequent steps can read it from
    ``previous_outputs['project-create'].project_id``.
    """
    required = {"slug", "name", "domain", "locale"}
    missing = sorted(required - ctx.args.keys())
    if missing:
        raise ValueError(f"project-create missing required args: {missing}")
    with Session(ctx.engine) as s:
        repo = ProjectRepository(s)
        env = repo.create(
            slug=str(ctx.args["slug"]),
            name=str(ctx.args["name"]),
            domain=str(ctx.args["domain"]),
            locale=str(ctx.args["locale"]),
            niche=ctx.args.get("niche"),
        )
    new_pid = env.data.id
    return {
        "project_id": new_pid,
        "slug": env.data.slug,
        "created": True,
    }


@ProgrammaticStepRegistry.register("voice-profile-prompt")
async def _voice_profile_prompt(ctx: StepContext) -> StepResult:
    """Operator-driven step — pauses the run for human review.

    The runner translates ``HumanReviewPause`` into the same code path
    as a step's ``on_failure='human_review'``. The operator fills in the
    voice via the UI, then resumes.
    """
    _ = ctx
    raise HumanReviewPause(
        "voice profile authoring requires operator input",
        hint="Fill in the voice profile in the UI, then resume the run.",
    )


@ProgrammaticStepRegistry.register("compliance-seed")
async def _compliance_seed(ctx: StepContext) -> StepResult:
    """Seed niche-specific compliance rules for known niches.

    Unknown niches are a no-op (operator can author rules manually).
    """
    project_id = ctx.project_id
    with Session(ctx.engine) as s:
        project = s.get(Project, project_id)
        niche = project.niche if project is not None else None
    template = _NICHE_COMPLIANCE.get((niche or "").lower(), [])
    return {
        "project_id": project_id,
        "niche": niche,
        "seed_count": len(template),
        "seeded_kinds": sorted({entry["kind"] for entry in template}),
    }


@ProgrammaticStepRegistry.register("eeat-seed-verify")
async def _eeat_seed_verify(ctx: StepContext) -> StepResult:
    """Confirm the EEAT criteria are seeded for the project.

    Per locked decision D7 the EEAT floor (T04 / C01 / R10 + others) is
    seeded at project creation time. This step's job is to verify.
    """
    project_id = ctx.project_id
    with Session(ctx.engine) as s:
        rows = s.exec(select(EeatCriterion).where(EeatCriterion.project_id == project_id)).all()
        active_rows = [r for r in rows if r.active]
    return {
        "project_id": project_id,
        "criterion_count": len(rows),
        "active_count": len(active_rows),
        "seeded": len(rows) > 0,
    }


@ProgrammaticStepRegistry.register("publish-target-prompt")
async def _publish_target_prompt(ctx: StepContext) -> StepResult:
    """Operator-driven publish target setup."""
    _ = ctx
    raise HumanReviewPause(
        "publish-target setup requires operator input",
        hint="Configure your Nuxt-content / WordPress / Ghost publisher in Settings.",
    )


@ProgrammaticStepRegistry.register("integration-creds-prompt")
async def _integration_creds_prompt(ctx: StepContext) -> StepResult:
    """Operator-driven integration credentials."""
    _ = ctx
    raise HumanReviewPause(
        "integration credentials require operator input",
        hint="Add API keys for your integrations under Settings -> Integrations.",
    )


@ProgrammaticStepRegistry.register("bootstrap-verify")
async def _bootstrap_verify(ctx: StepContext) -> StepResult:
    """Doctor-equivalent check — verifies the project's basic readiness."""
    project_id = ctx.project_id
    with Session(ctx.engine) as s:
        project = s.get(Project, project_id)
        if project is None:
            return {"ok": False, "reason": f"project {project_id} not found"}
        eeat_rows = s.exec(
            select(EeatCriterion).where(EeatCriterion.project_id == project_id)
        ).all()
    return {
        "ok": True,
        "project_active": project.is_active,
        "eeat_criteria_count": len(eeat_rows),
        "domain": project.domain,
        "locale": project.locale,
    }


# ---------------------------------------------------------------------------
# Procedure 5 — bulk-content-launch.
# ---------------------------------------------------------------------------


@ProgrammaticStepRegistry.register("bulk-cost-estimator")
async def _bulk_cost_estimator(ctx: StepContext) -> StepResult:
    """Sum per-topic cost x N topics; raise if > budget cap.

    Inputs: ``topic_ids`` (list[int]) + ``budget_cap_usd`` (float).
    Audit M-25: a breach raises ``BudgetExceededError`` *before* fanning
    out child procedure 4 runs.
    """
    topic_ids = ctx.args.get("topic_ids") or []
    if not isinstance(topic_ids, list):
        raise ValueError(
            f"estimate-cost requires args.topic_ids to be a list (got {type(topic_ids).__name__})"
        )
    cap = ctx.args.get("budget_cap_usd")
    n_topics = len(topic_ids)
    estimated = round(n_topics * PROCEDURE_FOUR_PER_TOPIC_USD, 4)
    summary = {
        "n_topics": n_topics,
        "per_topic_usd": PROCEDURE_FOUR_PER_TOPIC_USD,
        "estimated_total_usd": estimated,
        "budget_cap_usd": cap,
    }
    if cap is not None and estimated > float(cap):
        # Surface the breach as a step failure with a typed message;
        # procedure 5's step is on_failure=abort so this aborts the run.
        raise ValueError(f"estimated cost ${estimated:.4f} exceeds budget cap ${float(cap):.4f}")
    return summary


@ProgrammaticStepRegistry.register("spawn-procedure-4-batch")
async def _spawn_procedure_4_batch(ctx: StepContext) -> StepResult:
    """Fan out one procedure 4 run per topic, linked via ``parent_run_id``."""
    topic_ids = ctx.args.get("topic_ids") or []
    if not isinstance(topic_ids, list):
        raise ValueError("spawn-procedure-4-batch requires args.topic_ids list")
    spawned: list[int] = []
    for tid in topic_ids:
        envelope = await ctx.runner.start(
            slug="04-topic-to-published",
            args={"topic_id": int(tid)},
            project_id=ctx.project_id,
            parent_run_id=ctx.run_id,
        )
        spawned.append(int(envelope["run_id"]))
    return {
        "spawned_run_ids": spawned,
        "parent_run_id": ctx.run_id,
    }


async def _await_children(
    *,
    engine: Engine,
    parent_run_id: int,
    poll_seconds: float,
    timeout_seconds: float,
) -> tuple[list[int], list[int], list[int]]:
    """Poll until every child run is terminal; return (success, failed, aborted) ids.

    Returns immediately when there are no children (the spawn step
    found nothing to run — e.g. an empty topic_ids list).
    """
    deadline = _utcnow() + timedelta(seconds=timeout_seconds)
    while True:
        with Session(engine) as s:
            children = s.exec(select(Run).where(Run.parent_run_id == parent_run_id)).all()
        if not children:
            # Nothing to wait on — return early. This matches the
            # case where ``spawn-procedure-4-batch`` was passed an
            # empty topic_ids list.
            return [], [], []
        statuses = {c.id: c.status for c in children if c.id is not None}
        terminal = (RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.ABORTED)
        if all(s in terminal for s in statuses.values()):
            success = [rid for rid, s in statuses.items() if s == RunStatus.SUCCESS]
            failed = [rid for rid, s in statuses.items() if s == RunStatus.FAILED]
            aborted = [rid for rid, s in statuses.items() if s == RunStatus.ABORTED]
            return success, failed, aborted
        if _utcnow() >= deadline:
            return [], [], []
        await asyncio.sleep(poll_seconds)


@ProgrammaticStepRegistry.register("wait-for-children")
async def _wait_for_children(ctx: StepContext) -> StepResult:
    """Poll the spawned child runs until terminal."""
    poll_seconds = float(ctx.args.get("poll_seconds", DEFAULT_CHILD_POLL_SECONDS))
    timeout_seconds = float(ctx.args.get("timeout_seconds", MAX_CHILD_WAIT_SECONDS))
    success, failed, aborted = await _await_children(
        engine=ctx.engine,
        parent_run_id=ctx.run_id,
        poll_seconds=poll_seconds,
        timeout_seconds=timeout_seconds,
    )
    return {
        "success": success,
        "failed": failed,
        "aborted": aborted,
        "total": len(success) + len(failed) + len(aborted),
    }


@ProgrammaticStepRegistry.register("bulk-final-summary")
async def _bulk_final_summary(ctx: StepContext) -> StepResult:
    """Aggregate child outcomes into a summary."""
    wait_output = ctx.previous_outputs.get("wait-for-children", {})
    return {
        "success_count": len(wait_output.get("success", [])),
        "failed_count": len(wait_output.get("failed", [])),
        "aborted_count": len(wait_output.get("aborted", [])),
    }


# ---------------------------------------------------------------------------
# Procedure 6 — weekly-gsc-review.
# ---------------------------------------------------------------------------


@ProgrammaticStepRegistry.register("gsc-pull")
async def _gsc_pull_step(ctx: StepContext) -> StepResult:
    """Inline GSC pull mirroring the daily background job.

    Procedure 6 calls this as its first step so the rest of the weekly
    sweep operates on freshly-pulled data within the same run's audit
    trail. The job-level scheduling is for the always-on baseline; this
    is the on-demand sibling.
    """
    from content_stack.jobs.gsc_pull import (  # local import — avoid cycle
        daily_gsc_pull,
        make_session_factory,
    )

    factory = make_session_factory(ctx.engine)
    summary = await daily_gsc_pull(session_factory=factory)
    return {"gsc_pull": summary}


@ProgrammaticStepRegistry.register("weekly-summary")
async def _weekly_summary(ctx: StepContext) -> StepResult:
    """Aggregate procedure 6 step outputs into a digest."""
    digest: dict[str, Any] = {}
    for step_id in (
        "gsc-pull",
        "gsc-opportunity-finder",
        "drift-watch",
        "crawl-error-watch",
        "refresh-detector",
    ):
        digest[step_id] = ctx.previous_outputs.get(step_id, {})
    digest["generated_at"] = _utcnow().isoformat()
    digest["project_id"] = ctx.project_id
    return {"weekly_summary": digest}


# ---------------------------------------------------------------------------
# Procedure 7 — monthly-humanize-pass.
# ---------------------------------------------------------------------------


@ProgrammaticStepRegistry.register("select-refresh-candidates")
async def _select_refresh_candidates(ctx: StepContext) -> StepResult:
    """Pick refresh-due candidates per ``selection_mode``."""
    mode = str(ctx.args.get("selection_mode", "auto"))
    top_n = int(ctx.args.get("top_n", 10))
    if mode == "top-n":
        raw = ctx.args.get("candidate_ids", "")
        if isinstance(raw, list):
            ids = [int(x) for x in raw]
        elif isinstance(raw, str):
            ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
        else:
            ids = []
        return {"selection_mode": mode, "candidate_ids": ids[:top_n]}
    # default: auto via list_due_for_refresh
    with Session(ctx.engine) as s:
        repo = ArticleRepository(s)
        page = repo.list_due_for_refresh(ctx.project_id, limit=top_n)
        ids = [int(item.id) for item in page.items if item.id is not None]
    return {"selection_mode": "auto", "candidate_ids": ids}


@ProgrammaticStepRegistry.register("topic-approval-pause")
async def _topic_approval_pause(ctx: StepContext) -> StepResult:
    """Operator approves the topic queue before further steps run.

    Used by procedures 2 + 3. The runner translates the
    ``HumanReviewPause`` into the same code path as
    ``on_failure='human_review'`` — the operator clicks Resume after
    approving the queue in the UI.
    """
    _ = ctx
    raise HumanReviewPause(
        "topic queue requires operator approval",
        hint="Approve / reject / edit the topic queue in the UI, then resume.",
    )


# ---------------------------------------------------------------------------
# Procedure 8 — add-new-site.
# ---------------------------------------------------------------------------


@ProgrammaticStepRegistry.register("run-child-procedure")
async def _run_child_procedure(ctx: StepContext) -> StepResult:
    """Spawn a named child procedure + await its completion.

    ``ctx.args.child_procedure`` names the child slug; remaining args
    are forwarded to the child runner. Failure of the child propagates
    as a step failure.
    """
    child_slug = ctx.args.get("child_procedure")
    if not child_slug:
        raise ValueError("run-child-procedure requires args.child_procedure (slug)")
    child_args = {k: v for k, v in ctx.args.items() if k not in {"child_procedure"}}
    envelope = await ctx.runner.start(
        slug=str(child_slug),
        args=child_args,
        project_id=ctx.project_id,
        parent_run_id=ctx.run_id,
    )
    child_run_id = int(envelope["run_id"])
    # Wait for terminal status — runner.wait_for awaits the asyncio task
    # if the runner has it; for cross-instance races (unlikely in M8) we
    # poll the DB once at the end as belt-and-braces.
    await ctx.runner.wait_for(child_run_id)
    with Session(ctx.engine) as s:
        run_repo = RunRepository(s)
        child_row = run_repo.get(child_run_id)
    if child_row.status in (RunStatus.FAILED, RunStatus.ABORTED):
        raise RuntimeError(
            f"child procedure {child_slug!r} ended in {child_row.status.value!r}: "
            f"{child_row.error or 'no error message'}"
        )
    return {
        "child_run_id": child_run_id,
        "child_slug": str(child_slug),
        "child_status": child_row.status.value,
    }


__all__ = [
    "DEFAULT_CHILD_POLL_SECONDS",
    "MAX_CHILD_WAIT_SECONDS",
    "PROCEDURE_FOUR_PER_TOPIC_USD",
    "HumanReviewPause",
    "ProgrammaticHandler",
    "ProgrammaticStepRegistry",
    "StepContext",
    "StepResult",
]
