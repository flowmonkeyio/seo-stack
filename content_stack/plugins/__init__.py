"""StackOS plugin manifest and catalog helpers."""

from content_stack.plugins.manifest import (
    BUILTIN_PLUGIN_MANIFESTS,
    ActionManifest,
    CapabilityManifest,
    PluginManifest,
    ProviderManifest,
    ResourceManifest,
    load_plugin_manifest_file,
    load_plugin_manifest_files,
)

__all__ = [
    "BUILTIN_PLUGIN_MANIFESTS",
    "ActionManifest",
    "CapabilityManifest",
    "PluginManifest",
    "ProviderManifest",
    "ResourceManifest",
    "load_plugin_manifest_file",
    "load_plugin_manifest_files",
]
