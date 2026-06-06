"""MCP adapter registration for execution context operations."""

from __future__ import annotations

from stackos.mcp.server import ToolRegistry
from stackos.operations.adapters.mcp import register_mcp_operation_names

_EXECUTION_CONTEXT_OPERATION_NAMES = (
    "executionContext.artifact.list",
    "executionContext.artifact.read",
    "executionContext.create",
    "executionContext.get",
    "executionContext.list",
    "executionContext.discover",
    "executionContext.resolve",
    "executionContext.update",
    "executionContext.link",
    "executionContext.unlink",
)


def register(registry: ToolRegistry) -> None:
    register_mcp_operation_names(registry, _EXECUTION_CONTEXT_OPERATION_NAMES)


__all__ = ["register"]
