"""Unit tests for StackOS agent preset contracts."""

from __future__ import annotations

from stackos.agents import AgentPresetLoader, parse_agent_preset_bundle_yaml
from stackos.agents.schema import validate_agent_preset_obj


def test_agent_preset_loader_lists_bundled_roles() -> None:
    listing = AgentPresetLoader().list_presets()
    keys = {item.key for item in listing.presets}

    assert len(keys) == 23
    assert "stackos.sdlc.planning" in keys
    assert "stackos.workflow.project-memory-review" in keys
    assert "seo.workflow.keyword-research" in keys
    assert "media-buying.workflow.campaign-launch" in keys
    assert "gtm.workflow.account-research" in keys
    assert "communications.workflow.rich-telegram-reply" in keys
    assert all(item.generic_preset for item in listing.presets)
    assert all(item.adaptation_required for item in listing.presets)


def test_agent_preset_describe_includes_tracker_adaptation_guidance() -> None:
    loaded = AgentPresetLoader().describe_preset(key="stackos.sdlc.planning")

    assert loaded.preset.project_adaptation.required is True
    assert loaded.preset.project_adaptation.do_not_use_verbatim is True
    assert "tracker" in loaded.preset.project_adaptation.required_agent_action.lower()
    assert "dependencies" in " ".join(loaded.preset.prompt_contract.must_do).lower()


def test_agent_preset_bundle_parser_accepts_multi_preset_yaml() -> None:
    presets = parse_agent_preset_bundle_yaml(
        """
presets:
  - schema_version: stackos.agent-preset.v1
    key: demo.agent
    name: Demo Agent
    role: demo
    workflow_roles: [demo]
    recommended_tools: [tracker.brief]
    prompt_contract:
      mission: Demo mission.
"""
    )

    assert [item.key for item in presets] == ["demo.agent"]
    assert presets[0].project_adaptation.required is True


def test_agent_preset_schema_rejects_secret_looking_values() -> None:
    result = validate_agent_preset_obj(
        {
            "schema_version": "stackos.agent-preset.v1",
            "key": "demo.agent",
            "name": "Demo Agent",
            "role": "demo",
            "workflow_roles": ["demo"],
            "metadata": {"api_key": "real-value"},
            "prompt_contract": {"mission": "Demo mission."},
        }
    )

    assert result.valid is False
    assert "must not contain secrets" in result.errors[0].message
