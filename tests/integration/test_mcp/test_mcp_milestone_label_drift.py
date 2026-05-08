"""Verify no MCP tool registers a stale milestone deferral.

After M8 the only active deferral is:

- ``M6`` — drift comparison engine (drift-watch skill).

The M8 jobs+scheduling subsystem landed alongside the runner driver, so
``run.resume`` / ``run.fork`` are live (they route through the
``ProcedureRunner`` the same way ``procedure.resume`` /
``procedure.fork`` already did since M7.A). The source no longer
carries the ``"milestone": "M7"`` or ``"milestone": "M8"`` deferral
literals anywhere.
"""

from __future__ import annotations

import re
from pathlib import Path

from .conftest import MCPClient


def test_no_stale_milestones_in_mcp_tools_source() -> None:
    """Source-level: ``content_stack/mcp/tools/*.py`` carries no stale labels."""
    repo_root = Path(__file__).resolve().parents[3]
    pat = re.compile(r'"milestone":\s*"(M5|M7|M8|M9)"')
    offenders: list[str] = []
    for path in (repo_root / "content_stack" / "mcp" / "tools").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in pat.finditer(text):
            offenders.append(f"{path}: {match.group(0)}")
    assert offenders == [], (
        "MCP tool sources still reference M5/M7/M8/M9 deferrals — after M8 only M6 remains: "
        + "; ".join(offenders)
    )


def test_drift_diff_reports_m6_milestone(
    mcp_client: MCPClient,
    seeded_project: dict,
) -> None:
    err = mcp_client.call_tool_error("drift.diff", {"baseline_id": 1, "current_md": "x"})
    assert err["data"]["milestone"] == "M6"
