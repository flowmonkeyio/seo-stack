---
name: refresh-detector
description: Score every published article on age + GSC trend + drift, mark articles with a refresh_score above the project floor as 'refresh_due' via article.markRefreshDue, and update last_evaluated_for_refresh_at on every candidate so a run-crash midway through does not double-evaluate.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: original
license: project-internal
allowed_tools:
  - meta.enums
  - project.get
  - article.list
  - article.markRefreshDue
  - gsc.queryArticle
  - drift.list
  - drift.get
  - run.start
  - run.heartbeat
  - run.finish
  - run.recordStepCall
inputs:
  project_id:
    source: env
    var: CONTENT_STACK_PROJECT_ID
    required: true
  run_id:
    source: env
    var: CONTENT_STACK_RUN_ID
    required: true
outputs:
  - table: articles
    write: article.markRefreshDue advances published → refresh_due for any article whose computed refresh_score crosses the project floor; last_evaluated_for_refresh_at is updated for every candidate inspected (passing or failing the floor).
  - table: runs
    write: per-article score breakdowns (age / gsc trend / drift sub-scores), the candidate roster, and the marked-for-refresh roster in runs.metadata_json.refresh_detector.
---

## When to use

The refresh-detector is the seed of procedure 7 (`monthly-humanize-pass`). The skill consumes the canonical query from PLAN.md Schema § "Canonical refresh-detector query" — published articles whose `last_refreshed_at` is older than the project's age floor (or null) and whose `last_evaluated_for_refresh_at` is older than 7 days (the per-audit-B-15 thrash guard). For each candidate it computes a refresh_score from three sub-scores, marks the article `refresh_due` when the score crosses the project floor, and writes a structured audit row.

Per audit P-I6 there are exactly two entry points to the `refresh_due` status: this skill (run weekly via `jobs/refresh_detector.py` — the APScheduler wiring lives in M8 but the skill prose is M6 and the contract is locked here) and the human in `ArticleDetailView.vue` clicking "flag for refresh" (which calls `article.markRefreshDue` directly). Both paths converge on procedure 7 consuming `WHERE status='refresh_due'`. The skill must respect this seam: it never advances `refresh_due → published` directly; that's procedure 7's job through skill #24 (content-refresher).

The skill also runs in operator-invoked one-off mode when the operator wants to inspect the candidate roster without acting on it (the `audit-only` variant below). The contract is identical except no `markRefreshDue` writes happen.

## Inputs

- `project.get(project_id)` — returns `schedule_json` for the per-project tuning knobs (the load-bearing inputs):
  - `refresh.refresh_age_days` — age floor in days. Articles whose `last_refreshed_at` (or `published_at` when never refreshed) is younger than this are skipped. Default 90 days.
  - `refresh.gsc_drop_pct` — the percentage drop in clicks-per-day between the trailing 28-day window and the prior 28-day window that flags a GSC trend signal. Default 30 (a 30% drop).
  - `refresh.drift_score_threshold` — the drift score (0-100, lower is worse) below which the article is flagged for drift. Default 30.
  - `refresh.refresh_score_min` — the integer score (sum of the three sub-scores) above which the skill marks the article `refresh_due`. Default 5.
  - `refresh.thrash_guard_days` — the days-since-last-evaluation floor; articles evaluated within this window are skipped to prevent thrash. Default 7 (matching the canonical query).
