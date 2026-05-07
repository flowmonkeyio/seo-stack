"""Fingerprint-check protecting D1/D2 clean-room posture.

Walks every ``skills/**/SKILL.md`` and rejects any verbatim substring
match against ``tests/fixtures/upstream-fingerprints.json``. The
fingerprints are distinctive multi-word phrases lifted from the
``codex-seo`` and ``cody-article-writer`` upstream skill bundles —
the two repos under restrictive licenses that locked decisions D1 and
D2 require us to clean-room re-author from. A match means a skill
author paraphrased verbatim from upstream; that's a license violation
plus a quality red flag.

The test runs as part of ``make test``. Adding a new skill that
accidentally echoes upstream prose fails the build until the prose is
re-authored.

Severities:

- ``block`` — match fails the test.
- ``warn`` — match is reported via ``warnings`` but does not fail.
  Useful for phrases that are common enough to potentially appear by
  chance (e.g. "Cannibalization check") but are still upstream voice.

The fixture file documents per-phrase rationale so future maintainers
understand why each phrase is on the list.
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "skills"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "upstream-fingerprints.json"


def _load_fingerprints() -> list[dict[str, str]]:
    """Load the fingerprint catalog from the fixture JSON file."""
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    entries = raw.get("fingerprints", [])
    assert isinstance(entries, list), "fingerprints fixture must be a list"
    return entries


def _iter_skill_files() -> Iterator[Path]:
    """Yield every ``SKILL.md`` under ``skills/``.

    The ``skills/`` tree may not exist yet on a brand-new clone if the
    skill milestone hasn't landed; that's fine — the test just yields
    nothing and the assert short-circuits.
    """
    if not SKILLS_ROOT.exists():
        return
    yield from SKILLS_ROOT.rglob("SKILL.md")


def test_fingerprints_fixture_is_well_formed() -> None:
    """Fixture loads, is non-empty, and every entry has the expected shape."""
    entries = _load_fingerprints()
    assert entries, "fingerprints fixture is empty — see CLAUDE.md D1/D2"
    for entry in entries:
        assert isinstance(entry.get("phrase"), str) and entry["phrase"], entry
        assert entry.get("upstream") in {"codex-seo", "cody-article-writer"}, entry
        assert entry.get("severity") in {"block", "warn"}, entry


def test_skills_tree_has_no_upstream_substring_matches() -> None:
    """No skill body contains a 'block' fingerprint as a verbatim substring.

    Searches are case-insensitive; whitespace is preserved verbatim. If
    a match is found the failure message names every offending
    ``(skill, phrase, upstream)`` triple so the author can fix the prose
    and rerun.
    """
    entries = _load_fingerprints()
    skill_files = list(_iter_skill_files())
    if not skill_files:
        # No skills authored yet — nothing to check. The fingerprint
        # fixture self-test above still runs to lock in the format.
        pytest.skip("skills/ tree empty — test runs vacuously")

    blocking_failures: list[str] = []
    warn_observations: list[str] = []

    for skill_path in skill_files:
        text = skill_path.read_text(encoding="utf-8")
        text_lower = text.lower()
        rel = skill_path.relative_to(REPO_ROOT)
        for entry in entries:
            phrase = entry["phrase"]
            if phrase.lower() not in text_lower:
                continue
            label = f"{rel}: matched upstream={entry['upstream']!r} phrase={phrase!r}"
            if entry["severity"] == "block":
                blocking_failures.append(label)
            else:
                warn_observations.append(label)

    for w in warn_observations:
        warnings.warn(f"upstream-fingerprint warn-severity match: {w}", stacklevel=2)

    if blocking_failures:
        joined = "\n  - ".join(blocking_failures)
        pytest.fail(
            "upstream-fingerprint check failed — D1/D2 clean-room posture "
            "violated. Re-author the offending prose in your own voice and "
            "rerun. Matches:\n  - " + joined
        )


def test_every_skill_has_yaml_frontmatter() -> None:
    """Smoke-check that each ``SKILL.md`` opens with a parseable frontmatter."""
    skill_files = list(_iter_skill_files())
    if not skill_files:
        pytest.skip("skills/ tree empty — test runs vacuously")

    failures: list[str] = []
    for skill_path in skill_files:
        rel = skill_path.relative_to(REPO_ROOT)
        text = skill_path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            failures.append(f"{rel}: missing leading '---' frontmatter delimiter")
            continue
        # Find the closing fence.
        rest = text[4:]
        if "\n---\n" not in rest:
            failures.append(f"{rest[:40]!r} {rel}: missing closing '---' delimiter")
            continue
        body = rest.split("\n---\n", 1)[1]
        if not body.strip():
            failures.append(f"{rel}: empty body after frontmatter")

    if failures:
        joined = "\n  - ".join(failures)
        pytest.fail("skill frontmatter smoke check failed:\n  - " + joined)
