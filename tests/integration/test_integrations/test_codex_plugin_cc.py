"""Codex-plugin-cc adversarial-review helper tests."""

from __future__ import annotations

import asyncio
import json
import stat
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from content_stack.integrations.codex_plugin_cc import (
    TIMEOUT_SECONDS,
    adversarial_review,
)


def test_skipped_when_plugin_root_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """No ``CLAUDE_PLUGIN_ROOT`` → SKIPPED with ``plugin-not-installed``."""
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    out = asyncio.run(
        adversarial_review(
            article_md="# X",
            eeat_criteria=[],
            project_id=1,
        )
    )
    assert out == {"verdict": "SKIPPED", "reason": "plugin-not-installed"}


def test_skipped_when_node_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``CLAUDE_PLUGIN_ROOT`` set but ``node`` not on PATH → SKIPPED."""
    plugin_root = tmp_path / "plugin"
    (plugin_root / "scripts").mkdir(parents=True)
    (plugin_root / "scripts" / "codex-companion.mjs").write_text("dummy")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))

    with patch("content_stack.integrations.codex_plugin_cc.shutil.which") as which_mock:
        which_mock.return_value = None
        out = asyncio.run(
            adversarial_review(
                article_md="# X",
                eeat_criteria=[],
                project_id=1,
            )
        )
    assert out == {"verdict": "SKIPPED", "reason": "plugin-not-installed"}


def test_happy_path_normalizes_approve_to_pass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Plugin returns ``approve`` → wrapper normalises to ``PASS``."""
    plugin_root = tmp_path / "plugin"
    (plugin_root / "scripts").mkdir(parents=True)
    script = plugin_root / "scripts" / "codex-companion.mjs"
    script.write_text("dummy")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))

    captured: dict = {}

    def fake_run(args: list[str], **kwargs: dict) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        # Capture the prompt-file content + permissions.
        idx = args.index("--prompt-file")
        prompt_path = Path(args[idx + 1])
        captured["prompt_text"] = prompt_path.read_text()
        captured["prompt_mode"] = stat.S_IMODE(prompt_path.stat().st_mode)
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(
                {
                    "verdict": "approve",
                    "summary": "All good",
                    "findings": [],
                    "next_steps": [],
                }
            ),
            stderr="",
        )

    with (
        patch(
            "content_stack.integrations.codex_plugin_cc.subprocess.run",
            side_effect=fake_run,
        ),
        patch(
            "content_stack.integrations.codex_plugin_cc.shutil.which",
            return_value="/usr/bin/node",
        ),
    ):
        out = asyncio.run(
            adversarial_review(
                article_md="# Article body",
                eeat_criteria=[{"code": "T04", "title": "Author"}],
                project_id=1,
            )
        )

    assert out == {"verdict": "PASS", "issues": []}
    # The XML wrapper is present in the prompt.
    assert "<article_under_review>" in captured["prompt_text"]
    assert "</article_under_review>" in captured["prompt_text"]
    # Mode was 0600 while the file existed.
    assert captured["prompt_mode"] == 0o600
    # Prompt-file flag form (not @path).
    assert "--prompt-file" in captured["args"]
    # The temp file was cleaned up.
    idx = captured["args"].index("--prompt-file")
    assert not Path(captured["args"][idx + 1]).exists()


