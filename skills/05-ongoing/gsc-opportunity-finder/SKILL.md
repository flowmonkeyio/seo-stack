---
name: gsc-opportunity-finder
description: Read the project's gsc_metrics_daily rollup, detect striking-distance / low-CTR-rank-1 / missing-intent / cannibalization opportunities, and write candidates back into the topic queue with source='gsc-opportunity'.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: original
license: project-internal
allowed_tools:
  - meta.enums
  - project.get
  - cluster.list
  - topic.list
  - topic.bulkCreate
  - article.list
  - gsc.queryProject
  - gsc.queryArticle
  - integration.test
  - integration.testGsc
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
  - table: topics
    write: one row per detected opportunity via topic.bulkCreate with source='gsc-opportunity'; the procedure runner's failure handler flips the status to 'queued' for human approval.
  - table: runs
    write: per-detector counts + the four opportunity buckets + the cannibalization map + cost.by_integration.gsc in runs.metadata_json.gsc_opportunity_finder.
---

## When to use

Procedure 6 (`weekly-gsc-review`) dispatches this skill once per project, immediately after `jobs/gsc_pull.py` lands the latest 28-day rollup into `gsc_metrics_daily`. The skill reads the rollup, detects four classes of opportunity that the rolling daily aggregate makes cheap to compute, and writes a row per opportunity into the `topics` queue with `source='gsc-opportunity'`. Drift-watch (#21) and crawl-error-watch (#22) then run against the same project, completing the weekly trio before the operator opens the topic queue for triage.

The skill also runs as an operator-invoked one-off when the operator clicks "find opportunities" on `GscOpportunitiesView.vue`. The contract is identical; the only difference is that the project's primary GSC integration must be live (the procedure-6 runner already verified it; the on-demand invocation runs `integration.testGsc` itself and aborts on failure).

## Inputs

- `project.get(project_id)` — returns `domain` (used to compose the `site_url` parameter for downstream gsc.* calls when the rollup is empty and the skill falls back to live API), `locale` (the `searchType=web` Search Analytics queries are locale-agnostic but per-locale projects keep the rollups separate), and `schedule_json` for the per-detector tuning knobs (`gsc.window_days` defaulting to 28, `gsc.striking_distance.min_impressions` defaulting to 100, `gsc.low_ctr_rank1.ctr_floor_pct` defaulting to 60% of the median CTR for rank-1, `gsc.missing_intent.min_impressions` defaulting to 50, `gsc.cannibalization.min_overlap_articles` defaulting to 2). Operators tune the floors per-project; the defaults are sane starting points.
- `cluster.list(project_id)` — every cluster the project has. The skill maps detected opportunities back to a cluster id when one of the project's articles already covers an adjacent topic, so the human triaging the queue can see where the opportunity fits in the topical map.
- `topic.list(project_id, status IN ['queued', 'approved', 'drafting', 'published'])` — the existing topic queue plus already-published topics. The skill dedupes against this list before emitting new rows: if a topic with the same `primary_kw` already exists for the project, the new opportunity merges into the existing topic's `runs.metadata_json.gsc_opportunity_finder.merged_into[]` list rather than creating a duplicate row.
- `article.list(project_id, status='published')` — every published article. The skill reads `slug`, `title`, `primary_kw`, `secondary_kws[]`, and `published_url` from each row; the canonical URL is built from the project's primary publish target's `public_url_pattern`. The published-URL list is the basis for the missing-intent and cannibalization detectors.
- `gsc.queryProject(project_id, since=<window start>, until=<window end>)` — the rolling 28-day rollup row at the project level. Returns one `GscMetricDaily`-shaped record per `(article_id, day)` pair plus the unattached query rows (rows where the GSC `page` did not match any of the project's published URLs). The handler reads from `gsc_metrics_daily` first; when the rollup is sparse for the requested window (some days missing, e.g., right after a fresh pull), the handler falls back to `gsc_metrics` raw rows for the missing days and aggregates inline. Quota cost is zero for the rollup path; live-API fallback consumes the GSC integration's qps budget per the wrapper's token-bucket (`default_qps=1.0`).
- `gsc.queryArticle(article_id, since=…, until=…)` — when a per-article slice is needed (the cannibalization detector compares two articles' query rosters; the low-CTR-rank-1 detector scopes to a single destination URL). Same rollup-first / live-fallback pattern as `queryProject`.
- `integration.test` and `integration.testGsc` — the pre-flight credential probes. The first checks that the project's `kind='gsc'` integration row carries a non-expired access token (the daemon's `jobs/oauth_refresh.py` should keep tokens fresh, but the skill double-checks). The second performs a probe Search Analytics call (`searchanalytics.query` with `dimensions=[]` and `rowLimit=1`) against the project's `site_url` to confirm the credential has access to that property; some accounts hold credentials for a property their token cannot read.
- `meta.enums` — surfaces `topics.source`, `topics.intent`, and `topics.status` so the skill can emit canonical strings rather than open-coding the enum values.

## Steps

1. **Read context.** Resolve the project and its `schedule_json` tuning knobs. Compute the window: `until = today - 1 day` (GSC has a one-day reporting lag), `since = until - schedule_json.gsc.window_days` (default 28). Record the window in the audit row so a future re-run can produce reproducible results. Run `integration.test` and `integration.testGsc` to confirm the credential is live; abort cleanly when the credential is dead and surface `runs.metadata_json.gsc_opportunity_finder.credential_dead=true` so procedure 6 can flag the project for re-auth.
2. **Hydrate the article roster.** Page through `article.list(project_id, status='published')` until the listing is exhausted. For each article, capture `id`, `slug`, `title`, `primary_kw`, `secondary_kws[]`, and the canonical URL (computed from the project's `is_primary=true` `publish_targets` row's `public_url_pattern` or `articles.canonical_target_id` when set). Build a URL-to-article-id map and a primary-keyword-to-article-id map. Both maps are used by the four detectors below.
3. **Pull the rollup.** Call `gsc.queryProject(project_id, since, until)`. Capture the row count, the unique-page count, and the unique-query count for the audit row. When the rollup returns zero rows, surface `runs.metadata_json.gsc_opportunity_finder.empty_rollup=true` and finish cleanly — a project newer than the window has nothing to detect.
4. **Detector 1 — Striking-distance queries.** A striking-distance query is one where the project's article ranks in positions 4 through 10 with high impression volume but a CTR below what the article would earn at position 1 to 3. The detector iterates the `(query, page)` rows and flags rows where `avg_position` is between 4.0 and 10.99 inclusive AND `impressions >= schedule_json.gsc.striking_distance.min_impressions` (default 100). For each flagged row, derive the opportunity:
   - **Quick-win subclass** — when the matching article's body already targets the query as a primary or secondary keyword. The opportunity is "tighten the existing article": refine the title, expand the relevant section, add internal links from related articles. The skill emits a topic with `intent='informational'` (or whatever intent the existing article carries), `primary_kw=<the GSC query>`, `secondary_kws=[<the existing article's primary_kw>]`, a `metadata.opportunity_kind='striking-distance-tighten'`, and a reference back to the matching article id so the human triaging the queue can see the article they should edit.
   - **Spillover subclass** — when the matching article's body does not currently target the query (the article ranks for it as a side-effect). The opportunity is "harvest the spillover into a new article": the rank-4-to-10 article is the parent and the new article is its spoke. Emit a topic with `primary_kw=<the GSC query>`, `cluster_id=<the parent's cluster_id>`, `metadata.opportunity_kind='striking-distance-spinoff'`, and a reference to the parent article id.
   Cap the detector at 50 striking-distance topics per run to keep the human review queue manageable; surplus candidates persist to `runs.metadata_json.gsc_opportunity_finder.striking_distance.dropped_over_cap[]` so a future run with adjusted floors can pick them up.
5. **Detector 2 — Low-CTR rank-1 queries.** A rank-1 article that earns substantially less click-through than its peers signals a weak title or meta description: the article ranks but does not convert. The detector aggregates per-page CTR for rows where `avg_position < 1.5` (effectively rank-1; allow 0.5 of fuzz for averaging across the window) AND `impressions >= schedule_json.gsc.low_ctr_rank1.min_impressions` (default 50). For each rank-1 page, compute the project's median CTR for rank-1 (across all rank-1 pages in the window). Flag any page whose CTR is below `median * (schedule_json.gsc.low_ctr_rank1.ctr_floor_pct / 100)` (default 60% of the median). For each flagged page, emit a topic with `primary_kw=<the page's top-impressions query>`, `intent='informational'` (rank-1 informational by default; commercial articles map to `commercial`), `metadata.opportunity_kind='low-ctr-rank-1'`, and a reference to the underperforming article id. The triage action is "rewrite the title and meta description" rather than "produce new content", but the topic queue is the right surface because procedure 7's content-refresher consumes the same `refresh_due` queue downstream.
6. **Detector 3 — Missing intents.** A query that earns impressions for the project but matches no published article on the project's domain is a content gap: search engines associate the project with the topic but the project has no destination URL. The detector iterates the `(query, page)` rows and identifies queries where every matching `page` falls outside the project's URL roster (the URL-to-article-id map from step 2 returns nothing for every page seen for this query). Aggregate impressions per query across the window; flag queries with `impressions >= schedule_json.gsc.missing_intent.min_impressions` (default 50). For each flagged query, classify the intent by heuristic against the query's surface form:
   - Question words (`how`, `what`, `why`, `when`, `where`, `which`) → `informational`.
   - Commercial modifiers (`best`, `top`, `vs`, `versus`, `review`, `comparison`, `cheapest`, `alternatives`) → `commercial`.
   - Transactional modifiers (`buy`, `pricing`, `cost`, `quote`, `signup`, `download`, `coupon`, `discount`) → `transactional`.
   - Brand mentions matching the project's `name` → `navigational`.
   - Otherwise → `mixed`.
   Emit a topic with `primary_kw=<query>`, the classified intent, `metadata.opportunity_kind='missing-intent'`, and the impression count for triage prioritisation. Cap at 30 missing-intent topics per run.
7. **Detector 4 — Cannibalization.** Two of the project's articles ranking for the same high-impression query split the click-share and confuse the search engine's canonical decision. The detector aggregates per-query the set of project URLs that earned impressions; flag queries where `len(unique_project_pages) >= schedule_json.gsc.cannibalization.min_overlap_articles` (default 2) AND the query has total impressions above the missing-intent floor (so trivial overlap doesn't generate noise). For each flagged query, identify the two-or-more articles competing, compute their relative impression / click share, and emit a single topic with `primary_kw=<query>`, `intent='informational'`, `metadata.opportunity_kind='cannibalization'`, `metadata.competing_article_ids=[id1, id2, …]`, and `metadata.consolidation_recommendation` set to either `'merge-into-leader'` (when one article carries 70%+ of the impressions; the others should redirect into it via the `redirects` table when the operator approves) or `'differentiate'` (when impressions are roughly even; the articles should be re-targeted to distinct sub-intents). The redirect itself is not the skill's write — the skill emits the topic as a triage signal; the human approves the action via the UI which then runs the consolidation procedure (a future procedure not in scope here). Cap at 20 cannibalization topics per run.
8. **Dedupe against the existing queue.** For each candidate topic the four detectors generated, query `topic.list(project_id, status IN ['queued', 'approved', 'drafting', 'published'])` filtered by `primary_kw` (case-insensitive). When a row already exists with the same primary keyword, do NOT emit a new topic; instead append the new opportunity's metadata under the existing row's `runs.metadata_json.gsc_opportunity_finder.merged_into[]` list (the existing row stays untouched in the `topics` table; the merge log lives in the audit row of THIS run). Avoid double-counting: a single `(detector, primary_kw)` pair contributes to the merge log at most once per run.
9. **Persist via `topic.bulkCreate`.** Compose the bulk-create payload from the surviving (post-dedupe) topics. Each row carries `project_id`, `cluster_id?` (set when the detector resolved a parent cluster), `title` (a human-readable one-liner derived from the detector kind: e.g., "Striking-distance: <query> at avg position 6.4"), `primary_kw`, `secondary_kws[]`, `intent`, `source='gsc-opportunity'`, `priority` (set per the impression-volume tier: 70 for queries above 1000 impressions, 50 for 100-1000, 30 for under 100), and the discovered metadata block. Bulk-create returns the ids; capture them for the audit row. The `topics.status` is `queued` by default — the human triaging the queue moves rows to `approved` before procedure 4 dispatches them through the production chain.
10. **Persist the audit row.** Write `runs.metadata_json.gsc_opportunity_finder = {window_since, window_until, articles_audited, rollup_rows_read, striking_distance: {found, dropped_over_cap}, low_ctr_rank_1: {found, median_ctr_used}, missing_intent: {found, dropped_over_cap}, cannibalization: {found, consolidation_recommendations}, topics_emitted_count, topics_merged_into_existing_count, credential_status, cost: {by_integration: {gsc: <usd>}}}`. The cost figure reads from the gsc integration's per-call cost recorder (the wrapper writes to `runs.metadata_json.cost.by_integration.gsc` after every call); the skill aggregates and surfaces the run-level total. Heartbeats fire after every detector pass so a long run on a project with thousands of GSC rows stays visible.
11. **Finish.** Call `run.finish` with `{project_id, window_since, window_until, topics_emitted, topics_merged, striking_distance_count, low_ctr_count, missing_intent_count, cannibalization_count, gsc_quota_remaining_estimate}`. The procedure-6 runner reads `topics_emitted` and continues into drift-watch (#21).

## Outputs

- `topics` — one row per surviving opportunity via `topic.bulkCreate`, with `source='gsc-opportunity'`, `status='queued'`, the discovered `primary_kw` / `intent` / `cluster_id?`, and the per-detector metadata block.
- `runs.metadata_json.gsc_opportunity_finder` — the per-detector counts, the dropped-over-cap lists, the cannibalization consolidation map, the credential status, and the GSC quota cost.

## Failure handling

- **No GSC integration row for the project.** Abort cleanly. Surface `runs.metadata_json.gsc_opportunity_finder.no_credential=true`. The procedure-6 runner advances to drift-watch (which has its own credential model via the project's Firecrawl integration); the operator wires GSC via the project bootstrap UI.
- **GSC credential expired and `oauth_refresh` could not refresh.** Same as no-credential: abort cleanly, surface `runs.metadata_json.gsc_opportunity_finder.credential_dead=true`. The operator re-authorises through the integrations UI.
- **GSC API returns 429 (quota exceeded).** The integration wrapper's token bucket should prevent this, but when it slips through (concurrent runs, manual API use outside the daemon), the skill retries once with a 60-second backoff. A second 429 aborts the detector that triggered it; surface `runs.metadata_json.gsc_opportunity_finder.<detector>.aborted_quota=true` and continue with the remaining detectors. Cannibalization is the lowest priority; striking-distance is the highest.
- **`topic.bulkCreate` rejects a duplicate-on-key.** Means the dedupe step missed a row that landed during the run (race with another concurrent skill, or a UI write). Drop the duplicate, log to the merge log, continue.
- **Striking-distance detector flags more than 200 candidates pre-cap.** Means the project's body of work is hugely under-tuned and the human review queue would explode. Cap is enforced at 50; the `dropped_over_cap[]` list captures the rest. Surface `runs.metadata_json.gsc_opportunity_finder.striking_distance.review_floor_recommended=true` so the operator can raise the impression floor in `schedule_json` and re-run with tighter selection.
- **Cannibalization detector flags a query where every competing article is in `refresh_due` status already.** The detector's recommendation can't run cleanly because the articles are already in the refresh pipeline. Surface in the topic's metadata as `metadata.refresh_pending=true`; the human triaging the queue waits for the refresh to land before approving the cannibalization action.
- **Median CTR for rank-1 cannot compute (zero rank-1 pages in the window).** The low-CTR-rank-1 detector skips entirely. Surface `runs.metadata_json.gsc_opportunity_finder.low_ctr_rank_1.skipped='no-rank-1-pages'` and continue.

## Variants

- **`fast`** — runs detectors 1 and 3 only (striking-distance + missing-intent); skips low-CTR-rank-1 and cannibalization. Useful when the project is in `bulk-content-launch` mode and the operator wants to feed the topic queue without spending detector cycles on optimisation candidates the bulk launch will outpace.
- **`standard`** — the default flow above with all four detectors.
- **`pillar-aware`** — biases the priority scoring toward queries whose intent classification matches a pillar that already exists in the project's cluster topology. The dedupe + cluster mapping at step 8 surface the pillar match; the variant raises the priority by 10 for matches and surfaces `metadata.pillar_aligned=true`. Useful for mature projects whose cluster strategy is the load-bearing organising principle.
- **`audit-only`** — runs every detector, persists the audit row, but does NOT emit topics. Used for periodic detector-tuning runs where the operator wants to inspect the candidate counts before committing to a queue dump.
