"""Smoke checks for ``skills/**/SKILL.md`` frontmatter.

Three invariants:

1. Frontmatter parses as valid YAML and carries the seven contract
   keys named in PLAN.md L957-L968: ``name``, ``description``,
   ``version``, ``runtime_compat``, ``derived_from``, ``license``,
   ``allowed_tools``.
2. ``allowed_tools`` matches the corresponding entry in
   ``content_stack.mcp.permissions.SKILL_TOOL_GRANTS`` — the
   frontmatter is human-readable docs; the registry is the canonical
   enforcement (audit B-10), and the two MUST agree.
3. Each ``derived_from`` SHA, when not the literal ``original``,
   matches the corresponding pinned SHA in
   ``docs/attribution.md``.

Skip the tests when ``skills/`` is empty (pre-M6 clones).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from content_stack.mcp.permissions import SKILL_TOOL_GRANTS

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "skills"
ATTRIBUTION_PATH = REPO_ROOT / "docs" / "attribution.md"

REQUIRED_FRONTMATTER_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "description",
        "version",
        "runtime_compat",
        "derived_from",
        "license",
        "allowed_tools",
    }
)


def _iter_skill_files() -> list[Path]:
    if not SKILLS_ROOT.exists():
        return []
    return sorted(SKILLS_ROOT.rglob("SKILL.md"))


def _parse_frontmatter(path: Path) -> dict[str, object]:
    """Extract YAML frontmatter from a ``SKILL.md`` file."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing leading '---' delimiter")
    rest = text[4:]
    if "\n---\n" not in rest:
        raise ValueError(f"{path}: missing closing '---' delimiter")
    fm_text = rest.split("\n---\n", 1)[0]
    parsed = yaml.safe_load(fm_text)
    if not isinstance(parsed, dict):
        raise ValueError(f"{path}: frontmatter is not a mapping")
    return parsed


def _skill_key_from_path(path: Path) -> str:
    """Return the ``<phase>/<skill>`` key used in ``SKILL_TOOL_GRANTS``."""
    rel = path.relative_to(SKILLS_ROOT)
    # SKILL.md sits at the leaf; the skill key is the parent directory
    # path expressed as ``phase/skill``.
    parent = rel.parent
    return parent.as_posix()


def _attribution_pins() -> dict[str, str]:
    """Parse the pinned-SHA table from ``docs/attribution.md``.

    Returns a mapping from upstream short-id (``codex-seo``,
    ``cody-article-writer``, etc.) to the pinned 40-char SHA. The
    table is markdown so we just regex over the rows.
    """
    text = ATTRIBUTION_PATH.read_text(encoding="utf-8")
    pins: dict[str, str] = {}
    pattern = re.compile(r"^\|\s*`([\w-]+)`\s*\|.*?\|\s*`([0-9a-f]{40})`\s*\|", re.MULTILINE)
    for match in pattern.finditer(text):
        pins[match.group(1)] = match.group(2)
    return pins


def test_frontmatter_required_keys_present() -> None:
    files = _iter_skill_files()
    if not files:
        pytest.skip("skills/ tree empty")

    failures: list[str] = []
    for path in files:
        try:
            fm = _parse_frontmatter(path)
        except (ValueError, yaml.YAMLError) as exc:
            failures.append(str(exc))
            continue
        missing = REQUIRED_FRONTMATTER_KEYS - set(fm.keys())
        if missing:
            failures.append(f"{path.relative_to(REPO_ROOT)}: missing keys {sorted(missing)}")

    assert not failures, "\n".join(failures)


def test_runtime_compat_lists_both_runtimes() -> None:
    """Per PLAN.md the same SKILL.md ships to both ~/.codex and ~/.claude."""
    files = _iter_skill_files()
    if not files:
        pytest.skip("skills/ tree empty")

    for path in files:
        fm = _parse_frontmatter(path)
        runtimes = fm.get("runtime_compat", [])
        assert isinstance(runtimes, list), f"{path}: runtime_compat must be a list"
        assert "codex" in runtimes, f"{path}: runtime_compat must include 'codex'"
        assert "claude-code" in runtimes, f"{path}: runtime_compat must include 'claude-code'"


def test_allowed_tools_matches_permissions_matrix() -> None:
    """Frontmatter ``allowed_tools`` must match ``SKILL_TOOL_GRANTS``."""
    files = _iter_skill_files()
    if not files:
        pytest.skip("skills/ tree empty")

    failures: list[str] = []
    for path in files:
        fm = _parse_frontmatter(path)
        skill_key = _skill_key_from_path(path)
        allowed = fm.get("allowed_tools", [])
        assert isinstance(allowed, list), f"{path}: allowed_tools must be a list"
        declared = frozenset(allowed)
        registered = SKILL_TOOL_GRANTS.get(skill_key)
        if registered is None:
            failures.append(f"{skill_key}: no entry in SKILL_TOOL_GRANTS")
            continue
        if declared != registered:
            only_in_frontmatter = declared - registered
            only_in_registry = registered - declared
            failures.append(
                f"{skill_key}: frontmatter ↔ registry mismatch — "
                f"only in frontmatter: {sorted(only_in_frontmatter)}; "
                f"only in registry: {sorted(only_in_registry)}"
            )

    assert not failures, "\n".join(failures)


def test_derived_from_sha_matches_attribution_pins() -> None:
    """Per ``docs/attribution.md`` the SHA in each ``derived_from`` must pin."""
    files = _iter_skill_files()
    if not files:
        pytest.skip("skills/ tree empty")

    pins = _attribution_pins()
    sha_pattern = re.compile(r"@\s*([0-9a-f]{40})")

    failures: list[str] = []
    for path in files:
        fm = _parse_frontmatter(path)
        derived = fm.get("derived_from", "")
        if not isinstance(derived, str):
            failures.append(f"{path}: derived_from must be a string")
            continue
        if derived.startswith("original"):
            continue  # No SHA expected for original skills.
        # Extract a SHA-shaped substring; require it to match the pin.
        match = sha_pattern.search(derived)
        if not match:
            failures.append(f"{path}: derived_from {derived!r} carries no parseable SHA")
            continue
        sha = match.group(1)
        # Each SHA must show up as a value in the pins table.
        if sha not in pins.values():
            failures.append(f"{path}: derived_from SHA {sha} not found in attribution.md pins")

    assert not failures, "\n".join(failures)
