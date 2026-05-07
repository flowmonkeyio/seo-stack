"""project.* + voice.* + eeat.* exercise via MCP, including D7 invariant."""

from __future__ import annotations

from .conftest import MCPClient


def test_project_create_returns_envelope(mcp_client: MCPClient) -> None:
    """project.create returns ``{data, run_id, project_id}`` envelope."""
    env = mcp_client.call_tool_structured(
        "project.create",
        {
            "slug": "p-create",
            "name": "P Create",
            "domain": "create.example",
            "locale": "en-US",
        },
    )
    assert "data" in env
    assert "project_id" in env
    assert env["data"]["slug"] == "p-create"


def test_project_get_by_slug(mcp_client: MCPClient, seeded_project: dict) -> None:
    """project.get accepts slug or id."""
    proj = mcp_client.call_tool_structured("project.get", {"id_or_slug": "test-project"})
    assert proj["slug"] == "test-project"
    proj2 = mcp_client.call_tool_structured(
        "project.get", {"id_or_slug": seeded_project["data"]["id"]}
    )
    assert proj2["id"] == seeded_project["data"]["id"]


def test_project_list_after_create(mcp_client: MCPClient, seeded_project: dict) -> None:
    """project.list returns the seeded project."""
    page = mcp_client.call_tool_structured("project.list", {})
    assert page["total_estimate"] >= 1
    slugs = [p["slug"] for p in page["items"]]
    assert "test-project" in slugs


def test_project_update_returns_envelope(mcp_client: MCPClient, seeded_project: dict) -> None:
    """project.update returns the new state under ``data``."""
    pid = seeded_project["data"]["id"]
    env = mcp_client.call_tool_structured(
        "project.update", {"project_id": pid, "patch": {"name": "Renamed"}}
    )
    assert env["data"]["name"] == "Renamed"


def test_project_set_active_writes_envelope(mcp_client: MCPClient, seeded_project: dict) -> None:
    """project.setActive returns an envelope with project_id."""
    pid = seeded_project["data"]["id"]
    env = mcp_client.call_tool_structured("project.setActive", {"project_id": pid})
    assert env["project_id"] == pid
    assert env["data"]["is_active"] is True


def test_eeat_seed_present_after_project_create(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """80 EEAT criteria seeded; D7 ``tier='core'`` items present."""
    pid = seeded_project["data"]["id"]
    rows = mcp_client.call_tool_structured("eeat.list", {"project_id": pid})
    assert isinstance(rows, dict)  # wrapped by _result_to_json into {"items": [...]}
    items = rows["items"]
    assert len(items) >= 80, f"got {len(items)} criteria"
    core_codes = {r["code"] for r in items if r["tier"] == "core"}
    assert {"T04", "C01", "R10"} <= core_codes


def test_eeat_toggle_core_floor_is_protected(mcp_client: MCPClient, seeded_project: dict) -> None:
    """eeat.toggle on a tier='core' criterion with active=False → -32008."""
    pid = seeded_project["data"]["id"]
    rows = mcp_client.call_tool_structured("eeat.list", {"project_id": pid})["items"]
    core_row = next(r for r in rows if r["tier"] == "core")
    err = mcp_client.call_tool_error(
        "eeat.toggle", {"criterion_id": core_row["id"], "active": False}
    )
    assert err["code"] == -32008  # ConflictError
    assert err["message"] == "ConflictError"


def test_voice_set_and_set_active(mcp_client: MCPClient, seeded_project: dict) -> None:
    """voice.set + voice.setActive form a working pair."""
    pid = seeded_project["data"]["id"]
    env = mcp_client.call_tool_structured(
        "voice.set",
        {
            "project_id": pid,
            "name": "default",
            "voice_md": "# Voice profile\n",
            "is_default": True,
        },
    )
    voice_id = env["data"]["id"]
    activated = mcp_client.call_tool_structured("voice.setActive", {"voice_id": voice_id})
    assert activated["data"]["is_default"] is True


def test_project_create_duplicate_slug_returns_conflict(
    mcp_client: MCPClient, seeded_project: dict
) -> None:
    """Creating a second project with the seeded slug returns -32008."""
    err = mcp_client.call_tool_error(
        "project.create",
        {
            "slug": "test-project",
            "name": "Duplicate",
            "domain": "dup.example",
            "locale": "en-US",
        },
    )
    assert err["code"] == -32008
    assert err["message"] == "ConflictError"
