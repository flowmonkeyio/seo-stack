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


def _create_article_with_skill(mcp: MCPClient, project_id: int, slug: str) -> dict:
    """Create an article through a real granted skill token."""
    token = _start_run_for_skill(mcp, project_id, "01-research/content-brief")
    return mcp.call_tool_structured(
        "article.create",
        {"project_id": project_id, "title": slug, "slug": slug, "run_token": token},
    )


def test_skill_with_grant_can_call_allowed_tool(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """The ``_test_editor`` skill can call article.get."""
    pid = seeded_project["data"]["id"]
    token = _start_run_for_skill(mcp_client, pid, "_test_editor")
    art = _create_article_with_skill(mcp_client, pid, "t")
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


def test_unmatched_token_is_forbidden(mcp_client: MCPClient, seeded_project: dict) -> None:
    """A run_token that doesn't match any row cannot call tools."""
    pid = seeded_project["data"]["id"]
    err = mcp_client.call_tool_error(
        "article.create",
        {
            "project_id": pid,
            "title": "T",
            "slug": "t-test-bypass",
            "run_token": "totally-bogus-token-not-in-runs",
        },
    )
    assert err["code"] == -32007
    assert err["data"]["skill"] == "__invalid__"


def test_no_run_token_is_bootstrap_only(mcp_client: MCPClient, seeded_project: dict) -> None:
    """No run_token can bootstrap runs, but cannot mutate article state."""
    pid = seeded_project["data"]["id"]
    run = mcp_client.call_tool_structured(
        "run.start",
        {"project_id": pid, "kind": "procedure", "skill_name": "_test_editor"},
    )
    assert run["data"]["run_token"]

    err = mcp_client.call_tool_error(
        "article.create",
        {"project_id": pid, "title": "T2", "slug": "t-sys"},
    )
    assert err["code"] == -32007
    assert err["data"]["skill"] == "__system__"


def test_run_token_cannot_read_other_project_object(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """Object-id-only reads are checked against the resolved run's project."""
    pid_1 = seeded_project["data"]["id"]
    project_2 = mcp_client.call_tool_structured(
        "project.create",
        {
            "slug": "second-project",
            "name": "Second Project",
            "domain": "second.example",
            "locale": "en-US",
        },
    )
    pid_2 = project_2["data"]["id"]
    token_1 = _start_run_for_skill(mcp_client, pid_1, "_test_editor")
    art_2 = _create_article_with_skill(mcp_client, pid_2, "other-project-article")

    err = mcp_client.call_tool_error(
        "article.get",
        {"article_id": art_2["data"]["id"], "run_token": token_1},
    )
    assert err["code"] == -32007
    assert err["data"]["run_project_id"] == pid_1
    assert err["data"]["result_project_id"] == pid_2
