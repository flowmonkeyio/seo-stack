"""Agent preset contracts and loading helpers."""

from stackos.agents.loader import (
    AgentPresetListOut,
    AgentPresetLoader,
    AgentPresetSummaryOut,
    LoadedAgentPreset,
)
from stackos.agents.schema import (
    AGENT_PRESET_SCHEMA_VERSION,
    AgentPresetBundleSpec,
    AgentPresetSpec,
    AgentPresetValidationOut,
    parse_agent_preset_bundle_yaml,
    parse_agent_preset_yaml,
    validate_agent_preset_obj,
    validate_agent_preset_yaml,
)

__all__ = [
    "AGENT_PRESET_SCHEMA_VERSION",
    "AgentPresetBundleSpec",
    "AgentPresetListOut",
    "AgentPresetLoader",
    "AgentPresetSpec",
    "AgentPresetSummaryOut",
    "AgentPresetValidationOut",
    "LoadedAgentPreset",
    "parse_agent_preset_bundle_yaml",
    "parse_agent_preset_yaml",
    "validate_agent_preset_obj",
    "validate_agent_preset_yaml",
]
