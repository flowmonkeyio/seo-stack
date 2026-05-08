---
name: add-new-site
slug: 08-add-new-site
version: 0.1.0
description: |
  End-to-end onboarding playbook for a brand-new site: bootstrap the
  project (procedure 1), then either the one-site shortcut
  (procedure 2) OR full keyword discovery (procedure 3) per the
  ``--use-shortcut`` flag, then optionally bulk-launch the first
  batch of content (procedure 5). The operator manages cost via the
  bulk launch's ``--budget-cap-usd`` gate.

triggers:
  - "Manual: operator runs `/procedure add-new-site --domain new.com --niche \"...\" --locale en-US --use-shortcut --competitors a.com,b.com`"

prerequisites:
  - "no projects row already exists for the requested domain (procedure 1's project-create step is the gate)"
  - "operator has at least one daemon-side LLM credential row so dispatched skill sessions can run"

produces:
  - projects
  - voice_profiles
  - compliance_rules
  - eeat_criteria
  - publish_targets
  - integration_credentials
  - clusters
  - topics
  - articles
  - runs
  - run_steps
  - procedure_run_steps

inputs:
  domain: "Project's primary domain (str; required)."
  niche: "Project's niche tag (str; required)."
  locale: "Singular IETF locale per D3 (str; required)."
  use_shortcut: "When true, run procedure 2 (sitemap shortcut). When false, run procedure 3 (keyword discovery) (bool; default true)."
  competitors: "Comma-separated competitor domains for procedure 2 (str; required when use_shortcut=true)."
  seed_keywords: "Comma-separated seed keywords for procedure 3 (str; required when use_shortcut=false)."
  bulk_launch: "When true, fan out procedure 5 once topic queue is approved (bool; default false — operator usually wants to manually approve the queue first, then trigger bulk separately)."
  budget_cap_usd: "Hard cost cap for the optional bulk launch step (float; required when bulk_launch=true)."

steps:
  - id: bootstrap
    skill: _programmatic/run-child-procedure
    args:
      child_procedure: 01-bootstrap-project
    on_failure: human_review
  - id: topic-discovery-shortcut
    skill: _programmatic/run-child-procedure
    args:
      child_procedure: 02-one-site-shortcut
    on_failure: human_review
  - id: topic-discovery-deep
    skill: _programmatic/run-child-procedure
    args:
      child_procedure: 03-keyword-to-topic-queue
    on_failure: human_review
  - id: bulk-launch
    skill: _programmatic/run-child-procedure
    args:
      child_procedure: 05-bulk-content-launch
    on_failure: human_review

variants:
  - name: shortcut
    description: "Use procedure 2 (sitemap shortcut). Skip the keyword-discovery deep path."
    steps_omit:
      - topic-discovery-deep
  - name: keyword-discovery
    description: "Use procedure 3 (keyword discovery). Skip the sitemap shortcut."
    steps_omit:
      - topic-discovery-shortcut

concurrency_limit: 1
resumable: true
---

# 08 — Add New Site

The umbrella playbook for a brand-new site onboarding. Composes
procedures 1, 2 or 3, and (optionally) 5 into a single operator-
visible run with an audit row in ``runs`` so the onboarding journey
is a single artefact in the UI.

## When to use

The first thing a new operator does. Walking the four sub-procedures
manually would mean four separate runs, four separate parent_run_id
roots, and four separate UI cards to track. Procedure 8 ties them
together so the operator sees one journey.

## Step-by-step

1. **bootstrap** — Composes procedure 1 (`bootstrap-project`).
   Creates the project, voice profile, compliance rules, EEAT
   rubric, publish target, and integration creds. ``on_failure=
   human_review``: the bootstrap is operator-driven; pausing here
   lets the operator finish the setup async + resume.
2. **topic-discovery-shortcut** — Composes procedure 2
   (`one-site-shortcut`). Only present when the ``shortcut``
   variant is applied (the canonical default). Pulls competitor
   sitemaps + clusters + presents the queue for approval.
   ``on_failure=human_review``: the human-approval pause inside
   procedure 2 surfaces here.
3. **topic-discovery-deep** — Composes procedure 3
   (`keyword-to-topic-queue`). Only present when the
   ``keyword-discovery`` variant is applied. Full DataForSEO +
   Reddit + PAA + SERP + cluster + approval pipeline.
   ``on_failure=human_review``: same pause pattern as procedure 2.
4. **bulk-launch** — Composes procedure 5 (`bulk-content-launch`).
   Optional; the operator can skip and run bulk-launch separately
   once they've reviewed the approved topic queue. The
   ``--budget-cap-usd`` flag is mandatory per audit M-25 if this
   step runs. ``on_failure=human_review``: a budget pre-emption
   abort surfaces here so the operator can adjust the cap.

## Variants

- ``shortcut`` — Use procedure 2 (sitemap shortcut). Faster, lighter
  signal. The canonical default for onboarding.
- ``keyword-discovery`` — Use procedure 3 (keyword discovery). Full
  research path; best for projects with the time + budget for the
  deeper analysis.

## Nested procedure dispatch (M8 follow-up)

The runner does **not** yet support a step's ``skill`` field naming
another procedure as a child. The current
``_programmatic/run-child-procedure`` step pattern is a
placeholder: in M7.B's StubDispatcher the step returns an acked
shape; in production (M8) the runner will recognise this synthetic
skill key, look up the named child procedure from
``step.args.child_procedure``, and dispatch ``procedure.run`` for
that child with ``parent_run_id`` set to this run.

Until M8 wires this natively, operators who want the full
end-to-end onboarding via procedure 8 see one combined run row in
the UI that:

1. Walks each step (each step's stub returns success in M7.B).
2. Surfaces the named child procedure in
   ``runs.metadata_json.step_outputs.<step-id>`` so the UI can
   render "go run procedure 1 manually" links.
3. Resumes cleanly via ``procedure.resume`` after the operator
   completes the named child procedure manually.

This documented fall-back keeps procedure 8 valid against the
current parser + runner without bending the runner's contract;
M8 lifts the placeholder and dispatches children natively.

## Failure handling commentary

All four steps use ``on_failure=human_review`` for two reasons:

1. The wrapped child procedures are themselves long-running and
   often hit human-review pauses inside (procedure 1's voice
   prompt, procedure 2/3's topic approval, procedure 5's budget
   gate). Pausing the parent matches the child's reality.
2. The operator can resume after fixing whatever caused the child
   to stall, without losing the parent's audit row.

## Why an umbrella procedure?

The deliverable's "fully operational new project" outcome benefits
from a single ``runs`` row that covers the full onboarding journey.
Operators tracking onboarding progress in the UI's Runs view see
one card with N step rows, not four separate cards. The
``parent_run_id`` linkage from the children (M8) keeps the audit
trail complete.
