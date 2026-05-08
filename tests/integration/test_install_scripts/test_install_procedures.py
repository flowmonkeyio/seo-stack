"""`scripts/install-procedures-{codex,claude}.sh` mirror `procedures/`.

The `_template/` directory must be excluded (audit A-MINOR-39); on
re-run the layout must be identical.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


def _run(script: Path, home: Path) -> str:
    return subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        env={**os.environ, "CONTENT_STACK_HOME": str(home)},
        check=True,
    ).stdout


@pytest.mark.parametrize(
    ("script_name", "runtime"),
    [
        ("install-procedures-codex.sh", "codex"),
        ("install-procedures-claude.sh", "claude"),
    ],
)
def test_install_procedures_excludes_template(
    sandbox_home: Path,
    scripts_dir: Path,
    repo_root: Path,
    script_name: str,
    runtime: str,
) -> None:
    output = _run(scripts_dir / script_name, sandbox_home)
    target = sandbox_home / f".{runtime}" / "procedures" / "content-stack"

    # `_template/` lives in the source repo but must NOT be in the install target.
    assert (repo_root / "procedures" / "_template").is_dir()
    assert not (target / "_template").exists()

    expected = sum(
        1 for p in (repo_root / "procedures").rglob("PROCEDURE.md") if "_template" not in p.parts
    )
    installed = sum(1 for _ in target.rglob("PROCEDURE.md"))
    assert installed == expected
    assert f"Installed {expected} procedures" in output


@pytest.mark.parametrize(
    "script_name",
    ["install-procedures-codex.sh", "install-procedures-claude.sh"],
)
def test_install_procedures_idempotent(
    sandbox_home: Path, scripts_dir: Path, script_name: str
) -> None:
    _run(scripts_dir / script_name, sandbox_home)
    target_root = (
        sandbox_home
        / (".codex" if "codex" in script_name else ".claude")
        / "procedures"
        / "content-stack"
    )
    first = {
        str(p.relative_to(target_root)): p.read_bytes()
        for p in sorted(target_root.rglob("*"))
        if p.is_file()
    }
    _run(scripts_dir / script_name, sandbox_home)
    second = {
        str(p.relative_to(target_root)): p.read_bytes()
        for p in sorted(target_root.rglob("*"))
        if p.is_file()
    }
    assert first == second
