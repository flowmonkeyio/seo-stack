---
name: bulk-content-launch
slug: 05-bulk-content-launch
version: 0.1.0
description: |
  Fan out procedure 4 (topic-to-published) across N approved topics
  with budget-aware pre-emption (audit M-25). Estimates cost up
  front, refuses to start if the projected spend exceeds
  ``--budget-cap-usd``, then opens procedure-4 child runs
  (parent_run_id linked) and pauses until the current agent completes
  them. Cascade
  abort is supported via ``run.abort(cascade=true)``.

triggers:
  - "Manual: operator runs `/procedure bulk-content-launch <project-id> --topic-ids 1,2,3,...,N --budget-cap-usd 50`"
  - "Manual: operator runs `/procedure bulk-content-launch <project-id> --all-approved --budget-cap-usd 50`"

prerequisites:
  - "topics WHERE status='approved' AND project_id=:project_id non-empty (or matching --topic-ids)"
  - "all procedure 4 prerequisites met (voice, EEAT seed, primary publish target, integration creds)"
  - "operator passes --budget-cap-usd; estimate-cost aborts before child runs open if estimated cost > cap (audit M-25)"

produces:
  - articles
  - article_versions
  - article_publishes
  - schema_emits
  - eeat_evaluations
  - runs
  - run_steps
  - procedure_run_steps

inputs:
  topic_ids: "Comma-separated topic IDs to draft + publish (str; optional — exclusive with --all-approved)."
  all_approved: "Bool flag; when true the runner pulls all topics with status='approved' for the project (bool; optional)."
  budget_cap_usd: "Hard cap on total estimated cost; the runner aborts at estimate-cost time if exceeded (float; required per audit M-25)."
  concurrency_override: "Optional override for the procedure-4 child concurrency cap (int; default 4 from procedure-4 frontmatter)."

steps:
  - id: estimate-cost
    skill: _programmatic/bulk-cost-estimator
    on_failure: abort
  - id: spawn-procedure-4-batch
    skill: _programmatic/spawn-procedure-4-batch
    on_failure: abort
  - id: wait-for-children
    skill: _programmatic/wait-for-children
    on_failure: abort
  - id: final-summary
    skill: _programmatic/bulk-final-summary
    on_failure: skip

variants:
  - name: all-approved
    description: "Pulls all topics with status='approved' for the project (operator-driven trigger sets all_approved=true)."
  - name: selected
    description: "Operator passes specific --topic-ids; the bulk launch only fans out across those rows."

concurrency_limit: 1
resumable: true
---

# 05 — Bulk Content Launch

Fan out procedure 4 across many approved topics in one orchestrated
run. The bulk launcher is the operator's primary first-content path
on a new site — the deliverable's "first 20-100 articles for a new
site" trigger.

## When to use

The operator has an approved topic queue (from procedure 2 or 3) and
wants to publish a batch of articles in one visible flow. Bulk launch
handles cost pre-emption, child-run linkage via ``parent_run_id``, and
cascade abort.

## Step-by-step

1. **estimate-cost** — Sum the conservative procedure-4 cost template
   times N topics, plus a buffer for retries. Compare against
   ``--budget-cap-usd``. ``on_failure=abort``: an over-budget batch
   refuses to start so the operator can either trim the topic list
   or raise the cap. Per audit M-25 this pre-emption is a hard gate,
   not a soft warning.
2. **spawn-procedure-4-batch** — For each topic: open a child run with
   ``slug='04-topic-to-published'``, ``args={topic_id: ...}``,
   ``parent_run_id=<bulk-run-id>``. The step records all child ids;
   the current agent chooses whether to work them sequentially,
   delegate them to caller-owned subagents, or pause for the operator.
   ``on_failure=abort``: a failed open (e.g., a topic missing
   required EEAT seed) means the batch can't proceed.
3. **wait-for-children** — Inspect each child's ``runs.status`` row.
   If any child is still running, record a human-review pause with the
   running ids. The current agent completes or aborts those children,
   then retries this step. ``on_failure=abort``: a failed child can
   terminate the batch.
4. **final-summary** — Aggregate the per-child results: success
   count, fail count, aborted count, per-fail link to
   ``RunDetailView``. Persists to
   ``runs.metadata_json.bulk_final_summary``. ``on_failure=skip``:
   a missing summary is cosmetic; the batch's outcome is already
   captured in the per-child run rows.

## Variants

- ``all-approved`` — Bulk-fan across every approved topic for the
  project. Used at site-launch time to ship the first 20-100
  articles.
- ``selected`` — Operator hand-picks ``--topic-ids``. Used for
  partial batches (e.g., "publish these five high-priority topics
  this week, the rest next sprint").

## Concurrency model

The bulk launcher itself has ``concurrency_limit=1`` — only one
bulk run per project at a time, otherwise two operators' batches
would race for the same procedure-4 slots. The procedure-4 children
inherit their own slug-keyed semaphore (default 4) so the system-
wide cap applies regardless of how many bulk launches are in flight.

Cascade abort: ``run.abort(parent_run_id, cascade=true)`` cancels the
parent + every child in one shot. The bulk launcher's
``wait-for-children`` step exits cleanly on cascade and writes a
cascade-aborted summary to metadata for the UI.

## Failure handling commentary

- **estimate-cost / spawn-procedure-4-batch / wait-for-children** →
  ``abort``. Each is a hard gate: budget breach, schedule failure,
  child crash. Better to fail fast than partially-publish.
- **final-summary** → ``skip``. Cosmetic; the per-child rows carry
  the truth.

## Audit anchor

Per audit M-25 (cost cap + rate-limit pre-emption): the
``--budget-cap-usd`` flag is mandatory for the deliverable's
spec. The estimate-cost step refuses to start if the projected spend
would exceed the cap. Operators get a clear error with the breakdown
(per-skill estimates × N topics) so they can adjust.
