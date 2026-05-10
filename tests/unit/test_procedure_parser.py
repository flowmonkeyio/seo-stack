"""Unit tests for ``content_stack.procedures.parser``.

Three contracts under test:

1. The pydantic schema rejects malformed frontmatter (missing required
   keys, bad on_failure values, dangling loop_back_to, etc.).
2. Round-trip: a fixture written via ``ProcedureSpec.model_dump`` +
   ``yaml.safe_dump`` parses back to an equal value.
3. Variant application replaces the in-memory step list correctly
   without mutating the source spec.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from content_stack.procedures.parser import (
    ProcedureParseError,
    ProcedureSchedule,
    ProcedureSpec,
    ProcedureStep,
    ProcedureVariant,
    load_all_procedures,
    load_procedure,
    parse_procedure,
)

# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _frontmatter(yaml_block: str, body: str = "") -> str:
    return f"---\n{yaml_block}\n---\n{body}"


def _baseline_spec_yaml() -> str:
    return """name: test-proc
slug: 99-test-proc
version: 0.1.0
description: A minimal valid procedure for the parser tests.
triggers:
  - "Manual"
prerequisites:
  - "project exists"
produces:
  - runs
inputs:
  topic_id: int
steps:
  - id: first
    skill: 01-research/keyword-discovery
    on_failure: abort
  - id: second
    skill: 02-content/editor
    on_failure: retry
    max_retries: 2
  - id: gate
    skill: 02-content/eeat-gate
    on_failure: loop_back
    loop_back_to: first
variants:
  - name: fast
    description: shorter run
    steps_omit:
      - second
  - name: heavy
    args_overrides:
      first:
        depth_tier: heavy
concurrency_limit: 2
resumable: true
"""


# ---------------------------------------------------------------------------
# Frontmatter splitting + IO.
# ---------------------------------------------------------------------------


def test_parse_minimal_procedure() -> None:
    """A baseline frontmatter parses cleanly + every field carries through."""
    spec = parse_procedure(_frontmatter(_baseline_spec_yaml(), "# Body\nNarrative."))
    assert spec.name == "test-proc"
    assert spec.slug == "99-test-proc"
    assert spec.version == "0.1.0"
    assert len(spec.steps) == 3
    assert spec.steps[0].id == "first"
    assert spec.steps[2].on_failure == "loop_back"
    assert spec.steps[2].loop_back_to == "first"
    assert len(spec.variants) == 2
    assert spec.variants[0].steps_omit == ["second"]
    assert spec.variants[1].args_overrides == {"first": {"depth_tier": "heavy"}}
    assert spec.concurrency_limit == 2
    assert spec.resumable is True


def test_round_trip_via_model_dump() -> None:
    """Serialising + re-parsing produces an equal spec."""
    spec = parse_procedure(_frontmatter(_baseline_spec_yaml()))
    redumped = yaml.safe_dump(spec.model_dump(), sort_keys=False)
    reparsed = parse_procedure(_frontmatter(redumped))
    assert reparsed.model_dump() == spec.model_dump()


def test_missing_frontmatter_delimiter_raises() -> None:
    """A file without leading ``---`` raises ``ProcedureParseError``."""
    with pytest.raises(ProcedureParseError):
        parse_procedure("name: oops\nversion: 0.1.0\n")


def test_missing_closing_delimiter_raises() -> None:
    """A file with leading ``---`` but no closing one raises."""
    with pytest.raises(ProcedureParseError):
        parse_procedure("---\nname: oops\nslug: x\nversion: 0.1.0\n")


def test_invalid_yaml_raises_with_context() -> None:
    """Malformed YAML surfaces ``ProcedureParseError`` (not a bare YAMLError)."""
    bad_yaml = "name: oops\nslug: x\nversion: 0.1.0\nsteps:\n  - id: a\n  -"
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(bad_yaml))


def test_non_mapping_yaml_raises() -> None:
    """A YAML list (not a mapping) raises."""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter("- foo\n- bar"))


# ---------------------------------------------------------------------------
# Schema validation — rejection cases.
# ---------------------------------------------------------------------------


def test_loop_back_without_target_raises() -> None:
    """``on_failure='loop_back'`` requires ``loop_back_to``."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
steps:
  - id: a
    skill: x
  - id: b
    skill: y
    on_failure: loop_back
"""
    with pytest.raises(ProcedureParseError) as exc:
        parse_procedure(_frontmatter(yaml_block))
    assert "loop_back_to" in str(exc.value)


def test_loop_back_to_must_reference_prior_step() -> None:
    """A loop_back_to that points forward / unknown raises."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
