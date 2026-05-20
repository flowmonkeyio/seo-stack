"""Hidden vendor tools are callable only through granted skill context."""

from __future__ import annotations

import base64

from pytest_httpx import HTTPXMock

from content_stack.config import Settings

from .conftest import MCPClient


def _start_run_for_skill(mcp: MCPClient, project_id: int, skill_name: str) -> str:
    env = mcp.call_tool_structured(
        "run.start",
        {
            "project_id": project_id,
            "kind": "procedure",
            "procedure_slug": skill_name,
            "skill_name": skill_name,
        },
    )
    return env["data"]["run_token"]


def test_hidden_vendor_tool_requires_grant(
    mcp_client: MCPClient,
    seeded_project: dict,
) -> None:
    project_id = seeded_project["data"]["id"]

    err = mcp_client.call_tool_error(
        "jina.read",
        {"project_id": project_id, "url": "https://example.com"},
    )

    assert err["code"] == -32007
    assert err["message"] == "ToolNotGrantedError"
    assert err["data"]["tool"] == "jina.read"
    assert err["data"]["skill"] == "__system__"


def test_granted_skill_can_call_hidden_vendor_tool(
    mcp_client: MCPClient,
    seeded_project: dict,
    httpx_mock: HTTPXMock,
) -> None:
    project_id = seeded_project["data"]["id"]
    token = _start_run_for_skill(mcp_client, project_id, "01-research/serp-analyzer")
    httpx_mock.add_response(
        method="GET",
        url="https://r.jina.ai/https://example.com",
        text="# Example\n\nReadable page.",
    )

    out = mcp_client.call_tool_structured(
        "jina.read",
        {
            "project_id": project_id,
            "url": "https://example.com",
            "run_token": token,
        },
    )

    assert out["vendor"] == "jina"
    assert out["credential_id"] is None
    assert out["data"].startswith("# Example")


def test_openai_images_generate_persists_to_app_generated_assets_dir(
    mcp_client: MCPClient,
    seeded_project: dict,
    httpx_mock: HTTPXMock,
    mcp_settings: Settings,
) -> None:
    project_id = seeded_project["data"]["id"]
    cred = mcp_client.call_tool_structured(
        "integration.set",
        {
            "project_id": project_id,
            "kind": "openai-images",
            "plaintext_payload_b64": base64.b64encode(b"sk-openai").decode("ascii"),
        },
    )
    budget_resp = mcp_client.test_client.post(
        f"/api/v1/projects/{project_id}/budgets",
        json={"kind": "openai-images", "monthly_budget_usd": 10.0},
        headers={"authorization": f"Bearer {mcp_client.auth_token}"},
    )
    assert budget_resp.status_code == 201
    token = _start_run_for_skill(mcp_client, project_id, "03-assets/image-generator")
    httpx_mock.add_response(
        method="POST",
        url="https://api.openai.com/v1/images/generations",
        json={"data": [{"b64_json": base64.b64encode(b"webp").decode("ascii")}]},
    )

    out = mcp_client.call_tool_structured(
        "openaiImages.generate",
        {
            "project_id": project_id,
            "prompt": "editorial hero",
            "run_token": token,
        },
    )

    assert "data" in out and isinstance(out["data"].get("data"), list), out
    item = out["data"]["data"][0]
    assert out["credential_id"] == cred["data"]["id"]
    assert "b64_json" not in item
    assert item["url"].startswith("/generated-assets/openai-images/openai-")
    path = mcp_settings.generated_assets_dir / item["url"].removeprefix("/generated-assets/")
    assert path.read_bytes() == b"webp"
