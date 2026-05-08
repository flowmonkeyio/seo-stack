"""``PROCEDURE.md`` frontmatter parser.

Per PLAN.md L880-L944 + audit B-04, every procedure ships as a directory
with a ``PROCEDURE.md`` file: YAML frontmatter (machine-readable) plus
markdown body (operator + LLM-readable narrative).

This module is the canonical truth for the frontmatter shape. The
runner reads ``ProcedureSpec`` instances; tests round-trip every
fixture; the procedure-template + procedure-04 frontmatter are
validated against the same schema. Drift between the frontmatter and
the runner is impossible because the runner consumes the ``ProcedureSpec``
instance directly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Pydantic schema.
# ---------------------------------------------------------------------------


# Failure-handling modes per the deliverable spec. ``loop_back`` requires
# ``loop_back_to`` to name a prior step; ``retry`` requires ``max_retries
# >= 1``. Validators below enforce these.
OnFailure = Literal["abort", "retry", "loop_back", "skip", "human_review"]


_STEP_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,79}$")
_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,79})$")


class ProcedureStep(BaseModel):
    """One declared step in a procedure.

    Round-trippable: the parser reads YAML into this model; the
    runner consumes the model directly. Step ids are alpha+dash so
    they're stable identifiers in ``procedure_run_steps.step_id``
    rows without quoting.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    skill: str
    args: dict[str, Any] = Field(default_factory=dict)
    on_failure: OnFailure = "abort"
    loop_back_to: str | None = None
    max_retries: int = 0
    concurrency_group: str | None = None

    @model_validator(mode="after")
    def _validate_id(self) -> ProcedureStep:
        if not _STEP_ID_RE.match(self.id):
            raise ValueError(
                f"step.id {self.id!r} must be alpha+dash (1..80 chars, lowercase, "
                "starting with a letter, e.g. 'editor' or 'eeat-gate')"
            )
        return self

    @model_validator(mode="after")
    def _validate_loop_back(self) -> ProcedureStep:
        if self.on_failure == "loop_back" and not self.loop_back_to:
            raise ValueError(
                f"step.{self.id!r}: on_failure='loop_back' requires loop_back_to "
                "(name a prior step.id to jump to)"
            )
        if self.loop_back_to is not None and self.on_failure != "loop_back":
            raise ValueError(
                f"step.{self.id!r}: loop_back_to is only valid with on_failure='loop_back'"
            )
        return self

    @model_validator(mode="after")
    def _validate_retry(self) -> ProcedureStep:
        if self.on_failure == "retry" and self.max_retries < 1:
            raise ValueError(f"step.{self.id!r}: on_failure='retry' requires max_retries>=1")
        if self.max_retries < 0:
            raise ValueError(f"step.{self.id!r}: max_retries must be >= 0 (got {self.max_retries})")
        return self


class ProcedureSchedule(BaseModel):
    """Optional cron metadata for scheduled procedures.

    Procedures 6 (``weekly-gsc-review``) and 7 (``monthly-humanize-pass``)
    are cron-triggered in production. M7.B carries the schedule on the
    spec so M8's APScheduler bootstrap can read the cron expression
    plus the project-level timezone field name without re-parsing the
    PROCEDURE.md file. The runner itself ignores this field — it only
    influences M8's scheduler, never an in-flight run.

    Shape:

    - ``cron``: a 5-field cron expression (minute hour day-of-month
      month day-of-week). Validated as five whitespace-separated
      tokens; APScheduler's ``CronTrigger.from_crontab`` does the deep
      validation when M8 wires it up.
    - ``timezone_field``: dotted path into the project row that names
      the IANA timezone for the schedule. Default
      ``projects.schedule_json.timezone`` matches the schema. Operators
      can override per-procedure (e.g. for a procedure that always runs
      in UTC regardless of project timezone).
    """

    model_config = ConfigDict(extra="forbid")

    cron: str
    timezone_field: str = "projects.schedule_json.timezone"

    @model_validator(mode="after")
    def _validate_cron(self) -> ProcedureSchedule:
        # Lightweight check — five whitespace-separated tokens. Deep
        # cron validation lives in APScheduler at M8 wire-up time; we
        # just guard against trivial typos at parse time.
        tokens = self.cron.split()
        if len(tokens) != 5:
            raise ValueError(
                f"schedule.cron {self.cron!r} must have 5 whitespace-separated fields "
                "(minute hour day-of-month month day-of-week)"
            )
        if not self.timezone_field:
            raise ValueError("schedule.timezone_field must be a non-empty dotted path")
        return self