- `article.list(project_id, status='published')` — every published article. The skill reads `id`, `slug`, `title`, `published_url`, `last_refreshed_at`, `last_evaluated_for_refresh_at`, and the `version`. Page through the listing.
- `article.markRefreshDue(article_id, reason=…)` — the writer. Repository advances `articles.status` from `published` to `refresh_due` and updates `last_evaluated_for_refresh_at`. The `reason` field carries the score breakdown so the operator can see why the article was flagged.
- `gsc.queryArticle(article_id, since=…, until=…)` — wraps the per-article rollup read. Returns `GscMetricDaily`-shaped rows aggregated per day. The skill reads two windows: trailing 28 days and the prior 28 days. The wrapper reads `gsc_metrics_daily` first; live-API fallback fires only when the rollup is sparse for the requested window.
- `drift.list(article_id)` — every drift baseline for the article. The skill reads the most recent `current_score` (the field `drift_baselines.current_score` set by drift-watch's diff). When the score is null (drift-watch has not yet run, or the diff is the M6-deferral path), the drift sub-score is zero — the article cannot be flagged on drift alone in that case.
- `drift.get(baseline_id)` — fetch a specific baseline's element bag when the diagnostic detail is needed for the audit row.
- `meta.enums` — surfaces `articles.status` values plus `runs.kind='refresh-detector'` so the skill emits canonical strings.

## Steps

The skill's job is to compute three numeric sub-scores per candidate, sum them, compare against the project floor, and either mark or skip. The sub-scores are weighted-by-design — age and GSC are the canonical drivers; drift is a tie-breaker that elevates ageing articles whose live HTML has actually changed.

1. **Read context.** Resolve the project and the tuning knobs. When `schedule_json.refresh.*` is absent (the project bootstrap did not seed defaults), apply the defaults documented above and surface `runs.metadata_json.refresh_detector.defaults_applied=true` so the operator can decide whether to lock the values into the project row.
2. **Compute the windows.** Today's date (or the run's `started_at` clipped to date) is `today`. The two GSC windows are `(today - 56 days, today - 28 days)` (the prior window) and `(today - 28 days, today)` (the trailing window). The age cutoff is `today - schedule_json.refresh.refresh_age_days`. The thrash cutoff is `today - schedule_json.refresh.thrash_guard_days`.
3. **Build the candidate roster.** Run the canonical query (paraphrased in this prose; the SQL lives in PLAN.md Schema § "Canonical refresh-detector query"):
   - `articles WHERE status='published' AND project_id=:project_id`
   - AND (`last_refreshed_at IS NULL OR last_refreshed_at < <age_cutoff>`)
   - AND (`last_evaluated_for_refresh_at IS NULL OR last_evaluated_for_refresh_at < <thrash_cutoff>`)
   - ORDER BY `COALESCE(last_refreshed_at, created_at) ASC`
   - LIMIT `schedule_json.refresh.candidates_per_run` (default 100; the project can raise or lower).
   The `article.list` MCP tool exposes filters via the standard column-filter convention; the skill composes the filter dict and pages through the listing. Capture the candidate count in the audit row.
4. **For each candidate, compute the age sub-score.** The age sub-score increases with months-since-last-refresh:
   - Age in days = `today - COALESCE(last_refreshed_at, published_at, created_at)`.
   - 0 to 89 days → score 0 (the candidate would not have passed the canonical query at this age, but the math is defensive).
   - 90 to 180 days (3 to 6 months) → score 1.
   - 181 to 365 days (6 to 12 months) → score 2.
   - 366 to 730 days (1 to 2 years) → score 4.
   - 731 to 1095 days (2 to 3 years) → score 5.
   - 1096+ days (3+ years) → score 6.
   The thresholds reflect search-quality reality: articles older than two years that have not been touched are stale candidates regardless of any other signal. Capture the per-candidate sub-score in `runs.metadata_json.refresh_detector.per_article[article_id].age_score`.
5. **For each candidate, compute the GSC trend sub-score.** Call `gsc.queryArticle(article_id, since=<prior_start>, until=<trailing_end>)` to read both windows in one shot (the wrapper splits the result by day for the score computation). The sub-score has three components:
   - **Clicks-per-day delta** — when `(trailing_clicks_per_day / prior_clicks_per_day) < (1 - schedule_json.refresh.gsc_drop_pct/100)`, add 3. (A 30% drop or worse on default settings.)
   - **Impressions delta** — when `(trailing_impressions_per_day / prior_impressions_per_day) < (1 - schedule_json.refresh.gsc_drop_pct/100)`, add 2.
   - **Average-position deterioration** — when `trailing_avg_position - prior_avg_position > 5` (the article slid down five positions or more), add 2.
   When the article has no GSC data for either window (cold start: never appeared in search, or the GSC integration was added recently), the GSC sub-score is 0 — null is treated as no-change, not as no-signal. The skill surfaces `runs.metadata_json.refresh_detector.per_article[article_id].gsc_cold_start=true` for cold-start articles so the operator can decide whether the project's GSC wiring has gaps.
   Cap the GSC sub-score at 7 (the maximum across all three components) to keep the score additive without runaway influence. Capture the components and the cap in the audit row.
