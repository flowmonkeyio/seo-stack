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
    run = mcp_client.call_tool_structured(
        "run.start",
        {
            "project_id": seeded_project["data"]["id"],
            "kind": "procedure",
            "procedure_slug": "05-ongoing/drift-watch",
            "skill_name": "05-ongoing/drift-watch",
        },
    )
    err = mcp_client.call_tool_error(
        "drift.diff",
        {"baseline_id": 1, "current_md": "x", "run_token": run["data"]["run_token"]},
    )
    assert err["code"] == -32601
    assert err["message"] == "MilestoneDeferralError"
    assert err["data"]["milestone"] == "M6"


def test_procedure_run_unknown_slug_404s(mcp_client: MCPClient, seeded_project: dict) -> None:
    """``procedure.run`` for an unknown slug returns -32004 NotFoundError.

    M7.A replaced the M3-era milestone deferral with the live runner;
    callers that ask for a procedure slug we haven't authored yet
    (procedures 1, 2, 3, 5, 6, 7, 8 land in M7.B) get a clean 404 instead
    of a stale milestone hint.
    """
    err = mcp_client.call_tool_error(
        "procedure.run",
        {"slug": "any-procedure", "project_id": seeded_project["data"]["id"]},
    )
    assert err["code"] == -32004
    assert err["message"] == "NotFoundError"


def test_procedure_list_returns_authored_slugs(mcp_client: MCPClient) -> None:
    """``procedure.list`` includes every slug the runner discovered on disk.

    M7.A: procedure 04-topic-to-published is authored as the workhorse;
    the rest land in M7.B. Tests assert presence rather than equality so
    M7.B can grow the list without revising this test.
    """
    payload = mcp_client.call_tool_structured("procedure.list", {})
    assert "04-topic-to-published" in payload.get("items", [])
