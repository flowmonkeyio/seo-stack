"""RepositoryError → JSON-RPC error code mapping."""

from __future__ import annotations

from .conftest import MCPClient


def test_not_found_maps_to_minus_32004(mcp_client: MCPClient) -> None:
    """project.get on a missing slug returns -32004."""
    err = mcp_client.call_tool_error("project.get", {"id_or_slug": "ghost"})
    assert err["code"] == -32004
    assert err["message"] == "NotFoundError"


def test_validation_error_maps_to_minus_32602(mcp_client: MCPClient) -> None:
    """project.create with empty slug → -32602."""
    err = mcp_client.call_tool_error(
        "project.create",
        {"slug": "", "name": "X", "domain": "x", "locale": "en-US"},
    )
    assert err["code"] == -32602
    # Either ValidationError or pydantic input validation; both -32602.


def test_drift_diff_returns_milestone_deferral(mcp_client: MCPClient, seeded_project: dict) -> None:
    """drift.diff returns -32601 with milestone='M6' hint (drift-watch skill)."""
    err = mcp_client.call_tool_error("drift.diff", {"baseline_id": 1, "current_md": "x"})
    assert err["code"] == -32601
    assert err["message"] == "MilestoneDeferralError"
    assert err["data"]["milestone"] == "M6"


def test_procedure_run_returns_m7_deferral(mcp_client: MCPClient, seeded_project: dict) -> None:
    """procedure.run returns -32601 with milestone='M7' hint (procedure runner)."""
    err = mcp_client.call_tool_error(
        "procedure.run",
        {"slug": "any-procedure", "project_id": seeded_project["data"]["id"]},
    )
    assert err["code"] == -32601
    assert err["data"]["milestone"] == "M7"


def test_procedure_list_returns_empty_list(mcp_client: MCPClient) -> None:
    """procedure.list returns ``[]`` (registry empty at M3)."""
    payload = mcp_client.call_tool_structured("procedure.list", {})
    # Wrapped under 'items' by the dispatcher's list serializer.
    assert payload == {"items": []}
