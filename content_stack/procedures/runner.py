"""Agent-led procedure controller.

The current external agent is the procedure brain. It opens a run,
claims a step, follows the returned ``SKILL.md`` instructions, calls MCP
tools directly, and records the result. The daemon owns durable state,
step-scoped grants, audit rows, fork/resume helpers, and deterministic
programmatic handlers. It does not spawn hidden writer LLM sessions.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from content_stack.config import Settings
from content_stack.db.models import (
    ProcedureRunStepStatus,
    PublishTarget,
    PublishTargetKind,
    Run,
    RunKind,
    RunStatus,
)
from content_stack.mcp.permissions import SKILL_TOOL_GRANTS
from content_stack.procedures.parser import (
    ProcedureSpec,
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
    ProcedureRunStepOut,
    ProcedureRunStepRepository,
    RunOut,
    RunRepository,
)

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

_PROGRAMMATIC_PREFIX = "_programmatic/"
_PUBLISH_STEP_ID = "publish"
_PUBLISH_PREFIX = "04-publishing/"

_PUBLISH_KIND_TO_SKILL: dict[PublishTargetKind, str] = {
    PublishTargetKind.NUXT_CONTENT: "04-publishing/nuxt-content-publish",
    PublishTargetKind.WORDPRESS: "04-publishing/wordpress-publish",
    PublishTargetKind.GHOST: "04-publishing/ghost-publish",
}

_log = logging.getLogger(__name__)


class ProcedureRunner:
    """Durable procedure controller for caller-owned agent execution."""

    def __init__(
        self,
        *,
        settings: Settings,
        engine: Engine,
        procedures_dir: Path | None = None,
        scheduler: AsyncIOScheduler | None = None,
    ) -> None:
        self._settings = settings
        self._engine = engine
        if procedures_dir is None:
            procedures_dir = _default_procedures_dir()
        self._procedures_dir = procedures_dir
        self._registry: dict[str, ProcedureSpec] = load_all_procedures(procedures_dir)
        self._skills_dir = _default_skills_dir(procedures_dir)
        self._skill_body_cache: dict[str, str] = {}
        self._scheduler = scheduler

    def bind_scheduler(self, scheduler: AsyncIOScheduler) -> None:
        """Attach the scheduler for cron registration bookkeeping."""
        self._scheduler = scheduler

    def list_procedures(self) -> list[str]:
        """Return registered procedure slugs."""
        return sorted(self._registry.keys())

    def list_procedures_with_specs(self) -> dict[str, ProcedureSpec]:
        """Return ``slug -> ProcedureSpec`` for scheduler registration."""
        return dict(self._registry)

    def get_spec(self, slug: str) -> ProcedureSpec:
        """Return one procedure spec or raise ``NotFoundError``."""
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
        variant: str | None = None,
        client_session_id: str | None = None,
    ) -> dict[str, Any]:
        """Open a procedure run for the current agent to manage."""
        spec = self.get_spec(slug)
        if variant is not None:
            spec = spec.apply_variant(variant)
        run_token, run_id = self._open_run(
            slug=slug,
            project_id=project_id,
            parent_run_id=parent_run_id,
            args=args,
            spec=spec,
            variant_name=variant,
            client_session_id=client_session_id,
        )
        return {
            "run_id": run_id,
            "run_token": run_token,
            "status_url": f"/api/v1/procedures/runs/{run_id}",
            "slug": slug,
            "project_id": project_id,
            "parent_run_id": parent_run_id,
            "started": True,
            "orchestration_mode": "agent-led",
        }

    async def resume(self, *, run_id: int) -> dict[str, Any]:
        """Re-open an aborted / paused procedure run without executing work."""
        with Session(self._engine) as s:
            run_row = self._fetch_procedure_run(s, run_id)
            metadata = dict(run_row.metadata_json or {})
            spec = self._spec_from_run_metadata(run_row.procedure_slug or "", metadata)
            if not spec.resumable:
                raise ConflictError(
                    f"procedure {spec.slug!r} declares resumable=false",
                    data={"slug": spec.slug, "run_id": run_id},
                )
            steps = ProcedureRunStepRepository(s).list_steps(run_id)
            self._guard_step_graph_matches(run_id=run_id, spec=spec, steps=steps)
            if self._is_eeat_blocked_run(run_row, steps):
                raise ConflictError(
                    "run was aborted by eeat-gate=BLOCK and cannot be resumed",
                    data={"run_id": run_id, "slug": spec.slug},
                )
            if run_row.status != RunStatus.RUNNING:
                run_row.status = RunStatus.RUNNING
                run_row.error = None
                run_row.ended_at = None
            metadata["orchestration_mode"] = "agent-led"
            metadata["agent_control"] = {"state": "waiting_for_agent"}
            metadata["skill_name"] = spec.slug
            run_row.metadata_json = metadata
            run_row.heartbeat_at = _utcnow()
            s.add(run_row)
            s.commit()
            project_id = run_row.project_id or 0
            run_token = run_row.client_session_id or ""
        return {
            "run_id": run_id,
            "run_token": run_token,
            "status_url": f"/api/v1/procedures/runs/{run_id}",
            "slug": spec.slug,
            "project_id": project_id,
            "started": True,
            "orchestration_mode": "agent-led",
        }

    async def fork(self, *, run_id: int, from_step_index: int) -> dict[str, Any]:
        """Fork a run for caller-managed execution from ``from_step_index``."""
        with Session(self._engine) as s:
            source_row = self._fetch_procedure_run(s, run_id)
            metadata = dict(source_row.metadata_json or {})
            spec = self._spec_from_run_metadata(source_row.procedure_slug or "", metadata)
            if from_step_index < 0 or from_step_index >= len(spec.steps):
                raise ValidationError(
                    f"from_step_index {from_step_index} out of range for procedure "
                    f"{spec.slug!r} (has {len(spec.steps)} steps)",
                    data={"from_step_index": from_step_index, "step_count": len(spec.steps)},
                )
            source_steps = ProcedureRunStepRepository(s).list_steps(run_id)
            self._guard_step_graph_matches(run_id=run_id, spec=spec, steps=source_steps)
            seed_outputs = _successful_outputs(source_steps[:from_step_index])
            args = metadata.get("procedure_args", {}) or {}
            project_id = source_row.project_id or 0
            variant_name = metadata.get("procedure_variant")
            if not isinstance(variant_name, str):
                variant_name = None

        run_token, new_run_id = self._open_run(
            slug=spec.slug,
            project_id=project_id,
            parent_run_id=run_id,
            args=args,
            spec=spec,
            variant_name=variant_name,
            client_session_id=None,
        )
        with Session(self._engine) as s:
            step_repo = ProcedureRunStepRepository(s)
            for step_row in step_repo.list_steps(new_run_id)[:from_step_index]:
                step_repo.advance_step(
                    step_row.id,  # type: ignore[arg-type]
                    status=ProcedureRunStepStatus.SKIPPED,
                    output_json=seed_outputs.get(step_row.step_id),
                )
        return {
            "run_id": new_run_id,
            "run_token": run_token,
            "status_url": f"/api/v1/procedures/runs/{new_run_id}",
            "slug": spec.slug,
            "project_id": project_id,
            "parent_run_id": run_id,
            "started": True,
            "orchestration_mode": "agent-led",
        }

    async def abort(self, *, run_id: int, cascade: bool = False) -> dict[str, Any]:
        """Abort a procedure run and optionally cascade to children."""
        with Session(self._engine) as s:
            RunRepository(s).abort(run_id, cascade=cascade)
            row = s.get(Run, run_id)
            project_id = row.project_id if row is not None else None
        return {
            "run_id": run_id,
            "project_id": project_id,
            "aborted": True,
            "cascade": cascade,
        }

    def current_step(self, *, run_id: int) -> dict[str, Any]:
        """Return the current step package the external agent should run."""
        with Session(self._engine) as s:
            run_row = self._fetch_procedure_run(s, run_id)
            metadata = dict(run_row.metadata_json or {})
            spec = self._spec_from_run_metadata(run_row.procedure_slug or "", metadata)
            steps = ProcedureRunStepRepository(s).list_steps(run_id)
            self._guard_step_graph_matches(run_id=run_id, spec=spec, steps=steps)
            return self._agent_step_payload(
                run_row=run_row,
                spec=spec,
                steps=steps,
                step_index=_current_step_index(steps),
                metadata=metadata,
            )

    def claim_step(self, *, run_id: int, step_id: str | None = None) -> dict[str, Any]:
        """Mark the current step running and bind the run token to its skill."""
        with Session(self._engine) as s:
            run_row = self._fetch_procedure_run(s, run_id)
            metadata = dict(run_row.metadata_json or {})
            spec = self._spec_from_run_metadata(run_row.procedure_slug or "", metadata)
            step_repo = ProcedureRunStepRepository(s)
            steps = step_repo.list_steps(run_id)
            self._guard_step_graph_matches(run_id=run_id, spec=spec, steps=steps)
            step_index = _current_step_index(steps)
            if step_index is None:
                return self._agent_step_payload(
                    run_row=run_row,
                    spec=spec,
                    steps=steps,
                    step_index=None,
                    metadata=metadata,
                )

            step_row = steps[step_index]
            step_spec = spec.steps[step_index]
            if step_id is not None and step_row.step_id != step_id:
                raise ConflictError(
                    "requested step is not the current claimable procedure step",
                    data={
                        "run_id": run_id,
                        "requested_step_id": step_id,
                        "current_step_id": step_row.step_id,
                    },
                )
            if step_row.status in {ProcedureRunStepStatus.PENDING, ProcedureRunStepStatus.FAILED}:
                step_repo.advance_step(
                    step_row.id,  # type: ignore[arg-type]
                    status=ProcedureRunStepStatus.RUNNING,
                )
                steps = step_repo.list_steps(run_id)
                step_row = steps[step_index]

            metadata["orchestration_mode"] = "agent-led"
            metadata["skill_name"] = self._resolved_skill(
                project_id=run_row.project_id or 0,
                step=step_spec,
            )
            metadata["agent_control"] = {
                "state": "step-claimed",
                "step_id": step_row.step_id,
                "step_index": step_row.step_index,
                "skill": metadata["skill_name"],
            }
            run_row.metadata_json = metadata
            run_row.last_step = step_row.step_id
            run_row.last_step_at = _utcnow()
            run_row.heartbeat_at = _utcnow()
            s.add(run_row)
            s.commit()
            s.refresh(run_row)
            return self._agent_step_payload(
                run_row=run_row,
                spec=spec,
                steps=steps,
                step_index=step_index,
                metadata=metadata,
            )

    def record_step(
        self,
        *,
        run_id: int,
        step_id: str,
        status: ProcedureRunStepStatus,
        output_json: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Persist the current agent's step result and return the next context."""
        if status not in {
            ProcedureRunStepStatus.SUCCESS,
            ProcedureRunStepStatus.FAILED,
            ProcedureRunStepStatus.SKIPPED,
        }:
            raise ValidationError(
                "procedure.recordStep status must be success, failed, or skipped",
                data={"status": status},
            )
        with Session(self._engine) as s:
            run_row = self._fetch_procedure_run(s, run_id)
            metadata = dict(run_row.metadata_json or {})
            spec = self._spec_from_run_metadata(run_row.procedure_slug or "", metadata)
            step_repo = ProcedureRunStepRepository(s)
            steps = step_repo.list_steps(run_id)
            self._guard_step_graph_matches(run_id=run_id, spec=spec, steps=steps)
            target = next((row for row in steps if row.step_id == step_id), None)
            if target is None:
                raise NotFoundError(
                    f"step {step_id!r} not found on run {run_id}",
                    data={"run_id": run_id, "step_id": step_id},
                )
            if target.status == ProcedureRunStepStatus.PENDING:
                step_repo.advance_step(
                    target.id,  # type: ignore[arg-type]
                    status=ProcedureRunStepStatus.RUNNING,
                )
            step_repo.advance_step(
                target.id,  # type: ignore[arg-type]
                status=status,
                output_json=output_json,
                error=error,
            )
            steps = step_repo.list_steps(run_id)
            run_row = self._fetch_procedure_run(s, run_id)
            metadata = dict(run_row.metadata_json or {})
            metadata["orchestration_mode"] = "agent-led"
            metadata["skill_name"] = spec.slug
            metadata["agent_control"] = {
                "state": "step-recorded",
                "step_id": step_id,
                "status": status.value,
                "failure_policy": spec.steps[target.step_index].on_failure,
            }
            if output_json is not None:
                step_outputs = dict(metadata.get("step_outputs") or {})
                step_outputs[step_id] = output_json
                metadata["step_outputs"] = step_outputs
            run_row.metadata_json = metadata
            run_row.last_step = step_id
            run_row.last_step_at = _utcnow()
            run_row.heartbeat_at = _utcnow()

            failure_policy = spec.steps[target.step_index].on_failure
            if status == ProcedureRunStepStatus.FAILED and failure_policy == "abort":
                run_row.status = RunStatus.FAILED
                run_row.error = error or f"procedure step {step_id!r} failed"
                run_row.ended_at = _utcnow()
            elif _all_steps_successful(steps):
                run_row.status = RunStatus.SUCCESS
                run_row.ended_at = _utcnow()
                metadata["procedure_complete"] = True
                run_row.metadata_json = metadata
            s.add(run_row)
            s.commit()
            s.refresh(run_row)
            return self._agent_step_payload(
                run_row=run_row,
                spec=spec,
                steps=steps,
                step_index=_current_step_index(steps),
                metadata=dict(run_row.metadata_json or {}),
            )

    async def execute_programmatic_step(
        self,
        *,
        run_id: int,
        step_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute the current deterministic ``_programmatic/*`` step."""
        claimed = self.claim_step(run_id=run_id, step_id=step_id)
        current = claimed.get("current_step")
        if not isinstance(current, dict):
            return claimed
        if current.get("step_type") != "programmatic":
            raise ValidationError(
                "current procedure step is not programmatic",
                data={"run_id": run_id, "step_id": current.get("step_id")},
            )
        skill = str(current["skill"])
        handler_name = skill[len(_PROGRAMMATIC_PREFIX) :]
        handler = ProgrammaticStepRegistry.get(handler_name)
        if handler is None:
            raise NotFoundError(
                f"no programmatic handler registered for {skill!r}",
                data={"skill": skill, "handler": handler_name},
            )
        ctx = ProgrammaticStepContext(
            runner=self,
            run_id=run_id,
            step_id=str(current["step_id"]),
            project_id=int(claimed["project_id"] or 0),
            args=dict(current.get("args") or {}),
            previous_outputs=dict(claimed.get("previous_outputs") or {}),
        )
        try:
            output = await handler(ctx)
        except HumanReviewPause as exc:
            return self.record_step(
                run_id=run_id,
                step_id=str(current["step_id"]),
                status=ProcedureRunStepStatus.FAILED,
                output_json={
                    "human_review": True,
                    "reason": exc.reason,
                    "hint": exc.hint,
                    "skill": skill,
                    **exc.data,
                },
                error=f"human-review-pause: {exc.reason}",
            )
        except Exception as exc:
            _log.warning(
                "procedure.programmatic_step_failed",
                extra={"run_id": run_id, "step_id": current.get("step_id"), "error": str(exc)},
            )
            return self.record_step(
                run_id=run_id,
                step_id=str(current["step_id"]),
                status=ProcedureRunStepStatus.FAILED,
                error=str(exc),
            )
        return self.record_step(
            run_id=run_id,
            step_id=str(current["step_id"]),
            status=ProcedureRunStepStatus.SUCCESS,
            output_json=output,
        )

    def _open_run(
        self,
        *,
        slug: str,
        project_id: int,
        parent_run_id: int | None,
        args: dict[str, Any],
        spec: ProcedureSpec,
        variant_name: str | None,
        client_session_id: str | None,
    ) -> tuple[str, int]:
        token = client_session_id or _mint_run_token()
        metadata = {
            "orchestration_mode": "agent-led",
            "procedure_slug": slug,
            "procedure_args": args,
            "procedure_step_ids": [step.id for step in spec.steps],
            "skill_name": spec.slug,
            "agent_control": {"state": "waiting_for_agent"},
        }
        if variant_name:
            metadata["procedure_variant"] = variant_name
        with Session(self._engine) as s:
            env = RunRepository(s).start(
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

    def _fetch_procedure_run(self, session: Session, run_id: int) -> Run:
        row = session.get(Run, run_id)
        if row is None:
            raise NotFoundError(f"run {run_id} not found", data={"run_id": run_id})
        if row.procedure_slug is None:
            raise ValidationError(
                f"run {run_id} is not a procedure run (no procedure_slug)",
                data={"run_id": run_id},
            )
        return row

    def _spec_from_run_metadata(self, slug: str, metadata: dict[str, Any]) -> ProcedureSpec:
        spec = self.get_spec(slug)
        variant_name = metadata.get("procedure_variant")
        if isinstance(variant_name, str) and variant_name:
            return spec.apply_variant(variant_name)
        return spec

    def _guard_step_graph_matches(
        self,
        *,
        run_id: int,
        spec: ProcedureSpec,
        steps: list[Any],
    ) -> None:
        expected = [step.id for step in spec.steps]
        actual = [row.step_id for row in sorted(steps, key=lambda row: row.step_index)]
        if actual != expected:
            raise ConflictError(
                "procedure step graph for run no longer matches the resolved spec",
                data={
                    "run_id": run_id,
                    "slug": spec.slug,
                    "expected_step_ids": expected,
                    "actual_step_ids": actual,
                },
            )

    def _is_eeat_blocked_run(self, run_row: Run, steps: list[Any]) -> bool:
        if run_row.status != RunStatus.ABORTED:
            return False
        if run_row.error and "eeat-gate=BLOCK" in run_row.error:
            return True
        for step_row in steps:
            if step_row.step_id != "eeat-gate":
                continue
            out = step_row.output_json
            if isinstance(out, dict) and out.get("verdict") == "BLOCK":
                return True
        return False

    def _agent_step_payload(
        self,
        *,
        run_row: Run,
        spec: ProcedureSpec,
        steps: list[ProcedureRunStepOut],
        step_index: int | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if run_row.status != RunStatus.RUNNING:
            step_index = None
        procedure_args = dict(metadata.get("procedure_args") or {})
        previous_outputs = {
            row.step_id: row.output_json
            for row in steps
            if row.output_json is not None and (step_index is None or row.step_index < step_index)
        }
        article_id = _resolve_article_id(procedure_args, previous_outputs)
        payload: dict[str, Any] = {
            "run": RunOut.model_validate(run_row),
            "steps": steps,
            "run_id": run_row.id,
            "run_token": run_row.client_session_id or "",
            "slug": spec.slug,
            "project_id": run_row.project_id,
            "orchestration_mode": "agent-led",
            "procedure_args": procedure_args,
            "previous_outputs": previous_outputs,
            "current_step": None,
            "next_action": _next_action(run_row, steps),
        }
        if step_index is None:
            return payload

        step_spec = spec.steps[step_index]
        step_row = next(row for row in steps if row.step_index == step_index)
        skill = self._resolved_skill(project_id=run_row.project_id or 0, step=step_spec)
        merged_args = dict(step_spec.args)
        for key, value in procedure_args.items():
            merged_args.setdefault(key, value)
        if article_id is not None:
            merged_args.setdefault("article_id", article_id)
        target_id = self._primary_target_id(
            project_id=run_row.project_id or 0,
            step=step_spec,
        )
        if target_id is not None:
            merged_args.setdefault("target_id", target_id)
        allowed_tools = sorted(SKILL_TOOL_GRANTS.get(skill, frozenset()))
        is_programmatic = skill.startswith(_PROGRAMMATIC_PREFIX)
        payload["current_step"] = {
            "row": step_row,
            "step_id": step_row.step_id,
            "step_index": step_row.step_index,
            "status": step_row.status,
            "skill": skill,
            "step_type": "programmatic" if is_programmatic else "skill",
            "skill_body": "" if is_programmatic else self._load_skill_body(skill),
            "allowed_tools": allowed_tools,
            "args": merged_args,
            "context": {
                "article_id": article_id,
                "previous_outputs": previous_outputs,
                "procedure_args": procedure_args,
                "allowed_tools": allowed_tools,
            },
            "failure_policy": {
                "on_failure": step_spec.on_failure,
                "loop_back_to": step_spec.loop_back_to,
                "max_retries": step_spec.max_retries,
            },
        }
        if is_programmatic:
            payload["next_action"] = "execute_programmatic_step"
        elif step_row.status == ProcedureRunStepStatus.RUNNING:
            payload["next_action"] = "execute_step"
        else:
            payload["next_action"] = "claim_step"
        return payload

    def _resolved_skill(self, *, project_id: int, step: Any) -> str:
        if not _is_target_publish_step(step):
            return step.skill
        with Session(self._engine) as s:
            row = s.exec(
                select(PublishTarget).where(
                    PublishTarget.project_id == project_id,
                    PublishTarget.is_primary.is_(True),  # type: ignore[union-attr,attr-defined]
                    PublishTarget.is_active.is_(True),  # type: ignore[union-attr,attr-defined]
                )
            ).first()
        if row is None:
            return step.skill
        return _PUBLISH_KIND_TO_SKILL.get(row.kind, step.skill)

    def _primary_target_id(self, *, project_id: int, step: Any) -> int | None:
        if not _is_target_publish_step(step):
            return None
        with Session(self._engine) as s:
            row = s.exec(
                select(PublishTarget).where(
                    PublishTarget.project_id == project_id,
                    PublishTarget.is_primary.is_(True),  # type: ignore[union-attr,attr-defined]
                    PublishTarget.is_active.is_(True),  # type: ignore[union-attr,attr-defined]
                )
            ).first()
        return row.id if row is not None else None

    def _load_skill_body(self, skill_path: str) -> str:
        cached = self._skill_body_cache.get(skill_path)
        if cached is not None:
            return cached
        skill_md = self._skills_dir / skill_path / "SKILL.md"
        if not skill_md.is_file():
            self._skill_body_cache[skill_path] = ""
            return ""
        body = skill_md.read_text(encoding="utf-8")
        self._skill_body_cache[skill_path] = body
        return body


def _current_step_index(steps: list[Any]) -> int | None:
    for row in sorted(steps, key=lambda item: item.step_index):
        if row.status in (
            ProcedureRunStepStatus.RUNNING,
            ProcedureRunStepStatus.PENDING,
            ProcedureRunStepStatus.FAILED,
        ):
            return row.step_index
    return None


def _is_target_publish_step(step: Any) -> bool:
    """Return true only for the final target-specific publish step.

    Procedure 4 also contains publishing-phase skills such as
    ``schema-emitter`` and ``interlinker``. Those must keep their authored
    skill bodies and grants; only the terminal ``publish`` step is swapped to
    the primary target's concrete publisher.
    """
    return getattr(step, "id", None) == _PUBLISH_STEP_ID and str(step.skill).startswith(
        _PUBLISH_PREFIX
    )


def _all_steps_terminal(steps: list[Any]) -> bool:
    if not steps:
        return False
    terminal = {
        ProcedureRunStepStatus.SUCCESS,
        ProcedureRunStepStatus.FAILED,
        ProcedureRunStepStatus.SKIPPED,
    }
    return all(row.status in terminal for row in steps)


def _all_steps_successful(steps: list[Any]) -> bool:
    if not steps:
        return False
    return all(
        row.status in {ProcedureRunStepStatus.SUCCESS, ProcedureRunStepStatus.SKIPPED}
        for row in steps
    )


def _next_action(run_row: Run, steps: list[Any]) -> str:
    if run_row.status != RunStatus.RUNNING:
        return f"run_{run_row.status.value}"
    if _all_steps_terminal(steps):
        return "complete"
    return "inspect"


def _successful_outputs(steps: list[Any]) -> dict[str, dict[str, Any]]:
    return {
        row.step_id: row.output_json
        for row in steps
        if row.status == ProcedureRunStepStatus.SUCCESS and row.output_json
    }


def _resolve_article_id(args: dict[str, Any], previous_outputs: dict[str, Any]) -> int | None:
    if "article_id" in args:
        try:
            return int(args["article_id"])
        except (TypeError, ValueError):
            return None
    for output in previous_outputs.values():
        if not isinstance(output, dict) or "article_id" not in output:
            continue
        try:
            return int(output["article_id"])
        except (TypeError, ValueError):
            continue
    return None


def _utcnow() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


def _mint_run_token() -> str:
    import secrets

    return secrets.token_urlsafe(32)


def _default_procedures_dir() -> Path:
    pkg = Path(__file__).resolve().parent.parent
    return pkg.parent / "procedures"


def _default_skills_dir(procedures_dir: Path) -> Path:
    return procedures_dir.parent / "skills"


RunnerFactory = Callable[[], "ProcedureRunner"]


__all__ = [
    "ProcedureRunner",
    "RunnerFactory",
]
