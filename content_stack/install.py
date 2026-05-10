"""Install pipeline shared by clone-mode (bash scripts) and pipx-mode (`content-stack install`).

Per PLAN.md "Distribution model" (~L1499): clone installs reach into
``${REPO_ROOT}/skills`` and ``${REPO_ROOT}/procedures`` directly via the
bash scripts under ``scripts/``. pipx installs cannot — there is no repo
on disk, only a wheel — so the assets are bundled at
``content_stack/_assets/skills``, ``content_stack/_assets/procedures``, and
``content_stack/_assets/plugins``
(audit P-G4) and resolved through ``importlib.resources``.

The two install paths copy from different *sources* but write to the same
*targets* and share the same idempotency contract (audit B-24): re-running
yields the same end state.

Public surface:

- :func:`detect_mode` — returns ``"clone"`` if the package import points at
  a checked-out repo with ``skills/`` + ``procedures/`` siblings, else
  ``"pipx"``.
- :func:`copy_skills` / :func:`copy_procedures` / :func:`copy_plugins` —
  mirror assets into ``~/.codex/...``, ``~/.claude/...``, or ``~/plugins`` with
  mtime-aware copy and
  ``--delete``-style cleanup of stale files.
- :func:`register_mcp_codex` / :func:`register_mcp_claude` — Python
  equivalents of the bash registration scripts. Used by ``content-stack
  install`` so a pipx install does not require the bash scripts to be
  on PATH.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterable
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Literal

InstallMode = Literal["clone", "pipx"]
"""How the daemon was installed: from a checked-out git repo or via pipx."""


# ---------------------------------------------------------------------------
# Mode detection + asset resolution
# ---------------------------------------------------------------------------


def _package_root() -> Path:
    """Return the on-disk path to the imported `content_stack` package."""
    import content_stack

    pkg_path = Path(content_stack.__file__).resolve().parent
    return pkg_path


def _repo_root_if_clone() -> Path | None:
    """Return the repo root iff the package import points at a clone.

    Heuristic: the parent of the package directory contains a ``skills/``
    folder with at least one ``SKILL.md`` and a ``pyproject.toml`` whose
    ``name`` is ``content-stack``. We do NOT rely on the presence of
    ``.git`` because users may install via ``uv pip install -e`` from a
    tarball checkout without ``.git``.
    """
    parent = _package_root().parent
    pyproj = parent / "pyproject.toml"
    skills = parent / "skills"
    procedures = parent / "procedures"
    if not (pyproj.exists() and skills.is_dir() and procedures.is_dir()):
        return None
    try:
        text = pyproj.read_text(encoding="utf-8")
    except OSError:
        return None
    if 'name = "content-stack"' not in text:
        return None
    if not any(skills.rglob("SKILL.md")):
        return None
    return parent


def detect_mode() -> InstallMode:
    """Return the install mode based on the on-disk layout."""
    return "clone" if _repo_root_if_clone() is not None else "pipx"


def _bundled_assets_root() -> Traversable:
    """Return a `Traversable` rooted at the wheel-bundled `_assets/` tree.

    Raises ``FileNotFoundError`` when the assets are not present, which
    happens during clone-mode development before the first wheel build.
    """
    root = resources.files("content_stack").joinpath("_assets")
    if not root.is_dir():
        raise FileNotFoundError(
            "content_stack/_assets/ not found in the installed package. "
            "In clone-mode, run `make build-ui` then re-run."
        )
    return root


def _resolve_source(kind: Literal["skills", "procedures", "plugins"]) -> Path | Traversable:
    """Return the source root for ``kind`` based on detected mode.

    Returns a :class:`Path` in clone mode (so callers can use ``rsync`` /
    ``shutil.copytree`` directly) or a :class:`Traversable` in pipx mode
    (so callers walk the bundled wheel resources).
    """
    repo = _repo_root_if_clone()
    if repo is not None:
        return repo / kind
    return _bundled_assets_root().joinpath(kind)


# ---------------------------------------------------------------------------
# Copy primitives
# ---------------------------------------------------------------------------


def _iter_traversable(
    root: Traversable, exclude_dirs: Iterable[str]
) -> Iterable[tuple[str, Traversable]]:
    """Yield ``(rel_posix_path, traversable)`` for every file under ``root``.

    Directories whose name appears in ``exclude_dirs`` are skipped wholesale.
    """
    excluded = frozenset(exclude_dirs)

    def walk(node: Traversable, rel: str) -> Iterable[tuple[str, Traversable]]:
        for child in node.iterdir():
            name = child.name
            if name in {".DS_Store", "__pycache__"}:
                continue
            child_rel = f"{rel}/{name}" if rel else name
            if child.is_dir():
                if name in excluded:
                    continue
                yield from walk(child, child_rel)
            else:
                yield child_rel, child

    yield from walk(root, "")


def _mirror_traversable(
    source: Traversable,
    dest: Path,
    exclude_dirs: Iterable[str],
) -> None:
    """Copy every file under ``source`` (``Traversable``) into ``dest``.

    Pre-existing files NOT present in ``source`` are removed so the result
    matches ``rsync --delete``.
    """
    dest.mkdir(parents=True, exist_ok=True)

    seen: set[Path] = set()
    for rel, node in _iter_traversable(source, exclude_dirs):
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # `Traversable.read_bytes()` covers both filesystem and
        # zipfile-backed resources.
        target.write_bytes(node.read_bytes())
        seen.add(target.resolve())

    # Sweep stale files / dirs.
    for existing in list(dest.rglob("*")):
        if existing.is_file() and existing.resolve() not in seen:
            existing.unlink()
    # Prune empty dirs left after file sweep — `rmdir` raises if a dir
    # is non-empty, which we accept silently.
    for d in sorted(
        (p for p in dest.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        with contextlib.suppress(OSError):
            d.rmdir()


def _mirror_path(source: Path, dest: Path, exclude_dirs: Iterable[str]) -> None:
    """Copy a filesystem ``source`` tree into ``dest`` with ``--delete`` semantics."""
    dest.mkdir(parents=True, exist_ok=True)
    excluded = frozenset(exclude_dirs)
    seen: set[Path] = set()
    for src in source.rglob("*"):
        if src.is_dir():
            if src.name in excluded:
                # Skip the entire subtree.
                continue
            continue
        # Skip files inside an excluded directory.
        rel = src.relative_to(source)
        if any(part in excluded for part in rel.parts):
            continue
        if src.name in {".DS_Store"} or src.name.endswith(".pyc"):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        seen.add(target.resolve())

    for existing in list(dest.rglob("*")):
        if existing.is_file() and existing.resolve() not in seen:
            existing.unlink()
    for d in sorted(
        (p for p in dest.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        with contextlib.suppress(OSError):
            d.rmdir()


# ---------------------------------------------------------------------------
# Public copy helpers
# ---------------------------------------------------------------------------


def _runtime_target(home: Path, runtime: Literal["codex", "claude"], kind: str) -> Path:
    """Return the runtime-specific install target under ``home``."""
    return home / f".{runtime}" / kind / "content-stack"


def copy_skills(
    runtime: Literal["codex", "claude"],
    home: Path | None = None,
) -> tuple[Path, int]:
    """Mirror skills into the runtime-specific path.

    Returns ``(target_dir, skill_count)`` so callers can echo the same
    summary as the bash scripts.
    """
    home_dir = home if home is not None else Path.home()
    target = _runtime_target(home_dir, runtime, "skills")
    source = _resolve_source("skills")
    if isinstance(source, Path):
        _mirror_path(source, target, exclude_dirs=())
    else:
        _mirror_traversable(source, target, exclude_dirs=())
    count = sum(1 for _ in target.rglob("SKILL.md"))
    return target, count


def copy_procedures(
    runtime: Literal["codex", "claude"],
    home: Path | None = None,
) -> tuple[Path, int]:
    """Mirror procedures into the runtime-specific path (excluding ``_template``)."""
    home_dir = home if home is not None else Path.home()
    target = _runtime_target(home_dir, runtime, "procedures")
    source = _resolve_source("procedures")
    if isinstance(source, Path):
        _mirror_path(source, target, exclude_dirs=("_template",))
    else:
        _mirror_traversable(source, target, exclude_dirs=("_template",))
    count = sum(1 for _ in target.rglob("PROCEDURE.md"))
    return target, count


def copy_plugins(home: Path | None = None) -> tuple[Path, int]:
    """Mirror and hydrate plugin packages into the home-local plugin directory."""
    home_dir = home if home is not None else Path.home()
    target = home_dir / "plugins" / "content-stack"
    source_root = _resolve_source("plugins")
    if isinstance(source_root, Path):
        _mirror_path(source_root / "content-stack", target, exclude_dirs=())
    else:
        _mirror_traversable(source_root.joinpath("content-stack"), target, exclude_dirs=())

    skills_source = _resolve_source("skills")
    skills_target = target / "skills" / "catalog"
    if isinstance(skills_source, Path):
        _mirror_path(skills_source, skills_target, exclude_dirs=())
    else:
        _mirror_traversable(skills_source, skills_target, exclude_dirs=())

    procedures_source = _resolve_source("procedures")
    procedures_target = target / "procedures"
    if isinstance(procedures_source, Path):
        _mirror_path(procedures_source, procedures_target, exclude_dirs=("_template",))
    else:
        _mirror_traversable(procedures_source, procedures_target, exclude_dirs=("_template",))

    count = sum(1 for p in target.rglob("plugin.json") if p.parent.name == ".codex-plugin")
    return target, count


def register_plugin_marketplace(
    *,
    home: Path | None = None,
    remove: bool = False,
) -> str:
    """Upsert the home-local plugin marketplace entry for content-stack."""
    home_dir = home if home is not None else Path.home()
    target = home_dir / ".agents" / "plugins" / "marketplace.json"
    target.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, object] = {
        "name": "local-content-stack",
        "interface": {"displayName": "Local content-stack Plugins"},
        "plugins": [],
    }
    if target.exists():
        text = target.read_text(encoding="utf-8").strip()
        if text:
            loaded = json.loads(text)
            if not isinstance(loaded, dict):
                raise ValueError(f"existing {target} is not a JSON object")
            existing = loaded

    plugins = existing.setdefault("plugins", [])
    if not isinstance(plugins, list):
        raise ValueError(f"`plugins` in {target} must be a list")

    plugins[:] = [
        p for p in plugins if not (isinstance(p, dict) and p.get("name") == "content-stack")
    ]
    if remove:
        msg = f"Unregistered plugin 'content-stack' from {target}"
    else:
        plugins.append(
            {
                "name": "content-stack",
                "source": {"source": "local", "path": "./plugins/content-stack"},
                "policy": {
                    "installation": "INSTALLED_BY_DEFAULT",
                    "authentication": "ON_USE",
                },
                "category": "Productivity",
            }
        )
        msg = f"Registered plugin 'content-stack' in {target}"

    fd, tmp = tempfile.mkstemp(prefix=".marketplace.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, target)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return msg


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------


def _read_token(home: Path) -> str:
    """Read the auth token from the canonical state path under ``home``."""
    token_path = home / ".local" / "state" / "content-stack" / "auth.token"
    if not token_path.is_file():
        raise FileNotFoundError(
            f"auth token missing at {token_path} — run `content-stack init` "
            "or `make install` first."
        )
    return token_path.read_text(encoding="utf-8").strip()


def register_mcp_codex(
    *,
    home: Path | None = None,
    port: int = 5180,
    remove: bool = False,
    force: bool = False,
) -> str:
    """Register (or remove) the content-stack MCP server in Codex CLI.

    Returns a human-readable status line; raises if ``codex`` is not on
    PATH AND we are asked to register (a missing CLI is a no-op rather
    than an error so ``make install`` succeeds on Claude-only machines).
    """
    home_dir = home if home is not None else Path.home()
    codex_bin = shutil.which("codex")
    if codex_bin is None:
        return "Codex CLI not on PATH — skipping MCP registration."

    def _list_has() -> bool:
        try:
            out = subprocess.run(
                [codex_bin, "mcp", "list"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
        except OSError:
            return False
        return any(line.strip().startswith("content-stack ") for line in out.splitlines())

    if remove:
        if _list_has():
            subprocess.run([codex_bin, "mcp", "remove", "content-stack"], check=False)
            return "Unregistered MCP 'content-stack' from Codex CLI"
        return "MCP 'content-stack' not registered with Codex CLI; nothing to remove"

    if _list_has() and not force:
        return "MCP 'content-stack' already registered with Codex CLI"

    # Sanity-check that the auth token exists; the bash script does the
    # same check before invoking codex.
    _read_token(home_dir)
    token_env_var = os.environ.get("CONTENT_STACK_TOKEN_ENV_VAR", "CONTENT_STACK_TOKEN")

    if _list_has() and force:
        subprocess.run([codex_bin, "mcp", "remove", "content-stack"], check=False)

    subprocess.run(
        [
            codex_bin,
            "mcp",
            "add",
            "content-stack",
            "--url",
            f"http://127.0.0.1:{port}/mcp",
            "--bearer-token-env-var",
            token_env_var,
        ],
        check=True,
    )
    return (
        f"Registered MCP 'content-stack' with Codex CLI (port {port}); "
        f"export {token_env_var} in your shell rc."
    )


def register_mcp_claude(
    *,
    home: Path | None = None,
    port: int = 5180,
    target: Path | None = None,
    remove: bool = False,
) -> str:
    """Atomic JSON merge for Claude Code's ``mcp.json``.

    Mirrors the bash script line-for-line so clone-mode and pipx-mode
    behave identically. Existing files are backed up to ``.bak``; the
    write itself is via a temp file in the same directory + ``os.replace``
    for atomicity (audit B-24).
    """
    home_dir = home if home is not None else Path.home()
    if target is None:
        env_target = os.environ.get("CONTENT_STACK_MCP_TARGET")
        target = Path(env_target) if env_target else home_dir / ".claude" / "mcp.json"

    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))

    existing: dict[str, object] = {}
    if target.exists():
        text = target.read_text(encoding="utf-8").strip()
        if text:
            try:
                loaded = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"existing {target} is not valid JSON: {exc}") from exc
            if not isinstance(loaded, dict):
                raise ValueError(f"existing {target} is not a JSON object")
            existing = loaded

    servers = existing.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError(f"`mcpServers` in {target} must be an object")

    if remove:
        if "content-stack" in servers:
            del servers["content-stack"]
            msg = f"Unregistered MCP 'content-stack' from {target}"
        else:
            msg = f"MCP 'content-stack' not present in {target}; nothing to remove"
    else:
        token = _read_token(home_dir)
        servers["content-stack"] = {
            "transport": "http",
            "url": f"http://127.0.0.1:{port}/mcp",
            "headers": {"Authorization": f"Bearer {token}"},
        }
        msg = f"Registered MCP 'content-stack' with Claude Code -> {target}"

    fd, tmp = tempfile.mkstemp(prefix=".mcp.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, target)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

    return msg


__all__ = [
    "InstallMode",
    "copy_plugins",
    "copy_procedures",
    "copy_skills",
    "detect_mode",
    "register_mcp_claude",
    "register_mcp_codex",
    "register_plugin_marketplace",
]
