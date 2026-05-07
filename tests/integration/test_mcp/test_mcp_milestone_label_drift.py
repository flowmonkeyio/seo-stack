"""Verify no MCP tool registers a ``milestone='M5'/'M9'`` deferral after M4.

After M4 the active deferrals are:

- ``M6`` — drift comparison engine (drift-watch skill).
- ``M7`` — procedure runner + procedure.resume + procedure.fork.
- ``M8`` — run.resume / run.fork (jobs/scheduling subsystem).

We grep the registered tool descriptions + invoke each deferred tool to
confirm the ``data.milestone`` field carries the right label. Hard-coded
test rather than a regex over source so a fresh deferral hidden behind a
new tool name still gets caught.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from .conftest import MCPClient


def test_no_m5_or_m9_milestones_in_mcp_tools_source() -> None:
    """Source-level: ``content_stack/mcp/tools/*.py`` carries no stale labels."""
    repo_root = Path(__file__).resolve().parents[3]
    pat = re.compile(r'"milestone":\s*"(M5|M9)"')
    offenders: list[str] = []
    for path in (repo_root / "content_stack" / "mcp" / "tools").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in pat.finditer(text):
            offenders.append(f"{path}: {match.group(0)}")
    assert offenders == [], (
        "MCP tool sources still reference M5/M9 milestones — they should be M6/M7/M8 after M4: "
        + "; ".join(offenders)
    )


def test_no_m8_label_for_procedure_runner_in_mcp_tools_source() -> None:
    """Procedure runner moved from M8 → M7; the source must reflect that."""
    repo_root = Path(__file__).resolve().parents[3]
    runs_path = repo_root / "content_stack" / "mcp" / "tools" / "runs.py"
    text = runs_path.read_text(encoding="utf-8")
    # The procedure_run/resume/fork helpers should now reference M7.
    assert '"milestone": "M7"' in text or '"milestone":"M7"' in text


def test_drift_diff_reports_m6_milestone(
    mcp_client: MCPClient,
    seeded_project: dict,
) -> None:
    err = mcp_client.call_tool_error("drift.diff", {"baseline_id": 1, "current_md": "x"})
    assert err["data"]["milestone"] == "M6"


@pytest.mark.parametrize(
    "tool, args",
    [
        ("procedure.run", {"slug": "x", "project_id": 0}),
        ("procedure.resume", {"run_id": 1}),
        ("procedure.fork", {"run_id": 1, "from_step": "x"}),
    ],
)
def test_procedure_tools_report_m7_milestone(
    mcp_client: MCPClient,
    seeded_project: dict,
    tool: str,
    args: dict,
) -> None:
    if "project_id" in args and args["project_id"] == 0:
        args = {**args, "project_id": seeded_project["data"]["id"]}
    err = mcp_client.call_tool_error(tool, args)
    assert err["data"]["milestone"] == "M7"


def test_run_resume_fork_report_m8_milestone(
    mcp_client: MCPClient,
    seeded_project: dict,
) -> None:
    """``run.resume`` / ``run.fork`` defer to M8 (jobs+scheduling)."""
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
