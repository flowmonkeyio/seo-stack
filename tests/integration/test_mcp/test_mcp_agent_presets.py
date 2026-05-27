"""MCP tests for StackOS agent preset tools."""

from __future__ import annotations

from .conftest import MCPClient


def test_agent_preset_tools_are_callable(mcp_client: MCPClient) -> None:
    listing = mcp_client.call_tool_structured(
        "agentPreset.list",
        {"workflow_key": "core.project-memory-review"},
    )
    described = mcp_client.call_tool_structured(
        "agentPreset.describe",
        {"key": "stackos.sdlc.planning"},
    )
    resolved = mcp_client.call_tool_structured(
        "agentPreset.resolveForWorkflow",
        {"workflow_key": "core.project-memory-review"},
    )

    assert "stackos.sdlc.planning" in {item["key"] for item in listing["presets"]}
    assert described["preset"]["summary"]["key"] == "stackos.sdlc.planning"
    assert described["project_adaptation"]["adaptation_required"] is True
    assert described["project_adaptation"]["do_not_use_verbatim"] is True
    assert "tracker" in described["project_adaptation"]["required_agent_action"].lower()
    assert resolved["workflow"]["key"] == "core.project-memory-review"
    assert resolved["required_agents"][0]["preset"]["summary"]["key"] == (
        "stackos.workflow.project-memory-review"
    )
    assert resolved["recommended_agents"][0]["preset"]["summary"]["key"] == (
        "stackos.sdlc.planning"
    )
    assert resolved["skill_requirements"][0]["skill_ref"] == "stackos:stackos"
    assert "Workflow templates are inert" in " ".join(resolved["setup_guidance"])
