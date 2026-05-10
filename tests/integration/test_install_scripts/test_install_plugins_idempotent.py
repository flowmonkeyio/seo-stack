"""`scripts/install-plugins.sh` mirrors plugin packages into a sandbox HOME."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def _run(script: Path, home: Path, *args: str) -> str:
    result = subprocess.run(
        ["bash", str(script), *args],
        capture_output=True,
        text=True,
        env={**os.environ, "CONTENT_STACK_HOME": str(home)},
        check=True,
    )
    return result.stdout


def _snapshot(target: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(target)): p.read_bytes() for p in sorted(target.rglob("*")) if p.is_file()
    }


def test_install_plugins_creates_plugin_and_marketplace(
    sandbox_home: Path, scripts_dir: Path
) -> None:
    output = _run(scripts_dir / "install-plugins.sh", sandbox_home)
    plugin_root = sandbox_home / "plugins" / "content-stack"
    marketplace = sandbox_home / ".agents" / "plugins" / "marketplace.json"
    payload = json.loads(marketplace.read_text(encoding="utf-8"))

    assert "Installed 1 plugins" in output
    assert (plugin_root / ".codex-plugin" / "plugin.json").is_file()
    assert (plugin_root / "skills" / "content-stack" / "SKILL.md").is_file()
    assert (
        plugin_root / "skills" / "catalog" / "01-research" / "keyword-discovery" / "SKILL.md"
    ).is_file()
    assert (plugin_root / "procedures" / "04-topic-to-published" / "PROCEDURE.md").is_file()
    assert any(p["name"] == "content-stack" for p in payload["plugins"])


def test_install_plugins_idempotent(sandbox_home: Path, scripts_dir: Path) -> None:
    _run(scripts_dir / "install-plugins.sh", sandbox_home)
    target = sandbox_home / "plugins"
    snap1 = _snapshot(target)

    _run(scripts_dir / "install-plugins.sh", sandbox_home)
    snap2 = _snapshot(target)

    assert snap1 == snap2


def test_install_plugins_remove_preserves_marketplace_file(
    sandbox_home: Path, scripts_dir: Path
) -> None:
    _run(scripts_dir / "install-plugins.sh", sandbox_home)

    _run(scripts_dir / "install-plugins.sh", sandbox_home, "--remove")

    plugin_root = sandbox_home / "plugins" / "content-stack"
    marketplace = sandbox_home / ".agents" / "plugins" / "marketplace.json"
    payload = json.loads(marketplace.read_text(encoding="utf-8"))
    assert not plugin_root.exists()
    assert all(p["name"] != "content-stack" for p in payload["plugins"])
