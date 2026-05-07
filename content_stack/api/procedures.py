"""Procedures router — list, run (501), poll.

PLAN.md L611-L617:

- ``GET /procedures`` — list discovered procedure files. M2 scans
  ``procedures/`` (which is empty until M8); we return a real list-of-dicts
  shape so the UI doesn't have to special-case "not yet implemented".
- ``POST /procedures/{slug}/run`` — 501 with M8 hint per the deliverable
  brief; the runner is daemon-orchestrated and lands in M8.
- ``GET /procedures/runs/{run_id}`` — poll a procedure run by id;
  works today via ``RunRepository`` + ``ProcedureRunStepRepository``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from content_stack.api.deps import get_session
from content_stack.config import Settings, get_settings
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


@router.post("/{slug}/run")
async def run_procedure(slug: str) -> Any:
    """Procedure runner — pending M7.

    PLAN.md L611-L617 + audit B-21 + D4: the runner is daemon-orchestrated
    and lands in M7 with the procedure-runner subsystem. M2 surfaces a
    501 so callers know the route exists but is not yet implemented.
    """
    raise HTTPException(
        status_code=501,
        detail={
            "detail": "Not yet implemented (M7)",
            "code": -32601,
            "data": {"slug": slug},
            "hint": (
                "Procedure runner is daemon-orchestrated; lands in M7. "
                "Until then, drive procedures manually via the article + run REST endpoints."
            ),
        },
    )


@router.get("/runs/{run_id}", response_model=ProcedureRunResponse)
async def get_procedure_run(
    run_id: int,
    session: Session = Depends(get_session),
) -> ProcedureRunResponse:
    """Poll a procedure run + its declared steps by run id."""
    run = RunRepository(session).get(run_id)
    steps = ProcedureRunStepRepository(session).list_steps(run_id)
    return ProcedureRunResponse(run=run, steps=steps)


__all__ = ["ProcedureRunResponse", "ProcedureSummary", "router"]
