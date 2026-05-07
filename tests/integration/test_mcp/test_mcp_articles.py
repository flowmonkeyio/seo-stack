"""Procedure-4 happy path through MCP — full pipeline article → published.

article.create → setBrief → setOutline → setDraft (x3 append) → markDrafted
→ setEdited → markEeatPassed → markPublished
"""

from __future__ import annotations

from .conftest import MCPClient


def _create_article(mcp: MCPClient, project_id: int, title: str = "T", slug: str = "t") -> dict:
    """Helper: spin up an article + return its data dict."""
    env = mcp.call_tool_structured(
        "article.create",
        {"project_id": project_id, "title": title, "slug": slug},
    )
    return env["data"]


def test_article_create_returns_envelope_with_etag(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """article.create populates step_etag; status='briefing'."""
    art = _create_article(mcp_client, seeded_project["data"]["id"])
    assert art["status"] == "briefing"
    assert art["step_etag"], "expected fresh step_etag"


def test_full_procedure_4_walk_via_mcp(mcp_client: MCPClient, seeded_project: dict) -> None:
    """Walk the article through every state transition via MCP tools."""
    pid = seeded_project["data"]["id"]
    # Open a run so subsequent state transitions have a valid owner_run_id.
    run_env = mcp_client.call_tool_structured(
        "run.start",
        {"project_id": pid, "kind": "procedure", "procedure_slug": "topic-to-published"},
    )
    run_id = run_env["data"]["run_id"]

    art = _create_article(mcp_client, pid, title="Workhorse", slug="workhorse")
    aid = art["id"]
    etag = art["step_etag"]

    # setBrief → outlined.
    env = mcp_client.call_tool_structured(
        "article.setBrief",
        {
            "article_id": aid,
            "brief_json": {"thesis": "x"},
            "expected_etag": etag,
        },
    )
    assert env["data"]["status"] == "outlined"
    etag = env["data"]["step_etag"]

    # setOutline (no transition).
    env = mcp_client.call_tool_structured(
        "article.setOutline",
        {"article_id": aid, "outline_md": "## H2\n", "expected_etag": etag},
    )
    assert env["data"]["status"] == "outlined"
    etag = env["data"]["step_etag"]

    # setDraft x3 (append=True after first).
    for i, append in enumerate([False, True, True]):
        env = mcp_client.call_tool_structured(
            "article.setDraft",
            {
                "article_id": aid,
                "draft_md": f"# Section {i}\n",
                "expected_etag": etag,
                "append": append,
            },
        )
        etag = env["data"]["step_etag"]

    # markDrafted → drafted.
    env = mcp_client.call_tool_structured(
        "article.markDrafted", {"article_id": aid, "expected_etag": etag}
    )
    assert env["data"]["status"] == "drafted"
    etag = env["data"]["step_etag"]

    # setEdited → edited.
    env = mcp_client.call_tool_structured(
        "article.setEdited",
        {"article_id": aid, "edited_md": "edited body", "expected_etag": etag},
    )
    assert env["data"]["status"] == "edited"
    etag = env["data"]["step_etag"]

    # markEeatPassed → eeat_passed.
    env = mcp_client.call_tool_structured(
        "article.markEeatPassed",
        {
            "article_id": aid,
            "expected_etag": etag,
            "run_id": run_id,
            "eeat_criteria_version": 1,
        },
    )
    assert env["data"]["status"] == "eeat_passed"
    etag = env["data"]["step_etag"]

    # markPublished → published.
    env = mcp_client.call_tool_structured(
        "article.markPublished",
        {"article_id": aid, "expected_etag": etag, "run_id": run_id},
    )
    assert env["data"]["status"] == "published"


def test_article_etag_mismatch_returns_conflict(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """Calling setBrief with a stale etag → -32008."""
    art = _create_article(mcp_client, seeded_project["data"]["id"])
    err = mcp_client.call_tool_error(
        "article.setBrief",
        {
            "article_id": art["id"],
            "brief_json": {},
            "expected_etag": "wrong-etag",
        },
    )
    assert err["code"] == -32008
    assert err["message"] == "ConflictError"


def test_article_set_brief_wrong_state_returns_conflict(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """Calling setBrief on an article past briefing → -32008."""
    art = _create_article(mcp_client, seeded_project["data"]["id"])
    aid = art["id"]
    # First brief succeeds.
    env = mcp_client.call_tool_structured(
        "article.setBrief",
        {"article_id": aid, "brief_json": {"x": 1}, "expected_etag": art["step_etag"]},
    )
    new_etag = env["data"]["step_etag"]
    # Second brief from outlined state → ConflictError.
    err = mcp_client.call_tool_error(
        "article.setBrief",
        {"article_id": aid, "brief_json": {"x": 2}, "expected_etag": new_etag},
    )
    assert err["code"] == -32008
