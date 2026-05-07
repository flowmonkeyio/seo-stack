"""interlink.* through MCP — suggest, apply, dismiss, repair, bulkApply."""

from __future__ import annotations

from .conftest import MCPClient


def _two_articles(mcp: MCPClient, pid: int) -> tuple[int, int]:
    """Create two articles and return their ids."""
    a = mcp.call_tool_structured("article.create", {"project_id": pid, "title": "A", "slug": "a"})[
        "data"
    ]["id"]
    b = mcp.call_tool_structured("article.create", {"project_id": pid, "title": "B", "slug": "b"})[
        "data"
    ]["id"]
    return a, b


def test_interlink_suggest_apply_dismiss_chain(mcp_client: MCPClient, seeded_project: dict) -> None:
    """Suggest one link, apply it, then ensure dismiss-from-applied works."""
    pid = seeded_project["data"]["id"]
    a, b = _two_articles(mcp_client, pid)
    env = mcp_client.call_tool_structured(
        "interlink.suggest",
        {
            "project_id": pid,
            "suggestions": [{"from_article_id": a, "to_article_id": b, "anchor_text": "see also"}],
        },
    )
    link_id = env["data"][0]["id"]
    applied = mcp_client.call_tool_structured("interlink.apply", {"link_id": link_id})
    assert applied["data"]["status"] == "applied"
    dismissed = mcp_client.call_tool_structured("interlink.dismiss", {"link_id": link_id})
    assert dismissed["data"]["status"] == "dismissed"


def test_interlink_bulk_apply_atomic(mcp_client: MCPClient, seeded_project: dict) -> None:
    """Bulk-apply multiple suggestions in one transaction."""
    pid = seeded_project["data"]["id"]
    a, b = _two_articles(mcp_client, pid)
    suggestions = [
        {"from_article_id": a, "to_article_id": b, "anchor_text": f"x-{i}", "position": i}
        for i in range(3)
    ]
    env = mcp_client.call_tool_structured(
        "interlink.suggest", {"project_id": pid, "suggestions": suggestions}
    )
    ids = [r["id"] for r in env["data"]]
    applied = mcp_client.call_tool_structured("interlink.bulkApply", {"ids": ids})
    assert all(r["status"] == "applied" for r in applied["data"])


def test_interlink_repair_marks_applied_as_broken(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """interlink.repair flips applied → broken when the target is unpublished."""
    pid = seeded_project["data"]["id"]
    a, b = _two_articles(mcp_client, pid)
    sug = mcp_client.call_tool_structured(
        "interlink.suggest",
        {
            "project_id": pid,
            "suggestions": [{"from_article_id": a, "to_article_id": b, "anchor_text": "see also"}],
        },
    )
    link_id = sug["data"][0]["id"]
    mcp_client.call_tool_structured("interlink.apply", {"link_id": link_id})
    repair = mcp_client.call_tool_structured("interlink.repair", {"article_id": b})
    assert repair["data"][0]["status"] == "broken"


def test_interlink_list_pagination(mcp_client: MCPClient, seeded_project: dict) -> None:
    """interlink.list returns a Page envelope."""
    pid = seeded_project["data"]["id"]
    page = mcp_client.call_tool_structured("interlink.list", {"project_id": pid})
    assert "items" in page
    assert "next_cursor" in page
    assert "total_estimate" in page
