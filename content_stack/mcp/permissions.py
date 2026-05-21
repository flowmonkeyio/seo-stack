"""Per-skill MCP tool-grant matrix per audit B-10 / PLAN.md L692-L718.

The matrix is the load-bearing seam for the security model: every MCP
tool call resolves to a skill name (via the ``run_token`` ↔
``runs.client_session_id`` lookup), then this module checks the tool
against the skill's allow-list.

The matrix keeps two different agent pathways explicit:

- ``__system__`` — the agent-owned setup and product-operation grant used
  before a run token exists. The browser UI is read-only, so these calls
  must remain available to the operator agent through MCP.
- ``__test__`` — a reserved full-grant sentinel for tests that bind it
  explicitly. Unmatched tokens never resolve to it.
- ``_test_*`` skills (e.g. ``_test_keyword_discovery``,
  ``_test_editor``) — narrow grants used by the verification tests in
  ``tests/integration/test_mcp/test_mcp_tool_grants.py``.

Real skill grants stay narrower and continue to own vendor calls,
high-cost research, and procedure-scoped work.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from content_stack.db.models import Run, RunPlan, RunPlanStatus, RunPlanStep, RunPlanStepStatus
from content_stack.mcp.errors import ToolNotGrantedError
from content_stack.workflows.run_plan_grants import (
    RUN_PLAN_GRANTABLE_TOOL_NAMES,
    RunPlanMcpToolGrant,
    parse_run_plan_mcp_tool_grants,
)

# ---------------------------------------------------------------------------
# Sentinel skill names.
# ---------------------------------------------------------------------------


SYSTEM_SKILL = "__system__"
TEST_SKILL = "__test__"
INVALID_SKILL = "__invalid__"
RUN_PLAN_CONTROLLER_SKILL = "stackos/run-plan-controller"

_DEFAULT_CONTEXT_SOURCES: tuple[str, ...] = ("runs", "learnings", "experiments", "decisions")
_SAFE_CONTEXT_FIELDS: dict[str, frozenset[str]] = {
    "runs": frozenset({"kind", "status", "procedure_slug", "last_step", "metadata_json"}),
    "events": frozenset({"event_type", "title", "summary", "tags", "metadata_json"}),
    "index": frozenset(
        {"source_type", "source_id", "title", "summary", "domain", "status", "tags"}
    ),
    "snapshots": frozenset({"name", "query_json", "selected_sources_json", "summary_json"}),
    "learnings": frozenset({"statement", "domain", "confidence", "status", "review_state", "tags"}),
    "experiments": frozenset(
        {"name", "domain", "hypothesis", "status", "metric_targets_json", "variants"}
    ),
    "decisions": frozenset({"title", "decision", "rationale", "status", "tags"}),
    "metrics": frozenset({"metric_key", "metric_value", "dimensions_json", "captured_at"}),
}


# ---------------------------------------------------------------------------
# Tool-grant matrix.
# ---------------------------------------------------------------------------


# Test skills used by ``tests/integration/test_mcp/test_mcp_tool_grants.py``.
# Each entry mimics the shape M7 will produce when real SKILL.md files
# land — narrow allow-lists per skill role. Naming convention: ``_test_``
# prefix so production skill names cannot accidentally collide.
_SYSTEM_TOOLS: frozenset[str] = frozenset(
    {
        # Bootstrapping and operator-owned actions. The browser UI is an
        # observer; product-state operations that are not vendor research calls
        # must be available to the agent through the MCP toolbox before a
        # procedure run exists. Costly/vendor calls remain per-skill grants.
        "action.describe",
        "action.validate",
        "article.bulkCreate",
        "article.create",
        "article.createVersion",
        "article.get",
        "article.list",
        "article.listDueForRefresh",
        "article.listPublishes",
        "article.listVersions",
        "article.markAbortedPublish",
        "article.markDrafted",
        "article.markEeatPassed",
        "article.markPublished",
        "article.markRefreshDue",
        "article.refreshDue",
        "article.setBrief",
        "article.setDraft",
        "article.setEdited",
        "article.setOutline",
        "artifact.get",
        "artifact.query",
        "auth.status",
        "auth.test",
        "asset.create",
        "asset.list",
        "asset.remove",
        "asset.update",
        "author.create",
        "author.delete",
        "author.get",
        "author.list",
        "author.update",
        "budget.list",
        "budget.queryProject",
        "budget.set",
        "budget.update",
        "cluster.create",
        "cluster.get",
        "cluster.list",
        "compliance.add",
        "compliance.list",
        "compliance.remove",
        "compliance.update",
        "context.query",
        "context.timeline",
        "cost.queryAll",
        "cost.queryProject",
        "catalog.describe",
        "catalog.list",
        "capability.describe",
        "capability.list",
        "drift.diff",
        "drift.get",
        "drift.list",
        "drift.snapshot",
        "eeat.bulkRecord",
        "eeat.bulkSet",
        "eeat.getReport",
        "eeat.list",
        "eeat.listEvaluations",
        "eeat.record",
        "eeat.score",
        "eeat.toggle",
        "decision.query",
        "experiment.query",
        "gsc.bulkIngest",
        "gsc.listDaily",
        "gsc.queryArticle",
        "gsc.queryProject",
        "gsc.rollup",
        "gscOauth.get",
        "integration.list",
        "integration.test",
        "integration.testGsc",
        "interlink.apply",
        "interlink.bulkApply",
        "interlink.dismiss",
        "interlink.list",
        "interlink.repair",
        "interlink.suggest",
        "learning.query",
        "meta.enums",
        "plugin.list",
        "project.create",
        "project.activate",
        "project.delete",
        "project.get",
        "project.getActive",
        "project.list",
        "project.setActive",
        "project.update",
        "publish.preview",
        "publish.recordExternal",
        "publish.recordPublish",
        "publish.setCanonical",
        "procedure.claimStep",
        "procedure.currentStep",
        "procedure.executeProgrammaticStep",
        "procedure.fork",
        "procedure.list",
        "procedure.recordStep",
        "procedure.resume",
        "procedure.run",
        "procedure.status",
        "redirect.create",
        "redirect.list",
        "redirect.lookup",
        "run.abort",
        "run.children",
        "run.cost",
        "run.finish",
        "run.fork",
        "run.get",
        "run.heartbeat",
        "run.insertStep",
        "run.list",
        "run.listStepCalls",
        "run.listSteps",
        "run.recordStepCall",
        "run.resume",
        "run.start",
        "runPlan.create",
        "runPlan.get",
        "runPlan.list",
        "runPlan.start",
        "runPlan.validate",
        "provider.describe",
        "provider.list",
        "resource.get",
        "resource.query",
        "schedule.list",
        "schedule.remove",
        "schedule.set",
        "schedule.toggle",
        "schema.get",
        "schema.list",
        "schema.set",
        "schema.validate",
        "sitemap.fetch",
        "source.add",
        "source.list",
        "source.update",
        "target.add",
        "target.list",
        "target.remove",
        "target.setPrimary",
        "target.update",
        "topic.approve",
        "topic.assignCluster",
        "topic.bulkCreate",
        "topic.bulkUpdateStatus",
        "topic.create",
        "topic.get",
        "topic.list",
        "topic.reject",
        "voice.get",
        "voice.listVariants",
        "voice.set",
        "voice.setActive",
        "workflowTemplate.describe",
        "workflowTemplate.list",
        "workflowTemplate.validate",
        "workspace.connect",
        "workspace.listBindings",
        "workspace.resolve",
        "workspace.startSession",
        "workspace.updateProfile",
    }
)

_TEST_KEYWORD_DISCOVERY: frozenset[str] = frozenset(
    {
        "topic.create",
        "topic.bulkCreate",
        "topic.list",
        "cluster.create",
        "cluster.list",
        "meta.enums",
    }
)

_TEST_EDITOR: frozenset[str] = frozenset(
    {
        "article.get",
        "voice.get",
        "article.setEdited",
        "compliance.list",
        "meta.enums",
    }
)

_TEST_EEAT_GATE: frozenset[str] = frozenset(
    {
        "article.get",
        "eeat.list",
        "eeat.score",
        "eeat.getReport",
        "compliance.list",
        "article.markEeatPassed",
        "meta.enums",
    }
)

_TEST_PUBLISHER: frozenset[str] = frozenset(
    {
        "article.get",
        "schema.get",
        "target.list",
        "publish.preview",
        "article.markPublished",
        "meta.enums",
    }
)


# ---------------------------------------------------------------------------
# M6.A real skill grants.
# ---------------------------------------------------------------------------
#
# Per PLAN.md L692-L718 the tool-grant matrix is the load-bearing seam
# for the security model — every skill declares the smallest set of MCP
# tools it needs, and ``check_grant`` rejects anything else. Grants for
# the five M6.A research-phase skills are below; the corresponding
# ``allowed_tools`` lists in each ``SKILL.md`` frontmatter must mirror
# this set verbatim (a startup smoke check enforces the parity).
#
# The shared ``_run_lifecycle`` set carries the four read-write tools
# every skill needs to participate in the runs audit trail; we factor
# it out so a future skill author doesn't accidentally drop one.


_RUN_LIFECYCLE: frozenset[str] = frozenset(
    {
        "run.start",
        "run.heartbeat",
        "run.finish",
        "run.recordStepCall",
        "procedure.currentStep",
        "procedure.recordStep",
    }
)


_SKILL_KEYWORD_DISCOVERY: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "cluster.list",
    "topic.bulkCreate",
    "topic.list",
    "integration.test",
    "integration.testGsc",
    "cost.queryProject",
    "dataforseo.serp",
    "dataforseo.keywordVolume",
    "dataforseo.keywordsForSite",
    "dataforseo.domainIntersection",
    "dataforseo.paa",
    "reddit.searchSubreddit",
    "reddit.topQuestions",
    "googlePaa.extract",
}


_SKILL_SERP_ANALYZER: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "article.get",
    "source.add",
    "source.list",
    "integration.test",
    "dataforseo.serp",
    "firecrawl.scrape",
    "jina.read",
}


_SKILL_TOPICAL_CLUSTER: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "cluster.create",
    "cluster.list",
    "cluster.get",
    "topic.list",
    "topic.assignCluster",
    "topic.bulkUpdateStatus",
}


_SKILL_CONTENT_BRIEF: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "cluster.get",
    "voice.get",
    "compliance.list",
    "eeat.list",
    "article.get",
    "article.create",
    "article.setBrief",
    "source.add",
    "source.list",
    "integration.test",
    "dataforseo.serp",
    "dataforseo.keywordVolume",
    "firecrawl.scrape",
    "jina.read",
}


_SKILL_COMPETITOR_SITEMAP: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "cluster.list",
    "cluster.create",
    "topic.bulkCreate",
    "topic.list",
    "integration.test",
    "sitemap.fetch",
    "ahrefs.keywordsForSite",
}


# ---------------------------------------------------------------------------
# M6.B real skill grants (content-production phase).
# ---------------------------------------------------------------------------
#
# Per PLAN.md L848-L854 the seven content-production skills (#6-#12) build
# the article from outline through humanizer pass. Each declares the
# narrowest set of tools it touches; the EEAT gate carries the unique
# eeat.bulkRecord + eeat.score + article.markEeatPassed grant so no other
# skill can mark a verdict.


_SKILL_OUTLINE: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "voice.get",
    "eeat.list",
    "article.get",
    "article.setOutline",
    "source.list",
}


_SKILL_DRAFT_INTRO: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "voice.get",
    "compliance.list",
    "eeat.list",
    "article.get",
    "article.setDraft",
    "source.list",
    "source.update",
}


_SKILL_DRAFT_BODY: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "voice.get",
    "compliance.list",
    "eeat.list",
    "article.get",
    "article.setDraft",
    "source.list",
    "source.update",
}


_SKILL_DRAFT_CONCLUSION: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "voice.get",
    "compliance.list",
    "eeat.list",
    "article.get",
    "article.setDraft",
    "article.markDrafted",
    "source.list",
    "source.update",
}


_SKILL_EDITOR: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "voice.get",
    "compliance.list",
    "eeat.list",
    "article.get",
    "article.setEdited",
    "source.list",
}


_SKILL_EEAT_GATE: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "voice.get",
    "eeat.list",
    "eeat.score",
    "eeat.bulkRecord",
    "article.get",
    "article.markEeatPassed",
    "article.markAbortedPublish",
    "compliance.list",
}


_SKILL_HUMANIZER: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "voice.get",
    "article.get",
    "article.setEdited",
}


# ---------------------------------------------------------------------------
# M6.C real skill grants (assets + publishing phase).
# ---------------------------------------------------------------------------
#
# The assets-and-publishing skills turn the EEAT-passed article into
# published artifacts. The image generator is the only skill that calls
# into the OpenAI Images integration (the wrapper handles cost recording
# and generated-asset persistence; the skill consults cost.queryProject
# pre-emptively). Procedure 4 authors agent-publish as the default
# targetless handoff and only swaps to a concrete target publisher when the
# primary target kind is wired.


_SKILL_IMAGE_GENERATOR: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "voice.get",
    "compliance.list",
    "article.get",
    "asset.create",
    "asset.list",
    "asset.update",
    "cost.queryProject",
    "integration.test",
    "openaiImages.generate",
}


_SKILL_ALT_TEXT_AUDITOR: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "article.get",
    "asset.list",
    "asset.update",
}


_SKILL_INTERLINKER: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "cluster.list",
    "topic.list",
    "article.list",
    "article.get",
    "interlink.suggest",
    "interlink.list",
    "interlink.repair",
}


_SKILL_SCHEMA_EMITTER: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "voice.get",
    "article.get",
    "asset.list",
    "author.get",
    "schema.set",
    "schema.get",
    "schema.list",
    "schema.validate",
}


_SKILL_AGENT_PUBLISH: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "article.get",
    "asset.list",
    "source.list",
    "schema.get",
    "schema.list",
    "publish.recordExternal",
}


# Publish skills share the same state-write grant set: they consume the
# same artefacts (article + assets + sources + schema_emits), call the
# target-backed publish writes, and may call article.markPublished. The
# runner maps only concrete target kinds with production-grade tool support.
# Deferred specs such as WordPress/Ghost must add real hidden media/post
# toolkit operations before the runner maps targets to them.
_SKILL_PUBLISH_BASE: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "voice.get",
    "compliance.list",
    "article.get",
    "article.markPublished",
    "asset.list",
    "source.list",
    "schema.get",
    "target.list",
    "publish.preview",
    "publish.recordPublish",
    "publish.setCanonical",
    "integration.test",
}


_SKILL_NUXT_CONTENT_PUBLISH: frozenset[str] = _SKILL_PUBLISH_BASE
_SKILL_WORDPRESS_PUBLISH: frozenset[str] = _SKILL_PUBLISH_BASE
_SKILL_GHOST_PUBLISH: frozenset[str] = _SKILL_PUBLISH_BASE


# ---------------------------------------------------------------------------
# M6.D real skill grants (ongoing-operations phase).
# ---------------------------------------------------------------------------
#
# Per PLAN.md L862-L866 the five ongoing-operations skills (#20-#24) carry
# the project from "first published" into the steady-state pipeline:
# weekly GSC opportunity finding, weekly drift / crawl-error watch,
# weekly-or-on-demand refresh detection, and the per-article content
# refresh that re-runs the production chain. The opportunity-finder, the
# drift-watch, and the crawl-error-watch are the GSC trio (procedure 6's
# weekly-gsc-review pipeline); refresh-detector is procedure 7's seed,
# and content-refresher composes the editor + humanizer + interlinker +
# schema-emitter + publish skills around an `article.createVersion`
# transaction.
#
# Skill #24 (content-refresher) inherits the publish-base grant set
# because it must drive the full re-publish chain. The drift-watch grant
# carries the four `drift.*` tools even though `drift.diff` is a
# MilestoneDeferralError until the comparison engine lands — the skill
# prose handles the deferral by falling through to capture-only mode and
# emitting a warning to the operator.


_SKILL_GSC_OPPORTUNITY_FINDER: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "cluster.list",
    "topic.list",
    "topic.bulkCreate",
    "article.list",
    "gsc.queryProject",
    "gsc.queryArticle",
    "integration.test",
    "integration.testGsc",
}


_SKILL_DRIFT_WATCH: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "article.list",
    "article.get",
    "drift.snapshot",
    "drift.list",
    "drift.get",
    "drift.diff",
    "integration.test",
    "firecrawl.scrape",
    "gsc.pagespeed",
}


_SKILL_CRAWL_ERROR_WATCH: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "article.list",
    "topic.list",
    "topic.bulkCreate",
    "gsc.inspectUrl",
    "integration.test",
    "integration.testGsc",
}


_SKILL_REFRESH_DETECTOR: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "article.list",
    "article.markRefreshDue",
    "gsc.queryArticle",
    "drift.list",
    "drift.get",
}


# Content-refresher composes the publish chain; it inherits the publish
# base set (article.markPublished + publish.recordPublish + the schema /
# target / asset reads) plus the version-management writes (createVersion
# / listVersions), the voice / compliance / EEAT reads the editor and
# the humanizer pull, and `interlink.repair` for stale-link cleanup on
# the refreshed body. The grant intentionally does NOT include
# `interlink.suggest` (the suggester runs as a separate dispatch when the
# refresh body needs new links) or `schema.validate` (the schema-emitter
# the refresher dispatches owns validation; the refresher only reads /
# rewrites schema_emits via schema.set when chaining the emitter).
_SKILL_CONTENT_REFRESHER: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "voice.get",
    "compliance.list",
    "eeat.list",
    "article.get",
    "article.list",
    "article.createVersion",
    "article.listVersions",
    "interlink.repair",
    "schema.list",
    "schema.set",
    "target.list",
    "publish.preview",
    "publish.recordPublish",
    "redirect.create",
}


# Procedure slugs are the grant bound to a run token between claimed
# skill steps. They can inspect/claim the next step and execute
# deterministic ``_programmatic/*`` helpers, but prose/content writes
# still require the concrete skill grant bound by ``procedure.claimStep``.
_PROCEDURE_CONTROL: frozenset[str] = frozenset(
    {
        "procedure.currentStep",
        "procedure.claimStep",
        "procedure.executeProgrammaticStep",
        "procedure.status",
        "run.get",
        "run.heartbeat",
        "run.listSteps",
    }
)


_RUN_PLAN_CONTROL: frozenset[str] = frozenset(
    {
        "run.get",
        "run.heartbeat",
        "runPlan.claimStep",
        "runPlan.get",
        "runPlan.list",
        "runPlan.recordStep",
    }
)
_RUN_PLAN_DYNAMIC_TOOLS: frozenset[str] = frozenset(RUN_PLAN_GRANTABLE_TOOL_NAMES)
_RUN_PLAN_CONTROLLER_TOOLS: frozenset[str] = _RUN_PLAN_CONTROL | _RUN_PLAN_DYNAMIC_TOOLS


_PROGRAMMATIC_CONTROL: frozenset[str] = frozenset(
    {
        "procedure.currentStep",
        "procedure.executeProgrammaticStep",
        "procedure.status",
        "run.get",
        "run.heartbeat",
        "run.listSteps",
    }
)


# The matrix proper. ``__system__`` is broad enough for agent-owned
# product-state operation, but it is still explicit and excludes vendor
# research tools that must remain bound to concrete skills.
SKILL_TOOL_GRANTS: dict[str, frozenset[str]] = {
    SYSTEM_SKILL: _SYSTEM_TOOLS,
    TEST_SKILL: frozenset(),  # full grant; sentinel-checked in check_grant
    "_test_keyword_discovery": _TEST_KEYWORD_DISCOVERY,
    "_test_editor": _TEST_EDITOR,
    "_test_eeat_gate": _TEST_EEAT_GATE,
    "_test_publisher": _TEST_PUBLISHER,
    RUN_PLAN_CONTROLLER_SKILL: _RUN_PLAN_CONTROLLER_TOOLS,
    # Agent-led procedure controllers (bound between claimed skill steps).
    "01-bootstrap-project": _PROCEDURE_CONTROL,
    "02-one-site-shortcut": _PROCEDURE_CONTROL,
    "03-keyword-to-topic-queue": _PROCEDURE_CONTROL,
    "04-topic-to-published": _PROCEDURE_CONTROL,
    "05-bulk-content-launch": _PROCEDURE_CONTROL,
    "06-weekly-gsc-review": _PROCEDURE_CONTROL,
    "07-monthly-humanize-pass": _PROCEDURE_CONTROL,
    "08-add-new-site": _PROCEDURE_CONTROL,
    # Deterministic programmatic helpers. The current agent explicitly
    # invokes these through ``procedure.executeProgrammaticStep``; no
    # hidden writer or vendor session is spawned.
    "_programmatic/bootstrap-verify": _PROGRAMMATIC_CONTROL,
    "_programmatic/bulk-cost-estimator": _PROGRAMMATIC_CONTROL,
    "_programmatic/bulk-final-summary": _PROGRAMMATIC_CONTROL,
    "_programmatic/compliance-seed": _PROGRAMMATIC_CONTROL,
    "_programmatic/eeat-seed-verify": _PROGRAMMATIC_CONTROL,
    "_programmatic/gsc-pull": _PROGRAMMATIC_CONTROL,
    "_programmatic/integration-creds-prompt": _PROGRAMMATIC_CONTROL,
    "_programmatic/project-create": _PROGRAMMATIC_CONTROL,
    "_programmatic/publish-target-prompt": _PROGRAMMATIC_CONTROL,
    "_programmatic/run-child-procedure": _PROGRAMMATIC_CONTROL,
    "_programmatic/select-refresh-candidates": _PROGRAMMATIC_CONTROL,
    "_programmatic/spawn-procedure-4-batch": _PROGRAMMATIC_CONTROL,
    "_programmatic/topic-approval-pause": _PROGRAMMATIC_CONTROL,
    "_programmatic/voice-profile-prompt": _PROGRAMMATIC_CONTROL,
    "_programmatic/wait-for-children": _PROGRAMMATIC_CONTROL,
    "_programmatic/weekly-summary": _PROGRAMMATIC_CONTROL,
    # M6.A skills (research phase).
    "01-research/keyword-discovery": _SKILL_KEYWORD_DISCOVERY,
    "01-research/serp-analyzer": _SKILL_SERP_ANALYZER,
    "01-research/topical-cluster": _SKILL_TOPICAL_CLUSTER,
    "01-research/content-brief": _SKILL_CONTENT_BRIEF,
    "01-research/competitor-sitemap-shortcut": _SKILL_COMPETITOR_SITEMAP,
    # M6.B skills (content-production phase).
    "02-content/outline": _SKILL_OUTLINE,
    "02-content/draft-intro": _SKILL_DRAFT_INTRO,
    "02-content/draft-body": _SKILL_DRAFT_BODY,
    "02-content/draft-conclusion": _SKILL_DRAFT_CONCLUSION,
    "02-content/editor": _SKILL_EDITOR,
    "02-content/eeat-gate": _SKILL_EEAT_GATE,
    "02-content/humanizer": _SKILL_HUMANIZER,
    # M6.C skills (assets + publishing phase).
    "03-assets/image-generator": _SKILL_IMAGE_GENERATOR,
    "03-assets/alt-text-auditor": _SKILL_ALT_TEXT_AUDITOR,
    "04-publishing/interlinker": _SKILL_INTERLINKER,
    "04-publishing/schema-emitter": _SKILL_SCHEMA_EMITTER,
    "04-publishing/agent-publish": _SKILL_AGENT_PUBLISH,
    "04-publishing/nuxt-content-publish": _SKILL_NUXT_CONTENT_PUBLISH,
    "04-publishing/wordpress-publish": _SKILL_WORDPRESS_PUBLISH,
    "04-publishing/ghost-publish": _SKILL_GHOST_PUBLISH,
    # M6.D skills (ongoing-operations phase).
    "05-ongoing/gsc-opportunity-finder": _SKILL_GSC_OPPORTUNITY_FINDER,
    "05-ongoing/drift-watch": _SKILL_DRIFT_WATCH,
    "05-ongoing/crawl-error-watch": _SKILL_CRAWL_ERROR_WATCH,
    "05-ongoing/refresh-detector": _SKILL_REFRESH_DETECTOR,
    "05-ongoing/content-refresher": _SKILL_CONTENT_REFRESHER,
}


# ---------------------------------------------------------------------------
# Public helpers.
# ---------------------------------------------------------------------------


def is_full_grant(skill_name: str) -> bool:
    """Return ``True`` iff ``skill_name`` carries an unrestricted grant.

    Only the explicit test sentinel bypasses the whitelist. System MCP
    calls use their explicit product-operation grant in ``SKILL_TOOL_GRANTS``.
    """
    return skill_name == TEST_SKILL


def resolve_run_token(
    token: str | None,
    session: Session,
) -> tuple[Run | None, str]:
    """Resolve a request's ``run_token`` to its calling skill.

    Lookup contract:

    - ``token=None`` → ``(None, "__system__")``. Direct MCP calls without
      a run token use the explicit agent setup/product-operation allow-list.
    - ``token`` matches a row's ``runs.client_session_id`` →
      ``(run, skill_name)`` where ``skill_name`` comes from
      ``runs.metadata_json.skill_name`` if set, else falls back to the
      run's ``procedure_slug``.
    - Token does not match any row → ``(None, "__invalid__")``.
    """
    if token is None or token == "":
        return None, SYSTEM_SKILL
    row = session.exec(select(Run).where(Run.client_session_id == token)).first()
    if row is None:
        return None, INVALID_SKILL
    metadata = row.metadata_json or {}
    skill_name = metadata.get("skill_name") or row.procedure_slug or INVALID_SKILL
    return row, skill_name


def check_grant(tool_name: str, skill_name: str) -> None:
    """Raise ``ToolNotGrantedError`` if the skill cannot call the tool.

    The ``__test__`` sentinel remains a full-grant fixture escape hatch,
    but normal system/bootstrap calls use an explicit allow-list.
    """
    if is_full_grant(skill_name):
        return
    allowed = SKILL_TOOL_GRANTS.get(skill_name, frozenset())
    if tool_name in allowed:
        return
    raise ToolNotGrantedError(
        f"skill {skill_name!r} is not granted tool {tool_name!r}",
        data={
            "tool": tool_name,
            "skill": skill_name,
            "allowed": sorted(allowed),
        },
    )


def _model_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    if isinstance(value, dict):
        return dict(value)
    return {}


def _arg_string_set(arguments: dict[str, Any], key: str) -> set[str] | None:
    raw = arguments.get(key)
    if raw is None:
        return None
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return set(raw)
    return None


def _requested_strings(arguments: dict[str, Any], key: str) -> list[str] | None:
    raw = arguments.get(key)
    if raw is None:
        return None
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return list(raw)
    return None


def _deny_context_fields(
    tool_name: str,
    *,
    source: str,
    denied_fields: set[str],
    allowed_fields: set[str],
) -> None:
    raise ToolNotGrantedError(
        "context fields beyond the direct safe set require a run-plan grant",
        data={
            "tool": tool_name,
            "skill": SYSTEM_SKILL,
            "source": source,
            "denied_fields": sorted(denied_fields),
            "allowed_fields": sorted(allowed_fields),
        },
    )


def _check_direct_context_fields(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    source: str | None = None,
) -> None:
    if source is not None:
        sources = [source]
    else:
        sources = _requested_strings(arguments, "sources") or list(_DEFAULT_CONTEXT_SOURCES)
    requested_fields = _requested_strings(arguments, "fields")
    for item in sources:
        allowed = _SAFE_CONTEXT_FIELDS.get(item)
        if allowed is None:
            continue
        fields = set(requested_fields or allowed)
        denied = fields - allowed
        if denied:
            _deny_context_fields(
                tool_name,
                source=item,
                denied_fields=denied,
                allowed_fields=set(allowed),
            )


def _grant_matches_arguments(
    grant: RunPlanMcpToolGrant,
    arguments: dict[str, Any],
) -> bool:
    if grant.action_refs:
        requested_action_ref = arguments.get("action_ref")
        if not isinstance(requested_action_ref, str):
            plugin_slug = arguments.get("plugin_slug")
            action_key = arguments.get("action_key")
            if isinstance(plugin_slug, str) and isinstance(action_key, str):
                requested_action_ref = f"{plugin_slug}.{action_key}"
        if requested_action_ref not in set(grant.action_refs):
            return False
    if grant.plugin_slug is not None and arguments.get("plugin_slug") != grant.plugin_slug:
        return False
    if grant.resource_key is not None and arguments.get("resource_key") != grant.resource_key:
        return False
    if grant.sources:
        requested_sources = _arg_string_set(arguments, "sources")
        if requested_sources is None or not requested_sources <= set(grant.sources):
            return False
    if grant.fields:
        requested_fields = _arg_string_set(arguments, "fields")
        if requested_fields is None or not requested_fields <= set(grant.fields):
            return False
    return True


def _deny_run_plan_tool(
    tool_name: str,
    *,
    reason: str,
    run_id: int | None = None,
    run_plan_id: int | None = None,
    step_id: str | None = None,
    allowed: set[str] | None = None,
) -> None:
    raise ToolNotGrantedError(
        reason,
        data={
            "tool": tool_name,
            "skill": RUN_PLAN_CONTROLLER_SKILL,
            "run_id": run_id,
            "run_plan_id": run_plan_id,
            "step_id": step_id,
            "allowed": sorted(allowed or set()),
        },
    )


def _running_run_plan_step(ctx: Any, tool_name: str) -> tuple[RunPlan, RunPlanStep]:
    run = getattr(ctx, "run", None)
    run_id = getattr(ctx, "run_id", None)
    session = getattr(ctx, "session", None)
    if run is None or session is None:
        _deny_run_plan_tool(
            tool_name,
            reason="run-plan scoped tools require a valid run token",
            run_id=run_id,
        )
    metadata = run.metadata_json or {}
    run_plan_id = metadata.get("run_plan_id")
    if metadata.get("stackos_type") != "run-plan" or not isinstance(run_plan_id, int):
        _deny_run_plan_tool(
            tool_name,
            reason="run token is not bound to a StackOS run plan",
            run_id=run_id,
        )
    plan = session.get(RunPlan, run_plan_id)
    if plan is None or plan.run_id != run_id:
        _deny_run_plan_tool(
            tool_name,
            reason="run token is not scoped to this run plan",
            run_id=run_id,
            run_plan_id=run_plan_id,
        )
    if plan.status != RunPlanStatus.STARTED:
        _deny_run_plan_tool(
            tool_name,
            reason="run plan must be started with a running step for this tool",
            run_id=run_id,
            run_plan_id=plan.id,
        )
    steps = list(
        session.exec(
            select(RunPlanStep)
            .where(
                RunPlanStep.run_plan_id == plan.id,
                RunPlanStep.status == RunPlanStepStatus.RUNNING,
            )
            .order_by(RunPlanStep.position.asc())  # type: ignore[union-attr]
        ).all()
    )
    if len(steps) != 1:
        _deny_run_plan_tool(
            tool_name,
            reason="run-plan scoped tools require exactly one running step",
            run_id=run_id,
            run_plan_id=plan.id,
        )
    return plan, steps[0]


def active_run_plan_step(ctx: Any, tool_name: str) -> tuple[RunPlan, RunPlanStep]:
    """Return the single running step for a valid run-plan controller token."""
    return _running_run_plan_step(ctx, tool_name)


def _check_run_plan_dynamic_grant(tool_name: str, ctx: Any, parsed_arguments: Any) -> None:
    arguments = _model_to_dict(parsed_arguments)
    plan, step = _running_run_plan_step(ctx, tool_name)
    requested_project_id = arguments.get("project_id")
    if requested_project_id != plan.project_id:
        _deny_run_plan_tool(
            tool_name,
            reason="run-plan scoped mutations must target the plan project",
            run_id=getattr(ctx, "run_id", None),
            run_plan_id=plan.id,
            step_id=step.step_id,
        )
    requested_run_id = arguments.get("run_id")
    if requested_run_id is not None and requested_run_id != getattr(ctx, "run_id", None):
        _deny_run_plan_tool(
            tool_name,
            reason="run-plan scoped mutations cannot spoof another run id",
            run_id=getattr(ctx, "run_id", None),
            run_plan_id=plan.id,
            step_id=step.step_id,
        )
    try:
        grants = [
            grant
            for grant in parse_run_plan_mcp_tool_grants(plan.grant_snapshot_json)
            if grant.step_id == step.step_id and grant.tool_name == tool_name
        ]
    except ValueError as exc:
        _deny_run_plan_tool(
            tool_name,
            reason=f"invalid run-plan grant snapshot: {exc}",
            run_id=getattr(ctx, "run_id", None),
            run_plan_id=plan.id,
            step_id=step.step_id,
        )
    allowed = {
        grant.tool_name
        for grant in parse_run_plan_mcp_tool_grants(plan.grant_snapshot_json)
        if grant.step_id == step.step_id
    }
    if not grants:
        _deny_run_plan_tool(
            tool_name,
            reason="tool is not granted to the active run-plan step",
            run_id=getattr(ctx, "run_id", None),
            run_plan_id=plan.id,
            step_id=step.step_id,
            allowed=allowed,
        )
    if tool_name == "action.execute":
        requested_action_ref = arguments.get("action_ref")
        if not isinstance(requested_action_ref, str):
            plugin_slug = arguments.get("plugin_slug")
            action_key = arguments.get("action_key")
            if isinstance(plugin_slug, str) and isinstance(action_key, str):
                requested_action_ref = f"{plugin_slug}.{action_key}"
        if not isinstance(requested_action_ref, str) or requested_action_ref not in set(
            step.action_refs_json or []
        ):
            _deny_run_plan_tool(
                tool_name,
                reason="action.execute must target an action_ref declared on the active step",
                run_id=getattr(ctx, "run_id", None),
                run_plan_id=plan.id,
                step_id=step.step_id,
                allowed=allowed,
            )
    if not any(_grant_matches_arguments(grant, arguments) for grant in grants):
        _deny_run_plan_tool(
            tool_name,
            reason="tool arguments do not match the active run-plan step grant",
            run_id=getattr(ctx, "run_id", None),
            run_plan_id=plan.id,
            step_id=step.step_id,
            allowed=allowed,
        )


def check_call_grant(tool_name: str, ctx: Any, parsed_arguments: Any | None = None) -> None:
    """Context-aware grant check used by the MCP dispatcher.

    Static grants keep procedure compatibility intact. Run-plan controller
    tokens also pass through a dynamic step check for generic mutation tools so
    a stored run plan, not agent discretion, defines what can be called.
    """
    skill_name = getattr(ctx, "skill_name", INVALID_SKILL)
    check_grant(tool_name, skill_name)
    if skill_name == SYSTEM_SKILL:
        arguments = _model_to_dict(parsed_arguments)
        if tool_name == "context.query":
            _check_direct_context_fields(tool_name, arguments)
        elif tool_name == "context.timeline":
            _check_direct_context_fields(tool_name, arguments, source="events")
        elif tool_name == "learning.query":
            _check_direct_context_fields(tool_name, arguments, source="learnings")
        elif tool_name == "experiment.query":
            _check_direct_context_fields(tool_name, arguments, source="experiments")
        elif tool_name == "decision.query":
            _check_direct_context_fields(tool_name, arguments, source="decisions")
        return
    if skill_name != RUN_PLAN_CONTROLLER_SKILL:
        return
    if tool_name not in _RUN_PLAN_DYNAMIC_TOOLS:
        return
    _check_run_plan_dynamic_grant(tool_name, ctx, parsed_arguments)


__all__ = [
    "INVALID_SKILL",
    "RUN_PLAN_CONTROLLER_SKILL",
    "SKILL_TOOL_GRANTS",
    "SYSTEM_SKILL",
    "TEST_SKILL",
    "active_run_plan_step",
    "check_call_grant",
    "check_grant",
    "is_full_grant",
    "resolve_run_token",
]
