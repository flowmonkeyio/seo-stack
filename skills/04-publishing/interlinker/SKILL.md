---
name: interlinker
description: Run the seven-step internal-linking workflow over the project's published articles, score the link graph against orphan / anchor-distribution / cluster-pattern targets, and emit suggested links via interlink.suggest for human approval before applying.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: seo-geo-claude-skills @ 7ecc77b181190fe17a8e3c22a5f6fe705569dc09 (Apache-2.0 reference; CORE-EEAT R08 link-graph rubric + the 7-step workflow + anchor-distribution and required-link-pattern tables — re-authored against our internal_links table, suggest-then-apply pattern, and clusters / topics rows)
license: Apache-2.0 reference (PLAN.md L857 + docs/upstream-stripping-map.md adapt notes; full attribution in docs/attribution.md and NOTICE)
allowed_tools:
  - meta.enums
  - project.get
  - cluster.list
  - topic.list
  - article.list
  - article.get
  - interlink.suggest
  - interlink.list
  - interlink.repair
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
  article_id:
    source: env
    var: CONTENT_STACK_ARTICLE_ID
    required: false
    description: When supplied, the suggester scopes contextual-link analysis to one article (procedure-4 mode); when absent, the auditor walks the full project (procedure-6 / standalone mode).
outputs:
  - table: internal_links
    write: one row per suggestion via interlink.suggest with status='suggested'; rows transition to applied via the human-driven interlink.apply path.
  - table: runs
    write: per-step diagnostic counts + scores + the orphan / over-optimised-anchors / pillar-spoke pattern report in runs.metadata_json.interlinker.
---

## When to use

