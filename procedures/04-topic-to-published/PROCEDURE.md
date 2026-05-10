---
name: topic-to-published
slug: 04-topic-to-published
version: 0.1.0
description: |
  The workhorse procedure — full pipeline from approved topic to
  published article. Thirteen steps, three-verdict EEAT gate with FIX
  loop-back to the editor, BLOCK aborts the procedure, image generation
  + alt-text + interlinks are skip-on-failure (the article ships
  without them when the integration is unavailable), schema-emitter
  and publish are abort-on-failure.

triggers:
  - "Manual: operator invokes via UI or `/procedure 04-topic-to-published <topic_id>`"
  - "Procedure 5 (bulk-content-launch) — fans out one topic-to-published per approved topic"

prerequisites:
  - "topic.status = 'approved'"
  - "project has voice_profiles with is_default=true"
  - "project has eeat_criteria with tier='core' for all 3 vetoes (T04 / C01 / R10)"
  - "project has at least one publish_targets row with is_active=true (and a primary)"
  - "project has integration_credentials.kind='openai-images' set when image-generator is in scope"

produces:
  - articles
  - article_versions
  - article_assets
  - research_sources
  - schema_emits
  - article_publishes
  - eeat_evaluations
  - runs
  - run_steps
  - run_step_calls
  - procedure_run_steps

inputs:
  topic_id: "The approved topic to draft + publish (int; required)."
  refresh_image: "When true, regenerate the hero image even if the topic already has one (bool; default false)."

steps:
  - id: brief
    skill: 01-research/content-brief
    on_failure: abort
  - id: outline
    skill: 02-content/outline
    on_failure: abort
  - id: draft-intro
    skill: 02-content/draft-intro
    on_failure: retry
    max_retries: 1
  - id: draft-body
    skill: 02-content/draft-body
    on_failure: retry
    max_retries: 1
  - id: draft-conclusion
    skill: 02-content/draft-conclusion
    on_failure: retry
    max_retries: 1
  - id: editor
    skill: 02-content/editor
    on_failure: abort
  - id: humanizer
    skill: 02-content/humanizer
    on_failure: retry
    max_retries: 1
  - id: eeat-gate
    skill: 02-content/eeat-gate
    on_failure: loop_back
    loop_back_to: editor
  - id: image-generator
    skill: 03-assets/image-generator
    on_failure: skip
  - id: alt-text-auditor
    skill: 03-assets/alt-text-auditor
    on_failure: skip
  - id: schema-emitter
    skill: 04-publishing/schema-emitter
    on_failure: abort
  - id: interlinker
    skill: 04-publishing/interlinker
    on_failure: skip
  - id: publish
    skill: 04-publishing/nuxt-content-publish
    on_failure: abort

variants:
  - name: short-form
    description: "Skip image-generator + alt-text-auditor for short articles (<800 words)."
    steps_omit:
      - image-generator
      - alt-text-auditor
  - name: pillar
    description: "Long-form pillar; deeper research + heavier image asset."
    args_overrides:
      brief:
        depth_tier: heavy
        target_word_count: 4000

concurrency_limit: 4
resumable: true
---

# 04 — Topic to Published

The workhorse pipeline: an approved topic comes in, a published
article comes out. Thirteen sequential steps, one EEAT FIX loop, three
absorbing terminal states (`success`, `failed`, `aborted`).

## When to use

This procedure is the canonical "draft + publish one article"
playbook. The operator runs it manually for a single topic, or
procedure 5 (bulk-content-launch) fans it out across an approved-topic
batch with `parent_run_id` set so the parent's status reflects the
child results.

## Step-by-step

