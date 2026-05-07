"""Verify no MCP tool registers a stale milestone deferral.

After M7.A the active deferrals are:

- ``M6`` — drift comparison engine (drift-watch skill).
- ``M8`` — run.resume / run.fork (jobs/scheduling subsystem; the
  high-level ``procedure.resume`` + ``procedure.fork`` ARE live, but the
  per-skill audit-row resume primitives are still M8).

The procedure runner itself + ``procedure.run/resume/fork`` were the
M7 deferrals; M7.A landed the runner so those tools now return live
envelopes. The source no longer carries the ``"milestone": "M7"``
literal anywhere.
"""

from __future__ import annotations

import re
from pathlib import Path

from .conftest import MCPClient


def test_no_m5_or_m9_milestones_in_mcp_tools_source() -> None:
    """Source-level: ``content_stack/mcp/tools/*.py`` carries no stale labels."""
    repo_root = Path(__file__).resolve().parents[3]
    pat = re.compile(r'"milestone":\s*"(M5|M7|M9)"')
    offenders: list[str] = []
    for path in (repo_root / "content_stack" / "mcp" / "tools").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in pat.finditer(text):
            offenders.append(f"{path}: {match.group(0)}")
    assert offenders == [], (
        "MCP tool sources still reference M5/M7/M9 milestones — after M7.A only M6/M8 remain: "
        + "; ".join(offenders)
    )


def test_drift_diff_reports_m6_milestone(
    mcp_client: MCPClient,
    seeded_project: dict,
) -> None:
    err = mcp_client.call_tool_error("drift.diff", {"baseline_id": 1, "current_md": "x"})
    assert err["data"]["milestone"] == "M6"


def test_run_resume_fork_report_m8_milestone(
    mcp_client: MCPClient,
    seeded_project: dict,
) -> None:
    """``run.resume`` / ``run.fork`` defer to M8 (jobs+scheduling).

    These are the per-skill audit-row primitives — distinct from the
    high-level ``procedure.resume`` / ``procedure.fork`` (live since M7.A).
    """
    env = mcp_client.call_tool_structured(
        "run.start",
        {"project_id": seeded_project["data"]["id"], "kind": "procedure"},
    )
    err_resume = mcp_client.call_tool_error("run.resume", {"run_id": env["data"]["run_id"]})
    assert err_resume["data"]["milestone"] == "M8"
    err_fork = mcp_client.call_tool_error(
        "run.fork", {"run_id": env["data"]["run_id"], "from_step": "x"}
    )
    assert err_fork["data"]["milestone"] == "M8"
