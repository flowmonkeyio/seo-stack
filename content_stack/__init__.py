"""content-stack: stateful CRUD seam for multi-project SEO content pipelines.

Public surface intentionally thin — the daemon is consumed via REST (`/api/v1`),
MCP (`/mcp`), or the bundled Vue UI (`/`), not via direct Python imports.
"""

from __future__ import annotations

__version__ = "0.0.1"
__milestone__ = "M0"

__all__ = ["__milestone__", "__version__"]
