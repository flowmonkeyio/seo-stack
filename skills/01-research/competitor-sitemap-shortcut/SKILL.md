---
name: competitor-sitemap-shortcut
description: Pull competitor sitemap.xml feeds (with optional Ahrefs ranking export), turn the URL list into a topical map, and seed the topic queue.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: original
license: project-internal
allowed_tools:
  - meta.enums
  - project.get
  - cluster.list
  - cluster.create
  - topic.bulkCreate
  - topic.list
  - integration.test
  - sitemap.fetch
  - run.start
  - run.heartbeat
  - run.finish
  - run.recordStepCall
  - procedure.currentStep
  - procedure.recordStep
inputs:
  project_id:
    source: env
    var: CONTENT_STACK_PROJECT_ID
    required: true
  run_id:
    source: env
    var: CONTENT_STACK_RUN_ID
    required: true
  competitor_domains:
    source: args
    type: list[str]
    required: true
    description: Procedure-level argument; each entry is a competitor's apex domain.
  per_competitor_url_cap:
    source: args
    type: int
    required: false
    default: 500
  use_ahrefs:
    source: args
    type: bool
    required: false
    default: false
outputs:
  - table: topics
    write: topic.bulkCreate persists candidate URLs as topic rows tagged source='competitor-sitemap'.
  - table: runs
    write: per-competitor counts + parsed URL lists in runs.metadata_json.competitor_sitemap.
---

## Shared operating contract

Before executing, read `../../references/skill-operating-contract.md` and
`../../references/seo-quality-baseline.md`. Apply the shared status, validation,
evidence, handoff, people-first, anti-spam, and tool-discipline rules before the
skill-specific steps below.

## When to use

The "shortcut" is the AM Media observation that a competitor's published sitemap is the highest-signal seed corpus available for free: every URL on it is a content investment the competitor was willing to commit to. Procedure 2 (`one-site-shortcut`) wires this skill as its first step, then hands the discovered URLs to the cluster skill (#3) so the operator gets a working topical map in one run instead of a multi-step keyword sweep.

