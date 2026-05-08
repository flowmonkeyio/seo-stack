"""``run.resume`` / ``run.fork`` route through the procedure runner (M8)."""

from __future__ import annotations

from .conftest import MCPClient


def test_run_resume_live_with_unknown_run_id(mcp_client: MCPClient, seeded_project: dict) -> None:
    """``run.resume`` on a missing run id surfaces -32004, not the M8 deferral."""
    err = mcp_client.call_tool_error("run.resume", {"run_id": 999999})
    assert err["code"] == -32004  # NotFoundError
    # No M8 deferral marker.
    assert "milestone" not in err.get("data", {})


def test_run_fork_live_with_unknown_run_id(mcp_client: MCPClient, seeded_project: dict) -> None:
    """``run.fork`` on a missing run id surfaces -32004, not the M8 deferral."""
    err = mcp_client.call_tool_error("run.fork", {"run_id": 999999, "from_step": "editor"})
    assert err["code"] == -32004
    assert "milestone" not in err.get("data", {})


def test_run_fork_with_unknown_step_id_404s(mcp_client: MCPClient, seeded_project: dict) -> None:
    """``run.fork(from_step='ghost')`` on a real run returns NotFound for the step."""
    env = mcp_client.call_tool_structured(
        "procedure.run",
        {
            "slug": "04-topic-to-published",
            "project_id": seeded_project["data"]["id"],
            "args": {"topic_id": 1},
        },
    )
    rid = env["data"]["run_id"]
    err = mcp_client.call_tool_error("run.fork", {"run_id": rid, "from_step": "ghost-step-name"})
    assert err["code"] == -32004
    assert "ghost-step-name" in err["data"]["detail"]
