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


def test_run_resume_routes_to_runner(mcp_client: MCPClient, seeded_project: dict) -> None:
    """run.resume now routes through the procedure controller."""
    # ``run.resume`` requires a procedure-kind run with a procedure_slug
    # set so the controller can resolve a spec. A bare ``run.start`` without a
    # procedure_slug is rejected at the runner layer with ValidationError
    # (-32602). That's the M8 contract — the deferral is gone.
    env = mcp_client.call_tool_structured(
        "run.start",
        {"project_id": seeded_project["data"]["id"], "kind": "procedure"},
    )
    err = mcp_client.call_tool_error("run.resume", {"run_id": env["data"]["run_id"]})
    # No procedure_slug on the run -> validation error, not milestone deferral.
    assert err["code"] in (-32602, -32603, -32604), err
    # Crucially: the error data does NOT carry a "milestone" key.
    assert err.get("data", {}).get("milestone") != "M8", err