Skip this skill when the operator has no competitor list — keyword discovery (#1) is the alternative path. Skip it when the operator's competitors block sitemap access — fall back to keyword discovery and document the blocked competitors in the run's metadata.

## Inputs

- `project.get(project_id)` returns the project's own `domain`. We exclude any URL whose host matches the project domain so the topic queue doesn't suggest cloning what we already publish.
- `cluster.list(project_id)` — existing topical coverage. URLs that map to existing pillars are tagged for prioritisation (compete vs. expand) but still get inserted; the operator decides during topic approval.
- `competitor_domains` — the procedure-level argument carrying the competitor apex list. Each domain becomes one or more sitemap fetches.

The skill does not read `projects.competitors_json` because no such column exists — competitor lists live entirely in procedure args.

## Steps

1. **Discover sitemap URLs.** For each competitor domain, the skill checks the conventional locations in order:
   - `https://<domain>/sitemap.xml` — the canonical location.
   - `https://<domain>/sitemap_index.xml` — the WordPress convention.
   - `https://<domain>/robots.txt` — parse the `Sitemap:` directive (one or more lines may be present); add every URL listed there to the work queue.
   `sitemap.fetch` handles redirects and follows up to two levels of sitemap-index recursion automatically. If robots discovery is needed and no granted fetch helper is exposed, stop with `NEEDS_INPUT` for operator-supplied sitemap URLs rather than using native browser/fetch calls.
2. **Honor robots.txt.** Before any fetch, use only daemon-exposed sitemap/robots results. If the competitor's robots disallows sitemap.xml access, mark the competitor as "blocked", log the reason, and skip to the next competitor. Do not map around a blocked competitor with Firecrawl or another crawler. Persist the blocked list in `runs.metadata_json.competitor_sitemap.blocked[]` so the operator can supply URLs from a licensed export if they want to.
3. **Parse and filter.** The `sitemap.fetch` tool returns parsed `{url, lastmod, changefreq, priority}` rows. Filter out non-content paths using URL pattern heuristics:
   - Drop tag/category archive pages (`/tag/...`, `/category/...`, `/topics/...`).
   - Drop author archives (`/author/...`).
   - Drop date archives (`/2024/01/...`, `/archive/...`).
   - Drop feed endpoints (`/feed/`, `/rss/`).
   - Drop pagination duplicates (`/page/2/...`).
   - Drop the project's own URLs (host match against `projects.domain`).
   The patterns are heuristic; document the filter list inline so the operator can tune them per niche. After filtering, cap the survivors per competitor at `per_competitor_url_cap` (default 500) — the cluster skill's pairwise SERP overlap is O(N²) and 500 URLs already produces a very rich map.
4. **Optional Ahrefs join.** When `use_ahrefs=true` AND the project has an Ahrefs credential, pull a ranking export per competitor via the daemon's Ahrefs integration. The export's stable column shape is `URL, Keyword, Position, Volume, Traffic`. Inner-join on `URL`; the matched rows pick up volume + ranking-position metadata that flows through to the topic row's `priority` field. Document the column shape inline so future Ahrefs API drift fails loud rather than silently producing zeroes.
5. **Build candidate topics.** For each surviving URL the skill mints a topic candidate:
   - `title` — derived from the URL's slug (last path segment, hyphens to spaces, title-cased) as a placeholder; the cluster skill's downstream SERP analysis will replace it with the actual page title once available.
   - `primary_kw` — the slug-derived title in lower case as a starting estimate; re-derived properly during clustering.
   - `intent` — heuristic from URL pattern: `/blog/` and informational paths default to `informational`; `/review/`, `/best-`, `/vs-` paths default to `commercial`; `/buy/`, `/pricing/`, `/discount/` default to `transactional`. Tag low-confidence guesses with `metadata_json.intent_confidence='low'` so the cluster skill knows to re-classify.
   - `source` — fixed at `'competitor-sitemap'` to keep the audit trail clean.
   - `priority` — when Ahrefs joined, derive from the keyword's volume; otherwise leave null so cluster scoring decides later.
   The topic table does not carry per-row metadata yet, so persist `source_competitor`, `source_url`, `lastmod`, `unique_reader_value`, `original_evidence_plan`, `audience_fit`, and `thin_content_risk` under `runs.metadata_json.competitor_sitemap.value_gate[source_url]` so the human approval step can reject thin competitor rewrites.
6. **Dedupe and persist.** Run the candidate set through the same dedupe pass that `keyword-discovery` uses: skip rows whose `(project_id, primary_kw)` collides with an existing topic. Persist the survivors via `topic.bulkCreate`; the streaming progress emitter fires every 50 inserts when the batch exceeds 50 rows.
7. **Hand off to clustering.** This skill does NOT cluster on its own — it explicitly defers to skill #3 (`topical-cluster`). The procedure runner schedules `topical-cluster` as the next step; the cluster skill reads the freshly-inserted topics and runs its SERP-overlap pass against them. Document this handoff in the skill's run metadata so the operator can trace the chain.
8. **Finish.** `run.finish` with `{competitors_processed, urls_discovered, urls_filtered_out, topics_created, blocked_competitors[]}`. Heartbeats fire after each competitor completes so a partial failure (one competitor down) is visible without waiting for the whole run.

## Outputs

- `topics` — one row per surviving competitor URL; tagged `source='competitor-sitemap'`.
- `runs.metadata_json.competitor_sitemap` — per-competitor counts, blocked list, filter trail, optional Ahrefs match counts.

## Failure handling

- **Sitemap fetch returns 404 / 403.** Mark the competitor as blocked, log the reason, continue to the next competitor. The procedure does not abort on per-competitor failures.
- **Sitemap is enormous (>5000 URLs).** The `sitemap.fetch` tool's hard cap (5000) protects the daemon. The skill should warn in metadata when the cap was hit so the operator knows the URL set was truncated.
- **Sitemap-index recursion exceeds depth 2.** The helper aborts that branch with an error; the skill records the partial fetch and continues.
- **Ahrefs export missing expected columns.** Fail loud on the run, not silently — emit a clear error in `runs.metadata_json.competitor_sitemap.ahrefs_error` and continue with sitemap data only. Do not silently produce zeroes that look like real ranking data.
- **All competitors blocked.** Persist what we have (an empty topic batch is allowed), finish with `partial=true`, and message the operator to either supply URLs manually or fall back to keyword discovery.

## Variants

- **`fast`** — sitemap-only, one competitor at a time, no Ahrefs, lower per-competitor cap (200). Use when the operator wants to scan a single competitor quickly.
- **`standard`** — the default flow above; up to 5 competitors, optional Ahrefs, default cap 500.
- **`deep`** — Ahrefs always enabled, per-competitor cap raised to 2000. Firecrawl mapping is allowed only when robots permits crawling and the daemon exposes an auditable integration call for this run; never use it to bypass a missing or blocked sitemap.
