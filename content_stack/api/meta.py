"""Meta lookup — ``GET /api/v1/meta/enums``.

Per audit M-16 / PLAN.md L618: the UI needs every enum value the daemon
might persist (status pickers, kind dropdowns, allowed transitions for
state-machine UIs). Sourcing this off the enum classes + transition maps
in ``content_stack.db.models`` keeps the wire shape and the persisted
shape in lockstep.
"""

from __future__ import annotations

import enum
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from content_stack.db.models import (
    ARTICLE_STATUS_TRANSITIONS,
    INTERNAL_LINK_STATUS_TRANSITIONS,
    RUN_STATUS_TRANSITIONS,
    TOPIC_STATUS_TRANSITIONS,
    ArticleAssetKind,
    ArticlePublishStatus,
    ArticleStatus,
    ClusterType,
    CompliancePosition,
    ComplianceRuleKind,
    EeatCategory,
    EeatTier,
    EeatVerdict,
    InternalLinkStatus,
    ProcedureRunStepStatus,
    PublishTargetKind,
    RedirectKind,
    RunKind,
    RunStatus,
    RunStepStatus,
    TopicIntent,
    TopicSource,
    TopicStatus,
)


def _values(cls: type[enum.Enum]) -> list[str]:
    """Return the persisted value strings for an enum class."""
    return [m.value for m in cls]


def _transitions(
    transitions: dict[Any, frozenset[Any]],
) -> dict[str, list[str]]:
    """Map an Enum→Enum transition table to a JSON-friendly dict."""
    return {k.value: sorted(v.value for v in vs) for k, vs in transitions.items()}


class EnumLookupResponse(BaseModel):
    """Wire shape for ``GET /meta/enums`` per audit M-16."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topics_status": ["queued", "approved", "drafting", "published", "rejected"],
                "articles_status": [
                    "briefing",
                    "outlined",
                    "drafted",
                    "edited",
                    "eeat_passed",
                    "published",
                    "refresh_due",
                    "aborted-publish",
                ],
                "allowed_transitions": {
                    "topics": {"queued": ["approved", "rejected"]},
                    "articles": {"briefing": ["aborted-publish", "outlined"]},
                },
            }
        }
    )

    # One enum-class per field, value lists in declaration order.
    topics_status: list[str]
    topics_intent: list[str]
    topics_source: list[str]
    articles_status: list[str]
    article_assets_kind: list[str]
    article_publishes_status: list[str]
    runs_status: list[str]
    runs_kind: list[str]
    run_steps_status: list[str]
    procedure_run_steps_status: list[str]
    clusters_type: list[str]
    compliance_rules_kind: list[str]
    compliance_rules_position: list[str]
    eeat_criteria_tier: list[str]
    eeat_criteria_category: list[str]
    eeat_evaluations_verdict: list[str]
    internal_links_status: list[str]
    publish_targets_kind: list[str]
    redirects_kind: list[str]
    allowed_transitions: dict[str, dict[str, list[str]]]


router = APIRouter(prefix="/api/v1", tags=["meta"])


@router.get("/meta/enums", response_model=EnumLookupResponse)
async def get_meta_enums() -> EnumLookupResponse:
    """Return every enum value + the legal state-machine transitions.

    Single source of truth: the enum classes and transition maps in
    ``content_stack.db.models``. UI / MCP consumers should call this on
    boot and cache.
    """
    return EnumLookupResponse(
        topics_status=_values(TopicStatus),
        topics_intent=_values(TopicIntent),
        topics_source=_values(TopicSource),
        articles_status=_values(ArticleStatus),
        article_assets_kind=_values(ArticleAssetKind),
        article_publishes_status=_values(ArticlePublishStatus),
        runs_status=_values(RunStatus),
        runs_kind=_values(RunKind),
        run_steps_status=_values(RunStepStatus),
        procedure_run_steps_status=_values(ProcedureRunStepStatus),
        clusters_type=_values(ClusterType),
        compliance_rules_kind=_values(ComplianceRuleKind),
        compliance_rules_position=_values(CompliancePosition),
        eeat_criteria_tier=_values(EeatTier),
        eeat_criteria_category=_values(EeatCategory),
        eeat_evaluations_verdict=_values(EeatVerdict),
        internal_links_status=_values(InternalLinkStatus),
        publish_targets_kind=_values(PublishTargetKind),
        redirects_kind=_values(RedirectKind),
        allowed_transitions={
            "topics": _transitions(TOPIC_STATUS_TRANSITIONS),
            "articles": _transitions(ARTICLE_STATUS_TRANSITIONS),
            "runs": _transitions(RUN_STATUS_TRANSITIONS),
            "internal_links": _transitions(INTERNAL_LINK_STATUS_TRANSITIONS),
        },
    )


__all__ = ["EnumLookupResponse", "router"]
