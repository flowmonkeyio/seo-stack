"""Streaming tools — progress notifications during long-running calls.

The MCP SDK's progress-token protocol requires the client to opt into
progress streaming via ``params._meta.progressToken``. This test sends
that opt-in and asserts that:

1. The four streaming tools accept progress-token requests without
   crashing.
2. The final response still arrives with the full payload.

Asserting the per-event shape requires a streaming HTTP client; for M3
we lock the wire-shape contract via the request/response pattern and
will round-trip the SSE stream in M9 once the integration-test infra
ships uvicorn-backed clients.
"""

from __future__ import annotations

from typing import Any

from .conftest import MCPClient


def _call_with_progress(mcp: MCPClient, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a tool with an explicit progressToken in ``params._meta``."""
    body = {
        "jsonrpc": "2.0",
        "id": "stream-1",
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments,
            "_meta": {"progressToken": "stream-progress"},
        },
    }
    mcp.initialize()
    r = mcp.test_client.post("/mcp", json=body, headers=mcp._headers())
    return r.json()


def _article_token(mcp: MCPClient, project_id: int) -> str:
    return mcp.call_tool_structured(
        "run.start",
        {
            "project_id": project_id,
            "kind": "procedure",
            "procedure_slug": "01-research/content-brief",
            "skill_name": "01-research/content-brief",
        },
    )["data"]["run_token"]


def test_topic_bulk_create_streaming_accepts_progress_token(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """topic.bulkCreate with N>50 + progressToken returns all rows."""
    pid = seeded_project["data"]["id"]
    items = [{"title": f"T-{i}"} for i in range(75)]
    res = _call_with_progress(mcp_client, "topic.bulkCreate", {"project_id": pid, "items": items})
    assert "result" in res
    payload = res["result"]["structuredContent"]
    assert len(payload["data"]) == 75


def test_gsc_bulk_ingest_accepts_progress_token(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """gsc.bulkIngest with N>1000 streams progress every 1000."""
    pid = seeded_project["data"]["id"]
    rows = [
        {
            "captured_at": "2026-05-01T00:00:00",
            "dimensions_hash": f"h-{i}",
            "impressions": 1,
        }
        for i in range(1500)
    ]
    res = _call_with_progress(mcp_client, "gsc.bulkIngest", {"project_id": pid, "rows": rows})
    assert "result" in res
    payload = res["result"]["structuredContent"]
    # All 1500 inserted.
    assert payload["data"] == 1500


def test_interlink_suggest_accepts_progress_token(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """interlink.suggest with N>10 emits progress."""
    pid = seeded_project["data"]["id"]
    token = _article_token(mcp_client, pid)
    a = mcp_client.call_tool_structured(
        "article.create", {"project_id": pid, "title": "A", "slug": "a", "run_token": token}
    )["data"]["id"]
    b = mcp_client.call_tool_structured(
        "article.create", {"project_id": pid, "title": "B", "slug": "b", "run_token": token}
    )["data"]["id"]
    suggestions = [
        {"from_article_id": a, "to_article_id": b, "anchor_text": f"x-{i}", "position": i}
        for i in range(25)
    ]
    res = _call_with_progress(
        mcp_client,
        "interlink.suggest",
        {"project_id": pid, "suggestions": suggestions},
    )
    assert "result" in res
    payload = res["result"]["structuredContent"]
    assert len(payload["data"]) == 25
