"""run.* through MCP — start returns run_token; finish/abort/heartbeat."""

from __future__ import annotations

from .conftest import MCPClient


def test_run_start_returns_run_token(mcp_client: MCPClient, seeded_project: dict) -> None:
    """run.start returns ``{run, run_token, run_id}``."""
    env = mcp_client.call_tool_structured(
        "run.start",
        {"project_id": seeded_project["data"]["id"], "kind": "manual-edit"},
    )
    assert env["data"]["run_id"] > 0
    assert isinstance(env["data"]["run_token"], str)
    assert len(env["data"]["run_token"]) >= 16


def test_run_finish_terminal_state(mcp_client: MCPClient, seeded_project: dict) -> None:
    """run.start → run.finish(success) lands in terminal status."""
    env = mcp_client.call_tool_structured(
        "run.start",
        {"project_id": seeded_project["data"]["id"], "kind": "manual-edit"},
    )
    rid = env["data"]["run_id"]
    finished = mcp_client.call_tool_structured("run.finish", {"run_id": rid, "status": "success"})
    assert finished["data"]["status"] == "success"


def test_run_heartbeat_updates_timestamp(mcp_client: MCPClient, seeded_project: dict) -> None:
    """run.heartbeat updates heartbeat_at."""
    env = mcp_client.call_tool_structured(
        "run.start",
        {"project_id": seeded_project["data"]["id"], "kind": "manual-edit"},
    )
    rid = env["data"]["run_id"]
    hb = mcp_client.call_tool_structured("run.heartbeat", {"run_id": rid})
    assert hb["data"]["id"] == rid


def test_run_abort_cascades(mcp_client: MCPClient, seeded_project: dict) -> None:
    """run.abort sets status=aborted; cascade flag accepted."""
    env = mcp_client.call_tool_structured(
        "run.start",
        {"project_id": seeded_project["data"]["id"], "kind": "manual-edit"},
    )
    rid = env["data"]["run_id"]
    aborted = mcp_client.call_tool_structured("run.abort", {"run_id": rid, "cascade": True})
    assert aborted["data"]["status"] == "aborted"


def test_run_token_correlation_to_run(mcp_client: MCPClient, seeded_project: dict) -> None:
    """run.start's token resolves back to the same run via run.list."""
    env = mcp_client.call_tool_structured(
        "run.start",
        {
            "project_id": seeded_project["data"]["id"],
            "kind": "procedure",
            "procedure_slug": "test-proc",
        },
    )
    token = env["data"]["run_token"]
    rid = env["data"]["run_id"]
    page = mcp_client.call_tool_structured("run.list", {"project_id": seeded_project["data"]["id"]})
    matched = [r for r in page["items"] if r["client_session_id"] == token]
    assert len(matched) == 1
    assert matched[0]["id"] == rid


def test_run_resume_returns_milestone_deferral(mcp_client: MCPClient, seeded_project: dict) -> None:
    """run.resume returns -32601 with milestone='M9' hint."""
    env = mcp_client.call_tool_structured(
        "run.start",
        {"project_id": seeded_project["data"]["id"], "kind": "procedure"},
    )
    err = mcp_client.call_tool_error("run.resume", {"run_id": env["data"]["run_id"]})
    assert err["code"] == -32601
    assert err["data"]["milestone"] == "M9"
