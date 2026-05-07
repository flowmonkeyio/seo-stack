# content-stack — Upstream Stripping Map

A skill-by-skill map of what to keep, what to drop, and what to adapt from each strip-target upstream when authoring content-stack's 24 skills under M7. This document is the bridge between PLAN.md's catalogue (lines 392–423) and the actual files our skill authors will read for inspiration. We **reference, don't vendor**: every keep below becomes a pattern that we re-author against our SQLite schema (PLAN.md lines 280–298) and MCP tools (PLAN.md lines 364–388).

The hierarchy of authority in this document:

1. **PLAN.md** is the spec. The 24 skills, the 16 tables, the 8 procedures, the 9 integrations are fixed there.
2. **Each upstream README + its top-level agent context file** (AGENTS.md / CLAUDE.md / SKILL.md). Read first; this is the upstream's own framing of what it does.
3. **The specific upstream files cited below**. These are the artifacts our skill authors will study when writing each `skills/<phase>/<skill>/SKILL.md`.

There are three strip-target repos plus one install-only peer:

| Upstream | HEAD pin | Files | Role |
|---|---|---|---|
| `AgriciDaniel/codex-seo` | `97c59bc` | 319 | Reference for 8 of our 24 skills (research/SERP/cluster/firecrawl/page/google/images/schema/drift) |
| `ibuildwith-ai/cody-article-writer` | `981ab43` | 20 | Reference for 7 content-production skills (brief/outline/3 drafts/editor/refresher) |
| `aaron-he-zhu/seo-geo-claude-skills` | `7ecc77b` | 181 | Reference for the EEAT gate + interlinker (CORE-EEAT 80-item; internal-linking-optimizer) |
| `openai/codex-plugin-cc` | `807e03a` | 61 | **Install-only peer**, not stripped, **not installed by us**. Optional adversarial EEAT review wiring (PLAN.md line 511); user installs the plugin themselves if they want the seam. |

The four highest-value adaptations are: skill #11 (eeat-gate, from seo-geo-claude-skills), skill #15 (interlinker, from seo-geo-claude-skills), skill #10 (editor, **clean-room from PLAN.md only — no cody reads**), and skill #3 (topical-cluster, **clean-room from PLAN.md only — concept verification of codex-seo allowed**).

### Status after audit fixes

This strip map was substantially revised on 2026-05-06 to apply the 12 citation fixes from `docs/plan-audit.md` §9 and add a new top-level "Original skills (no upstream)" section covering 7 skills that have no upstream artifact. Highlights:

- **Cody license posture is now "clean-room re-author from PLAN.md only"** — skill authors for #4/#6/#7/#8/#9/#10/#24 do NOT read any cody file. Zero verbatim text.
- **codex-seo posture is the same clean-room rule** — skill authors for #1/#2/#3/#14/#16/#20/#21/#22 may read codex-seo files for concept verification (e.g., confirm SERP-overlap thresholds are still 7-10/4-6/2-3/0-1) but copy zero prose, prompt text, or script body verbatim.
- **codex-plugin-cc is dropped from `scripts/install-codex.sh`** — users install the plugin themselves via Claude Code's marketplace if they want the optional adversarial-review seam.
- **All 12 citation errors from audit §9 have been corrected** (cody line counts; editor-style-guide §9/§10 line ranges; veto-item attribution; internal-linking-optimizer file size; misattributed "Hard targets"; article-workflow §3 reframing; research-workflow depth tiers; LICENSE.md sub-line ranges; seo-google striking-distance line; content-quality-auditor 689-line reality).
- **The 7 originals** (`competitor-sitemap-shortcut`, `humanizer`, `image-generator`, `nuxt-content-publish`, `wordpress-publish`, `ghost-publish`, `refresh-detector`) now have a dedicated top-level section with algorithm sketches, DB-table touches, MCP-tool lists, and key risks each.
- **"Approximate volume kept: ~N LOC" language is replaced with "Reading commitment: ideas, not lines"** throughout — content-stack commits to zero verbatim text from cody and codex-seo.

---

## `codex-seo` (HEAD `97c59bc`)

Daniel Agrici's Codex-first SEO suite. This is a port of his earlier `claude-seo` repo, shipped as a Codex plugin. Twenty-six specialist `skills/seo-*/SKILL.md` files plus one orchestrator `skills/seo/SKILL.md`, twenty-four TOML agent profiles in `agents/`, fifty Python runners in `scripts/`, three optional MCP extensions (DataForSEO, Firecrawl, banana/Gemini), and a thick `tests/` directory. We reference patterns from eight skills only — the rest is irrelevant to content-stack's content-production focus.

### 1. Inventory

```
codex-seo/                                     (319 files; HEAD 97c59bc)
├── skills/                                    27 skill dirs; 26 specialists + 1 orchestrator
│   ├── seo/                                   Orchestrator + shared references (eeat-framework.md, schema-types.md, shared-data-cache.md, etc.)
│   ├── seo-dataforseo/                        DataForSEO MCP wrapper (SERP/keywords/backlinks)
│   ├── seo-firecrawl/                         Firecrawl MCP wrapper (crawl/map/scrape)
│   ├── seo-cluster/                           SERP-overlap topical clustering + hub-spoke planner
│   ├── seo-page/                              Single-URL deep on-page audit
│   ├── seo-google/                            GSC + PageSpeed + CrUX + Indexing API + GA4
│   ├── seo-images/                            Image SEO audit (alt/size/format/CWV)
│   ├── seo-schema/                            JSON-LD detect / validate / generate
│   ├── seo-drift/                             Baseline + diff for on-page SEO regressions
│   ├── seo-content/, seo-geo/, seo-flow/      Content quality / GEO / FLOW prompt framework (we DON'T use these directly; PLAN.md sources EEAT from aaron-he-zhu and content from cody)
│   ├── seo-audit/, seo-technical/, seo-sxo/   Full-site audit, technical SEO, search experience (out of scope)
│   ├── seo-local/, seo-maps/, seo-hreflang/   Local/maps/i18n SEO (out of scope)
│   ├── seo-ecommerce/, seo-programmatic/      E-commerce/programmatic SEO (out of scope)
│   ├── seo-backlinks/, seo-sitemap/           Backlinks/sitemap analysis (out of scope; we use sitemap as data source not skill)
│   ├── seo-image-gen/, seo-visual/            AI image gen wrapper / screenshots (we have our own image-generator)
│   ├── seo-performance/, seo-plan/, seo-competitor-pages/   Performance/strategy/comparison pages (out of scope)
├── agents/                                    24 TOML "agent profiles" — Codex-specific routing hints; not portable
├── scripts/                                   ~50 Python runners (drift_*, gsc_*, dataforseo_*, ga4_*, parse_html, fetch_page, etc.)
├── extensions/                                Optional MCP server installers (DataForSEO / Firecrawl / banana)
│   ├── dataforseo/                            install.sh + skill copy + field-config.json
│   ├── firecrawl/                             install.sh + skill copy
│   └── banana/                                Gemini/nanobanana MCP for image gen
├── hooks/                                     Codex pre-commit hook + schema validator
├── schema/templates.json                      JSON-LD template library (Article/Product/FAQ/Org/LocalBusiness/...)
├── tests/                                     ~30 contract + smoke tests (pytest)
├── docs/                                      ARCHITECTURE.md / COMMANDS.md / etc.
├── .codex-plugin/plugin.json                  Codex plugin manifest
├── pyproject.toml + requirements*.txt         Python packaging + 5 capability groups (core/google/ocr/report/visual)
├── install.sh / install.ps1                   One-line installers (curl|bash style)
├── pdf/, screenshots/                         Cover image, demo screenshots
├── llms.txt                                   Agent-facing project context
├── README.md (24654 bytes)                    Long marketing-flavored README
├── AGENTS.md                                  Short developer rules file
├── CITATION.cff / CHANGELOG.md / etc.         Standard repo paperwork
└── LICENSE                                    See risk note in §2 below
```

### 2. License

**Mixed signals — actively risky.**

- **Asserted license:** MIT (badge in `README.md:16`; `pyproject.toml:6` `license = "MIT"`; `.codex-plugin/plugin.json:11` `"license": "MIT"`; `CITATION.cff:11` `license: "MIT"`; every per-skill `skills/seo-*/LICENSE.txt` says `"MIT License - see repository root LICENSE file for complete terms."`).
- **Actual root file:** `/Users/sergeyrura/Bin/content-stack/.upstream/codex-seo/LICENSE:1` is a **proprietary "Avalon Reset" license** that explicitly forbids redistribution, modification for distribution, derivative works, sublicensing, and competing products. It also requires "active membership" (line 27–32).

This is a packaging defect upstream — six different sources say MIT and one says proprietary. The proprietary text ("Copyright (c) 2026 Avalon Reset") matches the contact email in the codex-companion README of a different Avalon Reset product, and it almost certainly leaked in via a botched fork chain. The CREDITS.md acknowledges Avalon Reset for the Codex conversion work.

**Practical implications and locked decision:**

- The LICENSE inconsistency is unresolved upstream. Six MIT signals plus one proprietary text creates real uncertainty.
- **Locked decision (per audit §3 D1)**: same clean-room re-author posture as cody. Skill authors for skills #1, #2, #3, #14, #16, #20, #21, #22 do **NOT** copy any prompt text, script body, or reference doc verbatim. They use the *concepts* (cost-aware DataForSEO discipline; SERP-overlap clustering thresholds; hub-spoke architecture word counts; ACTIVE/RESTRICTED/DEPRECATED schema taxonomy; striking-distance position-4-10 heuristic; drift baseline element list; alt-text rubric thresholds) — but author every line of skill prose, every Python wrapper, and every test fixture themselves.
- **Zero verbatim text** from codex-seo in content-stack skills, including no copy-paste of any prompt-text segment longer than three consecutive words.
- **Decision (locked, per audit §3 D2)**: the proposed `scripts/install-codex.sh --with-codex-seo` flag is **dropped from the installer**. Inducing the install via our scripts is contributory under the proprietary text. Users who want codex-seo install it themselves — documented in `docs/extending.md`. PLAN.md line 498 is updated to reflect this.
- We **must** flag the upstream LICENSE inconsistency in `docs/attribution.md` and ask Daniel Agrici / Avalon Reset to reconcile.
- **Quote of concern from `LICENSE:18-21`**: "You may NOT … Modify, adapt, translate, reverse engineer, decompile, or disassemble the Software for the purpose of creating derivative works for distribution".

### 3. KEEP map

#### `01-research/keyword-discovery` (PLAN.md row #1)

- **Upstream source files:**
  - `skills/seo-dataforseo/SKILL.md:1-423` (the full SKILL definition; 423 lines)
  - `skills/seo-dataforseo/references/cost-tiers.md` (pricing-tier table; budget guardrails)
  - `skills/seo-dataforseo/references/tool-catalog.md` (the 79+ MCP tool inventory)
  - `skills/seo-cluster/SKILL.md:60-115` (Step 1 "Seed Keyword Expansion": related searches, PAA, modifiers, intent splits) — this is the keyword-discovery seed expansion logic
  - `scripts/dataforseo_costs.py` (cost-guardrail call shape)
  - `scripts/dataforseo_normalize.py`
- **Patterns/sections we reuse:**
  - The "before each call, run cost estimation" guardrail pattern (`SKILL.md:65-87`)
  - The DataForSEO endpoint catalogue mapping (`/seo dataforseo serp <kw>`, `volume <kws>`, `difficulty`, `intent`, `trends`, `keywords <seed>`, `ranked <domain>`, `intersection <doms>`)
  - The default `location_code=2840 (US), language_code=en` parameter discipline
  - Seed-expansion modifier list: "best", "how to", "vs", "for beginners", "tools", "examples", "guide", "template", "mistakes", "checklist" (`seo-cluster/SKILL.md:66`)
  - Intent classification (informational/commercial/transactional/navigational with signals — `seo-cluster/SKILL.md:102-115`)
- **Reading commitment:** ideas, not lines. Per the locked codex-seo license posture (clean-room re-author from PLAN.md only), we do **NOT** copy any prompt text, script, or reference doc verbatim. We use the *concepts* (cost-aware DataForSEO call discipline, the seed-expansion modifier list as inspiration, intent-classification signals as a categorisation pattern) and re-author every line in our own voice, against our DataForSEO wrapper + `topics`/`research_sources` schema. Add Reddit/PAA branches per PLAN.md row #1.

#### `01-research/serp-analyzer` (PLAN.md row #2)

- **Upstream source files:**
  - `skills/seo-firecrawl/SKILL.md:1-222` (crawl/map/scrape commands and parameters; full file)
  - `skills/seo-page/SKILL.md:1-114` (the on-page audit checklist: title length, meta length, H1, H2-H6 hierarchy, URL hygiene, internal/external link discipline, word-count-vs-page-type, readability, keyword density, EEAT signals, freshness, canonical, robots, OG/Twitter, hreflang, schema, images; full file)
  - `skills/seo/references/quality-gates.md` (thin-content thresholds per page type)
  - `scripts/fetch_page.py`, `scripts/parse_html.py` (for SSRF-guarded fetch + DOM parse — pattern only)
- **Patterns/sections we reuse:**
  - The "scrape then audit" two-phase recipe — Firecrawl for SERP top-N, then per-URL on-page audit
  - Single-page audit checklist verbatim categories: On-Page SEO, Content Quality, Technical Elements, Schema, Images, Core Web Vitals (`seo-page/SKILL.md:36-76`)
  - Cost-aware Firecrawl pattern: `firecrawl_map` first (cheap, URLs only), then `firecrawl_crawl` on top-50 (`seo-firecrawl/SKILL.md:78-90`)
  - Scenario routing table "static HTML → fetch_page; JS-rendered SPA → firecrawl_scrape; need clean markdown → firecrawl_scrape" (`seo-firecrawl/SKILL.md:145-152`)
- **Reading commitment:** ideas, not lines. Clean-room re-author. We use the *categories* of the on-page audit (On-Page SEO / Content Quality / Technical / Schema / Images / CWV) as a checklist scaffold and the two-phase Firecrawl recipe as orchestration logic, but author every prompt and rubric line ourselves against our schema. Zero verbatim text from `seo-firecrawl` or `seo-page` SKILL.md, references, or scripts.