class ProcedureVariant(BaseModel):
    """A named variant of the procedure.

    Per PLAN.md L941: ``{ name: pillar, overrides: { brief.target_word_count: 4000 } }``.
    Two shapes supported:

    - ``args_overrides`` — dict keyed by step id; merges into that step's
      ``args`` at dispatch time.
    - ``steps_omit`` — list of step ids to skip entirely (status='skipped').

    Variants are applied at ``ProcedureRunner.start`` time when the caller
    passes ``variant=<name>``. The runner deep-copies the spec, applies
    the overrides, then dispatches; the original spec stays untouched
    so concurrent runs of different variants don't cross-contaminate.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    args_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    steps_omit: list[str] = Field(default_factory=list)


class ProcedureSpec(BaseModel):
    """Top-level frontmatter shape.

    Round-trippable to/from YAML. ``slug`` must match the directory
    name; the loader enforces this so the on-disk + in-memory views
    stay aligned.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    slug: str
    version: str
    description: str
    triggers: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list)
    inputs: dict[str, str] = Field(default_factory=dict)
    steps: list[ProcedureStep]
    variants: list[ProcedureVariant] = Field(default_factory=list)
    concurrency_limit: int = 1
    resumable: bool = True
    schedule: ProcedureSchedule | None = None
    """Optional cron metadata for M8's APScheduler bootstrap.

    Per the M7.B deliverable (procedures 6 + 7): the schedule block
    declares the cron expression + the timezone field on the project
    row. The runner ignores this field; M8 reads it at job-registration
    time. ``None`` means the procedure is operator-only / parent-driven.
    """

    @model_validator(mode="after")
    def _validate_slug(self) -> ProcedureSpec:
        if not _SLUG_RE.match(self.slug):
            raise ValueError(f"slug {self.slug!r} must be alpha+digit+dash, lowercase, 1..80 chars")
        return self

    @model_validator(mode="after")
    def _validate_steps(self) -> ProcedureSpec:
        if not self.steps:
            raise ValueError("procedure must declare at least one step")
        ids = [s.id for s in self.steps]
        dupes = sorted({sid for sid in ids if ids.count(sid) > 1})
        if dupes:
            raise ValueError(f"duplicate step.id: {dupes}")
        # loop_back_to must reference a real, prior step.
        for idx, step in enumerate(self.steps):
            if step.loop_back_to is None:
                continue
            target_idx = next(
                (i for i, s in enumerate(self.steps) if s.id == step.loop_back_to),
                None,
            )
            if target_idx is None:
                raise ValueError(
                    f"step.{step.id!r}.loop_back_to: target {step.loop_back_to!r} "
                    "is not a declared step"
                )
            if target_idx >= idx:
                raise ValueError(
                    f"step.{step.id!r}.loop_back_to: target {step.loop_back_to!r} must "
                    "be a PRIOR step (forward jumps not allowed; use a separate variant)"
                )
        return self

    @model_validator(mode="after")
    def _validate_variants(self) -> ProcedureSpec:
        # Each variant's overrides + omits must reference real step ids.
        step_ids = {s.id for s in self.steps}
        for variant in self.variants:
            unknown_overrides = set(variant.args_overrides.keys()) - step_ids
            if unknown_overrides:
                raise ValueError(
                    f"variant {variant.name!r}.args_overrides: unknown step ids "
                    f"{sorted(unknown_overrides)}"
                )
            unknown_omits = set(variant.steps_omit) - step_ids
            if unknown_omits:
                raise ValueError(
                    f"variant {variant.name!r}.steps_omit: unknown step ids {sorted(unknown_omits)}"
                )
        # Variant names must be unique.
        names = [v.name for v in self.variants]
        dupe_names = sorted({n for n in names if names.count(n) > 1})
        if dupe_names:
            raise ValueError(f"duplicate variant name(s): {dupe_names}")
        return self

    @model_validator(mode="after")
    def _validate_concurrency_limit(self) -> ProcedureSpec:
        if self.concurrency_limit < 1:
            raise ValueError(f"concurrency_limit must be >= 1 (got {self.concurrency_limit})")
        return self

    def apply_variant(self, variant_name: str) -> ProcedureSpec:
        """Return a new ``ProcedureSpec`` with the named variant applied.

        Deep-copies via pydantic ``model_dump`` + ``model_validate``,
        mutates the steps list, and returns the result. The receiver's
        own attributes are untouched so concurrent variant applications
        don't trample each other.
        """
        variant = next((v for v in self.variants if v.name == variant_name), None)
        if variant is None:
            raise ValueError(f"unknown variant {variant_name!r} for procedure {self.slug!r}")
        as_dict = self.model_dump()
        # Apply omits.
        as_dict["steps"] = [s for s in as_dict["steps"] if s["id"] not in variant.steps_omit]
        # Apply args overrides.
        for step in as_dict["steps"]:
            override = variant.args_overrides.get(step["id"])
            if override is not None:
                merged = dict(step.get("args") or {})
                merged.update(override)
                step["args"] = merged
        # Clear ``variants`` on the resulting spec — re-validating with
        # the original variants list would fail when an omit removes a
        # step that another variant references. The variant is already
        # resolved into ``steps``; downstream callers don't re-apply.
        as_dict["variants"] = []
        return ProcedureSpec.model_validate(as_dict)