6. **For each candidate, compute the drift sub-score.** Call `drift.list(article_id)` and read the most recent baseline. The `current_score` field on the most recent baseline is the diff engine's verdict (0-100, lower-is-worse). The sub-score has two paths:
   - **Severity-driven** — when the most recent diff verdict carries CRITICAL severity (the verdict envelope persists in `runs.metadata_json` of drift-watch's run, but the skill reads the score-driven proxy here): add 5.
   - **Score-driven** — when `drift_baselines.current_score < schedule_json.refresh.drift_score_threshold` (default 30), add 2. Stack with the severity-driven add when both apply (CRITICAL + low score = 7).
   When the article has no drift baselines (drift-watch has not yet inspected it; or the article was published after the last drift-watch run), the drift sub-score is 0. Surface `runs.metadata_json.refresh_detector.per_article[article_id].drift_unaudited=true` so the operator can either run drift-watch on demand or accept that the article will not be flagged on drift this cycle.
   When `drift.diff` is the M6 deferral path (drift-watch captured a snapshot but the diff did not run), `current_score` is null. The skill treats null as drift_unaudited and the sub-score is 0; the deferral does not penalise the candidate.
7. **Sum and threshold.** For each candidate, `refresh_score = age_score + gsc_score + drift_score`. When `refresh_score >= schedule_json.refresh.refresh_score_min` (default 5), the article is marked. Compose the reason string from the per-component breakdown: e.g., `"age=2 gsc=3 drift=2 (total=7; threshold=5; trailing_clicks_drop=42%, drift_baseline_score=18)"`. The reason is human-readable on the operator's UI — short enough to fit in a list-row description, structured enough that the operator can act on it.
8. **Mark for refresh.** For each candidate that crosses the threshold, call `article.markRefreshDue(article_id, reason=<reason_string>)`. The repository advances `articles.status` to `refresh_due` and updates `last_evaluated_for_refresh_at` to `now`. When the call returns 409 (the article moved to a different status concurrently — e.g., the operator hard-deleted between `article.list` and the mark), capture in `runs.metadata_json.refresh_detector.skipped_articles[]` and continue.
9. **Update the evaluation timestamp on skipped candidates.** Per audit B-15, articles that were inspected but did NOT cross the threshold STILL get their `last_evaluated_for_refresh_at` updated to `now` so they don't re-evaluate every day. The repository exposes this via the `markRefreshDue` no-op path (call with the article id but the repository detects the no-mark case from the score and updates the timestamp without changing status). When the repository tool does not yet expose this no-op path, the skill bumps `last_evaluated_for_refresh_at` via a separate update call; the M3 article repository's `setStepProgress`-style API is the right seam (the M7 wave wires this if not already done).
10. **Sort the marked roster.** Order the marked-for-refresh articles by `refresh_score DESC, trailing_28d_impressions DESC` so procedure 7's content-refresher consumes the highest-impact / highest-traffic candidates first. The order persists to `runs.metadata_json.refresh_detector.marked_roster[]` as a list of `{article_id, refresh_score, age_score, gsc_score, drift_score, trailing_impressions, reason}`; procedure 7's runner reads the list straight off this audit row.
11. **Persist the audit row.** Write `runs.metadata_json.refresh_detector = {window_today, age_cutoff, thrash_cutoff, candidates_inspected, candidates_marked, marked_roster: [...], skipped_thrash_guard, skipped_age_floor, score_breakdowns: [...], cold_start_articles, drift_unaudited_articles, defaults_applied}`. Heartbeats fire after every 25 candidates so a long run on a 200-article project stays visible.
12. **Finish.** Call `run.finish` with `{project_id, candidates_inspected, candidates_marked, oldest_article_age_days, highest_refresh_score, mean_refresh_score}`. The procedure-7 runner reads `candidates_marked` and continues into the per-article refresh chain via skill #24.

## Outputs

- `articles` — `status='refresh_due'` on every article that crosses the threshold; `last_evaluated_for_refresh_at` updated on every candidate inspected (passing or failing the threshold).
- `runs.metadata_json.refresh_detector` — the per-article score breakdowns, the marked roster sorted by score, the candidate-vs-marked counts, and the cold-start / drift-unaudited rosters.

## Failure handling

- **Project has zero published articles.** Surface `runs.metadata_json.refresh_detector.empty_roster=true` and finish cleanly. Procedure 7 advances; the project simply has no articles to refresh.
- **Project has zero candidates after the canonical query.** Means every published article was either younger than the age floor or evaluated within the thrash window. Surface `runs.metadata_json.refresh_detector.zero_candidates=true` and finish cleanly. The next weekly run picks up new candidates as the age cohort moves.
- **GSC integration row missing.** The skill cannot compute the GSC sub-score; treat every candidate as `gsc_cold_start=true` and the sub-score is 0. Surface `runs.metadata_json.refresh_detector.gsc_unwired=true`. The skill still flags candidates on age + drift alone; the operator wires GSC for richer scoring on the next run.
- **GSC API returns 429 on a per-article query.** Retry once with a 60-second backoff. A second 429 sets that article's `gsc_score=0` and surfaces `runs.metadata_json.refresh_detector.per_article[article_id].gsc_quota_skip=true`. The article is still scored on age + drift; quota-driven scoring gaps don't abort the run.
- **`article.markRefreshDue` rejects with a state-machine error.** Means the article's status changed concurrently (the operator hard-deleted, or another procedure transitioned it). Capture in `runs.metadata_json.refresh_detector.skipped_articles[]` and continue.
- **`article.markRefreshDue` succeeded for some articles but a later `article.list` call fails with a transient error.** The successful marks are durable. Surface `runs.metadata_json.refresh_detector.partial_run=true` and finish what was inspected; the next run picks up where this run left off because `last_evaluated_for_refresh_at` was bumped on every successful mark.
- **The refresh score crosses the threshold but the canonical query also returns the same article on every subsequent run (thrash guard not bumping).** Means the no-op timestamp-update path in step 9 is not wired. Surface `runs.metadata_json.refresh_detector.thrash_guard_unwired=true` and abort to prevent the operator from missing the regression. Engineering escalates to add the timestamp-update path before the skill is re-enabled in production.
- **Drift baseline timestamp lags an actual drift event by more than the project's drift-watch frequency.** Means drift-watch missed a run for this article. Surface `runs.metadata_json.refresh_detector.drift_baseline_stale[]` with the article id and the baseline's age; the operator can re-run drift-watch ad-hoc.
- **Two consecutive runs mark the same article without procedure 7 having processed it in between.** Means procedure 7 is backlogged. The skill does not re-mark (the article is already in `refresh_due`); the canonical query's status filter excludes it. Surface `runs.metadata_json.refresh_detector.refresh_backlog_count` (the count of articles in `refresh_due` going into THIS run). When the count is large, the operator scales procedure 7's concurrency.

## Variants

- **`fast`** — disables the GSC sub-score (skips the per-article GSC queries) and scores on age + drift only. Useful for smoke-tests where the operator wants the candidate roster without the GSC quota burn.
- **`standard`** — the default flow above with all three sub-scores.
- **`audit-only`** — runs every step, persists the audit row, but does NOT call `article.markRefreshDue` for any candidate. Useful for periodic threshold tuning where the operator wants to inspect what would be marked under a hypothetical floor before committing to the writes.
- **`single-article`** — invoked from `ArticleDetailView.vue` against one article id. The skill computes the score for that article alone, surfaces it to the UI, and respects the operator's manual override (the operator may flag for refresh even when the score is below the floor; the skill does not recompute or refuse — the operator's flag wins).
