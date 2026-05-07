"""``meta.enums`` returns every enum + transitions; mirrors REST."""

from __future__ import annotations

from .conftest import MCPClient


def test_meta_enums_returns_full_payload(mcp_client: MCPClient) -> None:
    """The MCP ``meta.enums`` tool returns the same shape as REST ``GET /meta/enums``."""
    payload = mcp_client.call_tool_structured("meta.enums", {})
    # Top-level keys mirror EnumLookupResponse exactly.
    expected_keys = {
        "topics_status",
        "topics_intent",
        "topics_source",
        "articles_status",
        "article_assets_kind",
        "article_publishes_status",
        "runs_status",
        "runs_kind",
        "run_steps_status",
        "procedure_run_steps_status",
        "clusters_type",
        "compliance_rules_kind",
        "compliance_rules_position",
        "eeat_criteria_tier",
        "eeat_criteria_category",
        "eeat_evaluations_verdict",
        "internal_links_status",
        "publish_targets_kind",
        "redirects_kind",
        "allowed_transitions",
    }
    assert expected_keys <= set(payload.keys())


def test_meta_enums_status_values_are_strings(mcp_client: MCPClient) -> None:
    """Every enum list contains stringly-typed values (matches StrEnum)."""
    payload = mcp_client.call_tool_structured("meta.enums", {})
    for key in ("topics_status", "articles_status", "runs_status"):
        assert all(isinstance(v, str) for v in payload[key])


def test_meta_enums_transitions_well_formed(mcp_client: MCPClient) -> None:
    """``allowed_transitions`` carries dict-of-dict-of-list shape."""
    payload = mcp_client.call_tool_structured("meta.enums", {})
    transitions = payload["allowed_transitions"]
    for table in ("topics", "articles", "runs", "internal_links"):
        assert table in transitions
        for state, allowed in transitions[table].items():
            assert isinstance(state, str)
            assert isinstance(allowed, list)
