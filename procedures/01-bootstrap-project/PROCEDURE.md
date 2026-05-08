---
name: bootstrap-project
slug: 01-bootstrap-project
version: 0.1.0
description: |
  First-run bootstrap for a new project — creates the project row,
  collects the voice profile, seeds compliance rules + the EEAT rubric
  (with T04 / C01 / R10 locked at tier='core' per D7), wires the
  publish target + integration credentials, and runs a final
  verification sweep. Operator-driven setup; the LLM walks the
  operator through each artifact and the runner tracks per-step
  completion in ``procedure_run_steps`` so a half-finished bootstrap
  resumes cleanly.

triggers:
  - "Manual: operator runs `/procedure bootstrap-project --domain example.com --niche saas --locale en-US`"
  - "Parent procedure: invoked from procedure 8 (add-new-site) as the first child"

prerequisites:
  - "no projects row already exists for the requested slug (the runner refuses with -32014 / 409 on conflict)"
  - "operator has at least one daemon-side LLM credential row (`integration_credentials.kind='openai'` or `'anthropic'`) so dispatched skill sessions can run"

produces:
  - projects
  - voice_profiles
  - compliance_rules
  - eeat_criteria
  - publish_targets
  - integration_credentials
  - runs
  - run_steps
  - procedure_run_steps

inputs:
  domain: "Project's primary domain (str; required). Becomes ``projects.domain``."
  niche: "Project's niche tag, freeform display only (str; required). Drives the compliance template selection."
  locale: "Singular IETF locale per D3 (str; required, e.g. ``en-US``)."
  slug: "Optional URL slug; default is the kebab-cased domain stem (str; optional)."
  voice_template: "Optional voice template key the operator wants pre-seeded (str; optional)."

steps:
  - id: project-create
    skill: _programmatic/project-create
    on_failure: abort
  - id: voice-profile
    skill: _programmatic/voice-profile-prompt
    on_failure: human_review
  - id: compliance-seed
    skill: _programmatic/compliance-seed
    on_failure: skip
  - id: eeat-seed
    skill: _programmatic/eeat-seed-verify
    on_failure: abort
  - id: publish-target
    skill: _programmatic/publish-target-prompt
    on_failure: human_review
  - id: integration-creds
    skill: _programmatic/integration-creds-prompt
    on_failure: human_review
  - id: verify
    skill: _programmatic/bootstrap-verify
    on_failure: abort

variants:
  - name: minimal
    description: "Skip publish-target + integration-creds (project + voice + compliance + EEAT only)."
    steps_omit:
      - publish-target
      - integration-creds
  - name: full
    description: "All seven steps — the canonical onboarding path."

concurrency_limit: 1
resumable: true
---

# 01 — Bootstrap Project

The bootstrap procedure stands up a brand-new project row with the
artefacts every downstream procedure expects: voice profile,
compliance rules, EEAT rubric, publish target, integration
credentials, and a final verification pass.

## When to use

The first thing an operator does for a new site. Procedure 8
(`add-new-site`) chains this as its first step; standalone use covers
"I'm onboarding a project the operator-facing UI doesn't yet show".

The procedure is operator-driven by design — the LLM client walks the
operator through each artefact and the runner tracks progress in
``procedure_run_steps``. The `human_review` failure mode on the
prompt-driven steps means the runner pauses politely if the operator
hasn't supplied everything yet (e.g., they want to come back tomorrow
to paste API keys); ``procedure.resume`` picks up at the next pending
step.

## Step-by-step

1. **project-create** — Persist a new ``projects`` row via
   ``project.create``. Required args: ``domain``, ``niche``,
   ``locale``, optional ``slug``. ``on_failure=abort``: a failed
   project create is structural (slug conflict, locale invalid) and
   shouldn't paper over.
2. **voice-profile** — Prompt the operator for the project's voice
   (template + tone + audience), persist via ``voice.set``.
   ``on_failure=human_review``: the operator pauses to draft the
   voice profile in the UI; resume picks up here.
3. **compliance-seed** — For niches with regulatory exposure
   (``igaming``, ``crypto``, ``health``, ``legal``, ``finance``):
   seed jurisdiction-aware compliance rules from the niche-specific
   template. For other niches: skip with an emitted note in
   ``runs.metadata_json``. ``on_failure=skip`` keeps the bootstrap
   flowing on a missing template.
4. **eeat-seed** — Verify the canonical 80-item EEAT rubric is seeded
   with the D7 invariant (T04 / C01 / R10 at ``tier='core'``,
   undeactivatable). The transactional ``project.create`` trigger
   pre-populates these rows; this step is a verification + a chance
   to surface any drift before procedure 4 starts gating on them.
   ``on_failure=abort``: a missing EEAT seed makes procedure 4
   refuse to score, so we surface the issue here rather than later.
5. **publish-target** — Operator picks a publisher kind from the
   six supported (``nuxt-content``, ``wordpress``, ``ghost``, ``hugo``,
   ``astro``, ``custom-webhook``) and provides the target's
   ``config_json``. The first target gets ``is_primary=true``.
   ``on_failure=human_review``: the operator can skip this for now
   and come back; procedure 4 will refuse to run until at least one
   ``is_primary`` target exists.
6. **integration-creds** — Prompt the operator for API keys for
   DataForSEO / Firecrawl / GSC OAuth (12-step setup deferred to
   ``docs/api-keys.md``) / OpenAI Images / Reddit / Ahrefs / Jina.
   Optional; persists via ``integration.set`` (encrypted via M4's
   AES-GCM seam). ``on_failure=human_review``: same pause-and-resume
   pattern as the publish-target step.
7. **verify** — Run a ``doctor``-equivalent sweep: project active,
   voice set, EEAT seeded with all 8 dimensions covered, integrations
   decrypt cleanly, primary publish target reachable. Emits a final
   summary onto ``runs.metadata_json.bootstrap_summary`` for the UI's
   onboarding wizard. ``on_failure=abort``: a verification fail is a
   structural issue the operator needs to investigate.

## Variants

- ``minimal`` — Skips publish-target + integration-creds. Useful when
  the operator wants the project skeleton wired before they have the
  publishing destination + API keys ready.
- ``full`` — All seven steps; the canonical onboarding path.

## Failure handling commentary

- **project-create / eeat-seed / verify** → ``abort``. These are
  structural: a failed project create can't be papered over, a
  missing EEAT rubric breaks procedure 4's gate, a verify fail
  surfaces a blocking integration issue. Better to surface the error
  than let downstream procedures fail with confusing symptoms.
- **voice-profile / publish-target / integration-creds** →
  ``human_review``. These steps can take days while the operator
  drafts the voice or wrangles OAuth callbacks; pausing the run with
  ``status='running'`` lets the heartbeat keep firing without
  burning a runner slot, and ``procedure.resume`` picks up cleanly.
- **compliance-seed** → ``skip``. A missing template for a niche
  shouldn't block the bootstrap; the operator can author rules
  manually post-bootstrap.

## Programmatic-step note (M7.B + M8 follow-up)

The seven steps use the ``_programmatic/<name>`` skill prefix —
synthetic skill keys that don't (yet) live under ``skills/``. The
StubDispatcher returns a permissive acked-style response for these in
M7.B's tests. M8 wires them up to dedicated repository calls (no LLM
session needed) so production bootstrap is a tight script that
doesn't burn LLM tokens for what's mostly DB CRUD + OAuth callbacks.

The ``human_review`` mode on the operator-prompt steps means that in
M7.B the runner pauses on a stub failure — operators interact via the
UI's Procedures detail view, then call ``procedure.resume``.
