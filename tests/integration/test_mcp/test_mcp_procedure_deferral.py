"""MCP procedure tools expose agent-led procedure state.

``procedure.run`` opens durable state; the current agent claims,
executes, and records steps. Deterministic ``_programmatic/*`` work is
available only through the explicit ``procedure.executeProgrammaticStep``
tool, not a daemon-spawned writer session.
"""

from __future__ import annotations

from .conftest import MCPClient


def test_procedure_list_includes_seed_procedures(mcp_client: MCPClient) -> None:
    """``procedure.list`` returns the slugs the runner discovered on disk.

    M7.A authored procedure 04-topic-to-published as the workhorse +
    proof-of-concept; M7.B added the remaining seven procedures
    (1, 2, 3, 5, 6, 7, 8). All eight should be in the registry now.
    """
    payload = mcp_client.call_tool_structured("procedure.list", {})
    items = payload.get("items", [])
    expected = {
        "01-bootstrap-project",
        "02-one-site-shortcut",
        "03-keyword-to-topic-queue",
        "04-topic-to-published",
        "05-bulk-content-launch",
        "06-weekly-gsc-review",
        "07-monthly-humanize-pass",
        "08-add-new-site",
    }
    assert expected.issubset(set(items)), items


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
    """``procedure.run`` opens an agent-led run + returns the envelope."""
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
    assert data["orchestration_mode"] == "agent-led"
    assert data["run_token"]
    assert data["run_id"] >= 1


def test_agent_led_claim_and_record_step(mcp_client: MCPClient, seeded_project: dict) -> None:
    """Agent-led procedures expose the skill prompt and persist caller output."""
    started = mcp_client.call_tool_structured(
        "procedure.run",
        {
            "slug": "04-topic-to-published",
            "project_id": seeded_project["data"]["id"],
            "args": {"topic_id": 1},
        },
    )["data"]
    run_id = started["run_id"]
    run_token = started["run_token"]

    current = mcp_client.call_tool_structured("procedure.currentStep", {"run_id": run_id})
    assert current["next_action"] == "claim_step"
    assert current["current_step"]["step_id"] == "brief"
    assert current["current_step"]["status"] == "pending"
    assert "article.create" in current["current_step"]["allowed_tools"]
    assert "content-brief" in current["current_step"]["skill"]
    assert current["current_step"]["skill_body"]

    claimed = mcp_client.call_tool_structured(
        "procedure.claimStep", {"run_id": run_id, "step_id": "brief"}
    )["data"]
    assert claimed["next_action"] == "execute_step"
    assert claimed["current_step"]["status"] == "running"

    recorded = mcp_client.call_tool_structured(
        "procedure.recordStep",
        {
            "run_id": run_id,
            "step_id": "brief",
            "status": "success",
            "output_json": {"article_id": 123, "brief_set": True},
            "run_token": run_token,
        },
    )["data"]
    assert recorded["next_action"] == "claim_step"
    assert recorded["current_step"]["step_id"] == "outline"
    assert recorded["previous_outputs"]["brief"]["brief_set"] is True

    status = mcp_client.call_tool_structured("procedure.status", {"run_id": run_id})
    assert status["steps"][0]["status"] == "success"
    assert status["steps"][0]["output_json"]["article_id"] == 123


def test_agent_led_execute_programmatic_step(mcp_client: MCPClient, seeded_project: dict) -> None:
    """A procedure run token can execute deterministic programmatic steps explicitly."""
    started = mcp_client.call_tool_structured(
        "procedure.run",
        {
            "slug": "05-bulk-content-launch",
            "project_id": seeded_project["data"]["id"],
            "args": {"topic_ids": [123], "budget_cap_usd": 10.0},
        },
    )["data"]
    run_id = started["run_id"]
    run_token = started["run_token"]

    current = mcp_client.call_tool_structured(
        "procedure.currentStep", {"run_id": run_id, "run_token": run_token}
    )
    assert current["next_action"] == "execute_programmatic_step"
    assert current["current_step"]["step_id"] == "estimate-cost"
    assert "procedure.executeProgrammaticStep" in current["current_step"]["allowed_tools"]

    executed = mcp_client.call_tool_structured(
        "procedure.executeProgrammaticStep",
        {"run_id": run_id, "step_id": "estimate-cost", "run_token": run_token},
    )["data"]
    assert executed["previous_outputs"]["estimate-cost"]["n_topics"] == 1
    assert executed["current_step"]["step_id"] == "spawn-procedure-4-batch"


def test_procedure_run_accepts_all_8_slugs(mcp_client: MCPClient, seeded_project: dict) -> None:
    """After M7.B every authored procedure slug is accepted by ``procedure.run``.

    Smokes that the registry exposes the M7.B catalogue at the MCP
    boundary — none of the eight slugs should surface a -32004
    NotFoundError. Per-procedure runtime behaviour is covered by the
    runner integration tests; this is a wire-shape sanity check.
    """
    for slug in (
        "01-bootstrap-project",
        "02-one-site-shortcut",
        "03-keyword-to-topic-queue",
        "04-topic-to-published",
        "05-bulk-content-launch",
        "06-weekly-gsc-review",
        "07-monthly-humanize-pass",
        "08-add-new-site",
    ):
        payload = mcp_client.call_tool_structured(
            "procedure.run",
            {
                "slug": slug,
                "project_id": seeded_project["data"]["id"],
                "args": {},
            },
        )
        data = payload["data"]
        assert data["slug"] == slug
        assert data["started"] is True
        assert data["run_id"] >= 1
