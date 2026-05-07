"""Procedures router — list, run, resume, fork, poll.

PLAN.md L611-L617:

- ``GET /procedures`` — list discovered procedure files (frontmatter
  metadata).
- ``POST /procedures/{slug}/run`` — enqueue a procedure run via the
  daemon-orchestrated runner (M7+, decision D4); 202 with envelope.
- ``POST /procedures/runs/{run_id}/resume`` — resume from the next
  pending step.
- ``POST /procedures/runs/{run_id}/fork`` — clone a run from a step
  index.
- ``GET /procedures/runs/{run_id}`` — poll a procedure run by id;
  works today via ``RunRepository`` + ``ProcedureRunStepRepository``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from content_stack.api.deps import get_session
from content_stack.config import Settings, get_settings
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

router = APIRouter(prefix="/api/v1/procedures", tags=["procedures"])


class ProcedureSummary(BaseModel):
    """Wire shape for one entry in ``GET /procedures``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "slug": "bootstrap",
                "name": "Bootstrap a new project",
                "version": "1.0.0",
                "description": "First-run setup of a project's voice / compliance / EEAT.",
            }
        }
    )

    slug: str
    name: str
    version: str | None = None
    description: str | None = None


class ProcedureRunResponse(BaseModel):
    """Wire shape for ``GET /procedures/runs/{run_id}``."""

    run: RunOut
    steps: list[ProcedureRunStepOut] = Field(default_factory=list)


class ProcedureRunRequest(BaseModel):
    """Wire shape for ``POST /procedures/{slug}/run``."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"project_id": 1, "args": {"topic_id": 1}}},
    )

    project_id: int
    args: dict[str, Any] = Field(default_factory=dict)
    parent_run_id: int | None = None
    variant: str | None = None


class ProcedureRunEnqueued(BaseModel):
    """Wire shape returned by the runner after ``start`` / ``resume`` / ``fork``."""

    run_id: int
    run_token: str
    status_url: str
    slug: str
    project_id: int
    started: bool
    parent_run_id: int | None = None


class ProcedureForkRequest(BaseModel):
    """Wire shape for ``POST /procedures/runs/{run_id}/fork``."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": {"from_step_index": 5}})

    from_step_index: int


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse a tiny YAML-ish frontmatter block.

    Tight subset: ``key: value`` per line. Full YAML lands in M8 with
    the runner; M2 just needs ``slug``, ``name``, ``version``, ``description``
    so the UI can list procedures in a sidebar.
    """
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return {}
    out: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _scan_procedures(root: Path) -> list[ProcedureSummary]:
    """Discover ``procedures/<slug>/PROCEDURE.md`` files under ``root``.

    M2 returns ``[]`` because ``procedures/`` is empty; the function is
    written generically so M8 can drop in PROCEDURE.md files and this
    endpoint surfaces them automatically.
    """
    if not root.is_dir():
        return []
    out: list[ProcedureSummary] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        manifest = entry / "PROCEDURE.md"
        if not manifest.is_file():
            continue
        try:
            text = manifest.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = _parse_frontmatter(text)
        out.append(
            ProcedureSummary(
                slug=meta.get("slug", entry.name),
                name=meta.get("name", entry.name),
                version=meta.get("version") or None,
                description=meta.get("description") or None,
            )
        )
    return out


def _procedures_root(settings: Settings) -> Path:
    """Resolve the procedures dir.

    First-class location is ``<repo>/procedures/`` which we discover by
    walking up from ``content_stack/`` (the package). Tests can override
    by symlinking; M8 will likely move discovery to a configured XDG
    path. We fall back to ``data_dir/procedures`` when running outside
    the repo (``make install`` pre-M10).
    """
    pkg = Path(__file__).resolve().parent.parent  # content_stack/
    repo_procedures = pkg.parent / "procedures"
    if repo_procedures.is_dir():
        return repo_procedures
    return settings.data_dir / "procedures"


@router.get("", response_model=list[ProcedureSummary])
async def list_procedures(
    settings: Settings = Depends(get_settings),
) -> list[ProcedureSummary]:
    """Discover ``procedures/`` and return any PROCEDURE.md frontmatter."""
    return _scan_procedures(_procedures_root(settings))


def _runner_from(request: Request) -> Any:
    """Resolve ``app.state.procedure_runner`` or 503."""
    runner = getattr(request.app.state, "procedure_runner", None)
    if runner is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="procedure_runner not initialised on app.state",
        )
    return runner


@router.post(
    "/{slug}/run",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ProcedureRunEnqueued,
)
async def run_procedure(
    slug: str,
    payload: ProcedureRunRequest,
    request: Request,
) -> ProcedureRunEnqueued:
    """Enqueue a procedure run via the daemon-orchestrated runner.

    Per locked decision D4 (PLAN.md L884-L900): the runner is daemon-side;
    the client only kicks off + polls. Returns 202 + the envelope so
    UI / MCP clients can navigate to ``status_url`` for live state.
    """
    runner = _runner_from(request)
    try:
        envelope = await runner.start(
            slug=slug,
            args=payload.args,
            project_id=payload.project_id,
            parent_run_id=payload.parent_run_id,
            variant=payload.variant,
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(exc), "data": exc.data},
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": str(exc), "data": exc.data},
        ) from exc
    return ProcedureRunEnqueued(**envelope)


@router.post(
    "/runs/{run_id}/resume",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ProcedureRunEnqueued,
)
async def resume_procedure_run(run_id: int, request: Request) -> ProcedureRunEnqueued:
    """Resume an aborted / paused procedure run from the next pending step."""
    runner = _runner_from(request)
    try:
        envelope = await runner.resume(run_id=run_id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(exc), "data": exc.data},
        ) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": str(exc), "data": exc.data},
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": str(exc), "data": exc.data},
        ) from exc
    return ProcedureRunEnqueued(**envelope)


@router.post(
    "/runs/{run_id}/fork",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ProcedureRunEnqueued,
)
async def fork_procedure_run(
    run_id: int,
    payload: ProcedureForkRequest,
    request: Request,
) -> ProcedureRunEnqueued:
    """Fork a procedure run from a step index, copying prior outputs."""
    runner = _runner_from(request)
    try:
        envelope = await runner.fork(run_id=run_id, from_step_index=payload.from_step_index)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(exc), "data": exc.data},
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": str(exc), "data": exc.data},
        ) from exc
    return ProcedureRunEnqueued(**envelope)


@router.get("/runs/{run_id}", response_model=ProcedureRunResponse)
async def get_procedure_run(
    run_id: int,
    session: Session = Depends(get_session),
) -> ProcedureRunResponse:
    """Poll a procedure run + its declared steps by run id."""
    run = RunRepository(session).get(run_id)
    steps = ProcedureRunStepRepository(session).list_steps(run_id)
    return ProcedureRunResponse(run=run, steps=steps)


__all__ = [
    "ProcedureForkRequest",
    "ProcedureRunEnqueued",
    "ProcedureRunRequest",
    "ProcedureRunResponse",
    "ProcedureSummary",
    "router",
]