steps:
  - id: a
    skill: x
    on_failure: loop_back
    loop_back_to: nope
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


def test_loop_back_to_must_be_strictly_prior() -> None:
    """Forward loops are rejected; the runner only walks forward."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
steps:
  - id: first
    skill: x
    on_failure: loop_back
    loop_back_to: second
  - id: second
    skill: y
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


def test_retry_requires_max_retries() -> None:
    """``on_failure='retry'`` with max_retries=0 is rejected."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
steps:
  - id: a
    skill: x
    on_failure: retry
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


def test_invalid_on_failure_mode_raises() -> None:
    """Anything outside the five-mode literal is rejected."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
steps:
  - id: a
    skill: x
    on_failure: silent-success
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


def test_duplicate_step_ids_rejected() -> None:
    """Two steps with the same id raises."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
steps:
  - id: dup
    skill: x
  - id: dup
    skill: y
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


def test_empty_steps_rejected() -> None:
    """A procedure must declare at least one step."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
steps: []
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


def test_invalid_step_id_format_rejected() -> None:
    """Step ids must be alpha+dash, lowercase, starting with a letter."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
steps:
  - id: "1-not-a-letter"
    skill: x
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


def test_invalid_slug_format_rejected() -> None:
    """Slug must be alpha+digit+dash, lowercase."""
    yaml_block = """name: x
slug: "Bad Slug"
version: 0.1.0
description: y
steps:
  - id: a
    skill: x
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


def test_concurrency_limit_must_be_positive() -> None:
    """concurrency_limit < 1 is rejected."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
steps:
  - id: a
    skill: x
concurrency_limit: 0
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


def test_variant_with_unknown_step_id_rejected() -> None:
    """A variant whose overrides reference a missing step raises."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
steps:
  - id: a
    skill: x
variants:
  - name: bad
    args_overrides:
      ghost-step:
        x: y
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


def test_duplicate_variant_names_rejected() -> None:
    """Two variants with the same name raises."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
steps:
  - id: a
    skill: x
variants:
  - name: dup
  - name: dup
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


def test_unknown_field_is_rejected() -> None:
    """Pydantic ``extra='forbid'`` rejects unknown frontmatter keys."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
unexpected_field: huh
steps:
  - id: a
    skill: x
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


# ---------------------------------------------------------------------------
# All five on_failure modes round-trip.
# ---------------------------------------------------------------------------


def test_all_five_on_failure_modes_round_trip() -> None:
    """Every ``OnFailure`` literal value parses + serialises cleanly."""
    yaml_block = """name: all-modes
slug: all-modes
version: 0.1.0
description: Exercises every on_failure mode.
steps:
  - id: ab
    skill: x
    on_failure: abort
  - id: re
    skill: x
    on_failure: retry
    max_retries: 1
  - id: sk
    skill: x
    on_failure: skip
  - id: hr
    skill: x
    on_failure: human_review
  - id: lb
    skill: x
    on_failure: loop_back
    loop_back_to: ab
"""
    spec = parse_procedure(_frontmatter(yaml_block))
    modes = [s.on_failure for s in spec.steps]
    assert modes == ["abort", "retry", "skip", "human_review", "loop_back"]
    # Round trip.
    redumped = yaml.safe_dump(spec.model_dump(), sort_keys=False)
    reparsed = parse_procedure(_frontmatter(redumped))
    assert [s.on_failure for s in reparsed.steps] == modes


# ---------------------------------------------------------------------------
# Variant application.
# ---------------------------------------------------------------------------


def test_apply_variant_omits_steps() -> None:
    """``apply_variant('fast')`` returns a copy with the omitted step removed."""
    spec = parse_procedure(_frontmatter(_baseline_spec_yaml()))
    fast = spec.apply_variant("fast")
    assert [s.id for s in fast.steps] == ["first", "gate"]
    # Source spec is untouched.
    assert [s.id for s in spec.steps] == ["first", "second", "gate"]


def test_apply_variant_overrides_args() -> None:
    """``apply_variant('heavy')`` merges the variant's overrides into step.args."""
    spec = parse_procedure(_frontmatter(_baseline_spec_yaml()))
    heavy = spec.apply_variant("heavy")
    first_step = next(s for s in heavy.steps if s.id == "first")
    assert first_step.args == {"depth_tier": "heavy"}


def test_apply_unknown_variant_raises() -> None:
    """Unknown variant name surfaces a clear ValueError."""
    spec = parse_procedure(_frontmatter(_baseline_spec_yaml()))
    with pytest.raises(ValueError):
        spec.apply_variant("ghost-variant")