# ---------------------------------------------------------------------------
# Frontmatter splitting + IO.
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


class ProcedureParseError(ValueError):
    """Raised when ``PROCEDURE.md`` cannot be parsed.

    Distinct from pydantic's ``ValidationError`` so callers (the loader,
    the route, the MCP tool) can map this to a user-facing 4xx with a
    pointer at the file path.
    """

    def __init__(self, message: str, *, path: Path | None = None) -> None:
        super().__init__(message)
        self.path = path


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return ``(yaml_block, body)`` from a ``PROCEDURE.md`` source.

    Raises ``ProcedureParseError`` when the leading ``---`` delimiter
    or the closing one is missing.
    """
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise ProcedureParseError(
            "PROCEDURE.md must begin with a YAML frontmatter block delimited by '---'"
        )
    return match.group(1), match.group(2)


def parse_procedure(text: str, *, path: Path | None = None) -> ProcedureSpec:
    """Parse a ``PROCEDURE.md`` source into a ``ProcedureSpec``.

    Splits the frontmatter, runs YAML, validates with pydantic. The
    body is discarded — it's documentation, not contract. Callers that
    need the body can use ``split_frontmatter`` directly.
    """
    yaml_block, _body = split_frontmatter(text)
    try:
        raw = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        raise ProcedureParseError(f"frontmatter YAML invalid: {exc}", path=path) from exc
    if not isinstance(raw, dict):
        raise ProcedureParseError("frontmatter must be a YAML mapping (key/value pairs)", path=path)
    try:
        return ProcedureSpec.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError + the AttributeError edge cases
        raise ProcedureParseError(f"frontmatter does not match schema: {exc}", path=path) from exc


def load_procedure(procedure_dir: Path) -> ProcedureSpec:
    """Load ``<procedure_dir>/PROCEDURE.md`` and return its spec.

    Enforces ``spec.slug == procedure_dir.name`` so the on-disk slug
    matches the in-memory truth.
    """
    md = procedure_dir / "PROCEDURE.md"
    if not md.is_file():
        raise ProcedureParseError(f"no PROCEDURE.md in {procedure_dir}", path=procedure_dir)
    text = md.read_text(encoding="utf-8")
    spec = parse_procedure(text, path=md)
    if spec.slug != procedure_dir.name:
        raise ProcedureParseError(
            f"slug {spec.slug!r} does not match directory name {procedure_dir.name!r}",
            path=md,
        )
    return spec


def load_all_procedures(procedures_dir: Path) -> dict[str, ProcedureSpec]:
    """Scan ``procedures_dir`` for ``<slug>/PROCEDURE.md`` files.

    Returns a slug → spec dict. Skips dotfiles and the ``_template``
    directory (the on-disk template carries placeholder values that
    don't satisfy the schema). Errors in any one file abort the whole
    scan — the caller surfaces the offending path.
    """
    if not procedures_dir.is_dir():
        return {}
    out: dict[str, ProcedureSpec] = {}
    for entry in sorted(procedures_dir.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        if name.startswith(".") or name.startswith("_"):
            continue
        manifest = entry / "PROCEDURE.md"
        if not manifest.is_file():
            continue
        spec = load_procedure(entry)
        out[spec.slug] = spec
    return out


__all__ = [
    "OnFailure",
    "ProcedureParseError",
    "ProcedureSchedule",
    "ProcedureSpec",
    "ProcedureStep",
    "ProcedureVariant",
    "load_all_procedures",
    "load_procedure",
    "parse_procedure",
    "split_frontmatter",
]