Procedure 4 dispatches this skill after the schema-emitter (#16) and before the active publish skill (#17 / #18 / #19). At that point the article is `eeat_passed`, has a body fixed by the editor, and is about to acquire its canonical URL — the perfect moment to plant the inbound and outbound link suggestions the post will carry into publication. The article-scoped mode runs all seven steps but the contextual-link search (step 5) and the implementation plan (step 7) are scoped to the single article; the other steps still see the full project graph because orphan and anchor analysis only make sense globally.

Procedure 6 (`weekly-gsc-review`) and the operator's UI also dispatch this skill in project-wide mode. In that mode every step audits the full graph; the output is a project-level repair plan plus a fan-out of contextual-link suggestions across whichever articles need new inbound links to clear orphan or under-linked status. The repair plan is informational; the actual writes are still suggestions the operator approves through the UI.

The skill operates only over `articles WHERE status='published' AND project_id=:active`. Drafts are excluded — there is no value in suggesting links into or out of an article that is not yet live, and the suggester would generate stale rows the moment the draft was rewritten.

## Inputs

- `project.get(project_id)` — returns the project's `domain` (used to render absolute URLs when the suggester emits its plan), the project's preferred locale (some anchor patterns are locale-sensitive — German nominal compounds vs. English noun phrases differ), and the cluster strategy hint when set on the project row.
- `cluster.list(project_id)` — every cluster the project has, including the parent / child topology. The suggester reads `cluster.type` to identify pillars (`type='pillar'`), spokes (`type='spoke'`), hubs (`type='hub'`), and the comparison / resource clusters that participate in cross-link patterns. Each cluster carries a `parent_id` field that wires spokes to their pillar.
- `topic.list(project_id, status IN ['published'])` — the topic queue restricted to topics whose article has shipped. Each topic carries the `cluster_id` linking it to its pillar / spoke / hub group; the suggester uses this to map articles into clusters when the article row alone does not carry the link.
- `article.list(project_id, status='published', limit=…)` — every published article in the project. Each row carries `id`, `slug`, `title`, `cluster_id` (the topic's cluster, copied at create time), `published_at`, `last_refreshed_at`, and the `primary_kw` / `secondary_kws[]` extracted from `brief_json`. Page through the listing for projects with hundreds of published articles.
- `article.get(article_id)` (procedure-4 article-scoped mode only) — returns the focal article's `edited_md`, brief, slug, and cluster id. The suggester walks the body for contextual link opportunities that target other published articles.
- `interlink.list(project_id, status=…)` — the current link graph. The suggester reads two slices: `status='applied'` (the live inbound / outbound graph the audit measures) and `status='suggested'` (already-pending suggestions the suggester must not duplicate).
- `meta.enums` — surfaces `cluster.type`, `internal_links.status`, and the canonical anchor-type labels the rubric reports.

## Steps

The seven-step workflow is the load-bearing structure of the skill. Each step persists a sub-section of `runs.metadata_json.interlinker` under `step1` … `step7`; the implementation plan (step 7) reads the sub-sections of the prior six and composes the final report.

1. **Analyze the current link structure.** For every published article, count its applied inbound and outbound link totals (`interlink.list` filtered by status), compute the average inbound count across the project (target benchmark: at least 3 incoming applied links per post — see CORE-EEAT R08 below), the average outbound count, and the median click-depth from the project's homepage / hub pages to each article. Surface the top ten articles by inbound count (the project's authority hubs) and the bottom ten (under-linked candidates). The structure score is a 0–100 number combining inbound-coverage, outbound-density, and click-depth; the suggester does not surface the precise formula in the SKILL — the repository computes it from the same inputs and the score is informational only. Write `runs.metadata_json.interlinker.step1 = {avg_in, avg_out, median_depth, top_inbound[], bottom_inbound[], structure_score}`.
2. **Identify orphan pages.** Run the orphan query: `articles WHERE status='published' AND id NOT IN (SELECT to_article_id FROM internal_links WHERE status='applied' AND to_article_id IS NOT NULL)` for the active project. The hard target is zero orphans: any published article without a single applied inbound link is an orphan and gets surfaced. Bucket each orphan into one of three priorities:
   - **High-value** — has GSC impressions in the last 28 days OR has been published more than 90 days OR is a pillar / hub. These need inbound links urgently.
   - **Medium-potential** — published less than 90 days, no GSC traffic yet, not a pillar / hub. Plant inbound links from cluster siblings; revisit at the next weekly run.
   - **Low-value** — orphan AND no impressions AND no recency tail (published > 365 days). Recommend redirect-or-delete; the suggester does not delete on the user's behalf, only flags.
   Write `runs.metadata_json.interlinker.step2 = {orphan_count, by_priority: {high: [...], medium: [...], low: [...]}}`. The `[]` entries carry `{article_id, slug, cluster_id, published_at, impressions_28d?}`.
3. **Anchor text distribution analysis (CORE-EEAT R08 alignment).** Walk the applied link graph and compute, per `to_article_id`, the distribution of anchor-text types across its inbound links. Each anchor is classified into one of four buckets based on how it relates to the destination article's `primary_kw`:
   - **Exact match** — the anchor equals the primary keyword (case-insensitive, punctuation-insensitive). Target distribution: 10–20% of inbound anchors.
   - **Partial match** — the anchor contains the primary keyword as a sub-string but adds modifiers (e.g., "best <kw> for 2026"). Target distribution: 30–40%.
   - **Branded** — the anchor names the project / brand explicitly. Target distribution: 10–20%.
   - **Natural** — descriptive non-keyword anchors (e.g., "this checklist", "the full guide", "see the worked example"). Target distribution: 20–30%.
   Over-optimised anchors are exact-match anchors above the 20% ceiling; the project-wide over-optimisation rate must stay below 10% across the full applied graph. Surface every destination article whose distribution exits the bands, name the most over-optimised anchors, and flag generic anchors ("click here", "read more") as `partial` violations because they add no relevance signal. Write `runs.metadata_json.interlinker.step3 = {distribution: {exact, partial, branded, natural}, over_optimisation_pct, ambiguous_anchors: [...], generic_anchors_count}`. The bands above are factual constants; do not paraphrase them away.
4. **Topic-cluster link strategy.** For each cluster of `type='pillar'`, audit the bidirectional pillar-spoke pattern and the cluster-cluster cross-links. The required-link-pattern table is load-bearing:
   - **Pillar → cluster** — every spoke in the cluster must have at least one applied inbound link from its pillar. Pillar pages that fail to link out to every spoke in their own cluster are the most common topical-authority gap.
   - **Cluster → pillar** — every spoke must have at least one applied outbound link back to its pillar. Reciprocity is what cements the cluster.
   - **Cluster ↔ cluster** — when two clusters share an audience (e.g., "email marketing" and "marketing automation"), at least one cross-link in each direction is recommended; not strictly required, but improves topical breadth.
   For every missing required link, queue a suggestion via `interlink.suggest` with status='suggested', the appropriate anchor (drawn from the destination article's primary or secondary keyword space and balanced against the bands in step 3), and a `position_hint` that names the section where the link should sit (typically the introduction for pillar→spoke and a body-section transition for spoke→pillar). Write `runs.metadata_json.interlinker.step4 = {pillars_audited, missing_pillar_to_spoke: [...], missing_spoke_to_pillar: [...], cross_cluster_suggestions: [...]}`.
5. **Contextual link opportunities.** For each article in scope (the focal article in procedure-4 mode; every recently-published article in project-wide mode), walk the body and identify mentions that could anchor outbound links to other published articles in the project. The mention-to-target match is two-sided:
   - The mention is a noun phrase that aligns with another article's `primary_kw` or one of its `secondary_kws[]`.
   - The other article is `status='published'` and is not already linked from the focal article (no duplicates of an existing applied link between the same `from_article_id` and `to_article_id` with status `applied` or `suggested`).
   - The other article is in the same cluster, in the parent / child cluster, or in a sibling cluster the project's strategy allows; cross-cluster contextual links are permitted when relevance is high but should not dominate the suggestions.
   For every match, queue an `interlink.suggest` row with the source article id, the destination article id, the anchor text (drawn from the mention itself, biased toward partial-match per step 3 to stay inside the 30–40% target band), a `position_hint` carrying the paragraph or section context, and a priority field (`high` / `medium` / `low`) based on traffic potential and topical proximity. Cap the per-article suggestion count at 12 outbound and 12 inbound to keep the human-review surface manageable; surplus candidates are dropped and noted in the report. Write `runs.metadata_json.interlinker.step5 = {focal_article_id?, suggestions_emitted, suggestions_dropped_over_cap, per_article: [...]}`.
6. **Navigation and footer link optimisation.** Audit the project's site-wide link surfaces — the main navigation, the footer, the sidebar, breadcrumbs — encoded on `publish_targets.config_json.navigation` (when the operator has populated it; many projects do not). The suggester's role is informational: surface which pillars are missing from the main nav, which footer links point at low-value pages, which breadcrumb chains have gaps. Site-wide link writes happen at the publish-target level (the operator edits `config_json.navigation` and the publish step rebuilds), not via `interlink.suggest`; the suggester writes recommendations into `runs.metadata_json.interlinker.step6 = {nav_pillars_missing: [...], footer_low_value: [...], breadcrumb_gaps: [...]}`. When the publish target does not encode navigation, surface `step6.nav_unmodelled=true` and skip — the suggester does not invent navigation strategy.
7. **Implementation plan.** Compose the structured plan that bundles the prior six steps into a single audit row the operator and the EEAT gate's rerun-after-images audit can both read. The plan carries:
   - **Executive summary** — current orphan count, current over-optimisation %, current avg inbound, and the target gaps.
   - **Phased actions** — phase 1 (orphan-fix and high-priority pillar-spoke gaps; week 1 in standalone mode); phase 2 (cluster cross-links and contextual additions; weeks 2–3); phase 3 (anchor diversification and nav rebalancing; week 4 onward).
   - **Tracking metrics** — orphan count, over-optimisation %, avg inbound per post, incoming traffic delta on previously-orphaned articles, click-depth distribution. The procedure-6 weekly run reads these and surfaces the deltas.
   The plan persists to `runs.metadata_json.interlinker.step7` in a structured shape; it is also the row the UI's `InterlinksView.vue` page renders for the operator. The implementation actions themselves are queued via `interlink.suggest` calls in steps 4 and 5; step 7 is the report, not new writes.
8. **Persist top issues.** Roll up the top three to five issues across all seven steps, sorted by impact: orphan-pillar (highest), missing pillar→spoke link, missing spoke→pillar link, anchor over-optimisation hotspot, navigation gap. Write `runs.metadata_json.interlinker.top_issues[]` with `{step, severity, finding, recommendation}` so the procedure runner's failure-handler can surface a useful message when the suggester returns FIX-class signals.
9. **Finish.** Call `run.finish` with `{project_id, focal_article_id?, orphan_count, over_optimisation_pct, suggestions_emitted, structure_score, top_issues_count}`. Heartbeats fire after each of the seven steps so a long project-wide audit on a hundred-article project stays visible.

## Outputs

- `internal_links` — one row per suggested link with status='suggested' and the source / destination / anchor / position-hint fields. The applied / dismissed transitions happen via `interlink.apply` and `interlink.dismiss` from the operator's UI; the suggester does not auto-apply anything.
- `runs.metadata_json.interlinker` — the structured seven-step report + top-issues + the cluster pattern audit + the navigation report.

## Failure handling

- **No published articles.** Surface `runs.metadata_json.interlinker.empty=true` and finish cleanly. The procedure runner advances; the project simply does not have a graph to audit yet.
- **No clusters defined.** Step 4 (cluster strategy) cannot run because there is no pillar-spoke topology. Surface `runs.metadata_json.interlinker.step4.skipped='no-clusters'` and proceed; orphan analysis (step 2), anchor distribution (step 3), and contextual-link suggestion (step 5) still run because they do not depend on clusters.
- **Project domain missing on `project.get`.** The implementation plan (step 7) cannot render absolute URLs in the report. Render relative paths instead and surface `runs.metadata_json.interlinker.step7.urls_relative=true`. The suggester's writes still succeed because `internal_links` carries article ids, not URLs.
- **`interlink.suggest` rejects a row (duplicate of an existing suggestion or applied link).** The repository's uniqueness invariant `uq_internal_links_unique` (PLAN.md L479) deduplicates on `(from_article_id, to_article_id, anchor_text, position) WHERE status != 'dismissed'`. The suggester catches the conflict, drops the duplicate, increments `runs.metadata_json.interlinker.duplicates_skipped`, continues.
- **Project graph too large to walk in a single run.** When `article.list` returns more than 1000 published articles the auditor pages through them; per-page heartbeats fire so the run stays visible. The suggester does not impose a hard cap because the daemon's per-run timeout already bounds the work; runs that exceed the timeout abort cleanly and the operator runs project-wide audits in narrower scopes.
- **Anchor distribution computed against a destination with fewer than three applied inbound links.** The bands assume a meaningful sample; with fewer than three inbound links the distribution is dominated by noise. Surface in `runs.metadata_json.interlinker.step3.thin_inbound[]` and report the destination as "needs more inbound links" rather than as an anchor-distribution violation.
- **A focal article (procedure-4 mode) has no published siblings to link to.** Step 5 emits zero suggestions; surface `runs.metadata_json.interlinker.step5.no_targets=true` and continue. The procedure runner advances; the publish step still runs because interlink suggestions are best-effort.

## Variants

- **`fast`** — runs steps 1, 2, 4, and 5 only (structure + orphans + clusters + contextual). Skips anchor distribution (step 3), navigation (step 6), and the executive plan (step 7). Useful in `bulk-content-launch` where dozens of articles publish in sequence and the project-wide audit would be redundant per-article.
- **`standard`** — the default flow above with all seven steps.
- **`strict`** — raises the orphan target from "high-priority orphans get same-week fix" to "every orphan gets same-day fix" by emitting suggestions for every orphan regardless of priority bucket; raises the over-optimisation ceiling to a hard <8% (down from <10%); enforces anchor-distribution bands at the per-article-pair level rather than per-destination. Useful for projects with strict editorial review where the operator wants the suggester to err toward more suggestions, not fewer.
- **`audit-only`** — performs every step and persists the report but does NOT call `interlink.suggest`. Used for periodic audits where the operator wants the rubric report without committing new suggestion rows the human review queue would have to clear.