#### `01-research/topical-cluster` (PLAN.md row #3)

- **Upstream source files:**
  - `skills/seo-cluster/SKILL.md:60-292` (the complete planning workflow)
  - `skills/seo-cluster/references/serp-overlap-methodology.md` (the SERP-overlap algorithm)
  - `skills/seo-cluster/references/hub-spoke-architecture.md`
  - `skills/seo-cluster/references/execution-workflow.md`
- **Patterns/sections we reuse:**
  - **The whole "SERP-overlap clustering" idea** — group keywords by shared top-10 URLs, not by text similarity (`seo-cluster/SKILL.md:74-100`). This is the entire reason we cite codex-seo for skill #3.
  - Threshold table: 7-10 shared = same post; 4-6 = same cluster; 2-3 = interlink; 0-1 = separate (`seo-cluster/SKILL.md:84-89`)
  - Optimization heuristic: pre-group by intent (4 groups of ~10 = 180 comparisons instead of full 780 pairwise) (`seo-cluster/SKILL.md:91-95`)
  - Hub-spoke architecture rules: pillar 2500-4000 words, spoke 1200-1800 words; cannibalization check (no two posts share primary kw); internal-link matrix (every spoke→pillar mandatory) (`seo-cluster/SKILL.md:117-170`)
  - Cluster scorecard metrics table (`seo-cluster/SKILL.md:255-267`)
- **Reading commitment:** ideas, not lines. Clean-room re-author. We adopt the *idea* of SERP-overlap clustering, the *threshold table values* (7-10 / 4-6 / 2-3 / 0-1), the *hub-spoke pillar/spoke word counts* (2500-4000 / 1200-1800), and the *intent classification signals* — but write every word of `topical-cluster/SKILL.md` ourselves against our `clusters`/`topics` schema. Zero verbatim text from `seo-cluster/SKILL.md` or its references.

#### `04-publishing/schema-emitter` (PLAN.md row #16)

- **Upstream source files:**
  - `skills/seo-schema/SKILL.md:1-187` (JSON-LD detect/validate/generate; full file)
  - `skills/seo/references/schema-types.md` (status of every schema type)
  - `schema/templates.json` (the actual JSON-LD template library — Article, BlogPosting, NewsArticle, Product, Organization, LocalBusiness, Review, AggregateRating, BreadcrumbList, WebSite, WebPage, Person, ProfilePage, ContactPage, VideoObject, ImageObject, Event, JobPosting, Course, DiscussionForumPosting, Service, SoftwareApplication, Offer, ProductGroup)
- **Patterns/sections we reuse:**
  - The ACTIVE / RESTRICTED / DEPRECATED schema-type taxonomy (`seo-schema/SKILL.md:54-79`). This is *load-bearing*: we must not emit HowTo (deprecated 2023-09) or FAQ on commercial sites (restricted 2023-08). PLAN.md has us emit JSON-LD per article/topic; we use this to pick types.
  - The JSON-LD template structures (Article/BlogPosting in particular — `seo-schema/SKILL.md:92-150`)
  - The validation discipline: required-properties checks, `@context`, `@type`, absolute URLs, ISO date formats, no placeholder text, deprecated-type flags
  - The "JSON-LD in initial server-rendered HTML, not JS-injected" rule (`seo-schema/SKILL.md:65`) — important for our Nuxt/WP/Ghost publishers
- **Reading commitment:** ideas, not lines. Clean-room re-author. We adopt the *taxonomy* of ACTIVE / RESTRICTED / DEPRECATED schema types and the *deprecation cliff dates* (HowTo 2023-09; FAQ restricted 2023-08; SpecialAnnouncement 2025-07-31; etc.) as load-bearing factual constants, but every JSON-LD template body, every prose explanation, and every validation rule is authored from the schema.org spec directly. Zero verbatim text from `seo-schema/SKILL.md`, `references/schema-types.md`, or `schema/templates.json`.

#### `05-ongoing/gsc-opportunity-finder` (PLAN.md row #20)

- **Upstream source files:**
  - `skills/seo-google/SKILL.md:1-365` (full Google API skill; 365 lines)
  - `skills/seo-google/references/auth-setup.md`
  - `skills/seo-google/references/search-console-api.md`
  - `skills/seo-google/references/indexing-api.md`
  - `skills/seo-google/references/pagespeed-crux-api.md`
  - `scripts/google_auth.py` — auth flow pattern (OAuth + service account)
  - `scripts/gsc_query.py` — Search Analytics call shape
  - `scripts/gsc_inspect.py` — URL Inspection call shape
  - `scripts/indexing_notify.py` — Indexing API call shape
- **Patterns/sections we reuse:**
  - The credential-tiers table (Tier 0 API key / Tier 1 OAuth-or-SA / Tier 2 GA4 / Tier 3 Ads) — gates which features are usable (`seo-google/SKILL.md:64-72`)
  - Search Console default pull: "28 days, dimensions=query,page, type=web, limit=1000" (`seo-google/SKILL.md:140-141`) — exactly what our nightly `jobs/gsc_pull.py` (PLAN.md line 167) needs
  - **The "striking distance" idea**: queries at position 4-10 with high impressions = quick wins (`seo-google/SKILL.md:143`). PLAN.md row #20 calls these "striking distance queries" — same concept.
  - URL Inspection pattern (verdict, coverage state, robots.txt status, indexing state, page fetch, canonical selection) — feeds our `runs` audit log
  - Quota awareness: Indexing API 200/day, URL Inspection 2,000/day per site
  - PageSpeed merge of lab + CrUX field data (lab + 28-day Chrome user metrics)
  - The `~/.config/codex-seo/google-api.json` config-file shape — adapted to our `integration_credentials` row schema instead
- **Reading commitment:** ideas, not lines. Clean-room re-author. We adopt the *concept* of striking-distance queries (position 4-10 + high impressions = quick wins), the *credential tiers table*, the *quota numbers* (Indexing 200/day, URL Inspection 2000/day), and the *default Search Analytics pull params* (28 days, dimensions=query,page) — these are factual constants from Google's own docs. All Python code (`integrations/gsc.py`, `jobs/gsc_pull.py`) is authored from the official `google-api-python-client` examples; zero verbatim text from `seo-google/SKILL.md` or its scripts.

#### `05-ongoing/drift-watch` (PLAN.md row #21)

- **Upstream source files:**
  - `skills/seo-drift/SKILL.md:1-239` (the entire drift skill; 239 lines)
  - `skills/seo-drift/references/comparison-rules.md` (17 rules across 3 severity levels)
  - `scripts/drift_baseline.py` — baseline-capture call shape
  - `scripts/drift_compare.py` — comparison engine
  - `scripts/drift_history.py` — history retrieval
- **Patterns/sections we reuse:**
  - The captured-elements table (`seo-drift/SKILL.md:53-69`): title, meta_description, canonical, meta_robots, h1[], h2[], h3[], schema[], open_graph, cwv, status_code, html_hash (SHA-256), schema_hash. This becomes our `drift_baselines` row content.
  - Severity levels CRITICAL / WARNING / INFO and the response-time guidance (`seo-drift/SKILL.md:78-85`)
  - URL normalization rules: lowercase scheme/host, strip default ports, sort query params, remove UTM, strip trailing slash (`seo-drift/SKILL.md:101-104`)
  - 17-rule comparison framework (in `references/comparison-rules.md`)
- **Reading commitment:** ideas, not lines. Clean-room re-author. We adopt the *list of captured elements* (title/meta/canonical/robots/h1/h2/h3/schema/og/cwv/status/html_hash/schema_hash) as the column shape for our `drift_baselines` table and the *severity-level taxonomy* (CRITICAL/WARNING/INFO), but author every comparison rule and severity-rule prose from first principles. Zero verbatim text from `seo-drift/SKILL.md` or `references/comparison-rules.md`.

#### `05-ongoing/crawl-error-watch` (PLAN.md row #22)

- **Upstream source files:**
  - `skills/seo-google/SKILL.md` (URL Inspection + Indexing API subset)
  - `scripts/gsc_inspect.py` (verdict / coverage / fetch state)
- **Patterns/sections we reuse:**
  - URL Inspection verdict schema (PASS/FAIL, coverage state, robots.txt, indexing, page fetch, canonical, mobile usability, rich results) — for our `runs` rows
  - Batch URL Inspection from a file pattern (`/seo google inspect-batch <file>` — `seo-google/SKILL.md:152-156`) — adapted to per-project iteration over published articles
- **Reading commitment:** ideas, not lines. Clean-room re-author. URL Inspection verdict shape and quota numbers are factual constants; everything else (skill prose, batch-iteration loop) is authored fresh against our `runs` table.

#### `03-assets/alt-text-auditor` (PLAN.md row #14)

- **Upstream source files:**
  - `skills/seo-images/SKILL.md:36-150` (Alt Text rubric, file size tiers, format recommendations, responsive image patterns, lazy-loading, CLS prevention)
- **Patterns/sections we reuse:**
  - Alt-text rubric: present, descriptive, 10–125 chars, keyword inclusion natural-not-stuffed (`seo-images/SKILL.md:40-44`)
  - Good/bad alt-text examples (`seo-images/SKILL.md:46-51`) — copy as test fixtures, paraphrase in our prompts
  - File-size tiered thresholds (thumbnail/content/hero) (`seo-images/SKILL.md:60-62`)
  - Format recommendations (WebP/AVIF over JPEG/PNG) and the `<picture>` progressive-enhancement pattern (`seo-images/SKILL.md:80-90`)
  - Above-the-fold rules: NO `loading="lazy"` on LCP images; YES `fetchpriority="high"` on hero (`seo-images/SKILL.md:124-130`)
- **Reading commitment:** ideas, not lines. Clean-room re-author. We adopt the *alt-text length window* (10-125 chars), the *file-size tier thresholds*, the *format ranking* (WebP/AVIF > JPEG/PNG), and the *above-the-fold rules* as factual constants — but every line of skill prose and every test-fixture string is authored fresh. Zero verbatim text from `seo-images/SKILL.md`.

### 4. STRIP map

Everything below is irrelevant to content-stack and would be noise to vendor.

- `skills/seo/SKILL.md` (the orchestrator) → It routes between specialists; we have our own procedures (PLAN.md procedures 1–8). No reuse.
- `skills/seo-audit/`, `skills/seo-technical/`, `skills/seo-sxo/`, `skills/seo-performance/`, `skills/seo-visual/` → Site auditing / SXO / CWV / screenshots are out of content-stack's "produce content" scope. (Drift baselines already use a CWV subset.)
- `skills/seo-content/`, `skills/seo-geo/`, `skills/seo-flow/` → Content quality / GEO / FLOW prompts. PLAN.md sources content quality from aaron-he-zhu (CORE-EEAT 80-item) and content production from cody-article-writer; codex-seo's content/GEO/FLOW skills are duplicates we don't want. Note `seo-flow/references/` carries CC BY 4.0 prompts from the FLOW framework — extra licensing surface to avoid.
- `skills/seo-local/`, `skills/seo-maps/`, `skills/seo-hreflang/` → Local SEO / Google Maps intelligence / multi-locale. Out of scope; PLAN.md scope is single-domain content pipeline, with `projects.locales` field but no GBP/maps work.
- `skills/seo-ecommerce/`, `skills/seo-programmatic/`, `skills/seo-competitor-pages/`, `skills/seo-plan/` → E-commerce / programmatic / comparison pages / strategic planning. Out of scope.
- `skills/seo-backlinks/`, `skills/seo-sitemap/` → Backlinks profile analysis is not in our pipeline. Sitemap analysis is referenced as a *data source* in the AM Media trick (procedure 2) but we don't need a whole skill — we just `httpx.get()` `sitemap.xml`.
- `skills/seo-image-gen/` (and `extensions/banana/`) → AI image gen via Gemini/nanobanana. PLAN.md row #13 uses OpenAI Images API directly; we don't want a Gemini MCP wrapper.
- `agents/*.toml` (24 files) → Codex-specific TOML agent profiles with `developer_instructions`. Codex-only routing — not portable to Claude Code or generic MCP. The same instructions can be written into our SKILL.md frontmatter without TOML.
- `scripts/run_skill_workflow.py`, `scripts/run_api_smoke_suite.py`, `scripts/verify_environment.py`, `scripts/bootstrap_environment.py`, `scripts/demo_readiness.py` → Codex-suite test/demo runners. We have our own pytest/CI pipeline.
- `scripts/run_headless_audit.py`, `scripts/generate_premium_audit_report.py`, `scripts/google_report.py`, `scripts/generate_seo_plan.py`, `scripts/generate_competitor_pages.py` → Audit-report generation. We don't generate audit reports — we publish articles.
- `scripts/analyze_*.py` (analyze_content/geo/hreflang/images/performance/programmatic/schema/sitemap/technical/visual.py) → Specialist analyzers feeding the audit pipeline. We persist per-table not per-report.
- `scripts/capture_screenshot.py`, `scripts/youtube_search.py`, `scripts/nlp_analyze.py`, `scripts/dataforseo_merchant.py`, `scripts/commoncrawl_graph.py`, `scripts/moz_api.py`, `scripts/bing_webmaster.py`, `scripts/keyword_planner.py`, `scripts/backlinks_auth.py`, `scripts/probe_skill_selection_provider.py`, `scripts/test_openai_responses_provider.py`, `scripts/sync_flow.py`, `scripts/seo_pipeline_utils.py`, `scripts/validate_backlink_report.py`, `scripts/verify_backlinks.py`, `scripts/dataforseo_normalize.py` → Out-of-scope or trivial helpers we re-author.
- `extensions/banana/` → Gemini image extension. Out of scope.
- `extensions/dataforseo/install.sh`, `extensions/firecrawl/install.sh` → Codex-specific MCP server registration into `~/.codex/settings.json`. We register MCP differently (MCP credentials in `integration_credentials` table). The install.sh files are useful as a reference for the actual MCP server names/URLs but not for vendoring.
- `extensions/*/agents/`, `extensions/*/docs/` → Codex agent profiles + docs duplicating skill content.
- `hooks/hooks.json`, `hooks/pre-commit-seo-check.sh`, `hooks/validate-schema.py` → Codex pre-commit hooks. We have our own hooks.
- `tests/` (~30 files) → Codex-suite tests. Not portable.
- `docs/` (ARCHITECTURE.md, COMMANDS.md, INSTALLATION.md, MCP.md, DEMO.md, etc.) → Their docs. We write our own.
- `screenshots/`, `pdf/` → Marketing assets.
- `install.sh`, `install.ps1`, `uninstall.sh`, `uninstall.ps1`, `pyproject.toml`, `requirements*.txt`, `.codex-plugin/plugin.json`, `.devcontainer/` → Codex plugin packaging. Their packaging is not our packaging.
- `.github/`, `.gitignore`, `.gitattributes`, `CITATION.cff`, `CHANGELOG.md`, `CODEOWNERS`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `CREDITS.md`, `SECURITY.md`, `llms.txt`, `README.md`, `AGENTS.md` → Standard repo paperwork. Read; do not vendor.
- `LICENSE` → See §2 risks. Do not copy.

