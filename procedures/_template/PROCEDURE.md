---
# PROCEDURE.md template (copy this into procedures/<your-slug>/PROCEDURE.md
# and fill in the values).

# Required: name (human-readable label) + slug (must match dir name).
name: my-procedure
slug: _template
version: 0.0.0
description: |
  One-paragraph summary of what the procedure does and when to use it.
  Operator-facing — surfaces in the UI's procedures list + the MCP
  client's `procedure.list` output.

# Triggers — natural-language; informational only. The runner does not
# parse these; they're for the operator's reference.
triggers:
  - "Manual: operator runs via UI / `/procedure my-procedure <args>`"
  - "Parent procedure: invoked from procedure-N as a child (set parent_run_id)"

# Prerequisites — natural-language predicates over DB rows. The runner
# does not validate these; the first step's skill is responsible for
# refusing to run when they're not met (returns a typed error). They're
# documentation for operators reading the procedure cold.
prerequisites:
  - "project has voice_profiles with is_default=true"
  - "topic.status = 'approved'"

# Tables / artefact tables this procedure mutates. Surfaced in the UI's
# procedures detail view so operators can predict the blast radius.
produces:
  - articles
  - runs
  - run_steps
  - procedure_run_steps

# Inputs — keys are arg names, values are descriptions. The runner
# passes the full args dict through to every step's `args` payload.
inputs:
  example_id: "An int identifier the procedure operates on."
  optional_flag: "An optional bool toggle (default false)."

# Steps — the playbook. One row per step, managed sequentially by the
# current agent. Each
# step's `skill` is the path-like skill key (e.g. `02-content/editor`);
# the runner resolves the skill body from `skills/<key>/SKILL.md` and
# the tool grants from `content_stack.mcp.permissions.SKILL_TOOL_GRANTS`.
#
# `on_failure` modes:
#   abort       — terminal failure; runs.status=failed.
#   retry       — agent retries up to max_retries; escalate to abort on exhaustion.
#   loop_back   — agent returns to the named prior step (loop_back_to).
#                 The controller exposes the loop cap in step context.
#   skip        — mark the step skipped, advance to the next.
#   human_review — record a review pause; agent retries after operator action.
steps:
  - id: first-step
    skill: 01-research/keyword-discovery
    on_failure: abort
  # - id: another-step
  #   skill: 02-content/editor
  #   args:
  #     # Step-level args; merged with procedure args in the step package.
  #     extra_field: example
  #   on_failure: retry
  #   max_retries: 2
  # - id: gate-step
  #   skill: 02-content/eeat-gate
  #   on_failure: loop_back
  #   loop_back_to: another-step

# Variants — named overrides. The runner applies the variant at start
# time when the caller passes `variant=<name>`.
variants:
  # - name: my-variant
  #   description: "Variant that skips one step + overrides another's args."
  #   steps_omit:
  #     - first-step
  #   args_overrides:
  #     another-step:
  #       extra_field: variant-value

# concurrency_limit — the maximum number of parallel runs of THIS
# procedure system-wide. The runner enforces via an asyncio.Semaphore
# keyed on the slug. Default 1 means strictly serialised; bump to 4
# for procedures that can fan out safely (e.g. procedure 4).
concurrency_limit: 1

# resumable — when true, the daemon's crash-recovery sweep can resume
# this procedure from its last clean step on restart. Set to false for
# procedures whose steps are not idempotent (each re-execution would
# create duplicate rows / fire side-effects twice).
resumable: true
---

# My Procedure

Replace this body with your procedure's narrative. The runner ignores
the body — it's pure documentation for operators + LLM clients reading
the procedure cold.

## When to use

Describe the trigger conditions, the human in the loop, and the
expected duration / cost.

## Step-by-step

Walk through each step's purpose + failure semantics. Operators
read this when a run aborts to understand what went wrong without
diving into the audit trail.

## Variants

Spell out when each variant applies + how the operator chooses.

## Failure handling commentary

Per-step rationale for the chosen `on_failure` mode — the YAML
frontmatter shows the choice, this body explains *why*.
