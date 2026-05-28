"""MCP adapter registration for scoped readiness operations."""

from __future__ import annotations

from stackos.mcp.server import ToolRegistry
from stackos.operations.adapters.mcp import register_mcp_operation_names


def register(registry: ToolRegistry) -> None:
    register_mcp_operation_names(registry, ("readiness.check",))


__all__ = ["register"]