def test_normalizes_critical_findings_to_block(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``needs-attention`` + critical → BLOCK."""
    plugin_root = tmp_path / "plugin"
    (plugin_root / "scripts").mkdir(parents=True)
    (plugin_root / "scripts" / "codex-companion.mjs").write_text("dummy")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))

    completed = subprocess.CompletedProcess(
        args=["node"],
        returncode=0,
        stdout=json.dumps(
            {
                "verdict": "needs-attention",
                "summary": "Issues found",
                "findings": [
                    {
                        "severity": "critical",
                        "title": "Author bio missing",
                        "body": "T04 floor not met",
                        "file": "x.md",
                        "line_start": 1,
                        "line_end": 1,
                        "confidence": 0.9,
                        "recommendation": "Add bio",
                    }
                ],
                "next_steps": [],
            }
        ),
        stderr="",
    )
    with (
        patch(
            "content_stack.integrations.codex_plugin_cc.subprocess.run",
            return_value=completed,
        ),
        patch(
            "content_stack.integrations.codex_plugin_cc.shutil.which",
            return_value="/usr/bin/node",
        ),
    ):
        out = asyncio.run(
            adversarial_review(
                article_md="# X",
                eeat_criteria=[],
                project_id=1,
            )
        )
    assert out["verdict"] == "BLOCK"
    assert out["issues"][0]["severity"] == "critical"


def test_normalizes_non_critical_to_fix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``needs-attention`` without critical → FIX."""
    plugin_root = tmp_path / "plugin"
    (plugin_root / "scripts").mkdir(parents=True)
    (plugin_root / "scripts" / "codex-companion.mjs").write_text("dummy")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))

    completed = subprocess.CompletedProcess(
        args=["node"],
        returncode=0,
        stdout=json.dumps(
            {
                "verdict": "needs-attention",
                "summary": "Minor issues",
                "findings": [
                    {
                        "severity": "low",
                        "title": "Style nit",
                        "body": "minor",
                        "file": "x.md",
                        "line_start": 1,
                        "line_end": 1,
                        "confidence": 0.5,
                        "recommendation": "tweak",
                    }
                ],
                "next_steps": [],
            }
        ),
        stderr="",
    )
    with (
        patch(
            "content_stack.integrations.codex_plugin_cc.subprocess.run",
            return_value=completed,
        ),
        patch(
            "content_stack.integrations.codex_plugin_cc.shutil.which",
            return_value="/usr/bin/node",
        ),
    ):
        out = asyncio.run(adversarial_review(article_md="# X", eeat_criteria=[], project_id=1))
    assert out["verdict"] == "FIX"


def test_timeout_returns_skipped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A subprocess timeout → SKIPPED with ``adversarial-review-timeout``."""
    plugin_root = tmp_path / "plugin"
    (plugin_root / "scripts").mkdir(parents=True)
    (plugin_root / "scripts" / "codex-companion.mjs").write_text("dummy")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))

    def raises_timeout(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd="node", timeout=TIMEOUT_SECONDS)

    with (
        patch(
            "content_stack.integrations.codex_plugin_cc.subprocess.run",
            side_effect=raises_timeout,
        ),
        patch(
            "content_stack.integrations.codex_plugin_cc.shutil.which",
            return_value="/usr/bin/node",
        ),
    ):
        out = asyncio.run(adversarial_review(article_md="# X", eeat_criteria=[], project_id=1))
    assert out == {"verdict": "SKIPPED", "reason": "adversarial-review-timeout"}


def test_nonzero_exit_returns_skipped_with_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Non-zero exit → SKIPPED + truncated stderr in ``error``."""
    plugin_root = tmp_path / "plugin"
    (plugin_root / "scripts").mkdir(parents=True)
    (plugin_root / "scripts" / "codex-companion.mjs").write_text("dummy")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))

    completed = subprocess.CompletedProcess(
        args=["node"],
        returncode=2,
        stdout="",
        stderr="boom" * 500,  # ensure truncation
    )
    with (
        patch(
            "content_stack.integrations.codex_plugin_cc.subprocess.run",
            return_value=completed,
        ),
        patch(
            "content_stack.integrations.codex_plugin_cc.shutil.which",
            return_value="/usr/bin/node",
        ),
    ):
        out = asyncio.run(adversarial_review(article_md="# X", eeat_criteria=[], project_id=1))
    assert out["verdict"] == "SKIPPED"
    assert out["reason"] == "adversarial-review-error"
    # Truncated to <= 1024 chars.
    assert len(out["error"]) <= 1024


def test_temp_file_deleted_after_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Even a happy path leaves no .md temp files behind."""
    plugin_root = tmp_path / "plugin"
    (plugin_root / "scripts").mkdir(parents=True)
    (plugin_root / "scripts" / "codex-companion.mjs").write_text("dummy")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))

    captured_path: dict[str, Path] = {}

    def fake_run(args: list[str], **kwargs: dict) -> subprocess.CompletedProcess[str]:
        idx = args.index("--prompt-file")
        captured_path["path"] = Path(args[idx + 1])
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(
                {"verdict": "approve", "summary": "ok", "findings": [], "next_steps": []}
            ),
            stderr="",
        )

    with (
        patch(
            "content_stack.integrations.codex_plugin_cc.subprocess.run",
            side_effect=fake_run,
        ),
        patch(
            "content_stack.integrations.codex_plugin_cc.shutil.which",
            return_value="/usr/bin/node",
        ),
    ):
        asyncio.run(adversarial_review(article_md="# X", eeat_criteria=[], project_id=1))
    assert captured_path["path"] is not None
    assert not captured_path["path"].exists()
