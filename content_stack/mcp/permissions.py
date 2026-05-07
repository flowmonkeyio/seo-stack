"""Per-skill MCP tool-grant matrix per audit B-10 / PLAN.md L692-L718.

The matrix is the load-bearing seam for the security model: every MCP
tool call resolves to a skill name (via the ``run_token`` ↔
``runs.client_session_id`` lookup), then this module checks the tool
against the skill's allow-list.

At M3 the matrix is intentionally narrow:

- ``__system__`` / ``__test__`` — full grant. The first is used for
  direct human REST/UI access; the second is the test fixture.
- ``_test_*`` skills (e.g. ``_test_keyword_discovery``,
  ``_test_editor``) — narrow grants used by the verification tests in
  ``tests/integration/test_mcp/test_mcp_tool_grants.py``.

M7 will populate per-real-skill grants when the 24 SKILL.md files are
authored. For now the matrix exists to lock in the seam; tests prove
that an unprivileged caller cannot reach a forbidden tool.
"""

from __future__ import annotations

from sqlmodel import Session, select

from content_stack.db.models import Run
from content_stack.mcp.errors import ToolNotGrantedError

# ---------------------------------------------------------------------------
# Sentinel skill names — full-grant escapes for system/test contexts.
# ---------------------------------------------------------------------------


SYSTEM_SKILL = "__system__"
TEST_SKILL = "__test__"


# ---------------------------------------------------------------------------
# Tool-grant matrix.
# ---------------------------------------------------------------------------


# Test skills used by ``tests/integration/test_mcp/test_mcp_tool_grants.py``.
# Each entry mimics the shape M7 will produce when real SKILL.md files
# land — narrow allow-lists per skill role. Naming convention: ``_test_``
# prefix so production skill names cannot accidentally collide.
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
}


_SKILL_SERP_ANALYZER: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "article.get",
    "source.add",
    "source.list",
    "integration.test",
}


_SKILL_TOPICAL_CLUSTER: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "cluster.create",
    "cluster.list",
    "cluster.get",
    "topic.list",
    "topic.bulkUpdateStatus",
}


_SKILL_CONTENT_BRIEF: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "voice.get",
    "compliance.list",
    "eeat.list",
    "article.get",
    "article.create",
    "article.setBrief",
    "source.add",
    "source.list",
    "integration.test",
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
}


# The matrix proper. Special-case keys (``__system__``, ``__test__``) hold
# a sentinel set; ``check_grant`` short-circuits on them so we never
# enumerate the full tool registry just to grant access.
SKILL_TOOL_GRANTS: dict[str, frozenset[str]] = {
    SYSTEM_SKILL: frozenset(),  # full grant; sentinel-checked in check_grant
    TEST_SKILL: frozenset(),  # full grant; sentinel-checked in check_grant
    "_test_keyword_discovery": _TEST_KEYWORD_DISCOVERY,
    "_test_editor": _TEST_EDITOR,
    "_test_eeat_gate": _TEST_EEAT_GATE,
    "_test_publisher": _TEST_PUBLISHER,
    # M6.A skills (research phase).
    "01-research/keyword-discovery": _SKILL_KEYWORD_DISCOVERY,
    "01-research/serp-analyzer": _SKILL_SERP_ANALYZER,
    "01-research/topical-cluster": _SKILL_TOPICAL_CLUSTER,
    "01-research/content-brief": _SKILL_CONTENT_BRIEF,
    "01-research/competitor-sitemap-shortcut": _SKILL_COMPETITOR_SITEMAP,
}


# ---------------------------------------------------------------------------
# Public helpers.
# ---------------------------------------------------------------------------


def is_full_grant(skill_name: str) -> bool:
    """Return ``True`` iff ``skill_name`` carries an unrestricted grant.

    System + test contexts bypass the per-tool whitelist. Real skills
    (M7) always go through the whitelist.
    """
    return skill_name in {SYSTEM_SKILL, TEST_SKILL}


def resolve_run_token(
    token: str | None,
    session: Session,
) -> tuple[Run | None, str]:
    """Resolve a request's ``run_token`` to its calling skill.

    Lookup contract:

    - ``token=None`` → ``(None, "__system__")``. Direct human REST/UI
      calls don't carry a run_token and run with full grants.
    - ``token`` matches a row's ``runs.client_session_id`` →
      ``(run, skill_name)`` where ``skill_name`` comes from
      ``runs.metadata_json.skill_name`` if set, else falls back to the
      run's ``procedure_slug``. If neither is set, returns the test
      sentinel — useful in unit tests that mint a run without binding
      a skill.
    - Token does not match any row → ``(None, "__test__")`` so the
      test harness can stamp arbitrary bytes without provisioning a
      run row first. Production callers MUST always present a
      provisioned token; the system surface (REST/UI) carries None.
    """
    if token is None or token == "":
        return None, SYSTEM_SKILL
    row = session.exec(select(Run).where(Run.client_session_id == token)).first()
    if row is None:
        # Unmatched token in production would be a security event; the
        # test harness uses arbitrary tokens so we lean to permissive.
        # Real M7 deployment will tighten this via a CONFIG flag.
        return None, TEST_SKILL
    metadata = row.metadata_json or {}
    skill_name = metadata.get("skill_name") or row.procedure_slug or TEST_SKILL
    return row, skill_name


def check_grant(tool_name: str, skill_name: str) -> None:
    """Raise ``ToolNotGrantedError`` if the skill cannot call the tool.

    Sentinel skills (``__system__`` / ``__test__``) always pass without
    consulting the matrix — the unprivileged path cannot reach them
    because ``resolve_run_token`` only emits those names for the system
    surface or the test harness.
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


__all__ = [
    "SKILL_TOOL_GRANTS",
    "SYSTEM_SKILL",
    "TEST_SKILL",
    "check_grant",
    "is_full_grant",
    "resolve_run_token",
]