### 5. ADAPT notes

For each KEEP item, what we change when re-authoring against content-stack:

- **Skill #1 (keyword-discovery)**: Replace file-based DataForSEO output with `topic.bulkCreate` MCP tool persisting `topics` rows with `source='dataforseo'`. Reddit + PAA branches (PLAN.md additions) write rows with `source='reddit'` / `source='paa'`. The cost-guardrail pattern moves into our `integrations/dataforseo.py` as a pre-call check that writes to `runs.metadata_json.cost`. Cache reads (`.seo-cache/site-meta.json`) become `gsc_metrics` lookups for the project, not file system.
- **Skill #2 (serp-analyzer)**: Replace local-file output with structured rows. SERP results (top 10 URLs per primary_kw) feed `research_sources` rows with `used=false` until the brief picks them. On-page audit results → `runs.metadata_json` keyed by article-id-or-topic-id. Firecrawl call goes through `content_stack/integrations/firecrawl.py`; `httpx.get()` fallback inside the wrapper replaces `scripts/fetch_page.py`'s SSRF guard (we replicate the SSRF check in the wrapper).
- **Skill #3 (topical-cluster)**: SERP-overlap algorithm output writes `clusters` rows (parent_id maps pillar→spoke) and `topics` rows for each candidate post. Cluster-map JSON visualisation is dropped (UI handles graph rendering via `ClustersView.vue`).
- **Skill #14 (alt-text-auditor)**: The rubric runs against `article_assets` rows; flags persist as `runs.metadata_json.warnings[]`. The "auto-rewrite weak alt-text" branch updates `article_assets.alt_text` via `asset.update` MCP.
- **Skill #16 (schema-emitter)**: Replace `schema/templates.json` with templates re-authored under `content_stack/db/seed.py` as default `schema_emits` patterns per article kind. JSON-LD validation runs through `repositories/schema.py` → `schema.set` MCP → `schema_emits.validated_at` timestamp.
- **Skill #20 (gsc-opportunity-finder)**: Replace `~/.config/codex-seo/google-api.json` with `integration_credentials` rows where `kind='gsc'`. The OAuth flow lands tokens in `encrypted_payload`. Periodic pull lives in `jobs/gsc_pull.py` (APScheduler) and writes `gsc_metrics` rows. Striking-distance detection writes new `topics` rows with `source='gsc-opportunity'` per the PLAN.md status enum (line 308).
- **Skill #21 (drift-watch)**: Replace `~/.cache/codex-seo/drift/baselines.db` with our `drift_baselines` table. The 17 comparison rules become `repositories/drift.py.compare()` returning a structured diff; severities map to `runs.metadata_json.severity`. `articles.edited_md` is the natural baseline for our content (we know what we wrote); the *current page state* is fetched at compare time.
- **Skill #22 (crawl-error-watch)**: URL Inspection iterates over `articles WHERE status='published'` for the active project and writes incidents to `runs` rows with `kind='crawl-error-watch'`, `status='success'` for clean runs and `'failed'` rows with the verdict in `error`.

Every adapt note ties an upstream pattern to a specific repository method + MCP tool + table column. None of these are "verbatim copies".

### 6. Integration callouts

- **DataForSEO**: `skills/seo-dataforseo/SKILL.md:1-423` + `extensions/dataforseo/install.sh`. **Adapt, don't copy verbatim.** The 79+ MCP tool list is exhaustive; we want only ~10 endpoints (SERP/keywords/volume/difficulty/intent/trends/ranked/competitors/onpage/backlinks). Our wrapper exposes those as Python methods on `integrations/dataforseo.py`. Cost-guardrail pattern from `scripts/dataforseo_costs.py` is reused conceptually but written into `runs.metadata_json` instead of a JSON file.
- **Firecrawl**: `skills/seo-firecrawl/SKILL.md:1-222` + `extensions/firecrawl/install.sh`. **Adapt.** We use `firecrawl-py` directly in `integrations/firecrawl.py`. Map → crawl two-phase pattern reused. We add a `playwright` fallback (PLAN.md line 111) for sites Firecrawl can't render, plus Jina Reader as a markdown-extraction fallback (PLAN.md line 162, 471).
- **Google Search Console**: `skills/seo-google/SKILL.md` + `references/auth-setup.md` + `scripts/google_auth.py`/`gsc_query.py`/`gsc_inspect.py`. **Adapt the auth flow carefully.** The OAuth + service-account dual-flow is non-trivial — we re-author with `google-auth` library and store tokens encrypted in `integration_credentials.encrypted_payload`. The Search Analytics defaults (28 days, dimensions=query,page) and quota numbers (200/day Indexing, 2000/day URL Inspection) are load-bearing — copy the constants, paraphrase the prose.
- **OpenAI Images**: Not present in codex-seo (their image-gen uses Gemini/nanobanana). **Authored fresh** for skill #13.
- **Reddit (PRAW)**: Not present in codex-seo. **Authored fresh** for skill #1.
- **Google PAA**: Not present as a clean module in codex-seo (referenced in `seo-cluster/SKILL.md:64`). **Authored fresh** as scraper.
- **Jina Reader**: Not present. **Authored fresh** as fallback.
- **Ahrefs**: Not present in codex-seo. **Authored fresh** (PLAN.md line 464 marks it optional).

### 7. Risks

- **License inconsistency** (highest priority): `LICENSE` says proprietary, every other source says MIT. We must (a) note it in `docs/attribution.md`, (b) avoid quoting prompt text or scripts verbatim, (c) preferably contact the upstream to fix the LICENSE file.
- **DataForSEO API drift**: The skill references `serp_organic_live_advanced`, `dataforseo_labs_*`, `kw_data_*`, `backlinks_*` endpoint families. If DataForSEO renames endpoints we will see runtime failures; we should pin our wrapper to a specific DataForSEO MCP version and write VCR-style cassettes (PLAN.md line 588).
- **Schema deprecation cliff**: HowTo (deprecated 2023-09), FAQ on commercial sites (restricted 2023-08), SpecialAnnouncement (deprecated 2025-07-31), CourseInfo/EstimatedSalary/LearningVideo (retired 2025-06), ClaimReview/VehicleListing (retired 2025-06), Practice Problem/Dataset (retired late 2025) — we must keep this list in our reference doc and update it. The codex-seo SKILL has it as of `seo-schema/SKILL.md:54-79`; we copy the *list*, paraphrase the prose.
- **CC BY 4.0 attribution surface in `seo-flow/`**: The FLOW framework prompts in `skills/seo-flow/references/prompts/` are licensed CC BY 4.0 (referenced in `seo-flow/SKILL.md:8`). We deliberately don't use FLOW (PLAN.md doesn't reference it), so this is moot — but if a future skill author tries to reference FLOW prompts, they must include attribution.
- **Heavy Python deps avoided**: codex-seo pulls in 5 capability groups (`requirements-google.txt`, `requirements-ocr.txt`, `requirements-report.txt`, `requirements-visual.txt`). We don't want OCR or report-generation deps. PLAN.md uses `firecrawl-py + playwright + httpx + google-auth + google-api-python-client + praw` only.
- **`shipping-rules.md` external reference**: `AGENTS.md:46` references `/home/agricidaniel/Desktop/shipping-rules.md` — a filesystem path on the upstream author's machine. Not portable; ignore.
- **"Community footer" promotional gunk**: `seo/SKILL.md:113-127` has a promotional Skool community footer that the LLM is supposed to append to deliverables when `CODEX_SEO_COMMUNITY_FOOTER=1`. We strip this completely and never copy. Our skills emit clean output.
- **Codex-specific routing assumptions**: TOML agents in `agents/*.toml` and `.codex-plugin/plugin.json` are Codex-only. Our skills must work in Claude Code too, so they live in `SKILL.md` only — no TOML, no plugin.json.
- **`shared-data-cache.md` filesystem-cache assumption**: Every skill's "Step 0 - Check shared data cache" reads `.seo-cache/*.json`. We have a database. Skill authors must replace this with DB lookups (e.g., `gsc.queryProject` MCP) and never ship a filesystem cache.

---

## `cody-article-writer` (HEAD `981ab43`)

iBuildWith.ai's article-writing skill. A single `.skill` bundle (zip-as-skill, `cody-article-writer.skill` is a 30KB compressed file at the repo root) plus the same content unzipped under `source/cody-article-writer/`. Designed for Claude Desktop / Claude Code / GitHub Copilot / OpenAI Codex. The repo authority is the unzipped form under `source/`. Twenty files total. We reference patterns for seven of our 24 skills (the entire `02-content/` phase except eeat-gate and humanizer, plus content-refresher).

### 1. Inventory

```
cody-article-writer/                          (20 files; HEAD 981ab43)
├── source/cody-article-writer/               The unpacked skill bundle (authoritative)
│   ├── SKILL.md                              252 lines: phase overview + JSON state schema + style/draft contract
│   ├── references/
│   │   ├── article-workflow.md               547 lines: detailed 12-phase workflow
│   │   ├── style-schema.md                   127 lines: voice/formatting/structure/context schema
│   │   ├── style-workflow.md                 ~250 lines: style creation/edit/delete flow
│   │   ├── research-workflow.md              ~550 lines: 6 research integration points
│   │   ├── editor-style-guide.md             243 lines: AI-tell removal + tightening + emphasis rules
│   │   └── migrations.md                     ~70 lines: version migration chain
│   └── assets/templates/
│       └── article_default.md                Frontmatter+body template (12 lines)
├── cody-article-writer.skill                 30KB zipped bundle of source/ (don't read; same content)
├── README.md                                 Marketing readme
├── LICENSE.md                                Custom restrictive license (see §2)
├── Release Notes.md                          Version history (v3.0)
├── images/                                   Logo + workflow screenshots (5 PNGs)
└── .gitignore
```

### 2. License

**Custom restrictive — read carefully.** `LICENSE.md` is a custom Red Pill Blue Pill Studios license:

- **Permitted**: use for "AI-assisted article writing, content creation, and structured blog/article workflows"; commercial use to create content (articles for clients OK); educational use; private internal modifications.
- **Forbidden** (`LICENSE.md:18-30`):
  - "**No Adaptation or Derivative Works**: You may not adapt, translate, extend, or otherwise use the codebase to create a different or competing framework, tool, or product. Using any part of Cody Article Writer in other software or projects is disallowed."
  - "**No Modification (Except for Contribution)**: You may not modify Cody Article Writer or create derivative works."
  - "**No Public Forking or Redistribution**" (line 25).
  - "**No Sale, Resale, or Redistribution of the Software**" (line 27–31, including "Integrating Cody Article Writer into a product or service that you sell, license, or offer for a fee").

**This is the strictest license among our three strip targets.** Practical implications and **locked decision**:

- The "No Adaptation or Derivative Works" clause directly threatens any re-authoring approach that reads from cody files. The clause says "Using any part of Cody Article Writer in other software or projects is disallowed." Even reading-then-paraphrasing ("different or competing framework") is uncomfortably close to forbidden.
- **Locked decision (per audit §3 D1)**: **clean-room re-author from PLAN.md only**. Skill authors for skills #4, #6, #7, #8, #9, #10, #24 do **NOT** read any cody file (no SKILL.md, no `references/*.md`, no LICENSE, no README). Their only sources are PLAN.md + this strip map's adapt notes (which are themselves second-order summaries, not paraphrases) + their own general editorial knowledge.
- **Mitigations (now invariants, not best-effort):**
  1. **Zero verbatim text** from cody-article-writer in any content-stack skill, doc, or test fixture — including phrases of more than three consecutive words.
  2. Do **not** vendor the `.skill` bundle, templates, JSON schemas, or per-section prose.
  3. Do **not** ship a CLI or skill literally called "Cody Article Writer" or any near-clone name.
  4. `docs/attribution.md` carries an explicit credit *and* an explicit "this is a separate, independently-authored implementation that did not read cody files during authoring" statement.
  5. CI fingerprint check (planned for M7 acceptance) rejects substrings ≥30 chars matching cody source files; failures block the merge.
- The PLAN.md "reference, don't vendor" line is the high-level posture; this clean-room rule is the operational floor.

### 3. KEEP map

#### `01-research/content-brief` (PLAN.md row #4)

- **Upstream source files:**
  - `source/cody-article-writer/SKILL.md:73-118` (Phase 1–3 workflow overview: ideation → research planning → style selection → title/thesis)
  - `source/cody-article-writer/references/article-workflow.md:48-241` (Phase 1 ideation, Phase 2 research planning, Phase 4 title/thesis)
  - `source/cody-article-writer/references/research-workflow.md:1-200+` (research integration points 1–4)
- **Patterns/sections we reuse:**
  - The "exploratory + comprehensive" two-phase research model
  - The depth-tier metaphor: light (1–5 sources) / medium (6–11) / heavy (12–20) (`research-workflow.md:118-120`)
  - JSON state schema for `approved_sources` (the brief carries source metadata: url/title/author/date/domain/excerpt/relevance/required/accessed; plus `depth`, `include_citations_in_export`, `citation_style`, `citations_used[]`) (`article-workflow.md:154-173`). We adapt this shape to `research_sources` rows (one per source) keyed off `articles.brief_json.research`.
  - Title + thesis informed by `voice + context` from style guide (paralleled by our `voice_profiles.voice_md`) (`article-workflow.md:217-241`)