# ---------------------------------------------------------------------------
# load_procedure + load_all_procedures.
# ---------------------------------------------------------------------------


def test_load_procedure_round_trip(tmp_path: Path) -> None:
    """``load_procedure`` reads a directory + matches slug to dir name."""
    proc_dir = tmp_path / "99-test-proc"
    proc_dir.mkdir()
    (proc_dir / "PROCEDURE.md").write_text(_frontmatter(_baseline_spec_yaml()), encoding="utf-8")
    spec = load_procedure(proc_dir)
    assert spec.slug == "99-test-proc"


def test_load_procedure_slug_mismatch_raises(tmp_path: Path) -> None:
    """Slug must match the parent directory name."""
    proc_dir = tmp_path / "wrong-name"
    proc_dir.mkdir()
    (proc_dir / "PROCEDURE.md").write_text(_frontmatter(_baseline_spec_yaml()), encoding="utf-8")
    with pytest.raises(ProcedureParseError) as exc:
        load_procedure(proc_dir)
    assert "wrong-name" in str(exc.value)


def test_load_all_procedures_skips_template_and_dotdirs(tmp_path: Path) -> None:
    """``load_all_procedures`` ignores ``_template/`` and dotfiles."""
    real = tmp_path / "99-test-proc"
    real.mkdir()
    (real / "PROCEDURE.md").write_text(_frontmatter(_baseline_spec_yaml()), encoding="utf-8")
    template = tmp_path / "_template"
    template.mkdir()
    # Note the slug doesn't match — the loader skips the dir before parsing.
    template_yaml = (
        "name: t\nslug: x\nversion: 0.1.0\ndescription: y\nsteps:\n  - id: a\n    skill: x\n"
    )
    (template / "PROCEDURE.md").write_text(
        _frontmatter(template_yaml),
        encoding="utf-8",
    )
    dotdir = tmp_path / ".hidden"
    dotdir.mkdir()
    (dotdir / "PROCEDURE.md").write_text("---\n---\n", encoding="utf-8")

    out = load_all_procedures(tmp_path)
    assert sorted(out.keys()) == ["99-test-proc"]


def test_load_all_procedures_missing_dir_returns_empty(tmp_path: Path) -> None:
    """A missing procedures dir is not an error — just an empty registry."""
    out = load_all_procedures(tmp_path / "does-not-exist")
    assert out == {}


# ---------------------------------------------------------------------------
# Procedure 04 specifically — the M7.A workhorse.
# ---------------------------------------------------------------------------


def test_procedure_04_parses_with_thirteen_steps() -> None:
    """Procedure 04 — the M7.A proof-of-concept — has the expected shape."""
    repo_root = Path(__file__).resolve().parents[2]
    spec = load_procedure(repo_root / "procedures" / "04-topic-to-published")
    assert len(spec.steps) == 13
    expected_ids = [
        "brief",
        "outline",
        "draft-intro",
        "draft-body",
        "draft-conclusion",
        "editor",
        "humanizer",
        "eeat-gate",
        "image-generator",
        "alt-text-auditor",
        "schema-emitter",
        "interlinker",
        "publish",
    ]
    assert [s.id for s in spec.steps] == expected_ids
    assert spec.concurrency_limit == 4
    assert spec.resumable is True
    # The eeat-gate step is the only loop_back step in the chain.
    eeat = next(s for s in spec.steps if s.id == "eeat-gate")
    assert eeat.on_failure == "loop_back"
    assert eeat.loop_back_to == "editor"
    # Two variants documented.
    assert sorted(v.name for v in spec.variants) == ["pillar", "short-form"]


def test_procedure_04_short_form_variant() -> None:
    """``short-form`` variant drops image-generator + alt-text-auditor."""
    repo_root = Path(__file__).resolve().parents[2]
    spec = load_procedure(repo_root / "procedures" / "04-topic-to-published")
    short = spec.apply_variant("short-form")
    short_ids = {s.id for s in short.steps}
    assert "image-generator" not in short_ids
    assert "alt-text-auditor" not in short_ids
    # Other steps remain.
    assert "publish" in short_ids


def test_procedure_04_pillar_variant() -> None:
    """``pillar`` variant pushes brief.depth_tier=heavy + bigger word target."""
    repo_root = Path(__file__).resolve().parents[2]
    spec = load_procedure(repo_root / "procedures" / "04-topic-to-published")
    pillar = spec.apply_variant("pillar")
    brief_step = next(s for s in pillar.steps if s.id == "brief")
    assert brief_step.args.get("depth_tier") == "heavy"
    assert brief_step.args.get("target_word_count") == 4000


