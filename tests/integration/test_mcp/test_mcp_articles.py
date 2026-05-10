"""Procedure-4 happy path through MCP — full pipeline article → published.

article.create → setBrief → setOutline → setDraft (x3 append) → markDrafted
→ setEdited → markEeatPassed → markPublished
"""

from __future__ import annotations

from .conftest import MCPClient


def _start_skill(mcp: MCPClient, project_id: int, skill_name: str) -> tuple[str, int]:
    env = mcp.call_tool_structured(
        "run.start",
        {
            "project_id": project_id,
            "kind": "procedure",
            "procedure_slug": skill_name,
            "skill_name": skill_name,
        },
    )
    return env["data"]["run_token"], env["data"]["run_id"]


def _create_article(mcp: MCPClient, project_id: int, title: str = "T", slug: str = "t") -> dict:
    """Helper: spin up an article + return its data dict."""
    token, _ = _start_skill(mcp, project_id, "01-research/content-brief")
    env = mcp.call_tool_structured(
        "article.create",
        {"project_id": project_id, "title": title, "slug": slug, "run_token": token},
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
    brief_token, _ = _start_skill(mcp_client, pid, "01-research/content-brief")
    outline_token, _ = _start_skill(mcp_client, pid, "02-content/outline")
    draft_token, _ = _start_skill(mcp_client, pid, "02-content/draft-conclusion")
    editor_token, _ = _start_skill(mcp_client, pid, "02-content/editor")
    eeat_token, eeat_run_id = _start_skill(mcp_client, pid, "02-content/eeat-gate")
    publish_token, publish_run_id = _start_skill(
        mcp_client, pid, "04-publishing/nuxt-content-publish"
    )

    art = mcp_client.call_tool_structured(
        "article.create",
        {"project_id": pid, "title": "Workhorse", "slug": "workhorse", "run_token": brief_token},
    )["data"]
    aid = art["id"]
    etag = art["step_etag"]

    # setBrief → outlined.
    env = mcp_client.call_tool_structured(
        "article.setBrief",
        {
            "article_id": aid,
            "brief_json": {"thesis": "x"},
            "expected_etag": etag,
            "run_token": brief_token,
        },
    )
    assert env["data"]["status"] == "outlined"
    etag = env["data"]["step_etag"]

    # setOutline (no transition).
    env = mcp_client.call_tool_structured(
        "article.setOutline",
        {
            "article_id": aid,
            "outline_md": "## H2\n",
            "expected_etag": etag,
            "run_token": outline_token,
        },
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
                "run_token": draft_token,
            },
        )
        etag = env["data"]["step_etag"]

    # markDrafted → drafted.
    env = mcp_client.call_tool_structured(
        "article.markDrafted",
        {"article_id": aid, "expected_etag": etag, "run_token": draft_token},
    )
    assert env["data"]["status"] == "drafted"
    etag = env["data"]["step_etag"]

    # setEdited → edited.
    env = mcp_client.call_tool_structured(
        "article.setEdited",
        {
            "article_id": aid,
            "edited_md": "edited body",
            "expected_etag": etag,
            "run_token": editor_token,
        },
    )
    assert env["data"]["status"] == "edited"
    etag = env["data"]["step_etag"]

    # markEeatPassed → eeat_passed.
    env = mcp_client.call_tool_structured(
        "article.markEeatPassed",
        {
            "article_id": aid,
            "expected_etag": etag,
            "run_id": eeat_run_id,
            "eeat_criteria_version": 1,
            "run_token": eeat_token,
        },
    )
    assert env["data"]["status"] == "eeat_passed"
    etag = env["data"]["step_etag"]

    # markPublished → published.
    env = mcp_client.call_tool_structured(
        "article.markPublished",
        {
            "article_id": aid,
            "expected_etag": etag,
            "run_id": publish_run_id,
            "run_token": publish_token,
        },
    )
    assert env["data"]["status"] == "published"


def test_article_etag_mismatch_returns_conflict(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """Calling setBrief with a stale etag → -32008."""
    pid = seeded_project["data"]["id"]
    token, _ = _start_skill(mcp_client, pid, "01-research/content-brief")
    art = mcp_client.call_tool_structured(
        "article.create",
        {"project_id": pid, "title": "T", "slug": "t-etag", "run_token": token},
    )["data"]
    err = mcp_client.call_tool_error(
        "article.setBrief",
        {
            "article_id": art["id"],
            "brief_json": {},
            "expected_etag": "wrong-etag",
            "run_token": token,
        },
    )
    assert err["code"] == -32008
    assert err["message"] == "ConflictError"


def test_article_set_brief_wrong_state_returns_conflict(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """Calling setBrief on an article past briefing → -32008."""
    pid = seeded_project["data"]["id"]
    token, _ = _start_skill(mcp_client, pid, "01-research/content-brief")
    art = mcp_client.call_tool_structured(
        "article.create",
        {"project_id": pid, "title": "T", "slug": "t-state", "run_token": token},
    )["data"]
    aid = art["id"]
    # First brief succeeds.
    env = mcp_client.call_tool_structured(
        "article.setBrief",
        {
            "article_id": aid,
            "brief_json": {"x": 1},
            "expected_etag": art["step_etag"],
            "run_token": token,
        },
    )
    new_etag = env["data"]["step_etag"]
    # Second brief from outlined state → ConflictError.
    err = mcp_client.call_tool_error(
        "article.setBrief",
        {
            "article_id": aid,
            "brief_json": {"x": 2},
            "expected_etag": new_etag,
            "run_token": token,
        },
    )
    assert err["code"] == -32008
