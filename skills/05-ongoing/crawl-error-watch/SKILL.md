---
name: crawl-error-watch
description: Iterate published articles, call the GSC URL Inspection API per page (or in batches via gsc.bulk_inspect when N>10), classify the verdict (PASS / PARTIAL / FAIL with reasons), and emit a topic with intent='technical-fix' for every FAIL or PARTIAL.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: codex-seo @ 97c59bcdac3c9538bf0e3ae456c1e73aa387f85a (clean-room; no upstream files read during authoring)
license: clean-room (PLAN.md L864 + docs/upstream-stripping-map.md adapt notes)
allowed_tools:
  - meta.enums
  - project.get
  - article.list
  - topic.bulkCreate
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
    write: one row per FAIL or PARTIAL via topic.bulkCreate with source='gsc-opportunity', intent='technical-fix', and the verdict reason in the metadata block.
  - table: runs
    write: per-article verdicts, the verdict-distribution histogram, the rate-limit reservation log, and the URL Inspection quota burndown in runs.metadata_json.crawl_error_watch.
---

## When to use

Procedure 6 (`weekly-gsc-review`) dispatches this skill once per project, after drift-watch (#21) has captured the week's element-bag baselines. The skill walks every `articles WHERE status='published' AND project_id=:p` row, calls the GSC URL Inspection API per page (or in batches when the roster exceeds 10), classifies each verdict, and emits topics for every FAIL or PARTIAL. The topics carry `intent='technical-fix'` to mark them as out-of-scope for content production but visible to the operator on the topic queue UI.

Crawl errors are technical issues — robots blocking, redirect loops, server errors, soft-404s, mobile-usability faults, rich-results malformations, canonical mismatches. The content-production pipeline (procedure 4) cannot fix these; the operator addresses them via the publish target's UI (WordPress / Ghost) or the publish target's repo (Nuxt). The skill's job is to surface the issue to the operator's queue, not to remediate.

The skill also runs as an operator-invoked one-off when the operator needs to confirm a single article's indexing state (the operator clicks "check indexing" on `ArticleDetailView.vue`). The contract is identical, scoped to one article id passed via args.

## Inputs

- `project.get(project_id)` — returns `domain` (composes the `siteUrl` parameter for the URL Inspection call), `locale`, and `schedule_json` for tuning knobs (`gsc.url_inspection.run_cap` defaulting to 100 per run to leave headroom in the 2000/day quota; `gsc.url_inspection.batch_threshold` defaulting to 10 below which the skill calls `gsc.queryArticle` per article and above which it batches).
- `article.list(project_id, status='published')` — every published article. The skill reads `id`, `slug`, `published_url`, `last_refreshed_at`, and `version`. Page through the listing for projects with hundreds of articles.
- `topic.list(project_id, status IN ['queued', 'approved'])` — used to dedupe verdicts before emitting new topics. A FAIL on the same article from a prior week is NOT re-emitted as a new topic if the prior topic is still `queued`; the skill instead increments the prior topic's `metadata.verdict_history[]` so the operator sees the issue is recurring.
- `gsc.queryArticle(article_id, since=…, until=…)` — wraps the URL Inspection API call. Returns the verdict object: `{verdict: 'PASS' | 'PARTIAL' | 'FAIL', coverage_state, robots_txt_state, indexing_state, page_fetch_state, mobile_usability, rich_results, canonical_mismatch_reason?, last_crawl_time}`. The wrapper enforces the project's per-integration QPS budget (`default_qps=1.0` for GSC) and accumulates cost into `runs.metadata_json.cost.by_integration.gsc`.
- `integration.test` and `integration.testGsc` — pre-flight credential probes. Same model as gsc-opportunity-finder (#20): the first checks the credential row is live, the second performs a probe Search Analytics call to confirm the credential has access to the project's GSC property. URL Inspection requires the same property authorisation; if the probe fails the inspection calls would 401 too.
- `meta.enums` — surfaces `topics.source`, `topics.intent`, `topics.status`, and the verdict enum strings the wrapper returns.

## Steps

1. **Read context.** Resolve the project and the tuning knobs. Run `integration.test` and `integration.testGsc`; abort cleanly when either fails. Capture the URL Inspection quota state — the wrapper exposes the per-day burndown figure on the integration row's `runs.metadata_json` accumulator. Refuse to start when the burndown is already above 1500/2000 (75% used) for the day; the skill respects the 100/run cap (default `schedule_json.gsc.url_inspection.run_cap`) but the absolute daily ceiling matters more.
2. **Hydrate the article roster.** Page through `article.list(project_id, status='published')` until the listing is exhausted. For each article, capture `id`, `slug`, `published_url`. Compose the `inspectionUrl` per article: it is the article's normalised canonical URL (the same normalisation rules drift-watch uses — lowercase scheme/host, strip default ports, sort query params, remove `utm_*`, strip trailing slash). The normalisation is critical because the URL Inspection API matches on the URL Google has indexed, which is itself canonicalised; an unnormalised input matches the unnormalised crawl and produces noise verdicts.
3. **Order the work.** Sort the article roster by `last_refreshed_at ASC NULLS FIRST` so the longest-untouched articles are inspected first; combined with the per-run cap (default 100), this gives the operator weekly coverage on a project of any size as the rotation cycles through.
4. **Decide single vs. batch.** Read the roster size (the bounded count after step 3 + the per-run cap). When `len(roster) >= schedule_json.gsc.url_inspection.batch_threshold` (default 10), the skill enters batch mode and uses the integration wrapper's `bulk_inspect(site_url, urls=[...])` (the wrapper fans out per-call internally because the GSC URL Inspection API has no native bulk endpoint, but the wrapper handles QPS pacing in one place). When the roster is under the threshold, the skill calls `gsc.queryArticle` (which routes to the wrapper's single-URL `inspect_url`) per article. The two paths produce identical verdict objects; the difference is purely in how the wrapper paces the calls.
5. **Inspect each URL.** For each article in the roster (or each batch), capture the verdict object the wrapper returns. The verdict is a structured envelope with these fields:
   - `verdict` — one of `PASS` (the page is indexed and serving correctly), `PARTIAL` (the page is indexed but with caveats — e.g., mobile usability warnings, rich-result eligibility loss), `FAIL` (the page is not indexed or is failing to serve).
   - `coverage_state` — Google's classification of the page's coverage: `INDEXING_ALLOWED`, `BLOCKED_BY_ROBOTS_TXT`, `BLOCKED_BY_NOINDEX`, `CRAWLED_NOT_INDEXED`, `DISCOVERED_NOT_INDEXED`, `EXCLUDED_BY_NOINDEX_TAG`, `SOFT_404`, `URL_HAS_NOFOLLOW`, etc. (the actual Google enum is more detailed; the skill normalises to the canonical strings here for the audit row).
   - `robots_txt_state` — `ALLOWED` or `DISALLOWED`.
   - `indexing_state` — `INDEXING_ALLOWED`, `INDEXING_DISALLOWED`, `BLOCKED_BY_META_TAG`.
   - `page_fetch_state` — `SUCCESSFUL`, `SOFT_404`, `BLOCKED_ROBOTS_TXT`, `NOT_FOUND`, `ACCESS_DENIED`, `SERVER_ERROR`, `REDIRECT_ERROR`, `ACCESS_FORBIDDEN`, `BLOCKED_4XX`, `INTERNAL_CRAWL_ERROR`, `INVALID_URL`.
   - `mobile_usability` — `MOBILE_FRIENDLY` or `NOT_MOBILE_FRIENDLY` plus a list of specific issues when not friendly.
   - `rich_results` — `VALID`, `INVALID`, or `UNKNOWN` plus the items the page emits.
   - `canonical_mismatch_reason` — when the user-declared canonical disagrees with Google's selected canonical; null when there is no mismatch.
   - `last_crawl_time` — ISO timestamp; useful for staleness diagnosis.
   Capture the verdict in `runs.metadata_json.crawl_error_watch.per_article[article_id] = {verdict, coverage_state, robots_txt_state, indexing_state, page_fetch_state, mobile_usability, rich_results, canonical_mismatch_reason?, last_crawl_time, inspection_url}`.
6. **Classify FAIL versus PARTIAL.** Many `verdict` envelopes return PARTIAL for things the operator should still address. The skill applies a normalisation pass:
   - `verdict='FAIL'` always emits a topic.
   - `verdict='PARTIAL'` emits a topic when any of: `mobile_usability='NOT_MOBILE_FRIENDLY'`, `rich_results='INVALID'`, `canonical_mismatch_reason` is non-null. Other PARTIAL states log to the audit row but do not emit a topic (e.g., a soft warning about an HTTPS-mixed-content issue surfaces but does not necessarily warrant a topic).
   - `verdict='PASS'` never emits a topic but the audit row captures the verdict for the trend.
7. **Compose the topic per FAIL / PARTIAL.** For each article needing a topic:
   - `title` — a human-readable one-liner: e.g., "Crawl FAIL: <slug> — <coverage_state>" or "Crawl PARTIAL: <slug> — mobile-usability".
   - `primary_kw` — the article's `primary_kw` (the topic is about the existing article's technical state, not a new keyword). The keyword preserves the cluster context.
   - `secondary_kws` — empty.
   - `intent` — `technical-fix` (the dedicated enum value for technical issues — call out: this enum value is added to `topics.intent` per PLAN.md Schema § enums; the M3 enum landed `informational | commercial | transactional | navigational | mixed` and the M6 wave extends it with `technical-fix` per the audit. When the live enum still rejects `technical-fix`, fall back to the article's existing intent and surface `runs.metadata_json.crawl_error_watch.intent_fallback_count` so the schema follow-up is visible).
   - `source` — `gsc-opportunity` (the cross-cutting GSC trio writes under the same provenance string per PLAN.md L386).
   - `priority` — derived from severity: 90 for FAIL, 60 for PARTIAL with a critical subreason (mobile-usability / canonical-mismatch / rich-results), 40 for PARTIAL with a soft subreason.
   - `metadata.opportunity_kind` — `'crawl-error'`.
   - `metadata.verdict` — the full verdict envelope captured at step 5.
   - `metadata.recommended_action` — a templated string keyed off the dominant failure reason: e.g., `'unblock-in-robots-txt'` for `BLOCKED_BY_ROBOTS_TXT`, `'fix-server-error'` for `page_fetch_state='SERVER_ERROR'`, `'fix-mobile-usability'` for the mobile path, `'fix-rich-results-malformed'` for `rich_results='INVALID'`, `'reconcile-canonical'` for canonical-mismatch, `'investigate-soft-404'` for `SOFT_404`. The triage UI surfaces the recommendation as a hint to the operator.
   - `metadata.article_id` — the affected article id (so the UI can link directly to the article detail page).
8. **Dedupe against the existing queue.** For each candidate topic, check `topic.list(project_id, status IN ['queued', 'approved'])` filtered by `metadata.article_id` and `metadata.opportunity_kind='crawl-error'`. When a row already exists, do NOT emit a new topic; instead, the new verdict appends to the existing topic's `metadata.verdict_history[]` (the audit row of THIS run records the merge). The dedupe is keyed on `(article_id, opportunity_kind)` rather than on `primary_kw` because the same article can have multiple consecutive FAIL verdicts and the operator needs to see the recurrence pattern, not duplicate rows.
9. **Persist via `topic.bulkCreate`.** Compose the bulk-create payload from the surviving (post-dedupe) candidates. Bulk-create returns the ids; capture for the audit row. The `topics.status` is `queued` by default; the human triages on the queue UI.
10. **Persist the audit row.** Write `runs.metadata_json.crawl_error_watch = {articles_inspected, verdict_distribution: {pass, partial, fail}, topics_emitted, topics_merged_into_existing, per_article_verdicts: [...], failure_reasons: {robots_blocked, redirect_loop, server_error, soft_404, mobile_usability, rich_results_invalid, canonical_mismatch}, quota_consumed, quota_remaining_estimate, cost: {by_integration: {gsc: <usd>}}}`. Heartbeats fire after every 25 inspections so a long run on a 100-article project stays visible.
11. **Finish.** Call `run.finish` with `{project_id, articles_inspected, verdict_pass_count, verdict_partial_count, verdict_fail_count, topics_emitted, topics_merged, quota_remaining_estimate}`. The procedure-6 runner reads the counts and concludes the weekly review.

## Outputs

- `topics` — one row per surviving FAIL / PARTIAL via `topic.bulkCreate` with `source='gsc-opportunity'`, `intent='technical-fix'`, and the verdict envelope in the metadata block.
- `runs.metadata_json.crawl_error_watch` — the per-article verdicts, the verdict distribution, the failure-reason histogram, the quota burndown, and the cost figure.

## Failure handling

- **GSC credential dead.** Abort cleanly. Surface `runs.metadata_json.crawl_error_watch.credential_dead=true`. Procedure 6 concludes; the operator re-authorises through the integrations UI.
- **URL Inspection quota exhausted.** When the per-day burndown reaches 2000 or the per-run cap (default 100) is reached, stop inspecting further articles. Persist what was inspected; surface `runs.metadata_json.crawl_error_watch.quota_exhausted=true` and the count of un-inspected articles. The next weekly run picks up where this run left off (the `last_refreshed_at ASC NULLS FIRST` ordering rotates the audit through the roster across runs).
- **Single inspection returns 5xx.** Retry once with a 60-second backoff. Two consecutive 5xx aborts that article's inspection and continues with the next; surface in `runs.metadata_json.crawl_error_watch.inspection_errors[]` with the URL and the error code.
- **Single inspection returns 4xx.** Means the URL is not in a property the credential can read (the operator wired GSC for a sibling property). Capture in `runs.metadata_json.crawl_error_watch.unauthorised_urls[]`; do not retry. The operator either fixes the property mapping or excludes the URL from the audit.
- **Verdict envelope arrives malformed.** Means the GSC API changed the response shape and the wrapper has not caught up. Capture the raw response in `runs.metadata_json.crawl_error_watch.malformed_envelopes[]`; surface to engineering. Do not abort; continue with the next article.
- **`topic.bulkCreate` rejects `intent='technical-fix'` (the enum value not yet wired).** Fall back per step 7's guidance: emit the topic with the article's existing intent and increment `runs.metadata_json.crawl_error_watch.intent_fallback_count`. The audit row's distinct field surfaces the migration follow-up to engineering.
- **Project has zero published articles.** Surface `runs.metadata_json.crawl_error_watch.empty_roster=true` and finish cleanly.
- **Article has no `published_url` resolvable from the canonical target or `is_primary` target row.** Skip and continue; surface in `runs.metadata_json.crawl_error_watch.unresolvable_urls[]`. The article was published to a target that has since been removed; the operator cleans up via the publish-targets UI.
- **A given article has been verdict='FAIL' for three consecutive weekly runs.** The skill emits the topic as usual but flags `metadata.recurrence_count=3` so the triage UI promotes it to a high-visibility lane; the operator's failure-handler may also auto-page when the count reaches 5+ (the paging configuration lives elsewhere; the skill just flags the recurrence).

## Variants

- **`fast`** — runs the inspection but only emits topics for FAIL verdicts; PARTIAL verdicts persist to the audit row without writing topics. Useful when the project's PARTIAL volume is high and the operator has agreed to triage them out-of-band.
- **`standard`** — the default flow above with FAIL + critical-PARTIAL emit.
- **`exhaustive`** — disables the per-run cap (default 100) and inspects every article in the roster. Quota-aware: still respects the per-day 2000 ceiling. Useful for the first audit on a new project where the operator wants full coverage, and accepts the quota burn.
- **`single-article`** — invoked from `ArticleDetailView.vue` against one article id. Skips the dedupe + bulk-create paths; surfaces the verdict directly to the UI without writing a topic. Useful for ad-hoc triage where the operator knows the issue and just wants the verdict for confirmation.