- **Reading commitment:** ideas, not lines. Per the locked cody license posture (clean-room re-author from PLAN.md only — see §2 below), the skill author for #4 does **NOT** read any cody file. Brief structure, depth tiers, and the source-tracking JSON shape are described in PLAN.md (or this strip map's adapt notes); the skill author writes `content-brief/SKILL.md` from those second-order summaries plus general editorial knowledge. Zero verbatim text from cody.

#### `02-content/outline` (PLAN.md row #6)

- **Upstream source files:**
  - `source/cody-article-writer/SKILL.md:106-119` (overview of outline phase)
  - `source/cody-article-writer/references/article-workflow.md:243-289` (Phase 5 outline + Phase 6 section confirmation)
- **Patterns/sections we reuse:**
  - H1 (article title) → ordered H2 sections → optional H3 subsections, with explicit `opening` and `closing` markers from style guide
  - Section confirmation phase: present sections, allow split/combine before writing (`article-workflow.md:268-286`)
  - Research integration point 5: required sources must map to specific outline sections; outline iteration loop until approved
- **Reading commitment:** ideas, not lines. Clean-room from PLAN.md only. Skill author for #6 does NOT read cody files. H1→H2→H3 with explicit `opening`/`closing` markers, a section-confirmation iteration loop, and source-section binding are all describable from PLAN.md row #6 + standard outline practice. Zero verbatim text from cody.

#### `02-content/draft-intro` (PLAN.md row #7)

- **Upstream source files:**
  - `source/cody-article-writer/references/article-workflow.md:289-352` (Phase 7 writing, "section by section" mode A; intro is the first iteration)
  - `source/cody-article-writer/references/style-schema.md:76-80` (`opening` types: direct / contextual / narrative / tension)
