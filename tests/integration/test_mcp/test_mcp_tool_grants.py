"""Tool-grant matrix enforcement per audit B-10."""

from __future__ import annotations

from .conftest import MCPClient


def _start_run_for_skill(mcp: MCPClient, project_id: int, skill_name: str) -> str:
    """Helper: start a run with the named skill and return its run_token."""
    env = mcp.call_tool_structured(
        "run.start",
        {
            "project_id": project_id,
            "kind": "procedure",
            "procedure_slug": skill_name,
            "skill_name": skill_name,
        },
    )
    return env["data"]["run_token"]


def test_skill_with_grant_can_call_allowed_tool(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """The ``_test_editor`` skill can call article.get."""
    pid = seeded_project["data"]["id"]
    token = _start_run_for_skill(mcp_client, pid, "_test_editor")
    art = mcp_client.call_tool_structured(
        "article.create",
        {"project_id": pid, "title": "T", "slug": "t"},
    )
    aid = art["data"]["id"]
    # Now call article.get with the test_editor token — allowed.
    got = mcp_client.call_tool_structured("article.get", {"article_id": aid, "run_token": token})
    assert got["id"] == aid


def test_skill_without_grant_returns_forbidden(mcp_client: MCPClient, seeded_project: dict) -> None:
    """The ``_test_editor`` skill cannot call article.markPublished → -32007."""
    pid = seeded_project["data"]["id"]
    token = _start_run_for_skill(mcp_client, pid, "_test_editor")
    err = mcp_client.call_tool_error(
        "article.markPublished",
        {
            "article_id": 1,
            "expected_etag": "x",
            "run_id": 1,
            "run_token": token,
        },
    )
    assert err["code"] == -32007
    assert err["message"] == "ToolNotGrantedError"
    assert err["data"]["tool"] == "article.markPublished"
    assert err["data"]["skill"] == "_test_editor"
    assert isinstance(err["data"]["allowed"], list)


def test_unknown_skill_with_provisioned_token_is_forbidden(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """A known token whose skill name is not in the matrix → forbidden.

    ``resolve_run_token`` reads the run row's ``metadata_json.skill_name``;
    skills not present in ``SKILL_TOOL_GRANTS`` get an empty grant set,
    so any tool call from such a token raises ToolNotGrantedError.
    The escape hatch is ``__system__`` (no token) or ``__test__``
    (unmatched bytes), both of which the test harness uses.
    """
    pid = seeded_project["data"]["id"]
    token = _start_run_for_skill(mcp_client, pid, "unknown-skill")
    err = mcp_client.call_tool_error(
        "article.create",
        {"project_id": pid, "title": "T", "slug": "t-unknown", "run_token": token},
    )
    assert err["code"] == -32007


def test_unmatched_token_falls_to_test_grant(mcp_client: MCPClient, seeded_project: dict) -> None:
    """A run_token that doesn't match any row → __test__ (full grant)."""
    pid = seeded_project["data"]["id"]
    art = mcp_client.call_tool_structured(
        "article.create",
        {
            "project_id": pid,
            "title": "T",
            "slug": "t-test-bypass",
            "run_token": "totally-bogus-token-not-in-runs",
        },
    )
    assert art["data"]["slug"] == "t-test-bypass"


def test_no_run_token_is_system_grant(mcp_client: MCPClient, seeded_project: dict) -> None:
    """No run_token → ``__system__`` skill (full grant)."""
    pid = seeded_project["data"]["id"]
    art = mcp_client.call_tool_structured(
        "article.create",
        {"project_id": pid, "title": "T2", "slug": "t-sys"},
    )
    assert art["data"]["slug"] == "t-sys"
