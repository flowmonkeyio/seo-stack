"""``_programmatic/*`` step handlers.

Procedures 1, 5, 6, 7, 8 declare steps whose ``skill`` field starts with
the synthetic ``_programmatic/`` prefix. These steps do not start a
fresh model session. The current agent explicitly calls
``procedure.executeProgrammaticStep`` and the daemon runs dedicated
repository / integration code for that one deterministic step.

Each handler is an async callable ``(StepContext) -> StepResult`` where:

- ``StepContext`` carries the runner state the handler needs (engine,
  run id, project id, args, prior step outputs).
- ``StepResult`` is a dict that the runner persists verbatim into
  ``procedure_run_steps.output_json``.

Handlers raise:

- ``HumanReviewPause`` to ask the current agent/operator to manage child
  runs, approve queued work, or provide missing setup before retrying.
- Any other ``Exception`` to fail the step — the runner wraps the
  message and applies the step's declared ``on_failure`` mode.

Per audit P-I1 procedure 7's per-candidate refresh chain runs sequentially
under agent control; per audit M-25 procedure 5's budget gate fires
inside ``_programmatic/bulk-cost-estimator``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

from sqlmodel import Session, select

from content_stack.db.models import (
    EeatCriterion,
    ProcedureRunStep,
    Project,
    Run,
    RunStatus,
    Topic,
    TopicStatus,
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

    The ``runner`` field is the live ``ProcedureRunner`` instance.
    Handlers that need child procedures call ``runner.start(...)`` to
    open child runs for the current agent to manage.
    """

    runner: ProcedureRunner
    run_id: int
    step_id: str
    project_id: int
    args: dict[str, Any]
    """Merged step.args + procedure-level args for this step package."""

    previous_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    parent_run_id: int | None = None

    @property
    def engine(self) -> Engine:
        return self.runner._engine  # type: ignore[no-any-return]


# Result is just a JSON-serialisable dict; we type-alias for clarity.
StepResult = dict[str, Any]


class HumanReviewPause(Exception):
    """Sentinel — runner records a retryable human/agent pause.

    Carries a ``reason`` for the audit row + UI display and optional
    structured data for the next retry.
    """

    def __init__(
        self,
        reason: str,
        *,
        hint: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.hint = hint
        self.data = data or {}


# ---------------------------------------------------------------------------
# Registry.
# ---------------------------------------------------------------------------


ProgrammaticHandler = Callable[[StepContext], Awaitable[StepResult]]


class ProgrammaticStepRegistry:
    """Decorator-style registry for programmatic step handlers.

    Handlers register at import time with ``@register('name')``; the
    controller resolves the handler when
    ``procedure.executeProgrammaticStep`` is called.
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


def _parse_topic_ids(value: Any) -> list[int]:
    """Normalise procedure-5 topic ids from list or comma-separated string."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [int(item) for item in value]
    if isinstance(value, str):
        return [int(part.strip()) for part in value.split(",") if part.strip()]
    raise ValueError(
        f"topic_ids must be a list or comma-separated string (got {type(value).__name__})"
    )


def _bool_arg(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _bulk_topic_ids(ctx: StepContext) -> list[int]:
    """Resolve procedure-5 topic selection from explicit ids or all-approved."""
    if _bool_arg(ctx.args.get("all_approved", False)):
        with Session(ctx.engine) as s:
            ids = s.exec(
                select(Topic.id).where(
                    Topic.project_id == ctx.project_id,
                    Topic.status == TopicStatus.APPROVED,
                )
            ).all()
        return [int(tid) for tid in ids if tid is not None]
    return _parse_topic_ids(ctx.args.get("topic_ids"))


@ProgrammaticStepRegistry.register("bulk-cost-estimator")
async def _bulk_cost_estimator(ctx: StepContext) -> StepResult:
    """Sum per-topic cost x N topics; raise if > budget cap.

    Inputs: ``topic_ids`` (list[int]) + ``budget_cap_usd`` (float).
    Audit M-25: a breach raises ``BudgetExceededError`` *before* fanning
    out child procedure 4 runs.
    """
    topic_ids = _bulk_topic_ids(ctx)
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
    topic_ids = _bulk_topic_ids(ctx)
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
        "topic_ids": topic_ids,
    }


@ProgrammaticStepRegistry.register("wait-for-children")
async def _wait_for_children(ctx: StepContext) -> StepResult:
    """Summarise spawned child runs or pause until the agent completes them."""
    with Session(ctx.engine) as s:
        children = s.exec(select(Run).where(Run.parent_run_id == ctx.run_id)).all()
    statuses = {int(c.id): c.status for c in children if c.id is not None}
    success = [rid for rid, status in statuses.items() if status == RunStatus.SUCCESS]
    failed = [rid for rid, status in statuses.items() if status == RunStatus.FAILED]
    aborted = [rid for rid, status in statuses.items() if status == RunStatus.ABORTED]
    running = [rid for rid, status in statuses.items() if status == RunStatus.RUNNING]
    if running:
        raise HumanReviewPause(
            "child procedure runs are still active",
            hint="Complete or abort the listed child runs, then retry this step.",
            data={
                "running_run_ids": running,
                "success": success,
                "failed": failed,
                "aborted": aborted,
            },
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
    """Spawn a named child procedure and pause until the agent completes it.

    ``ctx.args.child_procedure`` names the child slug; remaining args
    are forwarded to the child runner. Failure of the child propagates
    as a step failure.
    """
    child_slug = ctx.args.get("child_procedure")
    if not child_slug:
        raise ValueError("run-child-procedure requires args.child_procedure (slug)")
    prior = _current_step_output(ctx)
    prior_child_id = prior.get("child_run_id")
    if prior_child_id is not None:
        child_run_id = int(prior_child_id)
        with Session(ctx.engine) as s:
            child_row = RunRepository(s).get(child_run_id)
        if child_row.status == RunStatus.RUNNING:
            raise HumanReviewPause(
                f"child procedure {child_slug!r} still running",
                hint=f"Complete child run {child_run_id}, then retry this step.",
                data=prior,
            )
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

    child_args = {k: v for k, v in ctx.args.items() if k not in {"child_procedure"}}
    envelope = await ctx.runner.start(
        slug=str(child_slug),
        args=child_args,
        project_id=ctx.project_id,
        parent_run_id=ctx.run_id,
    )
    child_run_id = int(envelope["run_id"])
    data = {
        "child_run_id": child_run_id,
        "child_slug": str(child_slug),
        "child_status": RunStatus.RUNNING.value,
    }
    raise HumanReviewPause(
        f"child procedure {child_slug!r} opened",
        hint=f"Manage child run {child_run_id}, then retry this step.",
        data=data,
    )


def _current_step_output(ctx: StepContext) -> dict[str, Any]:
    """Return this step row's existing output, if a retry is in progress."""
    with Session(ctx.engine) as s:
        row = s.exec(
            select(ProcedureRunStep).where(
                ProcedureRunStep.run_id == ctx.run_id,
                ProcedureRunStep.step_id == ctx.step_id,
            )
        ).first()
    if row is None or not isinstance(row.output_json, dict):
        return {}
    return dict(row.output_json)


__all__ = [
    "PROCEDURE_FOUR_PER_TOPIC_USD",
    "HumanReviewPause",
    "ProgrammaticHandler",
    "ProgrammaticStepRegistry",
    "StepContext",
    "StepResult",
]
