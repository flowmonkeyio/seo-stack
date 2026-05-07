"""REST adapter for the codex-plugin-cc adversarial-review helper (M4).

Exposes ``POST /api/v1/adversarial-review`` so the UI / external skills
can request an independent EEAT review of generated article content.
The skill #11 wiring (``eeat-gate``) lives in M6; M4 lands the helper
+ the route.

Concurrency: a per-project ``asyncio.Semaphore(1)`` ensures only one
review runs per project at a time (the underlying subprocess is
expensive — 90s budget — and we don't want a runaway skill kicking off
a swarm of subprocesses against the same project's run-step audit
trail).
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from content_stack.integrations.codex_plugin_cc import adversarial_review

router = APIRouter(
    prefix="/api/v1/adversarial-review",
    tags=["adversarial-review"],
)


class AdversarialReviewRequest(BaseModel):
    """Body for ``POST /adversarial-review``."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "article_md": "# Sample article\n\nLorem ipsum.",
                "eeat_criteria": [
                    {"code": "T04", "title": "Author bio present"},
                ],
                "project_id": 1,
            }
        },
    )

    article_md: str = Field(min_length=1, max_length=200_000)
    eeat_criteria: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    project_id: int


# Per-project semaphore registry — ensures at most one adversarial
# review runs per project at a time. The lock guards mutation of the
# dict itself (Python's GIL makes ``dict.setdefault`` atomic for
# CPython but the explicit lock keeps the contract clean).
_project_semaphores: dict[int, asyncio.Semaphore] = {}
_project_semaphore_lock = asyncio.Lock()


async def _semaphore_for(project_id: int) -> asyncio.Semaphore:
    async with _project_semaphore_lock:
        sem = _project_semaphores.get(project_id)
        if sem is None:
            sem = asyncio.Semaphore(1)
            _project_semaphores[project_id] = sem
        return sem


@router.post("")
async def post_adversarial_review(body: AdversarialReviewRequest) -> dict[str, Any]:
    """Run the codex-plugin-cc adversarial review.

    Always returns 200 with a verdict envelope:

    - ``{"verdict": "PASS", "issues": []}`` — review approved.
    - ``{"verdict": "FIX", "issues": [...]}`` / ``{"verdict": "BLOCK",
      "issues": [...]}`` — needs work.
    - ``{"verdict": "SKIPPED", "reason": "plugin-not-installed"|...}``
      — helper short-circuited (plugin missing, timeout, etc.).
    """
    sem = await _semaphore_for(body.project_id)
    async with sem:
        return await adversarial_review(
            article_md=body.article_md,
            eeat_criteria=body.eeat_criteria,
            project_id=body.project_id,
        )


__all__ = ["AdversarialReviewRequest", "router"]
