---
name: serp-analyzer
description: For a given primary keyword (or article), scrape the SERP top results and run a structured on-page audit per URL.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: codex-seo @ 97c59bcdac3c9538bf0e3ae456c1e73aa387f85a (clean-room; no upstream files read during authoring)
license: clean-room (PLAN.md L844 + docs/upstream-stripping-map.md adapt notes)
allowed_tools:
  - meta.enums
  - project.get
  - article.get
  - source.add
  - source.list
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
  article_id:
    source: env
    var: CONTENT_STACK_ARTICLE_ID
    required: false
    description: Optional — when supplied, the skill scopes the audit to one article's primary keyword and persists per-URL audits as research_sources rows.
  primary_kw:
    source: args
    type: str
    required: false
    description: Required when article_id is absent (project-level scratch sweep).
  top_n:
    source: args
    type: int
    required: false
    default: 10
outputs:
  - table: research_sources
    write: one row per audited URL when article_id is supplied (used=false until brief picks them).
  - table: runs
    write: per-URL audit blob in runs.metadata_json.serp_analyzer.audits[]; aggregate scores in runs.metadata_json.serp_analyzer.summary.
---

## When to use

Two-phase pattern: scrape → audit. Run this skill when you need to understand what is currently ranking for a target keyword and how those pages stack up against the on-page rubric. Procedure 3 (`keyword-to-topic-queue`) drives the project-scope variant after `keyword-discovery`; procedure 4 (`topic-to-published`) runs the article-scope variant during research planning.

Skip this skill for purely informational meta-research where you only need URL counts — the upstream `cluster.list` + previously-cached SERP data are usually sufficient.

## Inputs

- `project.get` resolves locale + niche so SERP queries route to the right Google market.
- When `article_id` is supplied, `article.get` returns the article row including `brief_json.primary_kw` (which the skill uses if `primary_kw` is omitted) and the project-level voice / compliance rules indirectly via `project_id`.
- `source.list` returns existing research-source rows so the skill skips already-audited URLs.
- `integration.test` confirms Firecrawl is healthy. Audit work is driven by the Firecrawl wrapper; if it's down, the skill aborts.

## Steps

1. **Resolve target keyword.** If `article_id` is supplied, read the article and use its `brief_json.primary_kw`. Otherwise the procedure runner passed `primary_kw` directly. Refuse to start if neither is present.
2. **Map the SERP cheaply.** Call DataForSEO's SERP endpoint to get the top organic URLs for the keyword (up to `top_n`, default 10). Filter out paid results, featured snippets, and PAA boxes — only organic positions count. Persist the URL list as a heartbeat payload so the audit step is resumable.
3. **Map-then-crawl discipline.** The audit costs scale linearly with URLs. Start with the cheapest signal (`firecrawl_map`) only when you need to enumerate site structure; for each ranking URL call the daemon's Firecrawl wrapper at `op='scrape'` with `formats=['markdown']` and `onlyMainContent=True`. The wrapper handles budget pre-emption per audit M-25; a single map call is roughly half a credit, scrape is one credit per page. The procedure runner sets `args.budget_cap_usd` if the operator wants a hard ceiling — read it from the step args and skip remaining URLs once the cap is hit.
4. **Per-URL on-page audit.** For every scraped URL, run the rubric. The rubric has six categories — score each on a 0–100 scale and capture concrete findings:
   - **On-page SEO** — title length (50–60 chars target), meta description length (150–160 chars), H1 presence and uniqueness, H2/H3 hierarchy depth, URL slug hygiene, canonical tag presence, meta robots correctness, hreflang correctness when locale != en-US.
   - **Content quality** — total word count vs the page-type minimum (informational long-form: 1500+; comparison/review: 1200+; transactional: 600+), readability proxy (sentence-length variance, paragraph density), evidence of first-hand experience or expertise markers, freshness signals (publication date, last-updated date).
   - **Technical** — canonical correctness, Open Graph completeness, Twitter Card completeness, status code, redirect chain length.
   - **Schema** — JSON-LD detection, required-properties validation, deprecated-type flags (avoid recommending HowTo or restricted FAQ types).
   - **Images** — alt-text presence + length window (10–125 chars), file format (WebP/AVIF preferred), explicit width/height for CLS prevention.
   - **Core Web Vitals proxy** — flag obvious red flags from the markdown alone: huge hero images, render-blocking inline scripts visible in source, missing image dimensions. The audit cannot replace a real Lighthouse run; document its limitations in the per-URL finding.
   For each category, emit a structured `{score: int, findings: [str], recommendations: [str]}` blob.
5. **Aggregate.** Roll the per-URL scores into a per-keyword summary: average score per category across the top-N URLs, bottom-quartile category (the gap to attack), top-quartile (the floor to clear). Capture an unranked list of structural patterns common to the top-3 (e.g., "every top-3 page has a comparison table; ours should too").
6. **Persist.** When `article_id` is supplied, each URL becomes one `research_sources` row via `source.add(article_id, url, title, snippet, used=false)`. The audit blob lands in `runs.metadata_json.serp_analyzer.audits[]` keyed by URL. The aggregate summary lands in `runs.metadata_json.serp_analyzer.summary`. When `article_id` is absent (project-level sweep), only the run blob is persisted — sources are not committed without an article anchor.
7. **Finish.** Call `run.finish` with the summary `{primary_kw, urls_audited, avg_score, top_gap, recommendations[]}`. The brief skill (#4) reads this run's metadata when composing the brief's "competitive landscape" section.

## Outputs

- `research_sources` (when `article_id` is set) — one row per audited URL; `used=false` so the brief skill can pick the canonical 5–12 to cite.
- `runs.metadata_json.serp_analyzer` — per-URL audit blob + aggregate summary.

## Failure handling

- **Firecrawl down.** Abort. Audit work depends on it; SERP-only data is too thin to be useful.
- **Per-URL scrape fails.** Skip the URL and continue. Record the failure in the per-URL audit blob with `score=null, error="..."`. The aggregate summary excludes failed rows from the average.
- **Budget cap hit mid-batch.** Persist what we have, mark the run summary `partial=true`, finish gracefully. The procedure runner can resume with `procedure.resume`.
- **JSON-LD parsing throws.** Treat as a per-URL category failure (schema score = 0); log the parser error in the finding. Don't abort the URL's other categories.

## Variants

- **`fast`** — top 5 URLs only, content-quality + on-page-SEO categories only, skip schema and CWV proxy. Useful for the procedure-3 sweep where the cluster step is the load-bearing analysis.
- **`standard`** — top 10 URLs, all six categories. The default flow.
- **`deep`** — top 20 URLs, all six categories, plus a Jina Reader fallback for any URL Firecrawl fails on (Jina handles paywalled and JS-heavy edge cases differently). Ideal during a procedure-4 brief.
