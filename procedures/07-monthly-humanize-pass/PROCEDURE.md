---
name: monthly-humanize-pass
slug: 07-monthly-humanize-pass
version: 0.1.0
description: |
  Monthly cron-triggered refresh sweep. Pick the N oldest published
  articles flagged ``refresh_due`` (entry points per audit P-I6),
  for each one snapshot the live row into ``article_versions``, run
  the humanizer + editor + EEAT gate on the new version, then
  republish via the project's primary publish target. Per audit
  P-I1 the humanizer runs **once per article version** — never twice
  on the same version row — so the candidate selection step
  guarantees a freshly-bumped version before the humanizer fires.

triggers:
  - "scheduled-job:monthly-humanize-pass"
  - "Manual: operator runs `/procedure monthly-humanize-pass <project-id> --top-n 10`"

prerequisites:
  - "projects has at least one articles row with status='published' (otherwise no candidates to refresh)"
  - "voice_profiles WHERE project_id=:project_id AND is_default=true has humanizer.allowed=true (default true; projects can opt out via voice_profile.config)"
  - "primary publish target is_active=true (procedure 4's publish step is the republish path)"

produces:
  - article_versions
  - articles
  - article_publishes
  - eeat_evaluations
  - redirects
  - runs
  - run_steps
  - procedure_run_steps

inputs:
  top_n: "Maximum candidates to refresh in one sweep (int; default 10)."
  selection_mode: "How candidates are chosen — 'auto' (refresh-detector ordering) or 'top-n' (operator picks IDs) (str; default 'auto')."
  candidate_ids: "Operator-supplied article IDs when selection_mode='top-n' (comma-separated str; optional)."

steps:
  - id: select-candidates
    skill: _programmatic/select-refresh-candidates
    on_failure: abort
  - id: humanize-each
    skill: 05-ongoing/content-refresher
    on_failure: skip

variants:
  - name: top-n
    description: "Operator picks the N candidates by hand via --candidate-ids."
    args_overrides:
      select-candidates:
        selection_mode: top-n
  - name: auto
    description: "refresh-detector picks the N oldest refresh_due candidates."
    args_overrides:
      select-candidates:
        selection_mode: auto

concurrency_limit: 1
resumable: true

schedule:
  cron: "0 4 1 * *"
  timezone_field: "projects.schedule_json.timezone"
---

# 07 — Monthly Humanize Pass

The monthly maintenance cycle for published articles. Picks
candidates flagged ``refresh_due``, snapshots each into
``article_versions``, runs the humanizer + editor + EEAT gate on the
new version, then republishes via the primary target. Slug change
pre-publish writes a ``redirects`` row.

## When to use

Cron-triggered monthly (1st of each month at 04:00 in the project's
timezone). Manual invocation via ``/procedure monthly-humanize-pass``
covers operator-driven catch-up runs ("I missed last month's pass,
flush the backlog now").

The operator can opt out of the monthly cron at the project level by
flipping ``voice_profile.config.humanizer.allowed=false``. The
candidate-selection step honours this flag and emits an empty
candidate list when the project has opted out.

## Step-by-step

1. **select-candidates** — Run the canonical refresh-detector query
   (PLAN.md L508-L518) over the project's published articles where
   ``status='refresh_due'``. Order by oldest ``last_refreshed_at``
   first (NULL = first). Cap at ``top_n`` (default 10). Honours the
   variant's selection mode: ``auto`` runs the query, ``top-n``
   uses the operator's explicit ``candidate_ids``.
   ``on_failure=abort``: a missing candidate list means we have
   nothing to refresh; better surface the issue (likely an empty
   queue or a bad operator id-list).
2. **humanize-each** (#24 content-refresher) — For each candidate
   sequentially (NOT parallel — humanizer is voice-sensitive and
   serialising prevents two concurrent versions racing on the same
   article row):
   1. ``article.createVersion`` — snapshot the live row into
      ``article_versions``, increment ``articles.version``. This
      satisfies the audit P-I1 invariant: the humanizer only ever
      runs against a freshly-bumped version row, never twice on the
      same one.
   2. **humanizer** (#12) — Re-edit pass on the new version's
      ``edited_md``. Varies sentence length, removes "AI tells".
   3. **editor** (#10) — Re-edit on the humanized output to settle
      voice + grammar.
   4. **eeat-gate** (#11) — Score the new version. SHIP advances;
      FIX loops back to editor (capped at
      ``settings.procedure_runner_max_loop_iterations``); BLOCK
      flips ``articles.status='aborted-publish'`` for that one
      candidate but doesn't abort the whole sweep — the next
      candidate proceeds.
   5. **republish** — Push the new version to the primary publish
      target (writes a new ``article_publishes`` row with
      ``version_published+1``). Slug change pre-publish writes a
      ``redirects`` row with ``kind='301'``.
   6. ``articles.last_refreshed_at = now()`` + flip
      ``articles.status='published'``.
   ``on_failure=skip``: a per-candidate failure marks that one
   article as skipped in the sweep; the rest of the candidates
   proceed. The summary captures per-candidate outcomes for the UI.

## Variants

- ``auto`` — refresh-detector ordering picks the N oldest. The
  canonical monthly path.
- ``top-n`` — Operator passes ``--candidate-ids`` for manual control
  (e.g., "I just landed a fresh study; refresh THESE three articles
  with the new data").

## Failure handling commentary

- **select-candidates** → ``abort``. An empty query result on a
  project that should have refresh-due candidates indicates the
  weekly refresh-detector hasn't run, the operator's flagged ids
  are stale, or the voice profile has opted out — all worth
  surfacing.
- **humanize-each** → ``skip``. The per-candidate iteration is
  internally serialised and resilient. A single candidate's BLOCK
  / republish failure marks that one as aborted-publish; the next
  candidate proceeds. The summary in
  ``runs.metadata_json.humanize_summary`` captures
  refreshed / skipped / blocked counts per audit.

## Audit P-I1 — humanizer once per version

The humanizer runs **once per article version**:

- ``article.createVersion`` snapshots live → ``article_versions``
  BEFORE the humanizer touches anything. ``articles.version`` is
  incremented atomically.
- The humanizer + editor + eeat-gate operate on the new version's
  body. ``article_versions`` is immutable after creation.
- A second pass on the same version is rejected at the repository
  layer (``articles.createVersion`` no-ops if a snapshot already
  exists for the same ``(article_id, version)``).

This invariant lives in two places: the
``repositories/articles.py:create_version`` predicate AND this
procedure's step ordering. The two-pronged enforcement matches the
deliverable's "humanizer once per article version" lock.

## Cron metadata

The ``schedule`` block declares the cron + timezone field for M8:

- ``schedule.cron``: ``0 4 1 * *`` — 1st of each month, 04:00.
- ``schedule.timezone_field``: ``projects.schedule_json.timezone``.

The 04:00 timing puts the run in the project's overnight window so
republishes don't hit the site during operator working hours. M8's
APScheduler bootstrap reads the schedule block at job-registration
time.

## Relationship to refresh entry points (audit P-I6)

Per the audit + procedure 6's prose: there are exactly two entry
points to ``status='refresh_due'``:

1. Procedure 6's **refresh-detector** step (weekly cron).
2. The operator clicking "flag for refresh" on
   ``ArticleDetailView.vue``.

Both converge on this procedure consuming
``WHERE status='refresh_due'``. The candidate-selection step is the
only place this procedure reads from that flag set.