def test_procedure_step_default_max_retries_zero() -> None:
    """``ProcedureStep`` defaults to max_retries=0 when not declared."""
    step = ProcedureStep(id="x", skill="y", on_failure="abort")
    assert step.max_retries == 0


def test_procedure_variant_defaults_empty() -> None:
    """``ProcedureVariant`` defaults are empty container values."""
    v = ProcedureVariant(name="x")
    assert v.args_overrides == {}
    assert v.steps_omit == []


def test_procedure_spec_default_concurrency_limit() -> None:
    """Top-level ``ProcedureSpec`` default concurrency_limit is 1."""
    spec = ProcedureSpec(
        name="x",
        slug="x",
        version="0.1.0",
        description="y",
        steps=[ProcedureStep(id="a", skill="x")],
    )
    assert spec.concurrency_limit == 1
    assert spec.resumable is True


# ---------------------------------------------------------------------------
# ProcedureSchedule (M7.B parser extension for procedures 6 + 7).
# ---------------------------------------------------------------------------


def test_schedule_default_is_none() -> None:
    """``ProcedureSpec.schedule`` defaults to ``None`` for non-cron procedures."""
    spec = ProcedureSpec(
        name="x",
        slug="x",
        version="0.1.0",
        description="y",
        steps=[ProcedureStep(id="a", skill="x")],
    )
    assert spec.schedule is None


def test_schedule_block_round_trips() -> None:
    """A schedule block parses + serialises through ``model_dump`` cleanly."""
    yaml_block = """name: weekly-job
slug: weekly-job
version: 0.1.0
description: A weekly cron-triggered procedure.
steps:
  - id: a
    skill: x
schedule:
  cron: "0 6 * * MON"
  timezone_field: projects.schedule_json.timezone
"""
    spec = parse_procedure(_frontmatter(yaml_block))
    assert spec.schedule is not None
    assert spec.schedule.cron == "0 6 * * MON"
    assert spec.schedule.timezone_field == "projects.schedule_json.timezone"
    # Round-trip.
    redumped = yaml.safe_dump(spec.model_dump(), sort_keys=False)
    reparsed = parse_procedure(_frontmatter(redumped))
    assert reparsed.schedule is not None
    assert reparsed.schedule.cron == spec.schedule.cron


def test_schedule_default_timezone_field() -> None:
    """``timezone_field`` defaults to the project's schedule_json.timezone path."""
    sched = ProcedureSchedule(cron="0 4 1 * *")
    assert sched.timezone_field == "projects.schedule_json.timezone"


def test_schedule_invalid_cron_token_count_rejected() -> None:
    """A cron expression with fewer than 5 fields is rejected at parse time."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
steps:
  - id: a
    skill: x
schedule:
  cron: "0 6 *"
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


def test_schedule_empty_timezone_field_rejected() -> None:
    """The timezone field path must be a non-empty dotted string."""
    with pytest.raises(ValueError):
        ProcedureSchedule(cron="0 4 1 * *", timezone_field="")


def test_schedule_extra_fields_rejected() -> None:
    """``ProcedureSchedule`` is closed (``extra='forbid'``)."""
    yaml_block = """name: x
slug: x
version: 0.1.0
description: y
steps:
  - id: a
    skill: x
schedule:
  cron: "0 6 * * MON"
  timezone_field: projects.schedule_json.timezone
  unknown_field: huh
"""
    with pytest.raises(ProcedureParseError):
        parse_procedure(_frontmatter(yaml_block))


# ---------------------------------------------------------------------------
# Procedures 6 + 7 specifically — schedule blocks present.
# ---------------------------------------------------------------------------


def test_procedure_06_carries_schedule_block() -> None:
    """Procedure 06 weekly-gsc-review carries a Mondays-06:00 cron."""
    repo_root = Path(__file__).resolve().parents[2]
    spec = load_procedure(repo_root / "procedures" / "06-weekly-gsc-review")
    assert spec.schedule is not None
    assert spec.schedule.cron == "0 6 * * MON"
    assert spec.schedule.timezone_field == "projects.schedule_json.timezone"


def test_procedure_07_carries_schedule_block() -> None:
    """Procedure 07 monthly-humanize-pass carries a 1st-of-month-04:00 cron."""
    repo_root = Path(__file__).resolve().parents[2]
    spec = load_procedure(repo_root / "procedures" / "07-monthly-humanize-pass")
    assert spec.schedule is not None
    assert spec.schedule.cron == "0 4 1 * *"
    assert spec.schedule.timezone_field == "projects.schedule_json.timezone"
