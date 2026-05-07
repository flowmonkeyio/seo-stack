"""``procedure.*`` returns -32601 (M7 procedure-runner deferral); status works today."""

from __future__ import annotations

from .conftest import MCPClient


def test_procedure_run_for_any_slug_returns_deferral(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """procedure.run with any slug returns -32601 + milestone='M7'."""
    err = mcp_client.call_tool_error(
        "procedure.run",
        {
            "slug": "topic-to-published",
            "project_id": seeded_project["data"]["id"],
        },
    )
    assert err["code"] == -32601
    assert err["data"]["milestone"] == "M7"


def test_procedure_list_returns_empty(mcp_client: MCPClient) -> None:
    """procedure.list returns ``[]`` (registry empty at M3)."""
    payload = mcp_client.call_tool_structured("procedure.list", {})
    assert payload == {"items": []}


def test_procedure_status_works_for_existing_run(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """procedure.status works today — reads RunRepository.get + step rows."""
    env = mcp_client.call_tool_structured(
        "run.start",
        {
            "project_id": seeded_project["data"]["id"],
            "kind": "procedure",
            "procedure_slug": "test",
        },
    )
    rid = env["data"]["run_id"]
    status = mcp_client.call_tool_structured("procedure.status", {"run_id": rid})
    assert status["run"]["id"] == rid
    # ProcedureStatusOutput has ``steps: list[...]``, serialised as a JSON
    # array (not the dispatcher's ``{"items": [...]}`` wrapper which is
    # used only for top-level list returns).
    assert status["steps"] == []


def test_procedure_resume_returns_deferral(mcp_client: MCPClient, seeded_project: dict) -> None:
    """procedure.resume returns -32601 + milestone='M7'."""
    err = mcp_client.call_tool_error("procedure.resume", {"run_id": 1})
    assert err["code"] == -32601
    assert err["data"]["milestone"] == "M7"


def test_procedure_fork_returns_deferral(mcp_client: MCPClient, seeded_project: dict) -> None:
    """procedure.fork returns -32601 + milestone='M7'."""
    err = mcp_client.call_tool_error("procedure.fork", {"run_id": 1, "from_step": "editor"})
    assert err["code"] == -32601
    assert err["data"]["milestone"] == "M7"
