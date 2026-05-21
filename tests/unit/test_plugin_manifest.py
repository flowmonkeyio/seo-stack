"""Unit tests for StackOS plugin manifests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from content_stack.plugins.manifest import BUILTIN_PLUGIN_MANIFESTS, PluginManifest


def test_builtin_plugin_manifests_validate() -> None:
    slugs = [manifest.slug for manifest in BUILTIN_PLUGIN_MANIFESTS]

    assert slugs == ["core", "seo", "utils"]
    for manifest in BUILTIN_PLUGIN_MANIFESTS:
        assert manifest.capabilities
        assert manifest.model_dump(mode="json")["slug"] == manifest.slug


def test_manifest_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(
            {
                "slug": "bad-plugin",
                "name": "Bad",
                "unexpected": True,
            }
        )


def test_manifest_rejects_invalid_identifier() -> None:
    with pytest.raises(ValidationError):
        PluginManifest.model_validate({"slug": "Bad Plugin", "name": "Bad"})