- **Patterns/sections we reuse:**
  - Four opening archetypes (direct / contextual / narrative / tension), pickable from style guide multi-select (`style-schema.md:76-80`)
  - Hook + thesis-restatement pattern in mode-A writing (`article-workflow.md:311-326`)
  - Citation marker insertion `[^1]` while writing (PLAN.md row #4 brief carries citation pref through to draft) (`article-workflow.md:318-321, 342-348`)
- **Reading commitment:** ideas, not lines. Clean-room from PLAN.md only. The four opening archetypes (direct/contextual/narrative/tension) are documented in this strip map's adapt notes and PLAN.md voice schema; the skill author writes #7 from those plus standard intro-craft principles. Zero verbatim text from cody.

#### `02-content/draft-body` (PLAN.md row #8)

- **Upstream source files:**
  - `source/cody-article-writer/references/article-workflow.md:289-352` (mode-A "section by section" — body sections iterate)
- **Patterns/sections we reuse:**
  - Per-section iteration with mode A: write → present → iterate → mark complete → next
  - "Reference relevant `approved_sources` for this section" + ensure required sources incorporated (`article-workflow.md:316-318`)
  - Section status tracking: `pending|in_progress|complete` (`SKILL.md:185`)
  - Working-file-per-section pattern: update `drafts/[draft-id].md` as you go so the user can preview without scrolling chat (`article-workflow.md:323-324`)
- **Reading commitment:** ideas, not lines. Clean-room from PLAN.md only. Per-section iteration with `pending|in_progress|complete` status tracking, a working-file-per-section preview pattern, and required-source binding can be specified from PLAN.md row #8 + general writing practice. Zero verbatim text from cody.

#### `02-content/draft-conclusion` (PLAN.md row #9)

- **Upstream source files:**
  - `source/cody-article-writer/references/style-schema.md:82-88` (`closing` types: summary / call_to_action / open_question / callback / provocation / key_takeaways)
  - `source/cody-article-writer/references/article-workflow.md:312-352`
- **Patterns/sections we reuse:**
  - Six closing archetypes pickable from style guide
  - Summary + CTA pattern as default
  - PLAN.md adds: insert compliance footer per `compliance_rules` rows for the project (responsible-gambling / affiliate-disclosure / jurisdiction / age-gate)
- **Reading commitment:** ideas, not lines. Clean-room from PLAN.md only. Six closing archetypes (summary/CTA/open_question/callback/provocation/key_takeaways) are documented in this strip map and the voice schema; #9 also writes the per-position compliance footer from `compliance_rules`. Zero verbatim text from cody.

#### `02-content/editor` (PLAN.md row #10)

- **Upstream source files:**
  - `source/cody-article-writer/references/editor-style-guide.md` (the entire 244 lines)
- **Patterns/sections we reuse:** This file is the heart of the editor pass. We keep:
  - **Section 1: Content Enhancement Pass** — examples (lists/tables/diagrams/code/quotes/case_studies) calibrated by `structure.examples` and `structure.example_types` (`editor-style-guide.md:18-66`)
  - **Section 2: Text Emphasis Guidelines** — bold for key terms / takeaways / warnings; italic for subtle emphasis / technical terms / titles / vocal stress (`:86-112`)
  - **Section 3: Visual Breaks** — minimal/moderate/generous calibration by `structure.visual_breaks` (`:114-129`)
  - **Section 4: Em Dashes** — calibration table 0-2 / 3-5 / 6-10 by `formatting.em_dashes` (`:132-138`)
  - **Section 5: Emoji Usage** — calibration table by `formatting.emojis` (`:140-148`)
  - **Section 6: AI Tell Removal** — *the most important keep*. Specific filler phrases ("It's important to note that...", "It's worth mentioning that...", "Interestingly enough...", "In today's world...", "In this article, we will..."), transitions to reduce ("Additionally", "Furthermore", "Moreover", "However", "Therefore"), overused structures (multiple "This..." paragraph starts, "When it comes to [X]...", weak "[X] is a [Y] that [Z]") (`:150-170`)
  - **Section 7: Tone Consistency** — calibration by `voice.tone` slider (`:172-179`)
  - **Section 8: Prose Tightening** — remove redundant words, weasel words, unnecessary qualifiers; passive→active; long→short sentences; weak→strong verbs (`:181-198`)
  - **Section 9: Spelling & Grammar** (`:194-199`)
  - **Section 10: Flow & Transitions** (`:200-205`)
  - **The `[id].md` + `[id]-editorpass.md` two-file discipline** — original preserved as backup (`:7-14`). Maps to `articles.draft_md` (preserved) + `articles.edited_md`.
- **Reading commitment:** ideas, not lines. Clean-room from PLAN.md only — **the editor pass is the highest-risk surface for license entanglement** because it has the densest matter from cody, so the skill author for #10 must be especially careful: they do NOT read `editor-style-guide.md` directly. Instead the strip-map ADAPT notes below + general editorial practice + a fresh authoring of the AI-tell removal list (specific filler phrases, weak transitions, overused structures) drive the skill body. The 10 editorial dimensions (content enhancement / emphasis / visual breaks / em-dashes / emojis / AI-tell removal / tone consistency / prose tightening / spelling-grammar / flow-transitions) are listed here as the *scaffold*; everything else is independently written. Zero verbatim text from cody.

#### `05-ongoing/content-refresher` (PLAN.md row #24)

- **Upstream source files:**
  - `source/cody-article-writer/references/editor-style-guide.md` (re-runs the editor pass on existing `articles.edited_md`)
  - `source/cody-article-writer/references/article-workflow.md:393-432` (Phase 10 editor pass + iteration handling)
- **Patterns/sections we reuse:**
  - Re-run editor checks on existing content; preserve original via `articles.createVersion` MCP
  - Iteration loop pattern (apply → summarize changes → iterate)
- **Reading commitment:** ideas, not lines. Clean-room from PLAN.md only. #24 composes the editor + humanizer skills (already authored fresh), so it inherits zero-verbatim-text by construction.

### 4. STRIP map

- `cody-article-writer.skill` (zipped bundle) → Same content as `source/`, ignore the zipped form.
- `images/` (5 PNGs: cody-article-writer-logo.png, article-workflow.png, user-style-guide.png, user-style-guide-workflow.png, editor-style-guide.png) → Marketing assets. Don't ship.
- `Release Notes.md` → Version history. Read for context, don't vendor.
- `README.md` (12246 bytes) → Marketing readme + install instructions for Claude/Codex/Copilot. Read; don't vendor.
- `LICENSE.md` → See §2. Read carefully; do not copy text.
- `source/cody-article-writer/references/style-workflow.md` → Style creation flow specifically inside Cody's UI loop ("show me my styles", "create a new style"). Our equivalent flow is the project bootstrap procedure (PLAN.md procedure 1) which writes `voice_profiles` rows via REST + UI. We do not need a chat-based style creation skill; the UI handles it.
- `source/cody-article-writer/references/migrations.md` → Cody's version migration chain (`.cody-version` file in `cody-projects/article-writer/`). We use Alembic for migrations (PLAN.md line 107). Not portable.
- `source/cody-article-writer/assets/templates/article_default.md` (12-line template) → Trivial frontmatter scaffold. We have per-publish-target frontmatter rules in `publish_targets.config_json` and our schema-emitter. Don't need.
- `source/cody-article-writer/SKILL.md:24-39` (Directory Setup section) → Creates `cody-projects/article-writer/{styles,drafts,articles,archive}/`. We don't use a filesystem; we use SQLite. Replace with DB-row creation.
- `source/cody-article-writer/SKILL.md:140-237` (Draft State JSON schema) → The big nested JSON object describing a draft. We have a relational schema (`articles` row with `brief_json`, `outline_md`, `draft_md`, `edited_md` columns + `research_sources` rows + `article_assets` rows). Their JSON shape is the right *idea*; our DB columns are the right *implementation*.
- `source/cody-article-writer/SKILL.md:215-242` (Export section) and Phase 12 in `article-workflow.md` → Writes a `.md` to `articles/`, archives JSON to `archive/`, deletes drafts. We never delete; we increment `articles.version` and keep history. Replace with `article.markPublished` MCP transition.
- `.gitignore` → trivial.

### 5. ADAPT notes

- **Skill #4 (content-brief)**: Replace JSON `draft.research.approved_sources[]` with `research_sources` rows (`article_id`, `url`, `title`, `snippet`, `fetched_at`, `used`). The `light/medium/heavy` depth maps to a `research_sources.required` boolean: required for `medium`/`heavy`, optional for `light`. Title + thesis become fields inside `articles.brief_json`. Pull voice via `voice.get` MCP at skill invocation; pull EEAT via `eeat.list`. Persist final brief via `article.setBrief` MCP.
- **Skill #6 (outline)**: Read brief from `articles.brief_json`; write the H1/H2/H3 markdown to `articles.outline_md` via `article.setOutline` MCP. Section status tracking happens in `articles.brief_json.outline[].status` (in-band) or via a derived field — keep it simple, don't add a new table.
- **Skill #7/8/9 (draft-intro/body/conclusion)**: Each skill reads outline + brief; writes its section to `articles.draft_md` (incrementally, via `article.setDraft` MCP — the call body holds the full assembled draft). Citation markers `[^1]`, `[^2]` reference `research_sources` rows by stable index. Source-section binding tracked in a per-citation map persisted in `articles.brief_json.citations_used`.
- **Skill #10 (editor)**: Reads `articles.draft_md`, runs the 10-section editor checklist from `editor-style-guide.md`, writes result to `articles.edited_md` via `article.setEdited`. **Do not modify citation markers.** AI-tell removal is the load-bearing pattern; our skill SKILL.md re-authors that list with content-stack voice. Preserve `draft_md` (it's a different column).
- **Skill #24 (content-refresher)**: Reads `articles.edited_md` (or `articles.draft_md` if re-running humanizer first), runs editor pass again, calls `article.createVersion` MCP which copies the row with `version+=1` and updates `last_refreshed_at`. Does not touch published articles' history.

Across all seven skills, replace upstream's "Cody acts as a firm sounding board" voice (`SKILL.md:90-101`) with content-stack's project-specific voice from `voice_profiles.voice_md`. The "firm sounding board" is one possible voice; content-stack supports many.

### 6. Integration callouts

- **WebSearch / WebFetch** (Claude Code's native tools): Cody depends on these for exploratory research (`research-workflow.md:25-67`). content-stack uses `Firecrawl` for primary, `WebSearch` (via runtime) as a fallback. **Adapt** — our skills call `Firecrawl` first, fall back to runtime's WebSearch for ad-hoc queries.
- **No external APIs** in cody-article-writer beyond WebSearch/WebFetch. The skill is intentionally local-filesystem + browser-research only. content-stack's research is richer (DataForSEO + Reddit + PAA + Firecrawl) — those wirings come from codex-seo and original code, not from cody.

### 7. Risks

- **License "No Adaptation or Derivative Works"** — already covered in §2.
- **`cody-projects/article-writer/` filesystem assumption is pervasive**: Almost every reference doc assumes JSON files in a working directory. Skill authors must rigorously translate to DB rows; an accidental `os.makedirs("cody-projects")` would be a disaster.
- **JSON-shape coupling to Cody's draft state**: `SKILL.md:140-205` describes a fat JSON object. Our equivalent is spread across 5 tables (`articles`, `research_sources`, `voice_profiles`, `compliance_rules`, `article_assets`). Skill authors must not preserve Cody's nested shape; persist atomically into the right tables.
- **Style guide field names** (`voice.tone`, `formatting.em_dashes`, `structure.opening`, `context.author_role`, etc.): Our `voice_profiles.voice_md` is *just markdown*. We deliberately don't replicate Cody's structured-fields schema because our voice is project-author-controlled and free-form. If a future skill author argues for porting Cody's struct, push back: it's a different design.
- **"Section by section vs. full draft" choice** (`article-workflow.md:300-340`): Cody asks the user. content-stack's procedure 4 doesn't ask — it always runs section-by-section because that lets each draft skill be a separate atomic step (PLAN.md rows 7/8/9 are *separate* skills per AM Media's recommendation in the catalogue). Skill authors should not preserve the "ask user" branch.
- **Editor pass is "optional" upstream, mandatory in content-stack**: `article-workflow.md:371-389` makes the editor pass optional. PLAN.md procedure 4 step "editor" is mandatory — and the EEAT gate after it loops back to draft on fail. Don't carry over the "skip editor" branch.
- **Voice field name collisions**: Cody's `voice.tone`, `voice.humor`, `voice.opinion`, `voice.technical` (0-10 sliders) are not the same as our project-defined voice. Don't accidentally export Cody's slider names through our SKILL.md frontmatter; that would imply our schema mirrors theirs (it doesn't).

---

## `seo-geo-claude-skills` (HEAD `7ecc77b`)

aaron-he-zhu's SEO + GEO skills bundle. Twenty skills in five phases (Research/Build/Optimize/Monitor/Cross-cutting), seventeen `commands/*.md`, four cross-cutting "protocol" skills, and the **CORE-EEAT 80-item benchmark** which is the single most important reference in this entire stripping map. PLAN.md rows #11 (eeat-gate) and #15 (interlinker) come from here. Apache-2.0 — the friendliest license among our three strip targets.

### 1. Inventory

```
seo-geo-claude-skills/                        (181 files; HEAD 7ecc77b)
├── research/                                 4 skills: keyword-research, competitor-analysis, serp-analysis, content-gap-analysis
│   └── <skill>/SKILL.md + references/        (typical: 1 SKILL.md per skill + 1-3 reference markdown files per skill)
├── build/                                    4 skills: seo-content-writer, geo-content-optimizer, meta-tags-optimizer, schema-markup-generator
├── optimize/                                 4 skills: on-page-seo-auditor, technical-seo-checker, internal-linking-optimizer, content-refresher
├── monitor/                                  4 skills: rank-tracker, backlink-analyzer, performance-reporter, alert-manager
├── cross-cutting/                            4 protocol skills: content-quality-auditor, domain-authority-auditor, entity-optimizer, memory-management
├── commands/                                 17 *.md slash commands (audit-page, audit-domain, check-technical, write-content, keyword-research, optimize-meta, generate-schema, report, setup-alert, geo-drift-check + 7 maintenance)
├── references/                               Top-level shared refs: core-eeat-benchmark.md, cite-domain-rating.md, skill-contract.md, state-model.md, auditor-runbook.md, AUDITOR-AUTHORS.md, contract-fail-caps.md, decisions/, evolution-*.md, geo-score-feedback-loop.md, entity-geo-handoff-schema.md, proposal-skillify-inspired-skill-authoring.md, proposal-wiki-layer-v3.md, skill-resolver.md
├── memory/                                   Sample memory layout (HOT/WARM/COLD with hot-cache.md, audits/, entities/, evolution/, geo-feedback/, archive/, wiki/)
├── docs/                                     README.zh.md (Chinese localization)
├── evals/                                    Eval cases for content-quality-auditor, geo-content-optimizer, memory-management
├── hooks/hooks.json                          PostToolUse hook recommending content-quality-auditor after content writes
├── monitor/                                  (top-level, separate from skill phase: not present — appears nested under monitor/)
├── scripts/                                  Sync + validate utilities (validate-skill.sh, validate-slimming-guardrails.sh)
├── .github/                                  CI workflow + scripts/sync-skills.js
├── .claude-plugin/plugin.json + marketplace.json   Claude Code plugin manifest
├── .codebuddy-plugin/                        CodeBuddy plugin manifest mirror
├── .mcp.json                                 14 included MCP servers (Ahrefs/Semrush/SE Ranking/SISTRIX/SimilarWeb/Cloudflare/Vercel/HubSpot/Amplitude/Notion/Webflow/Sanity/Contentful/Slack)
├── gemini-extension.json + qwen-extension.json + openclaw.bundle.json   Mirrored manifests for other agent runtimes
├── README.md                                 9122 bytes; phase summary + install commands per agent
├── CLAUDE.md                                 10510 bytes; the authoritative agent-context doc
├── AGENTS.md                                 3771 bytes; Codex/Gemini/Qwen agent context
├── CONNECTORS.md                             6393 bytes; tool-category placeholders + 14 included MCPs
├── CONTRIBUTING.md / SECURITY.md / PRIVACY.md / VERSIONS.md
├── LICENSE                                   Apache 2.0 (full text, 11347 bytes)
├── CITATION.cff
└── .gitignore + .clawhubignore + .mailmap
```

### 2. License

**Apache License 2.0** (`LICENSE:1`).

The friendliest license of the three strip targets. Apache 2.0 affects our "reference, don't vendor" approach as follows:

- **Permission to use, modify, redistribute** (with conditions) is granted.
- **Attribution requirement** (Section 4 of Apache 2.0): we must include a copy of the license, list any modifications, retain the original copyright notice, and include any NOTICE file. There is no top-level `NOTICE` in this repo, so we just need to retain the license + state our modifications.
- **Patent grant** (Section 3): any patent claims inherent in aaron-he-zhu's contributions are granted to us; if we sue someone over those patents, the grant terminates.

Practical implications for content-stack:

- We **could** vendor with attribution (we're not — PLAN.md says reference, don't vendor).
- We **must** credit aaron-he-zhu in `docs/attribution.md` and our skill SKILL.md frontmatter for skills #11 and #15: e.g., `derived_from: aaron-he-zhu/seo-geo-claude-skills@7ecc77b`, `license: Apache-2.0` (PLAN.md lines 482–492).
- We **must not** strip the upstream copyright headers from any content we paraphrase closely.

Quote from Apache 2.0 Section 4 paraphrased: redistributors of modified work must retain the original license, copyright notice, and notice of changes made. Since we are *paraphrasing rather than redistributing*, the exact application is lighter, but attribution is non-negotiable.

### 3. KEEP map

#### `02-content/eeat-gate` (PLAN.md row #11)

- **Upstream source files:**
  - `cross-cutting/content-quality-auditor/SKILL.md` (the entire **689 lines**; auditor-class skill — note this is materially larger than typical skills because it inlines the auditor runbook §1-5 per ADR-001 in `references/decisions/2026-04-adr-001-inline-auditor-runbook.md`)
  - `cross-cutting/content-quality-auditor/references/item-reference.md`
  - `references/core-eeat-benchmark.md` (the **80-item benchmark itself** — 8 dimensions × 10 items, with priority tags GEO 🎯 / SEO 🔍 / Dual ⚡); also the canonical home of the three veto rows
  - `references/auditor-runbook.md`
  - `references/contract-fail-caps.md`
  - `references/skill-contract.md` (handoff-summary format)
  - `references/state-model.md` (HOT/WARM/COLD memory layout)
  - `seo-geo-claude-skills/CLAUDE.md` (top-level: also names T04/C01/R10 as the three veto items)
- **Patterns/sections we reuse:**
  - **The 80-item CORE-EEAT framework**, structure verbatim:
    - 8 dimensions: Contextual Clarity (C), Organization (O), Referenceability (R), Exclusivity (E), Experience (Exp), Expertise (Ept), Authority (A), Trust (T)
    - 10 items per dimension = 80 total
    - Per-item priority tag (GEO 🎯 / SEO 🔍 / Dual ⚡)
    - Per-item one-line standard (`core-eeat-benchmark.md` item table; per-dimension item rows begin at `:51` for C, `:61` for O, `:71` for R, `:126` for T, with full per-dimension blocks at `:51-130`; detailed criteria reference begins at `:254`)
  - **Three veto items** (T04, C01, R10): trust violations that BLOCK publishing regardless of overall score. The canonical definition table is `core-eeat-benchmark.md:184-188` (Veto Items section, lines 180-194 with rationale and rules); the project's `CLAUDE.md` (top-level of the seo-geo-claude-skills repo) names them in the "Quality Frameworks" section. **Note**: `content-quality-auditor/SKILL.md:113-115` is example-invocation templates ("CORE-EEAT audit for this product review …"), not the veto definitions — earlier audits of this strip map mis-cited those lines.
  - **Scoring rubric**: Pass=10, Partial=5, Fail=0; per-dimension 0-100; system scores GEO=avg(C,O,R,E), SEO=avg(Exp,Ept,A,T) (`content-quality-auditor/SKILL.md:196-199`)
  - **Three verdicts**: SHIP / FIX / BLOCK based on score thresholds and veto state (`content-quality-auditor/SKILL.md:127`)
  - **Decision-gate questions** (when to stop and ask user vs. continue silently) (`content-quality-auditor/SKILL.md:151-166`)
  - **Critical Trust Check (Emergency Brake)** table at top of each audit (affiliate disclosure / title-content match / data consistency) (`content-quality-auditor/SKILL.md:181-188`)
  - Content-type-specific dimension weights (Product Review / How-to / Comparison / Landing / Blog / FAQ / Alternative / Best-of / Testimonial)
- **Reading commitment:** ideas, not lines. We use the rubric's *structure* (8 dimensions, 10 items each, priority tags, three vetoes) and the *scoring algorithm* but author every word of `eeat-gate/SKILL.md` from first principles against our `eeat_criteria` schema. Zero verbatim text, including the per-item one-line standards. Apache 2.0 attribution to aaron-he-zhu in skill frontmatter and `docs/attribution.md` is mandatory.

#### `04-publishing/interlinker` (PLAN.md row #15)

- **Upstream source files:**
  - `optimize/internal-linking-optimizer/SKILL.md:1-151` (the full skill — all 151 lines)
  - `optimize/internal-linking-optimizer/references/link-architecture-patterns.md` (75 lines)
  - `optimize/internal-linking-optimizer/references/linking-templates.md` (120 lines; output templates for steps 3-7)
  - `optimize/internal-linking-optimizer/references/linking-example.md` (a worked example)
- **Patterns/sections we reuse:**
  - **The 7-step interlinking workflow** (`internal-linking-optimizer/SKILL.md:111-122`):
    1. Analyze current structure (link distribution, top linked, under-linked, structure score)
    2. Identify orphan pages (high-value with traffic / medium-potential / low-value-delete)
    3. Anchor text distribution analysis (over-optimization / generic / CORE-EEAT R08 alignment)
    4. Topic cluster link strategy (pillar↔spoke required pattern)
    5. Contextual link opportunities per page
    6. Navigation/footer link optimization
    7. Implementation plan (priority + tracking)
  - **Anchor text variation table** (`linking-templates.md:19-25`):
    - Exact match: 10–20%
    - Partial match: 30–40%
    - Branded: 10–20%
    - Natural: 20–30%
  - **Hard targets — load-bearing thresholds**:
    - Orphan pages target: **0** (`linking-templates.md:3`)
    - Over-optimized anchors: **<10%** (`linking-templates.md:3`)
    - Exact-match anchors: stay at 10–20% (`linking-templates.md:3` / table at `:22`)
    - Min 3 incoming internal links per post — sourced from `codex-seo/skills/seo-cluster/SKILL.md:158`; same constraint also surfaces in `seo-cluster/references/hub-spoke-architecture.md:93`
    - No more than 2 clicks from pillar to any spoke — sourced from `seo-geo-claude-skills/optimize/internal-linking-optimizer/references/link-architecture-patterns.md:21` ("Letting pages drift beyond 2 clicks" as the Flat-architecture failure mode); same constraint stated affirmatively in `codex-seo/skills/seo-cluster/SKILL.md:159`
  - **Required-link-pattern table** for clusters (Pillar→cluster, Cluster→pillar, Cluster↔cluster) (`linking-templates.md:39-44`)
  - **Per-link suggestion shape**: from-URL, to-URL, anchor text, location, priority (`linking-templates.md:46-49`)
- **Reading commitment:** ideas, not lines. Apache 2.0 permits verbatim copying with attribution, but content-stack still authors fresh: we adopt the *7-step structure*, the *anchor-text variation percentages* (10-20 / 30-40 / 10-20 / 20-30), the *required-link-pattern table values*, and the *hard targets* as load-bearing thresholds, but every line of `interlinker/SKILL.md` is written from scratch against the `internal_links` table and `interlink.suggest`/`interlink.apply` MCPs. Apache 2.0 attribution to aaron-he-zhu in skill frontmatter and `docs/attribution.md` is mandatory.

### 4. STRIP map

- `research/keyword-research/`, `research/competitor-analysis/`, `research/serp-analysis/`, `research/content-gap-analysis/` → Research-phase skills. PLAN.md rows #1–3 source from codex-seo, not from here. We get richer DataForSEO/Firecrawl wiring from codex-seo. Don't double-source.
- `build/seo-content-writer/`, `build/geo-content-optimizer/`, `build/meta-tags-optimizer/`, `build/schema-markup-generator/` → Build-phase skills. PLAN.md content-production rows (#7/8/9/10) source from cody, not here. Schema (#16) sources from codex-seo. We don't need parallel skills.
- `optimize/on-page-seo-auditor/`, `optimize/technical-seo-checker/`, `optimize/content-refresher/` → On-page audit + technical SEO + content refresh from this upstream. PLAN.md row #2 (serp-analyzer) covers on-page audit via codex-seo's `seo-page`; technical SEO is out of scope; content-refresher (#24) sources from cody. Don't double-source.
- `monitor/rank-tracker/`, `monitor/backlink-analyzer/`, `monitor/performance-reporter/`, `monitor/alert-manager/` → Monitor phase. PLAN.md row #20 (gsc-opportunity-finder) is via codex-seo; backlinks/performance/rank-tracking are out of scope.
- `cross-cutting/domain-authority-auditor/` → CITE 40-item domain trust framework. PLAN.md doesn't include domain authority scoring; out of scope.
- `cross-cutting/entity-optimizer/` → Canonical entity profile (KG-style). Out of scope.
- `cross-cutting/memory-management/` → HOT/WARM/COLD project memory using `memory/hot-cache.md`. We have a database; this is a competing memory abstraction. Don't vendor.
- `commands/` (17 files) → Slash commands invoked as `/seo:<command>`. We use our own slash commands inside our procedures (PLAN.md). Don't vendor.
- `memory/` (sample HOT/WARM/COLD layout, audits/, entities/, evolution/, geo-feedback/, wiki/) → Memory layout. Don't vendor; our DB is the memory.
- `evals/` (eval cases for 3 skills) → Library-internal eval seeds. Out of scope.
- `hooks/hooks.json` → PostToolUse hook recommending `content-quality-auditor` after content writes. content-stack runs the EEAT gate as a *procedure step*, not a hook. Different invocation model.
- `.mcp.json` (14 servers including Ahrefs/Semrush/Cloudflare/Webflow/Sanity etc.) → Pre-configured MCP servers. We have our own integration list (PLAN.md line 462). Don't vendor.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codebuddy-plugin/marketplace.json`, `gemini-extension.json`, `qwen-extension.json`, `openclaw.bundle.json` → Six manifest files mirroring the same plugin to six runtimes. We mirror to two (Codex + Claude Code) via our `scripts/install-{codex,claude}.sh` (PLAN.md line 248).
- `references/cite-domain-rating.md` → CITE 40-item domain authority framework. Out of scope (no domain-authority skill).
- `references/AUDITOR-AUTHORS.md`, `references/contract-fail-caps.md`, `references/auditor-runbook.md`, `references/skill-contract.md`, `references/state-model.md` → Library-internal authoring references. The auditor-runbook bits we *do* need are inlined into `content-quality-auditor/SKILL.md` (per their ADR-001 about inlining the runbook for activation reliability) — we read the inlined version, not these.
- `references/decisions/` (ADRs) → Library-internal architecture decisions. Read for context, don't vendor.
- `references/evolution-*.md`, `references/skill-resolver.md`, `references/proposal-*.md`, `references/geo-score-feedback-loop.md`, `references/entity-geo-handoff-schema.md` → Skill-evolution + GEO loop + proposals. Library-internal, out of scope.
- `docs/README.zh.md` → Chinese localization. Don't vendor.
- `scripts/validate-skill.sh`, `scripts/validate-slimming-guardrails.sh` → Library-validation utilities.
- `.github/`, `CITATION.cff`, `CONTRIBUTING.md`, `SECURITY.md`, `PRIVACY.md`, `VERSIONS.md`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `CONNECTORS.md`, `.gitignore`, `.mailmap`, `.clawhubignore` → Standard repo paperwork. Read; don't vendor.

### 5. ADAPT notes

- **Skill #11 (eeat-gate)**: This is the most important adaptation in the stripping map.
  - **Critical change from upstream**: we use **project-specific EEAT criteria from the `eeat_criteria` table**, not the hardcoded 80-item list. The 80-item list is a *default seed* that `db/seed.py` populates for new projects, but each project can customize: re-weight items, deactivate items that don't apply (e.g., "first-person sensory details" doesn't apply to a B2B SaaS product page), or add custom items.
  - The skill calls `eeat.list` MCP at invocation time and audits against *those* criteria. Verdict comes from `eeat.score` MCP using the project's weights.
  - The three veto items (T04, C01, R10) become rows with `eeat_criteria.required = true`; ANY required-item Fail blocks publishing. This generalizes beyond exactly-three-vetoes.
  - On Fail → return loops to draft (PLAN.md procedure 4 step "eeat-gate" → "fail loops back to draft").
  - On Pass → `article.markEeatPassed` MCP transition.
  - `articles.status` enum for transitions: `edited → eeat_passed → published` (PLAN.md line 304).
  - Audit results land in `runs.metadata_json.eeat = {dimension_scores, system_scores, veto_state, top_issues}` for trail.
  - **Adversarial Codex review hook** (PLAN.md line 511, codex-plugin-cc): an optional invocation of `/codex:adversarial-review` runs on the same artifact for a second opinion before `markEeatPassed`. This is the seam in §codex-plugin-cc-install-summary.
- **Skill #15 (interlinker)**: 
  - The 7-step workflow runs against `articles WHERE status='published' AND project_id=:active`. Output is a list of `internal_links` rows with `status='suggested'`.
  - **Suggest-then-apply pattern**: `interlink.suggest` MCP creates `internal_links` rows with `status='suggested'`. The human (UI: `InterlinksView.vue`) reviews and either calls `interlink.apply` (transitions to `applied` and writes the actual link into `articles.edited_md` via a careful in-place edit) or `interlink.dismiss`.
  - Anchor text variation table (10/30/15/30 split for exact/partial/branded/natural) is enforced by the suggester: it tracks the cumulative anchor distribution per `to_article_id` and won't propose an anchor that violates the distribution.
  - Orphan-page detection: `articles WHERE id NOT IN (SELECT to_article_id FROM internal_links WHERE status='applied')` for the active project.
  - `R08 Internal Link Graph` from CORE-EEAT becomes a query: "every article has ≥3 incoming applied links and links to pillar/cluster siblings via descriptive anchors".

### 6. Integration callouts

- **MCP servers in `.mcp.json`**: 14 vendor MCPs (Ahrefs / Semrush / SE Ranking / SISTRIX / SimilarWeb / Cloudflare / Vercel / HubSpot / Amplitude / Notion / Webflow / Sanity / Contentful / Slack). We use Ahrefs (PLAN.md line 464, optional). The others are out of scope. **Carefully avoid copying** — using their `.mcp.json` would imply we depend on services we don't actually need, and would conflict with our own MCP registration approach (PLAN.md lines 547–561, MCP only points at our own daemon at localhost:5180).
- **`~~placeholder` connectors** (`CONNECTORS.md:1-126`): The library uses `~~SEO tool`, `~~web crawler`, `~~analytics`, `~~search console`, `~~AI monitor`, `~~CDN`, etc. as tool-category placeholders. We do not adopt this pattern — content-stack has explicit named integrations in `integrations/` per PLAN.md line 462. If a future skill author wants tool-agnostic prompts, they can read CONNECTORS.md for inspiration but should not propagate the `~~` syntax.
- **GSC-style search console connector**: The library docs mention `~~search console` (`CONNECTORS.md:11`) but no included MCP for it (note in `CONNECTORS.md:62-87` — manual paste from PSI). We use Google Search Console API directly via `integrations/gsc.py` (sourced from codex-seo). **Don't adapt their no-GSC-MCP fallback** because we have a real GSC integration.

### 7. Risks

- **Apache 2.0 attribution discipline**: We must credit aaron-he-zhu in our SKILL.md frontmatter for skills #11 and #15, and in `docs/attribution.md`. If we forget, we breach Apache 2.0 even though we're not vendoring.
- **80-item version drift**: `core-eeat-benchmark.md:1-7` says "v3.0" and notes a version-sync hint. The benchmark is itself a separate repo (`github.com/aaron-he-zhu/core-eeat-content-benchmark`) which evolves. Our `db/seed.py` should pin to v3.0 with a comment + a doc procedure for upgrading the seed when v4.0 lands. Don't auto-pull.
- **Veto-item ID stability**: The three vetoes (T04, C01, R10) are referenced in multiple files and our schema. If the upstream renumbers, our seed breaks. Keep the IDs in our seed but also store the *one-line standard text* so the row is self-describing.
- **`memory-management` and HOT/WARM/COLD memory model**: Their model assumes a markdown-file-tree. Our DB-row equivalent is fine, but a future skill author tempted to bring back `memory/hot-cache.md` should be reminded the database is canonical.
- **Skill naming collision with their phases**: We have `01-research/`, `02-content/`, `03-assets/`, `04-publishing/`, `05-ongoing/`. They have `research/`, `build/`, `optimize/`, `monitor/`, `cross-cutting/`. Don't accidentally adopt their phase names; PLAN.md is canonical (lines 207–233).
- **GEO 🎯 / SEO 🔍 / Dual ⚡ priority tags**: These are *theirs*, embedded in the rubric. We can keep the tags as-is (they're useful for prioritization), but in our voice we should note "GEO = AI-engine optimization" the first time the symbol appears; not every reader knows the distinction.
- **CC BY 4.0 not present in license metadata of the rubric**: The CORE-EEAT benchmark itself (separate repo) is licensed under what license? Check `github.com/aaron-he-zhu/core-eeat-content-benchmark` separately before we even paraphrase the standard. We'll need to update this risk row once that's confirmed; for now: assume Apache 2.0 carries through and credit accordingly, and re-check at M7 implementation.
- **`compatibility:` field in their SKILL.md frontmatter** (e.g., `content-quality-auditor/SKILL.md:7`): they declare compatibility with 12 agent runtimes. Our skills declare two (Codex + Claude Code) — don't copy that long compatibility list.
- **Their `class: auditor` and `allowed-tools: WebFetch` frontmatter fields** (`content-quality-auditor/SKILL.md:11, 6`): Claude Skills have an `allowed-tools` field that gates which tools the skill can call. We must replicate that for skills that fetch URLs (e.g., `eeat-gate` if it pulls live HTML via `firecrawl.scrape`). Don't forget. PLAN.md doesn't explicitly cover skill frontmatter discipline; we should add a row to `docs/extending.md`.
- **PostToolUse hooks**: `hooks/hooks.json` auto-triggers `content-quality-auditor` after content edits. Our procedure 4 explicitly chains EEAT after editor; we don't need a hook. If a future skill author tries to install a hook, that's a different invocation model and conflicts with our procedure-driven flow.

---

## codex-plugin-cc — INSTALL SUMMARY (not a strip map; not installed by us)

This is the **install-only peer** and we **do NOT bundle it in our installer**. PLAN.md line 511 marks the integration seam optional: "Optional: enables Codex sub-agents inside Claude Code; documented in `docs/extending.md` for adversarial EEAT review". 

**Locked decision (per audit §3 D2 cascade)**: codex-plugin-cc is **dropped from `scripts/install-codex.sh`** and from any other content-stack installer. The user installs it themselves via Claude Code's plugin marketplace if they want the adversarial-review seam; otherwise the EEAT gate runs primary-only. This avoids us inducing the install of a third-party plugin and keeps content-stack's installer dependency-free for that surface. `docs/extending.md` documents the manual install path for users who opt in.

**What is it.** OpenAI's official Claude Code plugin that wraps the local `codex` CLI as Claude Code slash commands. It exposes Codex as a delegate-able subprocess inside a Claude Code session: code review, adversarial review, rescue (delegate task), status/result/cancel for background jobs. Runtime is Node.js (`>=18.18.0`); the plugin itself is TypeScript-compiled-to-JS (`scripts/codex-companion.mjs`) that proxies to the global `codex` binary via the Codex app server. License: Apache-2.0 (`LICENSE` + `NOTICE`, `package.json:7`).

**How it's installed.** `package.json:1-22` is the npm manifest (`@openai/codex-plugin-cc`), private (not published to npm — installed via Claude Code's plugin marketplace). The user runs:

```
# In Claude Code:
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup
```

Behind the scenes Claude Code clones the plugin into its plugin store and invokes the marketplace.json (`/Users/sergeyrura/Bin/content-stack/.upstream/codex-plugin-cc/.claude-plugin/marketplace.json`) which points at `./plugins/codex/`. Inside `plugins/codex/.claude-plugin/plugin.json` (`name: codex, version: 1.0.4`) Claude Code discovers the commands directory + agents directory + hooks. Required prereq: the global `codex` binary, installed separately via `npm install -g @openai/codex` and authenticated via `codex login` (ChatGPT or API key).

`package.json:11-17` lists three scripts — `bump-version`, `prebuild` (regenerates app-server TS types via `codex app-server generate-ts`), `build` (tsc), `test` (node --test). None of these are run at user install.

**What it exposes to Claude Code.**

- **Slash commands** in `plugins/codex/commands/` (7 files):
  - `/codex:review` (`commands/review.md`): normal Codex code review of working tree or branch (`--base <ref>`).
  - `/codex:adversarial-review` (`commands/adversarial-review.md`): steerable challenge review that questions design/tradeoffs/assumptions. Read-only. Takes optional focus text after flags. The seam we care about (see below).
  - `/codex:rescue` (`commands/rescue.md`): delegates a coding task to Codex via the `codex:codex-rescue` subagent. `--background`, `--wait`, `--resume`, `--fresh`, `--model`, `--effort`, `--write` (default).
  - `/codex:status` (`commands/status.md`), `/codex:result` (`commands/result.md`), `/codex:cancel` (`commands/cancel.md`): inspect & manage background jobs.
  - `/codex:setup` (`commands/setup.md`): doctor + optional review-gate toggle.
- **Subagents** in `plugins/codex/agents/`:
  - `codex-rescue.md`: a thin forwarder that takes a rescue request and invokes `node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task ...`. Frontmatter declares `tools: Bash`, `skills: [codex-cli-runtime, gpt-5-4-prompting]`.
- **Internal skills** in `plugins/codex/skills/` (3 dirs):
  - `codex-cli-runtime/SKILL.md` (`user-invocable: false`): contract for calling `codex-companion.mjs`.
  - `codex-result-handling/SKILL.md`: how to present Codex output back to user.
  - `gpt-5-4-prompting/SKILL.md` + 3 reference docs: how to compose Codex/GPT-5.4 prompts with XML-tagged blocks (`<task>`, `<structured_output_contract>`, `<verification_loop>`, `<grounding_rules>`, etc.).
- **Hooks** in `plugins/codex/hooks/hooks.json`:
  - `Stop` hook (optional, opt-in via `/codex:setup --enable-review-gate`): runs a Codex review before letting Claude Code finish. Backed by `scripts/stop-review-gate-hook.mjs`. **Off by default.**
  - `SessionStart` hook (`scripts/session-lifecycle-hook.mjs`): bookkeeping.
- **Schemas**: `plugins/codex/schemas/review-output.schema.json` constrains Codex review output structure.

**The seam for content-stack.** PLAN.md procedure 4 step "eeat-gate" (lines 446–447) has an EEAT pass that, on `fail`, loops back to draft. If the user has codex-plugin-cc installed, we add an *optional adversarial second-pass* sandwich:

1. `eeat-gate` skill (#11) runs against the project's `eeat_criteria` rows → emits primary verdict + scored audit.
2. **If verdict == SHIP and `integrations.codex_plugin_cc.enabled = true`**: the skill issues a Bash call equivalent to:
   ```
   /codex:adversarial-review --background --wait
     "Audit this article against project EEAT criteria.
      Identify hidden weaknesses the primary auditor may have missed.
      Output: bullet list of issues with severity Critical/High/Medium/Low."
   ```
   Implementation in our skill SKILL.md will be a `Bash` invocation (Claude Code's plugin context provides `${CLAUDE_PLUGIN_ROOT}` at the codex-plugin-cc location) that pipes the article markdown via stdin or temp-arg.
3. The adversarial result merges into `runs.metadata_json.adversarial_review`. Critical/High issues add to the audit's blocker set; if any Critical issue surfaces, verdict downgrades to FIX or BLOCK and the article loops back to `editor`.
4. The user can disable this via `integration_credentials` row with `kind='codex-plugin-cc'`, `enabled=false`. Or simply not install the plugin (the call returns "plugin not available" and our skill skips the adversarial pass).

The exact call shape (verbatim, for reference at M7 authoring time):

```
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" adversarial-review "$ARGUMENTS"
```

We never call `codex` directly — we always go through `codex-companion.mjs` because that's the contract documented in `plugins/codex/skills/codex-cli-runtime/SKILL.md:11`.

**Prereqs.**

- Node.js 18.18.0+ (`package.json:9`). Our daemon is Python; this is a separate user-side prereq.
- Global `codex` binary installed (`npm install -g @openai/codex`) and authenticated (`codex login` — accepts ChatGPT subscription or API key per `README.md:18-19, 51`).
- Claude Code with plugin marketplace support.
- After plugin install, run `/codex:setup` to verify (and optionally `/codex:setup --enable-review-gate` if the user wants the Stop-time review hook — **we do not enable this** because it would interfere with our procedure-driven flow).
- All optional. If the user doesn't install codex-plugin-cc, content-stack works unchanged; the EEAT gate just runs primary-only.

**Read order for the M7 author wiring this seam:** start with `README.md:1-100` (overview + slash command catalog), then `plugins/codex/commands/adversarial-review.md` (the exact command we invoke), then `plugins/codex/skills/codex-cli-runtime/SKILL.md` (call contract). The implementation files (`scripts/codex-companion.mjs`, `scripts/lib/*.mjs`) are interesting for understanding but not required for our integration. Skill authors for #11 (eeat-gate) wire the seam *conditionally* — if the plugin is detected at runtime via the presence of `${CLAUDE_PLUGIN_ROOT}` and an enabled `integrations.codex_plugin_cc` row, otherwise the seam is a no-op.

---

## Original skills (no upstream)

Seven of content-stack's 24 skills have **no upstream reference**: they are authored entirely from PLAN.md and original design. Skill authors for these skills should **NOT** look for upstream artifacts — there are none. The PLAN.md catalogue rows (lines 466, 473, 474, 478, 479, 480, 484) are the canonical descriptions; this section expands each with a one-paragraph algorithm sketch, the DB tables touched, the MCP tools used, and the key risks that drive the design.

Skill authors must read PLAN.md's Database schema section (lines 341-404) and MCP tools section (lines 646-674) before writing each of these. There is no "what to keep / what to drop" map here because there is nothing upstream to keep or drop.

---

### `01-research/competitor-sitemap-shortcut` (PLAN.md row #5)

**Source:** Original (no upstream); concept reference: AM Media's "competitor sitemap trick" mentioned in PLAN.md row #5.

**Algorithm sketch:**
- Step 1: Resolve competitor domains. The project's own domain is in `projects.domain`; competitor URLs are passed in as a procedure-level argument (`procedures/02-topical-research`'s `args.competitor_domains: list[str]`) or seeded via human input in the bootstrap procedure. There is no `projects.competitors_json` column — competitor lists live in procedure args, not on the project row.
- Step 2: `httpx.get("<domain>/sitemap.xml")` — handle `sitemap-index.xml` recursion (sub-sitemaps) and gzipped variants. Fall back to `/robots.txt` `Sitemap:` directive discovery.
- Step 3: Parse XML, extract `<url><loc>` entries; filter out non-content paths (tag pages, author archives) by URL pattern heuristics.
- Step 4: Optional: pull an Ahrefs CSV export (top organic keywords + ranking URLs) and join it on the URL list to add ranking-volume signal.
- Step 5: Hand the deduplicated, signal-augmented URL list to skill #3 (`topical-cluster`) as the seed corpus instead of the usual keyword-discovery output. Topical-cluster's SERP-overlap algorithm runs against the URLs' titles and meta descriptions.

**DB tables touched:** `topics` (writes one row per identified competitor URL with `source='competitor-sitemap'`); reads `projects.domain` (the project's own domain, for self-exclusion); reads `clusters` to dedupe vs. existing clusters; writes `runs.metadata_json.competitor_url_count` for trail. Competitor domains themselves are NOT stored on the project — they arrive as procedure args.

**MCP tools used:** `topic.bulkCreate` (to write the discovered URLs as topic candidates), `cluster.list` (to check existing topical coverage), `project.get` (to read the project's own `domain` for self-exclusion).

**Key risks:**
- Sitemaps can be enormous (10k+ URLs). Apply pagination + a cap (PLAN.md should specify; suggested 500 URLs/competitor) to avoid OOM and DataForSEO budget blowouts when the cluster skill processes them.
- Some sites disallow `sitemap.xml` access via `robots.txt`. Honor robots.txt; document fallback as "manual paste" in the skill.
- Ahrefs CSV format drifts; pin to a documented column shape (`URL,Keyword,Position,Volume,Traffic`) and fail loud on missing columns rather than silently corrupting clusters.

---

### `02-content/humanizer` (PLAN.md row #12)

**Source:** Original (no upstream); concept reference: AM Media's "post-publish humanization pass" mentioned in PLAN.md row #12.

**Algorithm sketch:**
- Step 1: Read `articles.edited_md` (the editor's already-cleaned output); humanizer runs *after* editor.
- Step 2: Parse the markdown into sections; for each paragraph, compute current sentence-length variance (avg + std-dev of sentence word counts).
- Step 3: For paragraphs with low variance (suggests AI-uniform rhythm), prompt the LLM to vary sentence length by combining short sentences with a longer sustained clause, or fragmenting a long sentence into a sharp short one.
- Step 4: Beyond the editor's AI-tell pass, scan for second-order tells: "let's dive into" / "in this comprehensive guide" / "we'll explore" / repetitive transition words at paragraph starts; suggest replacements.
- Step 5: Inject one anecdote-style aside per ~700 words at natural section boundaries (the LLM produces an aside grounded in the brief's `voice.author_voice` description; user reviews and accepts/rejects).
- Step 6: Persist result to `articles.edited_md` (overwrite) — humanizer runs *once* per article version per AM Media's recommendation (PLAN.md row #12 narrative); rerunning is allowed only after a new editor pass.
- Step 7: Audit completion is recorded by the `runs` row this skill writes (`kind='humanize-pass'`). To detect "already humanized at this version" without a dedicated column, query `runs WHERE kind='humanize-pass' AND article_id=:a AND status='success' ORDER BY started_at DESC LIMIT 1` and compare its `started_at` against `articles.updated_at` — if the most recent successful humanize-pass post-dates the last edit, the version is already humanized. Refresh-detector and refresher use the same query rather than a denormalized timestamp.

**DB tables touched:** `articles` (reads `edited_md`, `brief_json`; writes `edited_md`); `voice_profiles` (reads active voice's prose-style preferences); `runs` (writes one row with `kind='humanize-pass'` per PLAN.md L391 enum). No new column; the `runs` audit log is the source of truth for "did we humanize this version".

**MCP tools used:** `article.get`, `article.setEdited`, `voice.get`, `run.start`, `run.finish`, `run.list` (to query prior humanize-pass runs for this article). **Note**: humanizer does NOT call `article.createVersion`; only refresh creates new versions.

**Key risks:**
- Voice drift: humanizer can over-stylize away from the project voice. Mitigation: pass the active `voice_profiles.voice_md` as a constraint in the prompt; reject paragraphs whose tone embedding diverges past a threshold (track in `runs.metadata_json.voice_drift_score`).
- Citation breakage: the editor pass already commits to "do not modify citation markers"; humanizer must inherit that invariant. Test: cite-marker count before/after must match exactly.
- Idempotency: running humanizer twice on the same `edited_md` should produce the same output (or a flag should refuse the second run). Per PLAN.md row #12 it is "once per article version" — enforce by querying the prior `runs` row of `kind='humanize-pass'` and comparing to `articles.updated_at` as described in step 7.

---

### `03-assets/image-generator` (PLAN.md row #13)

**Source:** Original (no upstream); reference: PLAN.md row #13 ("OpenAI Images API wrapper; persists to `article_assets`").

**Algorithm sketch:**
- Step 1: Read article context: `articles.edited_md` (for hero alt-text grounding), `articles.brief_json.image_directives` (per-PLAN.md L410-422, an optional sub-field on `brief_json` carrying `{count, style?, alt_text_hints?, allow_real_persons?}`), and the active voice's `voice_profiles.voice_md` (free-form markdown). Image style is parsed out of `voice_md` via prompt instruction; there is no dedicated `image_style` column.
- Step 2: For each requested image (typically 1 hero + N inline + 1 OG/social), compose a prompt that grounds in the article's primary topic, the surrounding paragraph for inline images, and the project's brand voice extracted from `voice_md`.
- Step 3: Call OpenAI Images API (`gpt-image-1` or `dall-e-3` per the model preference in `integration_credentials WHERE kind='openai-images'` config_json).
- Step 4: For each generated image: write the PNG bytes to disk under `~/.local/share/content-stack/assets/<project_slug>/<article_id>/<asset_id>.png` (binary blobs are not stored in SQLite to keep the DB small and `make backup` fast); persist metadata to `article_assets` (alt_text, kind, file_size_bytes, format, width, height, file_path).
- Step 5: Auto-generate `alt_text` from the image-prompt + article-context using the same LLM (10-125 chars, descriptive, includes natural keyword from the section's H2). The `brief_json.image_directives.alt_text_hints` (optional) is used as priming.
- Step 6: Hand off to skill #14 (`alt-text-auditor`) which validates the generated alt-text against the rubric.

**DB tables touched:** `article_assets` (writes one row per generated image with `kind ∈ {hero, inline, og, twitter}`); reads `articles.brief_json.image_directives` (the documented sub-field on the existing `brief_json` JSON column); reads `voice_profiles.voice_md` for style extraction; reads `integration_credentials WHERE kind='openai-images'`; reads `integration_budgets WHERE kind='openai-images'` for the per-project monthly budget; reads `compliance_rules WHERE kind='custom'` to discover any `validators.real_persons_in_images` rule; writes `runs.metadata_json.images_generated_count` and per-image cost into `runs.metadata_json.cost.by_integration['openai-images']`.

**MCP tools used:** `asset.create`, `asset.update`, `article.get`, `voice.get`, `compliance.list` (filtered by `kind='custom'` to fetch any real-persons rule), `budget.queryProject` (pre-call check), `cost.queryProject` (estimate vs. monthly cap), `run.start`, `run.finish`. The skill does NOT need a dedicated `integration.get` — credentials are resolved by the daemon on the OpenAI Images call itself.

**Key risks:**
- Cost runaway: image gen is the most expensive per-call OpenAI integration. The per-project image budget lives in `integration_budgets WHERE kind='openai-images'`; the skill calls `cost.queryProject` and refuses if `current_month_spend + estimated_cost > monthly_budget_usd`. Per-article count caps live in `articles.brief_json.image_directives.count` (defaulting to 6 if omitted).
- Brand-voice drift: stock-photo aesthetic vs. illustrated vs. photorealistic must be project-controlled. Read it from `voice_profiles.voice_md` (free-form markdown, parsed via prompt instruction) or from `brief_json.image_directives.style` if the brief author overrode it for this article. Skill must refuse generation if neither source provides any style guidance.
- Storage location vs. backup: blobs live on disk, not in SQLite. `make backup` must include the assets directory; `make restore` must symlink-or-copy back. Document this clearly.
- Right-of-publicity / face generation: prompts that name real people are forbidden by default. The opt-in is set globally in the project's `compliance_rules` with `kind='custom'` and validator name `validators.real_persons_in_images`; the image-generator reads `compliance.list(project_id, kind='custom')` at invocation. A per-article override is available via `brief_json.image_directives.allow_real_persons` (boolean).

---

### `04-publishing/nuxt-content-publish` (PLAN.md row #17)

**Source:** Original (no upstream); reference: PLAN.md row #17 ("Write `.md` + frontmatter to `content/` repo, git commit, git push").

**Algorithm sketch:**
- Step 1: The procedure runner already knows which target it is publishing to (procedure 4 fans out across active targets). The skill reads its target row via `target.list(project_id)` filtered to `kind='nuxt-content'`. The target's `config_json` holds: `repo_path`, `content_subdir`, `branch`, `git_remote`, `commit_template`, `public_url_pattern`, AND the per-target frontmatter template configuration. There is no separate `frontmatter_template_json` column — template config lives inside the existing `publish_targets.config_json`.
- Step 2: Read the article: `articles.edited_md`, `articles.brief_json` (for SEO meta), `article_assets` rows (for hero/inline images), `schema_emits` rows (for JSON-LD frontmatter or `<script>` injection).
- Step 3: Compose Nuxt Content frontmatter by merging `articles.edited_md` + `schema_emits.schema_json` + the template configuration from `publish_targets.config_json`. Standard fields: title, description, slug, published_at, updated_at, author, tags, hero_image, og_image, schema_jsonld. Persist the resulting flat key→value map into `article_publishes.frontmatter_json` (per PLAN.md L425-431, this column is per-target snapshot at publish time).
- Step 4: Compose the `.md` body: edited_md inlined, with image references rewritten to point at the published asset paths (typically `/images/<asset_filename>` relative to the Nuxt site).
- Step 5: Resolve target file path: `<repo_path>/<content_subdir>/<article.slug>.md` (e.g., `content/blog/<slug>.md`).
- Step 6: Copy referenced assets from `~/.local/share/content-stack/assets/<project>/<article>/*` to `<repo_path>/public/images/`.
- Step 7: `git add`, `git commit -m "<commit_template applied to article>"`, `git push origin <branch>` via `subprocess.run(["git", ...], cwd=repo_path)`. The git work runs inside the daemon process (the publish step in procedure 4 is daemon-orchestrated) — there is no separate `publish.run` MCP. Skill authors should use `publish.preview` (the only publish MCP, per PLAN.md L670) to dry-run a payload during development.
- Step 8: Capture commit SHA + push response into `article_publishes` row (one per target per version published per B-08 schema additions): `published_url` is computed from `<publish_targets.config_json.public_url_pattern>` (e.g., `https://example.com/blog/{slug}`). Status `published` if push succeeded, `failed` with `error` if not.

**DB tables touched:** `articles` (reads), `article_assets` (reads + copies blobs), `schema_emits` (reads), `publish_targets` (reads `config_json` for both target and frontmatter template config), `article_publishes` (writes the publish row including its `frontmatter_json` snapshot), `runs` (writes `kind='publish-push'` per PLAN.md L391 enum).

**MCP tools used:** `article.get`, `asset.list`, `schema.get`, `target.list` (filtered by `kind='nuxt-content'`), `publish.preview` (for dry-run during development), `run.start`, `run.finish`. The git push itself is performed in the daemon's publish step — it is not a separate MCP tool.

**Key risks:**
- Git auth: the daemon must have access to the repo's push credentials. Spec via SSH key or git-credential-helper; document in `docs/api-keys.md`. Refuse to publish if `git push` would prompt for password.
- Slug collisions inside the target repo: if `<slug>.md` already exists from an earlier publish (different project, same slug), publish fails. Detect at preview time, surface to user via `publish.preview` MCP.
- Stale repo: the local clone must be `git pull --ff-only` before composing changes. Refuse the publish if the working tree is dirty (avoid clobbering uncommitted edits in the target repo).
- Commit-message safety: `commit_template` is user-controlled and goes into shell. Pass via `-m` arg, not a shell-interpolated string; never `eval` it.

---

### `04-publishing/wordpress-publish` (PLAN.md row #18)

**Source:** Original (no upstream); reference: PLAN.md row #18 ("WordPress REST API `/wp-json/wp/v2/posts`").

**Algorithm sketch:**
- Step 1: Resolve target via `target.list(project_id)` filtered to `kind='wordpress'`. The target's `config_json` holds `wp_url`, `auth_method` (application_password | jwt), `default_status` (draft | publish | future), `category_ids[]`, `tag_ids[]`, and the per-target frontmatter/meta template. There is no separate `frontmatter_template_json` column. Credentials live in `integration_credentials WHERE kind='wordpress'` and are resolved by the daemon's helper at REST call time — the skill does not read encrypted blobs directly.
- Step 2: For each `article_assets` row of kind hero/inline: POST to `/wp-json/wp/v2/media` with multipart form-data; capture the returned media ID and replace in-body image paths with the WP-hosted URL.
- Step 3: Compose post payload: title, content (HTML rendered from `edited_md` via markdown-it; honor the project's WP-specific HTML rules), excerpt (from `brief_json.meta_description`), slug, status, categories, tags, featured_media (the hero image's WP media ID), meta (custom fields including JSON-LD body). The composed flat-map snapshot persists to `article_publishes.frontmatter_json` per PLAN.md L425-431.
- Step 4: POST to `/wp-json/wp/v2/posts` with `Authorization: Basic` (application password) or `Authorization: Bearer` (JWT). Capture returned post ID, link, modified_at. The HTTP work happens inside the daemon's procedure 4 publish step; there is no separate `publish.run` MCP.
- Step 5: Persist to `article_publishes` row (with the per-target `frontmatter_json` snapshot from step 3).

**DB tables touched:** `articles`, `article_assets`, `publish_targets` (reads `config_json` for both target and frontmatter template config), `article_publishes` (writes including `frontmatter_json` snapshot), `integration_credentials` (read indirectly by the daemon helper via `kind='wordpress'`), `runs` (writes `kind='publish-push'`).

**MCP tools used:** `article.get`, `asset.list`, `target.list` (filtered by `kind='wordpress'`), `publish.preview` (for dry-run), `run.start`, `run.finish`. Credential resolution is handled by the daemon's HTTP helper, not by an MCP call from the skill.

**Key risks:**
- Application passwords have wide privileges; refuse to operate if the target user account isn't role-restricted (Editor or Author, not Administrator). Document in `docs/api-keys.md`.
- Media uploads can fail mid-batch; either rollback (delete uploaded media on post failure) or accept orphan media. Recommendation: track every uploaded media ID in `article_publishes.metadata_json.media_ids` so a retry can dedupe.
- HTML sanitization: WordPress strips some HTML by default (depending on user role). Test with a canonical article and lock the markdown-to-HTML rules accordingly.
- Status semantics: `draft` lands invisibly; `publish` goes live immediately; `future` requires `date` field. Skill should default to `draft` and require an explicit user confirmation (UI-side) before `publish`.

---

### `04-publishing/ghost-publish` (PLAN.md row #19)

**Source:** Original (no upstream); reference: PLAN.md row #19 ("Ghost Admin API").

**Algorithm sketch:**
- Step 1: Resolve target via `target.list(project_id)` filtered to `kind='ghost'`. The target's `config_json` holds `ghost_url`, `default_status`, and per-target frontmatter/meta template. The Ghost Admin API key (`{key_id}:{secret}` form) lives in `integration_credentials WHERE kind='ghost'` and is resolved by the daemon's HTTP helper at PUT-time — the skill does not read encrypted blobs directly.
- Step 2: The daemon's helper mints a JWT per Ghost's Admin API auth (HS256 signing with the secret half of the admin API key, 5-minute exp, `kid` from the key_id half). The JWT lifecycle is handled inside the helper, not the skill.
- Step 3: Upload images via `PUT /ghost/api/admin/images/upload/` (multipart) through the daemon helper; capture returned URLs.
- Step 4: Compose post payload using Ghost's Lexical or mobiledoc format. Lexical is preferred for v5+; use `mobiledoc` only if `config_json.format='mobiledoc'`. Fields: title, slug, html (we send HTML and let Ghost convert), feature_image, status, custom_excerpt, tags[], authors[]. The composed flat-map snapshot persists to `article_publishes.frontmatter_json`.
- Step 5: PUT to `/ghost/api/admin/posts/?source=html` (the `?source=html` is critical — it tells Ghost to convert from HTML rather than expecting Lexical/mobiledoc). The HTTP work happens inside the daemon's procedure 4 publish step; there is no separate `publish.run` MCP.
- Step 6: Persist to `article_publishes` row with the returned post ID and URL (and the per-target `frontmatter_json` snapshot from step 4).

**DB tables touched:** `articles`, `article_assets`, `publish_targets` (reads `config_json` for both target and template config), `article_publishes` (writes including `frontmatter_json`), `integration_credentials` (read indirectly by the daemon helper via `kind='ghost'`), `runs` (writes `kind='publish-push'`).

**MCP tools used:** `article.get`, `asset.list`, `target.list` (filtered by `kind='ghost'`), `publish.preview` (for dry-run), `run.start`, `run.finish`. Credential resolution and JWT minting are handled by the daemon's helper, not by MCP calls from the skill.

**Key risks:**
- JWT expiration: tokens are short-lived (5 minutes); if upload + post takes longer, mint a fresh token mid-flow. Don't cache tokens past their `exp`.
- HTML→Lexical conversion lossiness: certain HTML constructs (custom shortcodes, complex tables) round-trip poorly. Test with a canonical article matching the project's typical content shape; lock the HTML emitter accordingly.
- Newsletter sending: Ghost's posts can auto-send to email subscribers when `email_only=false` and `status='published'`. Default to `email_only=true` (or `status='draft'` then user manually publishes via Ghost UI) to avoid accidental email blasts during automation.
- Tag taxonomy drift: Ghost requires tags to exist (or it auto-creates). Decide a policy: auto-create tags from `articles.brief_json.tags`, or refuse-if-not-found. Recommend auto-create with a flag.

---

### `05-ongoing/refresh-detector` (PLAN.md row #23)

**Source:** Original (no upstream); reference: PLAN.md row #23 ("articles.published_at age + GSC trend + drift score → schedule refresh").

**Algorithm sketch:**
- Step 1: Read project config first via `project.get(project_id)`. Refresh thresholds live inside `projects.schedule_json` (the existing JSON column already used for cron schedules); the skill expects keys like `{refresh_age_days: 90, gsc_drop_pct: 30, drift_score_threshold: 0.3, refresh_score_min: 5}`. There is no dedicated `projects.refresh_threshold` column — extending `schedule_json` to carry these tuning knobs keeps the schema stable.
- Step 2: Iterate `articles WHERE status='published' AND last_evaluated_for_refresh_at < NOW() - INTERVAL '7 days'` (the `last_evaluated_for_refresh_at` column is added per audit B-15; reading this avoids re-evaluating articles every day).
- Step 3: For each candidate, compute three sub-scores:
  - **Age score**: months since the article's last `article_versions.published_at`; >12 months = +2, >24 months = +4, >36 months = +6. Threshold-based.
  - **GSC trend score**: query `gsc_metrics_daily` (the rollup added per audit M-01) for last-90d trailing trend. Falling clicks (>15% drop, or per `schedule_json.gsc_drop_pct`) = +3. Falling impressions = +2. Position-rank deterioration (avg position >5 worse than 90d ago) = +2.
  - **Drift score**: fetch the latest `drift_baselines` snapshot for this article via `drift.list(article_id, limit=1, sort=-captured_at)` (per PLAN.md L667 catalog: `drift.* snapshot | diff | list | get`). CRITICAL diffs since `articles.last_refreshed_at` = +5; WARNING diffs = +2.
- Step 4: Sum to a `refresh_score`. If `refresh_score >= schedule_json.refresh_score_min` (default 5), call `article.markRefreshDue` and write a `runs` row with `kind='refresh-detector'` and the score breakdown in `metadata_json` per PLAN.md L441.
- Step 5: Update `articles.last_evaluated_for_refresh_at = NOW()` for ALL candidates (passing or failing the threshold) so we don't reconsider them tomorrow.
- Step 6: Sort the `refresh_due` queue by score DESC + impressions DESC (high-traffic stale first); skill #24 (`content-refresher`) consumes from that queue.

**DB tables touched:** `articles` (reads `status`, `last_refreshed_at`, `last_evaluated_for_refresh_at`; writes `status='refresh_due'`, `last_evaluated_for_refresh_at`); `article_versions` (reads `published_at` of the latest version per article); `gsc_metrics_daily` (reads for trend); `drift_baselines` (reads latest snapshot); `runs` (writes `kind='refresh-detector'`); `projects` (reads `schedule_json` for thresholds).

**MCP tools used:** `article.list` (with status filter), `article.markRefreshDue` (per audit M-13), `gsc.queryProject` (trailing 90d aggregate), `drift.list(article_id, limit=1, sort=-captured_at)` (latest baseline per article), `run.start`, `run.finish`. Reads project config via `project.get` (which surfaces `schedule_json`).

**Key risks:**
- Cold-start: articles with no GSC data (no impressions ever) score 0 on GSC trend. Don't treat 0 as "no signal" — treat as "no change" so age/drift can still trigger.
- Threshold sensitivity: too low → constant refresh churn; too high → stale content. Default `refresh_score_min=5` (in `projects.schedule_json`) is a guess; expose as project setting and document tuning guidance.
- GSC quota: the trailing 90d query per article is expensive. Mitigation: the `gsc_metrics_daily` rollup (M-01) lets us aggregate from local data; only fall back to live GSC if the rollup is empty for the period.
- Idempotency vs. eventual consistency: a refresh-detector run that crashes mid-way may have set `last_evaluated_for_refresh_at` for some but not all candidates. Use a single transaction per candidate (acquire `articles.lock_token` per B-07/M-40 invariants) so partial state is consistent.

---

### Critical Files for Implementation

Per the locked clean-room decisions, **the read-allow-list depends on which skill is being authored**.

**For skills sourced from cody-article-writer (#4, #6, #7, #8, #9, #10, #24)** — the skill author must NOT read any cody file. Allowed reads are:

- /Users/sergeyrura/Bin/content-stack/PLAN.md
- /Users/sergeyrura/Bin/content-stack/docs/upstream-stripping-map.md (this file — the adapt notes are second-order summaries authored against PLAN.md)

**For skills sourced from codex-seo (#1, #2, #3, #14, #16, #20, #21, #22)** — the skill author may read codex-seo files for *concept verification* (e.g., to confirm the SERP-overlap thresholds we cite are still 7-10/4-6/2-3/0-1) but must NOT copy any prose, prompt text, or script body verbatim. Allowed reads:

- /Users/sergeyrura/Bin/content-stack/PLAN.md
- /Users/sergeyrura/Bin/content-stack/docs/upstream-stripping-map.md
- /Users/sergeyrura/Bin/content-stack/.upstream/codex-seo/skills/seo-cluster/SKILL.md (for concept verification of skill #3 only)
- /Users/sergeyrura/Bin/content-stack/.upstream/codex-seo/skills/seo-google/SKILL.md (for concept verification of skill #20 only)

**For skills sourced from seo-geo-claude-skills (#11, #15)** — Apache 2.0 permits reading; attribution required:

- /Users/sergeyrura/Bin/content-stack/PLAN.md
- /Users/sergeyrura/Bin/content-stack/docs/upstream-stripping-map.md
- /Users/sergeyrura/Bin/content-stack/.upstream/seo-geo-claude-skills/references/core-eeat-benchmark.md (the 80-item rubric — load-bearing for #11)
- /Users/sergeyrura/Bin/content-stack/.upstream/seo-geo-claude-skills/optimize/internal-linking-optimizer/references/linking-templates.md (output templates — load-bearing for #15)

**For original skills (#5, #12, #13, #17, #18, #19, #23)** — there are no upstream reads:

- /Users/sergeyrura/Bin/content-stack/PLAN.md
- /Users/sergeyrura/Bin/content-stack/docs/upstream-stripping-map.md (this file — the "Original skills (no upstream)" section above)

In every case, PLAN.md is the canonical spec and this strip map is the only second-order reference; everything else is concept-verification scope only and must be paraphrased to zero verbatim text per the licensed-clean-room rule.