1. **brief** (#4 content-brief) — Resolve the topic, voice, compliance
   rules, and active EEAT criteria. Persist a `brief_json` to
   `articles.brief_json`. `on_failure=abort`: a missing voice or empty
   EEAT seed cannot be papered over.
2. **outline** (#6 outline) — Generate H1/H2/H3 from the brief. Writes
   `articles.outline_md`. `on_failure=abort`: an outline failure
   indicates the brief was malformed; we surface the error rather than
   retry.
3. **draft-intro** / **draft-body** / **draft-conclusion** (#7/#8/#9) —
   Three sequential drafting passes against the outline. Each appends
   to `articles.draft_md`. `on_failure=retry(max_retries=1)`: a
   transient LLM hiccup gets one re-shot; persistent failure escalates
   to abort.
4. **editor** (#10 editor) — Polish the stitched draft against the
   voice and the active criteria. Writes `articles.edited_md` and
   advances `articles.status=edited`. `on_failure=abort`: an editor
   failure is structural (missing voice / criteria / source rows) and
   shouldn't loop.
5. **humanizer** (#12 humanizer) — Run once on this article version
   after the editor and before the gate. Writes back to
   `articles.edited_md` without changing status. `on_failure=retry(1)`:
   a recoverable rhythm/citation invariant failure gets one re-shot;
   a second failure ships the editor-only body to the gate only if the
   failure handler records `DONE_WITH_CONCERNS`.
6. **eeat-gate** (#11 eeat-gate) — Score the edited article against the
   project's active criteria. Three verdicts:
   - `SHIP` → advance.
   - `FIX` → loop back to **editor** with the gate's fix list. The
     current agent respects the loop cap from
     `settings.procedure_runner_max_loop_iterations` (default 3); on
     exhaustion the procedure aborts with `runs.error` describing the
     loop-cap breach.
   - `BLOCK` → abort the procedure. The agent records
     `articles.status=aborted-publish` and `runs.status=aborted`
     per audit BLOCKER-09.
7. **image-generator** (#13 image-generator) — Generate the hero image
   via OpenAI Images. `on_failure=skip`: a missing image doesn't block
   publishing; the article ships with no `article_assets` rows and the
   schema-emitter handles the `image:` JSON-LD field accordingly.
8. **alt-text-auditor** (#14 alt-text-auditor) — Audit / generate alt
   text for any image assets. `on_failure=skip`: an alt-text gap is a
   warning, not a blocker.
9. **schema-emitter** (#16 schema-emitter) — Build the article's
   JSON-LD payload (Article + Author + Image refs). Writes one
   `schema_emits` row, sets `is_primary=true`. `on_failure=abort`: a
   missing schema means the publish step would fall over downstream.
10. **interlinker** (#15 interlinker) — Suggest internal links from the
   project's existing articles. `on_failure=skip`: suggestions are
   advisory and the publish step works without them.
11. **publish** (#17/#18/#19) — Push the article to the project's
    primary publish target. The controller inspects
    `project.publish_targets WHERE is_primary=true AND is_active=true`
    and selects the appropriate skill (`#17 nuxt-content-publish`,
    `#18 wordpress-publish`, or `#19 ghost-publish`) in the step package.
    `on_failure=abort`: a publish failure reverts to manual
    intervention rather than retrying through the chain.

## EEAT three-verdict semantics (audit BLOCKER-09)

The `eeat-gate` step is the only step with a verdict-driven branch.
Per PLAN.md L1018-L1027:

- `SHIP` advances the article and the procedure walks the next step.
- `FIX` loops back to the editor with the gate's `fix_required[]` list
  in `runs.metadata_json.eeat`. The current agent increments a per-target
  counter and aborts when the counter exceeds
  `procedure_runner_max_loop_iterations`.
- `BLOCK` aborts the procedure with `runs.status=aborted` and flips
  `articles.status=aborted-publish`. The article does not advance to
  `eeat_passed`; the operator has to start fresh after fixing the
  veto cause (e.g. adding the missing affiliate disclosure for a T04
  fail).

## Variants

- `short-form` — Skip image-generator + alt-text-auditor for short
  articles (<800 words, typically informational FAQ updates).
- `pillar` — Long-form pillar. Brief gets `depth_tier=heavy` and a
  4000-word target; the rest of the chain runs with the standard
  thresholds. Pillars typically come paired with the `strict` EEAT
  variant set per project (configured in voice profile, not here).

## Failure handling commentary

- **brief / outline / editor / schema-emitter / publish** → abort.
  These are structural failures; retrying without fixing the cause
  just burns tokens.
- **draft-intro / draft-body / draft-conclusion** → retry once. The
  drafting LLM occasionally returns malformed output; one retry
  succeeds in most cases. Two consecutive failures escalate to abort.
- **eeat-gate** → loop-back-to-editor on FIX, abort on BLOCK,
  advance on SHIP. The loop is capped at
  `procedure_runner_max_loop_iterations`.
- **image-generator / alt-text-auditor / interlinker** → skip. These
  are quality enhancers; the article publishes without them.

## Relationship to procedure 5 (bulk-content-launch)

When invoked from procedure 5, the `parent_run_id` carries the bulk
launch's `runs.id` so the parent's status reflects the child results.
Procedure 5 opens one child run per topic. The current agent decides how
many child runs to work at once and records progress through the parent
run's `wait-for-children` step.
