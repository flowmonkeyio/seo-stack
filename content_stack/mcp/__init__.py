"""MCP tool definitions + Streamable HTTP transport mount.

Top-level export is ``register_mcp`` — the single entry point
``content_stack.server.create_app`` calls to wire the MCP transport
onto the FastAPI app.
"""

from __future__ import annotations

from content_stack.mcp.server import register_mcp

__all__ = ["register_mcp"]
