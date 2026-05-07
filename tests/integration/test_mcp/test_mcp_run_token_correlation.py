"""Per audit M-29: tool calls under a run_token correlate to that run.

The dispatcher resolves the run_token to a runs.id; subsequent record
calls (run.recordStepCall) reference the same run_id.
"""

from __future__ import annotations

from .conftest import MCPClient


def test_run_step_call_records_under_owning_run(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """recordStepCall + listStepCalls round-trips on the same run_step_id."""
    env = mcp_client.call_tool_structured(
        "run.start",
        {
            "project_id": seeded_project["data"]["id"],
            "kind": "procedure",
            "procedure_slug": "test",
        },
    )
    rid = env["data"]["run_id"]
    step_env = mcp_client.call_tool_structured(
        "run.insertStep",
        {"run_id": rid, "step_index": 0, "skill_name": "outline"},
    )
    step_id = step_env["data"]["id"]
    call_env = mcp_client.call_tool_structured(
        "run.recordStepCall",
        {
            "run_step_id": step_id,
            "mcp_tool": "article.get",
            "request_json": {"article_id": 1},
            "response_json": {"id": 1, "title": "X"},
        },
    )
    assert call_env["data"]["run_step_id"] == step_id
    listing = mcp_client.call_tool_structured("run.listStepCalls", {"run_step_id": step_id})
    assert len(listing["items"]) == 1


def test_run_token_resolves_to_correct_run(mcp_client: MCPClient, seeded_project: dict) -> None:
    """run.start's token correlates back to its run via the dispatcher."""
    env = mcp_client.call_tool_structured(
        "run.start",
        {
            "project_id": seeded_project["data"]["id"],
            "kind": "procedure",
            "procedure_slug": "test",
            "skill_name": "_test_keyword_discovery",
        },
    )
    token = env["data"]["run_token"]
    rid = env["data"]["run_id"]
    # Make a call carrying the token; the dispatcher resolves it and
    # logs the run_id (visible via run.get).
    mcp_client.call_tool_structured(
        "topic.create",
        {
            "project_id": seeded_project["data"]["id"],
            "title": "Token-bound topic",
            "run_token": token,
        },
    )
    run_row = mcp_client.call_tool_structured("run.get", {"run_id": rid})
    assert run_row["client_session_id"] == token
