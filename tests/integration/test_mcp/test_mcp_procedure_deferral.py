"""``procedure.list`` / ``procedure.status`` work today; the rest are M7 live now.

Pre-M7 these tools returned ``MilestoneDeferralError(milestone='M7')``;
M7.A replaced the deferrals with the daemon-orchestrated runner per
locked decision D4. The remaining M7 marker is M7's follow-up
(real OpenAI / Anthropic dispatchers); the runner itself + the
StubDispatcher land in M7.A.

Tests that used to assert on the M7 deferral envelope now assert on
the live ``procedure.run`` / ``procedure.resume`` / ``procedure.fork``
behaviour. Smoke checks only — full coverage lives in
``tests/integration/test_procedure_runner/`` and
``tests/integration/test_routes/test_procedures_run_route.py``.
"""

from __future__ import annotations

from .conftest import MCPClient


def test_procedure_list_includes_seed_procedures(mcp_client: MCPClient) -> None:
    """``procedure.list`` returns the slugs the runner discovered on disk.

    M7.A authors procedure 04-topic-to-published as the workhorse +
    proof-of-concept; subsequent procedures (1, 2, 3, 5, 6, 7, 8) land
    in M7.B. The runner's registry is built at lifespan startup, so
    the slug list is non-empty.
    """
    payload = mcp_client.call_tool_structured("procedure.list", {})
    items = payload.get("items", [])
    assert "04-topic-to-published" in items, items


def test_procedure_status_works_for_existing_run(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """procedure.status reads RunRepository.get + step rows."""
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
    assert status["steps"] == []


def test_procedure_run_unknown_slug_surfaces_404(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """An unknown slug surfaces -32004 NotFoundError (procedure not registered)."""
    err = mcp_client.call_tool_error(
        "procedure.run",
        {
            "slug": "nope-not-a-real-procedure",
            "project_id": seeded_project["data"]["id"],
        },
    )
    assert err["code"] == -32004
    assert "nope-not-a-real-procedure" in err["data"]["detail"]


def test_procedure_run_returns_envelope(mcp_client: MCPClient, seeded_project: dict) -> None:
    """``procedure.run`` enqueues the runner + returns the envelope.

    Asserts the wire shape; full happy-path coverage lives in the
    procedure runner's integration tests.
    """
    payload = mcp_client.call_tool_structured(
        "procedure.run",
        {
            "slug": "04-topic-to-published",
            "project_id": seeded_project["data"]["id"],
            "args": {"topic_id": 1},
        },
    )
    data = payload["data"]
    assert data["slug"] == "04-topic-to-published"
    assert data["started"] is True
    assert data["run_token"]
    assert data["run_id"] >= 1
