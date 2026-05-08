"""Catalogue-level checks for the M7.B procedure manifest.

After M7.B all 8 PROCEDURE.md files are present, validate against the
``ProcedureSpec`` model, and reference real skills (or the documented
``_programmatic/`` placeholder prefix) for every step. Tests below
parametrise over the eight slugs so a missing or malformed file
surfaces as a single failed assertion per offender rather than a
cryptic registry error at runner construction.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from content_stack.procedures.parser import (
    ProcedureSpec,
    load_all_procedures,
    load_procedure,
)

# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    """Return the repo root (``content-stack/``) for filesystem lookups."""
    return Path(__file__).resolve().parents[3]


def _procedures_dir() -> Path:
    return _repo_root() / "procedures"


def _skills_dir() -> Path:
    return _repo_root() / "skills"


# Per the M7.B deliverable: every step.skill must either resolve to a
# real skill directory under ``skills/<key>`` or use the documented
# ``_programmatic/`` synthetic prefix. The synthetic prefix names
# steps the runner dispatches to a no-op stub today; M8 wires them
# to dedicated repository calls (no LLM session needed).
_PROGRAMMATIC_PREFIX = "_programmatic/"


# All 8 slugs the deliverable requires after M7.B.
EXPECTED_SLUGS: list[str] = [
    "01-bootstrap-project",
    "02-one-site-shortcut",
    "03-keyword-to-topic-queue",
    "04-topic-to-published",
    "05-bulk-content-launch",
    "06-weekly-gsc-review",
    "07-monthly-humanize-pass",
    "08-add-new-site",
]


# Procedures whose deliverable mandates a cron schedule block.
SCHEDULED_SLUGS: list[str] = [
    "06-weekly-gsc-review",
    "07-monthly-humanize-pass",
]


# ---------------------------------------------------------------------------
# Catalogue-level invariants.
# ---------------------------------------------------------------------------


def test_all_8_procedures_load_via_registry() -> None:
    """``load_all_procedures`` returns exactly the 8 expected slugs."""
    registry = load_all_procedures(_procedures_dir())
    assert sorted(registry.keys()) == EXPECTED_SLUGS, sorted(registry.keys())


@pytest.mark.parametrize("slug", EXPECTED_SLUGS)
def test_each_procedure_validates_against_parser(slug: str) -> None:
    """Each PROCEDURE.md file parses cleanly and yields a valid ProcedureSpec."""
    spec = load_procedure(_procedures_dir() / slug)
    assert isinstance(spec, ProcedureSpec)
    assert spec.slug == slug
    assert spec.steps, f"procedure {slug!r} declares no steps"


@pytest.mark.parametrize("slug", EXPECTED_SLUGS)
def test_each_procedure_steps_reference_real_skills_or_programmatic(slug: str) -> None:
    """Every step.skill resolves to a skills/ directory OR uses _programmatic/.

    Per the M7.B deliverable: steps backed by a real LLM-driven skill
    must reference a directory under ``skills/<key>``. Programmatic
    steps (project-create, gsc-pull, etc.) — those that don't need an
    LLM session — declare ``skill: _programmatic/<name>`` so the
    runner can route them to a no-op default in M7.B and to dedicated
    repository calls in M8.
    """
    spec = load_procedure(_procedures_dir() / slug)
    skills_dir = _skills_dir()
    for step in spec.steps:
        if step.skill.startswith(_PROGRAMMATIC_PREFIX):
            continue  # Synthetic step, deferred to M8 — see procedure body.
        path = skills_dir / step.skill
        assert path.is_dir(), (
            f"procedure {slug!r} step {step.id!r} references skill {step.skill!r} "
            f"but {path} is not a directory under skills/"
        )


@pytest.mark.parametrize("slug", EXPECTED_SLUGS)
def test_each_procedure_concurrency_limit_set(slug: str) -> None:
    """Every procedure declares a positive integer ``concurrency_limit``."""
    spec = load_procedure(_procedures_dir() / slug)
    assert isinstance(spec.concurrency_limit, int)
    assert spec.concurrency_limit >= 1, (
        f"procedure {slug!r} has concurrency_limit={spec.concurrency_limit}"
    )


@pytest.mark.parametrize("slug", EXPECTED_SLUGS)
def test_each_procedure_resumable_set(slug: str) -> None:
    """Every procedure declares ``resumable`` (the M7.A + M7.B contract requires it)."""
    spec = load_procedure(_procedures_dir() / slug)
    assert isinstance(spec.resumable, bool)


@pytest.mark.parametrize("slug", SCHEDULED_SLUGS)
def test_procedure_06_07_have_schedule_block(slug: str) -> None:
    """Procedures 6 + 7 carry a cron schedule block that M8 will read."""
    spec = load_procedure(_procedures_dir() / slug)
    assert spec.schedule is not None, f"procedure {slug!r} should carry a schedule block"
    assert spec.schedule.cron, f"procedure {slug!r} schedule.cron is empty"
    assert spec.schedule.timezone_field, f"procedure {slug!r} schedule.timezone_field is empty"


# ---------------------------------------------------------------------------
# Per-procedure step shape — quick assertions that catch typos.
# ---------------------------------------------------------------------------


def test_procedure_01_bootstrap_step_ids() -> None:
    """Procedure 01 declares the seven setup steps in the documented order."""
    spec = load_procedure(_procedures_dir() / "01-bootstrap-project")
    assert [s.id for s in spec.steps] == [
        "project-create",
        "voice-profile",
        "compliance-seed",
        "eeat-seed",
        "publish-target",
        "integration-creds",
        "verify",
    ]


def test_procedure_02_one_site_shortcut_pauses() -> None:
    """Procedure 02 includes a ``human-approval`` step with human_review on_failure."""
    spec = load_procedure(_procedures_dir() / "02-one-site-shortcut")
    human_step = next((s for s in spec.steps if s.id == "human-approval"), None)
    assert human_step is not None, "procedure 02 must declare a human-approval step"
    assert human_step.on_failure == "human_review"


def test_procedure_03_keyword_queue_pauses() -> None:
    """Procedure 03 includes a ``human-review-queue`` step with human_review on_failure."""
    spec = load_procedure(_procedures_dir() / "03-keyword-to-topic-queue")
    human_step = next((s for s in spec.steps if s.id == "human-review-queue"), None)
    assert human_step is not None
    assert human_step.on_failure == "human_review"


def test_procedure_05_bulk_estimate_step_first() -> None:
    """Procedure 05 starts with the cost estimate step (audit M-25 pre-emption)."""
    spec = load_procedure(_procedures_dir() / "05-bulk-content-launch")
    assert spec.steps[0].id == "estimate-cost"
    assert spec.steps[0].on_failure == "abort"


def test_procedure_06_weekly_gsc_starts_with_pull() -> None:
    """Procedure 06 starts with ``gsc-pull`` (everything else depends on data)."""
    spec = load_procedure(_procedures_dir() / "06-weekly-gsc-review")
    assert spec.steps[0].id == "gsc-pull"
    assert spec.steps[0].on_failure == "abort"


def test_procedure_07_humanize_uses_content_refresher() -> None:
    """Procedure 07 routes the per-candidate refresh through skill #24."""
    spec = load_procedure(_procedures_dir() / "07-monthly-humanize-pass")
    refresh_step = next((s for s in spec.steps if s.id == "humanize-each"), None)
    assert refresh_step is not None
    assert refresh_step.skill == "05-ongoing/content-refresher"


def test_procedure_08_add_new_site_has_shortcut_variant() -> None:
    """Procedure 08 declares both shortcut + keyword-discovery variants."""
    spec = load_procedure(_procedures_dir() / "08-add-new-site")
    variant_names = sorted(v.name for v in spec.variants)
    assert variant_names == ["keyword-discovery", "shortcut"]
