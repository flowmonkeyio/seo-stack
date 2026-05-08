---
name: weekly-gsc-review
slug: 06-weekly-gsc-review
version: 0.1.0
description: |
  Weekly cron-triggered ongoing-operations sweep — pull GSC data,
  surface striking-distance + cannibalization opportunities, capture
  drift baselines, audit crawl errors per published article, mark
  refresh-due articles, then aggregate findings into a weekly digest
  for the UI. Per audit P-I6 this procedure is one of two entry
  points to ``status='refresh_due'`` (the other being human flag-for-
  refresh on ArticleDetailView).

triggers:
  - "scheduled-job:weekly-gsc-review"
  - "Manual: operator runs `/procedure weekly-gsc-review <project-id>`"

prerequisites:
  - "integration_credentials.kind='gsc' is set + last refresh successful (oauth not expired)"
  - "projects.id exists AND projects.is_active=true"
  - "at least one articles row with status='published' for the project (otherwise the GSC pull has nothing to attribute)"

produces:
  - topics
  - drift_baselines
  - articles
  - gsc_metrics
  - gsc_metrics_daily
  - runs
  - run_steps
  - procedure_run_steps

inputs:
  window_days: "Lookback window for the GSC pull, in days (int; default 7)."
  top_n_drift_check: "Maximum number of articles to drift-check this run (int; default 25 — keeps weekly cost bounded)."
  refresh_detector_n: "Maximum articles to evaluate for refresh in one sweep (int; default 50)."

steps:
  - id: gsc-pull
    skill: _programmatic/gsc-pull
    on_failure: abort
  - id: gsc-opportunity-finder
    skill: 05-ongoing/gsc-opportunity-finder
    on_failure: skip
  - id: drift-watch
    skill: 05-ongoing/drift-watch
    on_failure: skip
  - id: crawl-error-watch
    skill: 05-ongoing/crawl-error-watch
    on_failure: skip
  - id: refresh-detector
    skill: 05-ongoing/refresh-detector
    on_failure: skip
  - id: summary
    skill: _programmatic/weekly-summary
    on_failure: skip

variants:
  - name: gsc-only
    description: "Skip drift + crawl-error + refresh-detector. Run only the GSC pull + opportunity finder."
    steps_omit:
      - drift-watch
      - crawl-error-watch
      - refresh-detector
  - name: full
    description: "All six steps — the canonical weekly sweep."

concurrency_limit: 1
resumable: true

schedule:
  cron: "0 6 * * MON"
  timezone_field: "projects.schedule_json.timezone"
---

# 06 — Weekly GSC Review

The weekly ongoing-operations sweep. Pulls a fresh GSC window,
surfaces opportunities + cannibalization, captures drift baselines
on top published articles, audits crawl errors, and marks
refresh-due candidates for procedure 7. The whole run produces one
digest that the UI's weekly-review tab renders for the operator.

## When to use

This is a cron-triggered procedure (Mondays 06:00 in the project's
local timezone). Operators can also invoke manually for "I just
landed a big push and want to check signal NOW" cases. The weekly
cadence balances signal freshness against API cost: most striking-
distance opportunities and drift events develop over multi-day
windows, so daily would over-spend without much new signal.

## Step-by-step

1. **gsc-pull** — Pull the last ``window_days`` (default 7) of GSC
   data into ``gsc_metrics`` (raw rows) + ``gsc_metrics_daily`` (the
   denormalised rollup per audit M-01). The integration wrapper
   handles OAuth refresh + rate limiting + the budget pre-emption
   per integration_budgets row.
   ``on_failure=abort``: a failed GSC pull means the rest of the
   sweep is signal-blind; better surface the OAuth or rate-limit
   issue than emit a hollow weekly digest.
2. **gsc-opportunity-finder** (#20) — Surface striking-distance
   queries (positions 4-15), cannibalization candidates (multiple
   URLs ranking for the same intent), missing intents (queries the
   site is appearing for that don't have a dedicated article).
   Persists rows to ``topics`` with ``source='gsc-opportunity'``.
   ``on_failure=skip``: a missing opportunity scan is graceful
   degradation; the rest of the sweep still runs.
3. **drift-watch** (#21) — For the top ``top_n_drift_check`` published
   articles by GSC traffic this week: capture a fresh snapshot,
   diff against the last baseline, persist the diff to
   ``drift_baselines``. ``on_failure=skip``: drift signal is
   advisory; the operator can still react to opportunities + crawl
   errors without it.
4. **crawl-error-watch** (#22) — Run URL Inspection per published
   article (rate-limited per GSC's budget); persist any error rows
   as ``topics`` with ``source='technical-fix'``.
   ``on_failure=skip``: same skip pattern.
5. **refresh-detector** (#23) — Run the canonical refresh-detector
   query (PLAN.md L508-L518) over the project's published articles.
   Flag candidates by flipping ``articles.status='refresh_due'``.
   This is the **first** of the two entry points per audit P-I6
   (the second is the operator clicking "flag for refresh" on the
   article detail view; both converge on procedure 7).
   ``on_failure=skip``: a missing refresh-detector run means
   procedure 7 won't have new candidates this week — operators can
   re-run manually or wait for next week.
6. **summary** — Aggregate the findings into
   ``runs.metadata_json.weekly_summary``: opportunity count, drift
   count, crawl-error count, refresh-due count, top issues per
   category. The UI's weekly-digest view renders this directly.
   ``on_failure=skip``: cosmetic; the per-step rows carry the truth.

## Variants

- ``gsc-only`` — Skip the drift / crawl-error / refresh-detector
  steps. Useful when the operator only cares about the
  opportunity-finder output (e.g., a project on pause where only
  ranking signal matters).
- ``full`` — All six steps. The canonical weekly sweep.

## Failure handling commentary

- **gsc-pull** → ``abort``. Without GSC data the rest of the sweep
  is signal-blind; better surface a 401 / OAuth-expired error than
  silently degrade.
- **gsc-opportunity-finder / drift-watch / crawl-error-watch /
  refresh-detector / summary** → ``skip``. Each is independent;
  one's failure shouldn't poison the others. The operator can
  re-run an individual skill via direct ``run.start`` if they
  need to chase a specific signal.

## Cron metadata

The ``schedule`` block in the frontmatter declares this procedure as
cron-triggered. M8's APScheduler bootstrap reads:

- ``schedule.cron``: ``0 6 * * MON`` — Mondays at 06:00.
- ``schedule.timezone_field``: ``projects.schedule_json.timezone`` —
  the project's locale-appropriate timezone (e.g., ``Europe/Berlin``,
  ``America/Los_Angeles``).

The runner itself ignores the schedule field (a manual invocation
bypasses the cron); M7.B authors the metadata, M8 wires the trigger.
The operator can opt out of the cron per-project by clearing the
project's ``schedule_json`` row; the daemon's job-registration loop
skips procedures with an unset schedule field.

## Two entry points to refresh_due (audit P-I6)

Per the deliverable's audit reference: the refresh-due flag has
exactly two entry points:

1. This procedure's **refresh-detector** step (weekly cron).
2. The operator clicking "flag for refresh" on
   ``ArticleDetailView.vue``.

Both converge on procedure 7 consuming
``WHERE status='refresh_due'``. The two-entry-point invariant means
operators can manually flag articles between weekly sweeps without
the weekly cron over-writing their picks.
