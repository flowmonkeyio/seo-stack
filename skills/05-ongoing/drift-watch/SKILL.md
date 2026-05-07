---
name: drift-watch
description: Snapshot the live HTML for every published article via Firecrawl, capture the canonical element bag (title / meta / canonical / robots / headings / schema_hash / og / cwv / status / html_hash), call drift.diff against the prior baseline when the comparison engine is live, and persist severity-classified findings to drift_baselines.current_score.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: codex-seo @ 97c59bcdac3c9538bf0e3ae456c1e73aa387f85a (clean-room; no upstream files read during authoring)
license: clean-room (PLAN.md L863 + docs/upstream-stripping-map.md adapt notes)
allowed_tools:
  - meta.enums
  - project.get
  - article.list
  - article.get
  - drift.snapshot
  - drift.list
  - drift.get
  - drift.diff
  - integration.test
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
  - table: drift_baselines
    write: one row per audited article via drift.snapshot capturing the element bag; the row's current_score is updated by drift.diff (or left null when the comparison engine is the M6 deferral path).
  - table: runs
    write: per-article diff verdicts, severity counts, response-time targets, the URL-normalisation log, and any Firecrawl fetch failures in runs.metadata_json.drift_watch.
---

## When to use

Procedure 6 (`weekly-gsc-review`) dispatches this skill once per project, after gsc-opportunity-finder (#20) has filed the week's queue updates. The skill walks every `articles WHERE status='published' AND project_id=:p` row, fetches the canonical published URL via Firecrawl, captures the element bag the comparison framework operates on, and either calls `drift.diff` (when the M6 comparison engine is live) or stops at snapshot capture (the M6 deferral path; the skill remains useful even without the diff because the snapshot history is what the engine eventually compares against).

Procedure 7 (`monthly-humanize-pass`) re-dispatches the skill against any single article being refreshed: the article's pre-refresh and post-refresh snapshots both feed the baseline so the operator can audit what the refresh changed at the rendered-HTML level. The operator can also trigger a single-article snapshot from `ArticleDetailView.vue` when they suspect a rogue WordPress edit; the contract is identical, scoped to one article id passed via args.

The skill graceful-degrades when `drift.diff` raises `MilestoneDeferralError` (the M6 deferral path documented in `content_stack/mcp/tools/gsc.py:_drift_diff`). In that mode the skill runs every step except the diff itself: it captures the snapshot, persists the element bag to `drift_baselines`, surfaces a deferred-diff warning to the operator via `runs.metadata_json.drift_watch.diff_deferred=true`, and exits cleanly. When the comparison engine lands in a follow-up milestone, the diff path activates without skill changes — the skill calls `drift.diff` first; only the deferral-error catch flips to the snapshot-only path.

## Inputs

- `project.get(project_id)` — returns `domain` (used to recognise off-project URLs that should not be audited; some publish targets cross-post to mirror domains and the audit must scope to the project's primary), `locale`, and `schedule_json` for tuning knobs (`drift.cwv.enabled` defaulting to true when the Firecrawl integration is on a tier that returns Web Vitals; `drift.fetch.timeout_seconds` defaulting to 30; `drift.severity_floors.critical` / `.warning` / `.info` defaulting to the rule-derived floors documented in step 4).
- `article.list(project_id, status='published')` — every published article. The skill reads `id`, `slug`, `published_url` (the publish step persisted the URL to `article_publishes.published_url`; the `articles` row carries it indirectly via the canonical target's `public_url_pattern` — both are valid sources), `last_refreshed_at`, and the `version` so the audit row can record which version was live when the snapshot was captured. Page through the listing for projects with hundreds of articles.
- `article.get(article_id)` — when the skill needs `edited_md` to compute the expected-content reference for the diff (the engine compares the live HTML against the intent of the editor's output, not against a prior snapshot only). The `edited_md` is the stable baseline we wrote; `drift_baselines.baseline_md` is the rendered baseline against which subsequent live captures are diffed.
- `drift.snapshot(article_id, baseline_md=<captured element bag serialised>)` — writes a `drift_baselines` row. The `baseline_md` field carries the serialised element bag (title, meta description, canonical href, meta robots, the heading lists, the schema hash, the open-graph block, the CWV numbers when available, the HTTP status code, and the html_hash). The serialisation format is canonical JSON sorted by key so two equivalent captures hash identically downstream.
- `drift.list(article_id)` — reads the article's snapshot history. The skill walks the list to find the most recent `current_score` baseline (the diff's prior comparison point) and reads the captured-at timestamps to decide whether the new snapshot supersedes the prior one.
- `drift.get(baseline_id)` — fetch one baseline by id when the diff needs the full prior element bag rather than just the metadata `drift.list` returns.
- `drift.diff(baseline_id, current_md)` — the comparison call. Returns a structured diff (per-rule findings + severity + response-time recommendation) plus the new `current_score`. Until the M6 comparison engine lands, this raises `MilestoneDeferralError` which the skill catches and routes to the snapshot-only path.
- `integration.test` — pre-flight Firecrawl probe. The wrapper's `test()` call confirms the credential is live before the audit walks the article roster. The skill aborts cleanly when the probe fails because every subsequent fetch would 401.
- `meta.enums` — surfaces `drift_baselines.severity` (the enum the diff returns) and `runs.kind='drift-check'` so the skill emits canonical strings.

## Steps

The skill captures one canonical element bag per article and wires the diff against the prior baseline. The element bag is the load-bearing data structure; the bag's contents are listed in step 4 below and the URL-normalisation rules in step 3 are factual constants we adopt verbatim from the codex-seo strip-map's documented reuse list (PLAN.md row #21 KEEP map).

1. **Read context.** Resolve the project, confirm the Firecrawl credential via `integration.test`. When the test fails, abort cleanly with `runs.metadata_json.drift_watch.firecrawl_dead=true`. Read the article roster page-by-page; capture the count for the audit row.
2. **Order the work.** Sort the article roster by `last_refreshed_at ASC NULLS FIRST` — the longest-untouched articles are the highest drift-risk because the operator forgot they exist. Capture the order in the audit row so a re-run can reproduce the walk.
3. **URL normalisation.** For each article's `published_url`, normalise per the canonical rules:
   - Lowercase the scheme and host (URLs are case-insensitive in their scheme + host but case-sensitive in their path).
   - Strip the default port when it matches the scheme (`:80` for http, `:443` for https).
   - Sort the query parameters lexicographically by key.
   - Remove every `utm_*` key (campaign tracking; not part of the canonical URL).
   - Remove the trailing slash from the path when the path is non-root and ends with `/`.
   The normalised URL is what the audit fetches. The pre-normalised URL is captured in the audit row so a future audit can detect a normalisation regression.
4. **Capture the live HTML.** Call the Firecrawl scrape endpoint via the integrations wrapper for the normalised URL. The wrapper enforces the project's per-integration QPS budget; long projects with hundreds of articles take time, so heartbeats fire every 10 articles. The wrapper returns the raw HTML, the HTTP status code, and the rendered metadata bag (title, meta description, canonical, robots, headings, schema, open graph, CWV when available). Compose the canonical element bag for the article:
   - **title** — the `<title>` element's text, trimmed and unicode-normalised (NFC).
   - **meta_description** — the `<meta name="description" content="…">` content, trimmed and NFC-normalised. Empty string when absent.
   - **canonical** — the `<link rel="canonical" href="…">` value. The drift signal is canonical-mismatch (the page declares a different canonical than its own URL); the diff returns CRITICAL severity for any change here because canonical drift breaks search-engine indexing.
   - **meta_robots** — the `<meta name="robots" content="…">` directives (lowercase, comma-split, sorted). The drift signal is `noindex` appearing where it was previously absent (a rogue edit can deindex a page silently).
   - **h1[]** — the H1 elements' text in document order. Most pages have exactly one; multiple H1s are an SEO smell and the diff flags them.
   - **h2[]** — the H2 elements' text in document order.
   - **h3[]** — the H3 elements' text in document order.
   - **schema_emits_hash** — SHA-256 of the canonical-sorted JSON of every JSON-LD `<script type="application/ld+json">` block on the page, concatenated. Schema drift is one of the most actionable signals because rich-result eligibility depends on the JSON-LD shape.
   - **open_graph** — a key-sorted dict of every `<meta property="og:*">` attribute the page declared.
   - **cwv** — Core Web Vitals (`lcp`, `fid_or_inp`, `cls`) from Firecrawl's CWV endpoint when the integration tier permits and `schedule_json.drift.cwv.enabled=true`. Captured as a numeric triple plus a fetch timestamp; null when unavailable.
   - **status_code** — the HTTP response status. Anything outside 200 is a diff signal (a 404 / 410 / 500 on a published URL is an outage).
   - **html_hash** — SHA-256 of the body HTML after stripping scripts, styles, comments, and whitespace runs. The hash is the cheap "did anything change" signal; the bag's other fields explain what.
   Serialise the bag to canonical JSON (sorted keys, no extra whitespace) and call `drift.snapshot(article_id, baseline_md=<canonical_json_string>)`. The repository writes the baseline row; capture the returned `baseline_id`.
5. **Run the diff.** Call `drift.diff(baseline_id, current_md=<canonical_json_string of the new bag>)`. The comparison engine walks the 17-rule comparison framework and returns `{rules: [{rule_id, severity, finding, response_time}], severity_max, current_score}`. The 17 rules cover the bag's fields end-to-end:
   - **Rules 1-3 (CRITICAL)** — canonical mismatch, status-code change to 4xx/5xx, meta_robots `noindex` regression. Response-time target: within 24 hours.
   - **Rules 4-9 (WARNING)** — title change, meta_description change, h1[] change, schema_emits_hash change, open_graph change, html_hash change beyond a threshold (the engine accepts cosmetic CSS-only changes silently; the threshold is the engine's tuning knob). Response-time target: within 7 days.
   - **Rules 10-17 (INFO)** — h2[] / h3[] reorder, cwv regression below the engine's tier threshold, open_graph image URL change with the same image hash, NFC-only string changes (rendered-vs-stored normalisation differences), trailing-whitespace differences. Logged only.
   The rule numbers above are the canonical bucket boundaries; each engine version may add or split rules within the buckets. The skill does NOT enumerate the rule prose — that lives in the comparison engine.
   Persist the diff verdict to `runs.metadata_json.drift_watch.per_article[article_id] = {baseline_id, severity_max, rules_fired, current_score, response_time_target}`.
6. **Update the score.** When the diff returned a verdict, the engine has already updated `drift_baselines.current_score` for the new row. The skill audits the prior row's score for the same article (read via `drift.list` filtered to the prior baseline_id) and computes the score delta; when the delta exceeds the project's `schedule_json.drift.score_alert_delta` (default 30 points, lower-is-worse), surface in `runs.metadata_json.drift_watch.score_alerts[]` so procedure 6's failure handler can raise the alert in the operator's UI.
7. **M6 deferral handling.** When `drift.diff` raises `MilestoneDeferralError` (the M6-deferral path until the comparison engine lands), the skill catches the error and routes to the snapshot-only path:
   - The snapshot from step 4 is already persisted; it is the diff engine's input when the engine eventually lands.
   - The audit row carries `runs.metadata_json.drift_watch.diff_deferred=true` and `runs.metadata_json.drift_watch.per_article[article_id] = {baseline_id, severity_max: null, rules_fired: 0, current_score: null, response_time_target: null}`.
   - The skill emits a single warning to the operator (visible on `RunsView.vue`'s detail panel) summarising the deferral so they understand the audit ran but the comparison did not.
   - When the operator runs the skill again after the engine lands, the prior baseline is still on disk; the diff comparison runs against the most recent prior snapshot.
8. **Severity-driven response queueing.** For each CRITICAL or WARNING verdict, the skill emits a `runs.metadata_json.drift_watch.response_queue[]` entry with `{article_id, severity, response_time_target_iso, recommended_action, rules_fired}`. The actions map per severity:
   - CRITICAL → procedure 7's content-refresher (#24) is the responder; the article gets pushed to `refresh_due` via `article.markRefreshDue` so the next pass picks it up. (The `markRefreshDue` call is the responsibility of skill #23 (refresh-detector) when its scoring window picks the article up; drift-watch surfaces the recommendation via the response-queue without writing to `articles` directly.)
   - WARNING → the operator's UI surfaces the article on `DriftView.vue` for human triage; the human decides whether to refresh or override.
   - INFO → logged only; no operator action.
   The split is intentional: drift-watch's job is to detect drift, not to drive the refresh pipeline. Refresh-detector (#23) reads drift baselines as one of its three inputs and consolidates the signal.
9. **Persist the audit row.** Write `runs.metadata_json.drift_watch = {articles_audited, articles_fetched, articles_fetch_failed, snapshots_taken, diffs_run, diffs_deferred, severity_counts: {critical, warning, info}, response_queue, score_alerts, top_drifts: [...top 5 by severity then current_score], cost: {by_integration: {firecrawl: <usd>}}}`. The cost figure reads from the Firecrawl integration's per-call cost recorder. Heartbeats fire every 10 articles so a long audit on a 200-article project stays visible.
10. **Finish.** Call `run.finish` with `{project_id, articles_audited, snapshots_taken, diffs_run, diffs_deferred, critical_count, warning_count, info_count, score_alerts_count}`. The procedure-6 runner reads the counts and continues into crawl-error-watch (#22).

## Outputs

- `drift_baselines` — one row per audited article via `drift.snapshot`, carrying the canonical element bag in `baseline_md` and (when the diff ran) the new `current_score`.
- `runs.metadata_json.drift_watch` — the per-article diff verdicts, the severity counts, the response queue, the score-alert list, and the cost figure.

## Failure handling

- **Firecrawl credential dead.** Abort cleanly. Surface `runs.metadata_json.drift_watch.firecrawl_dead=true`. The procedure-6 runner skips this skill but continues into crawl-error-watch (#22) which uses the GSC credential, not Firecrawl.
- **Single article fetch fails (network error / Firecrawl 5xx).** Retry once with a 30-second backoff. Two consecutive failures abort the snapshot for that article and continue with the next; surface in `runs.metadata_json.drift_watch.fetch_failures[]` with the URL, the error code, and the retry count. The audit does not abort because of a single fetch — partial coverage is better than no coverage.
- **Article fetch returns a non-200 status.** Capture the status code in the bag's `status_code` field and continue with the snapshot. The diff engine will flag the change to a non-200 as a CRITICAL drift signal at the next comparison; the snapshot itself succeeds because the bag accommodates the failure mode by design.
- **`drift.diff` raises `MilestoneDeferralError`.** Documented behaviour. Catch, route to snapshot-only path (step 7), continue with the next article. The skill exits successfully with `diff_deferred=true` set.
- **`drift.diff` raises a non-deferral error.** Means the comparison engine is live but rejected the bag (e.g., schema mismatch between an old serialisation and a new engine version). Capture in `runs.metadata_json.drift_watch.diff_errors[]`; surface to the operator. The snapshot is still on disk; the operator can re-run the skill after the engine fix.
- **`drift.snapshot` rejects the row.** Means the article id is gone (the article was hard-deleted between `article.list` and the snapshot — rare but possible). Skip and continue; surface in `runs.metadata_json.drift_watch.skipped_articles[]`.
- **Element bag serialisation diverges between two equivalent captures.** Detected when re-running the skill produces different `baseline_md` hashes for the same article without a real page change. Means the canonical-JSON encoder regressed; the engine's diff would over-report. Surface in `runs.metadata_json.drift_watch.serialisation_warnings[]`; do not abort. The operator escalates to engineering.
- **CWV unavailable for an article (Firecrawl tier missing the CWV endpoint).** Set the `cwv` field to null and continue. The diff engine treats null-to-null as no-change and null-to-numeric as a transition (logged INFO when the tier upgrade lands).
- **Project has zero published articles.** Surface `runs.metadata_json.drift_watch.empty_roster=true` and finish cleanly. Procedure 6 advances; the project simply has no live URLs to audit yet.

## Variants

- **`fast`** — captures snapshots but skips the diff entirely (treat as if `MilestoneDeferralError` always fires). Useful for the first run on a new project where there is no prior baseline to compare against; the skill's job in that mode is to seed the baseline history.
- **`standard`** — the default flow above, full snapshot + diff + severity routing.
- **`critical-only`** — runs the full snapshot + diff but only emits response-queue entries for CRITICAL severity; WARNING and INFO findings persist to the audit row but do not drive operator UI alerts. Useful when the project's drift volume is high and the operator wants to focus on the actionable subset.
- **`single-article`** — invoked from procedure 7 against a refresh candidate. The skill scopes to one article id passed via args; the snapshot + diff still run identically but the response-queue routing skips because procedure 7 is already driving a refresh.
