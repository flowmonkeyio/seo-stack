I now have everything I need. Producing the audit.

---

# content-stack — PLAN.md audit (pre-M0 sign-off)

This audit walks every paragraph of `PLAN.md` against the locked decisions, the strip-map, and the four cloned upstreams. It surfaces gaps, inconsistencies, and unlocked sub-decisions that must be resolved before the foundation is poured. Findings are grouped by dimension (A–K). Every finding has a Location, Severity, and a concrete Fix.

---

## A. COMPLETENESS

### A1 — Every claim must have a spec section

**Finding**: PLAN.md mentions a Makefile target `make install` (lines 642–643) and `make build-ui` (line 574) but no Makefile section enumerates targets. Doctor must "report green on a fresh machine after `make install`" — but `make install` is not specified anywhere.
**Location**: lines 575, 642–643, plus `Makefile` filename at line 128.
**Severity**: BLOCKER (M0 ships the Makefile).
**Fix**: Insert a "Makefile targets" subsection after line 119 listing exactly: `install`, `serve`, `build-ui`, `register-codex`, `register-claude`, `install-skills-codex`, `install-skills-claude`, `install-procedures-codex`, `install-procedures-claude`, `install-launchd`, `doctor`, `test`, `migrate`, `lint`, `clean`. State which targets are idempotent, which require a running daemon, and the order `make install` runs them in.

### A2 — `cli.py` commands are listed but not specified

**Finding**: line 133 says `cli.py # serve | init | migrate | install | doctor`. No spec section explains what each subcommand does, the flags, or exit codes.
**Location**: line 133.
**Severity**: BLOCKER for M0.
**Fix**: Add a "CLI reference" section after Daemon Strategy (line 537). For each subcommand, specify: name, args/flags, side effects (touches DB? touches filesystem? prompts user?), exit codes (0 success / 1 misuse / 2 dependency missing / 3 db locked / 4 migration failed). Specifically: `init` is mentioned only here — does it create XDG dirs, run `alembic upgrade head`, write a default config, or all three?

### A3 — `procedures/_template/` content unspecified

**Finding**: line 245, 452 references the template scaffold but PLAN.md never lists the YAML frontmatter fields that every `PROCEDURE.md` must contain. The fields are alluded to as "When to use / Prerequisites / Steps / Outputs / Failure handling / Variants" (lines 432–435) but none are formally specified as YAML frontmatter keys vs. markdown sections.
**Location**: lines 432–435, 245, 452.
**Severity**: BLOCKER for M0 (procedure template is a foundation deliverable).
**Fix**: Insert after line 437 a fenced YAML block showing the canonical frontmatter: `name`, `version`, `triggers`, `prerequisites` (list of DB-row predicates), `produces` (list of mutated tables), `steps` (each with `id`, `skill`, `mcp_calls`, `on_failure`), `variants`, `concurrency_limit`. Then specify which fields are frontmatter vs. body markdown.

### A4 — UI `MarkdownEditor` is "(textarea)" — no spec for save semantics

**Finding**: line 199, 589 — the editor is a textarea. PLAN.md does not specify autosave vs. explicit save, conflict resolution if the LLM writes the same row, or whether edits create a new `articles.version`.
**Location**: lines 199, 589.
**Severity**: MAJOR for M2 (UI is M6).
**Fix**: After line 202, add: "Editor uses optimistic concurrency on `articles.updated_at`; PUT returns 409 on stale write; the UI prompts "remote changed — reload or overwrite". Manual save creates a `runs` row with `kind='manual-edit'` and increments `articles.version` only if `edited_md` differs by ≥ 1 line."

### A5 — "Auto-generate TS types from FastAPI OpenAPI in CI" claimed but no tool named

**Finding**: line 632 says auto-gen TS types in CI. line 183 says `api.ts # auto-generated from FastAPI OpenAPI`. Tool not named (e.g., `openapi-typescript`, `orval`, `swagger-typescript-api`).
**Location**: lines 183, 632.
**Severity**: MINOR (M3 deliverable).
**Fix**: After line 183, append: "Generated via `openapi-typescript` invoked from `make build-ui`. Lockfile committed; CI fails if regeneration would produce a diff."

### A6 — `frontmatter_json` on `articles` is mentioned but its shape isn't defined

**Finding**: line 288 lists `frontmatter_json` as an `articles` column. Used by publish skills (rows 17/18/19) — but no schema for the JSON. Each publish target (Nuxt Content vs. WP vs. Ghost) needs different frontmatter.
**Location**: line 288.
**Severity**: MAJOR for M7 (skill authors need this), BLOCKER for schema design at M1.
**Fix**: Add a subsection "JSON column shapes" after line 309. Specify `articles.frontmatter_json` is a flat key→value map computed at publish time from the active `publish_targets.config_json` template + article fields. Specifically: title, slug, description, canonical_url, og_image, og_description, schema_ref (FK-like into `schema_emits`), tags, categories, author, published_at_iso, last_refreshed_at_iso. Persisted on each publish for auditability.

### A7 — `runs.metadata_json` is referenced six times but no schema

**Finding**: lines 295, 631, 636, plus strip-map references. Skills write per-run cost, eeat verdict, drift severity, adversarial review, etc. Without a stable shape, downstream UI/queries fragment.
**Location**: line 295.
**Severity**: BLOCKER for M2.
**Fix**: Add a "JSON column shapes" subsection after line 309. Specify `runs.metadata_json` is a discriminated-union by `runs.kind`. List the `kind` values exhaustively: `procedure-run`, `skill-run`, `gsc-pull`, `drift-check`, `refresh-detector`, `eeat-audit`, `publish-push`, `manual-edit`, `crawl-error-watch`, `humanize-pass`, `bulk-launch`, `interlink-suggest`. For each, list required keys (e.g., `eeat-audit` requires `dimension_scores: {C,O,R,E,Exp,Ept,A,T → 0–100}`, `system_scores: {GEO,SEO}`, `verdict: SHIP|FIX|BLOCK`, `vetoes: string[]`, `top_issues: {item_id, severity, finding}[]`).

### A8 — Logging strategy unspecified

**Finding**: line 531 names a daemon log file but never names a logging library, log format, rotation policy, or per-skill correlation. `runs` row IDs should appear in log lines for trace.
**Location**: line 531.
**Severity**: MAJOR.
**Fix**: After line 532, add: "Logs use Python's `logging` with `structlog` for JSON output. Format: `{ts, level, logger, run_id?, project_id?, msg, kv}`. Rotation via `RotatingFileHandler` at 10MB×5. `runs.id` is set in a contextvar at procedure-run start so all downstream calls inherit it."

### A9 — i18n / locale mention is incoherent

**Finding**: line 282 lists `projects.locales` (plural). line 620 says "translation pipeline" out of scope but "handle via skill prompt + locale on `projects`". `articles` has no locale FK or column. The `slug` is project-scoped but locale-blind.
**Location**: lines 282, 288, 620.
**Severity**: MAJOR (covered fully in §B6; flagged here as a completeness gap because PLAN.md asserts locales are supported but doesn't carry them through to articles/topics).
**Fix**: See B6.

### A10 — `seed.py` content unspecified

**Finding**: line 140, 590, 591 reference `db/seed.py`. The strip-map (cody §5 ADAPT, aaron §5 ADAPT) implies seed includes default EEAT 80-item rows, default schema-emit templates, default voice profile, default compliance rule set. None of this is in PLAN.md.
**Location**: line 140.
**Severity**: BLOCKER for M1 (seed is M1).
**Fix**: Add a "Seed data" subsection after the database schema (after line 309). List exactly what `seed.py` populates: (a) zero rows in any project-scoped table — projects bootstrap themselves; (b) a default row in `eeat_criteria` *only when a project is created* (template seeded at project creation, not at DB init); (c) `schema_emits` default templates (Article, BlogPosting, FAQPage, Product, Organization, Review) with placeholders. Clarify: does `seed.py` run on every daemon start (idempotent), only on `init`, or only when DB is empty?

### A11 — README quickstart and PLAN.md install diverge

**Finding**: README.md says `uv pip install -e .` then `make build-ui` then `make serve`; PLAN.md says `make install` brings up everything (line 642). The two install paths are not reconciled.
**Location**: PLAN.md line 642, README.md line 21–37.
**Severity**: MINOR.
**Fix**: After line 567 in PLAN.md, add: "`make install` is the single onboarding command and wraps: `uv pip install -e .`, `alembic upgrade head`, `make build-ui` (idempotent), `make register-codex`, `make register-claude`, `make install-skills-codex`, `make install-skills-claude`, `scripts/doctor.sh --json`. README quickstart MUST be regenerated from this list to stay in sync."

### A12 — `procedures-guide.md` content unspecified

**Finding**: line 262 lists this doc; no contract for what it contains.
**Location**: line 262.
**Severity**: MINOR.
**Fix**: Add to docs section: "Documents PROCEDURE.md frontmatter (see A3), step DSL, MCP-tool inventory, failure handling primitives (`retry`, `loop_back`, `abort`, `human_review`), and shows the topic-to-published procedure as a worked example."

---

## B. SCHEMA SOUNDNESS

A walk through procedures 1–8 against the 16 tables.

### B1 — `refresh_detector`'s scheduling query has no expressible schema

**Finding**: refresh-detector (skill #23, line 421) selects "N oldest articles" using `articles.published_at` age + GSC trend + drift score. Schema gaps:
- `articles.published_at` exists. Good.
- "GSC trend" requires a window function over `gsc_metrics` per article. `gsc_metrics` is captured per snapshot and per query — but refresh-detector wants per-article trend. The query `SELECT article_id, AVG(impressions) WHERE captured_at > date('now', '-30 days')` is expensive without an index on `(article_id, captured_at)`.
- "drift score" comes from `drift_baselines.current_score` — but `drift_baselines` has `article_id` as the only project link, and the strip-map says drift watches *published* articles. So we need `WHERE drift_baselines.article_id IN (SELECT id FROM articles WHERE status='published' AND project_id=:p)` with two joins.
- No table records "I evaluated this article on date X and decided not to refresh." Without a "last decision" timestamp, the detector re-evaluates the same articles every run.
**Location**: lines 167, 421, 449, 294.
**Severity**: BLOCKER for M1 schema.
**Fix**:
1. Add column `articles.last_evaluated_for_refresh_at TIMESTAMP NULL`.
2. Add index `CREATE INDEX idx_gsc_metrics_article_time ON gsc_metrics(article_id, captured_at)`.
3. Add index `CREATE INDEX idx_articles_status_project ON articles(project_id, status)`.
4. Document the canonical query as an example after line 309: "refresh_detector selects WHERE status='published' AND (last_refreshed_at IS NULL OR last_refreshed_at < date('now','-90 days')) AND (last_evaluated_for_refresh_at IS NULL OR last_evaluated_for_refresh_at < date('now','-7 days')) ORDER BY published_at ASC".

### B2 — Topic queue ordering: `priority` scale & tiebreaker undefined

**Finding**: line 287 lists `topics.priority`. No domain (integer? 1–10? unbounded?), no tiebreaker, no default. Bulk-launch (procedure 5) iterates topics in some order; that order needs to be deterministic.
**Location**: line 287, procedure 5 line 447.
**Severity**: BLOCKER for M1.
**Fix**: Insert clarification after line 287: "`topics.priority` is INTEGER 0–100; NULL=50 default; higher = sooner. Tiebreaker: `(priority DESC, created_at ASC, id ASC)`. Procedure 5 picks topics with `status='approved'` ORDER BY this triple."

### B3 — GSC time-series schema is too wide

**Finding**: `gsc_metrics` has `(project_id, article_id, captured_at, query, impressions, clicks, ctr, avg_position)`. Each nightly pull of 1000 query rows × N articles = explosive growth. No partition, no rollup table.
**Location**: line 293.
**Severity**: MAJOR for M5.
**Fix**: Add column `gsc_metrics.dimensions_hash CHAR(40)` (SHA-1 of `query|page|country|device|date_bucket`) for dedup. Add a `gsc_rollup` table `(project_id, article_id, week_start, impressions_sum, clicks_sum, avg_position_avg)` updated at end of each nightly job. Index on `(project_id, week_start)`. Strip-map (codex-seo §3) confirms 28-day default pull window — rollup at week granularity is appropriate. Update Database schema header to "**18 tables**" if rollup is added, or document `gsc_rollup` as a materialized view.

### B4 — `articles.version` is a column; prior bodies are lossy

**Finding**: line 288 — `articles.version` is a single integer. No `content_versions` table. The strip-map (cody §5, line 430) says "calls `article.createVersion` MCP which copies the row with `version+=1`" — but copying into the same `articles` table adds a row whose `(project_id, slug)` would now collide unless there's a uniqueness scope tweak, and historical bodies become indistinguishable from "current" without a flag.
**Location**: lines 288, 422.
**Severity**: BLOCKER for M1.
**Fix**: Choose ONE explicitly:
- (Recommended) Add a 17th (or 19th if rollup) table `article_versions` with `(id, article_id, version, brief_json, outline_md, draft_md, edited_md, frontmatter_json, published_url, published_at, created_at, refreshed_at, refresh_reason)`. `articles` keeps only "current". `article.createVersion` copies the live row into `article_versions` BEFORE mutating. Strip-map cody §5 line 430 is consistent with this.
- (Alternative) Use a self-FK `articles.parent_article_id`, mark prior rows with `status='archived'`, scope slug uniqueness to `WHERE status != 'archived'`. Fragile.
Update line 278 "14 tables" → "18 tables" reflecting B3 + B4.

### B5 — Procedure-run resume points have no storage

**Finding**: PLAN.md line 631 claims "per-procedure runs are queued" and line 634 that runs are audit-trailed. But: if procedure 4 crashes after step 5 (editor) and before step 6 (eeat-gate), how does it resume? `runs.metadata_json` is a flat JSON; nothing models the step-cursor.
**Location**: lines 295, 446, 631.
**Severity**: BLOCKER for M8 (jobs/scheduling), but the *schema* must be in M1.
**Fix**: Add a 19th table `procedure_run_steps` with `(id, run_id, step_index, step_id, status (pending|running|success|failed|skipped), started_at, ended_at, output_json, error)`. The procedure runner writes one row per step BEFORE invoking the skill. On daemon restart, `runs WHERE status='running'` joined with the latest `procedure_run_steps WHERE status='running' OR 'pending'` tells us exactly where to resume. Resume policy: re-run failed step from scratch (idempotent skills) by default; per-skill opt-out flag in skill frontmatter. Update line 278 to final table count after this addition.

### B6 — Multi-locale: `projects.locales` doesn't propagate

**Finding**: `projects.locales` exists; `articles` has no `locale` column; `topics` has no `locale`; `slug` is implicitly project-global. PLAN.md line 620 says translation is "out of scope" but immediately couples it to `projects.locales` — internal contradiction.
**Location**: lines 282, 288, 620.
**Severity**: MAJOR for M1.
**Fix**: Choose explicitly:
- (Recommended) Add `articles.locale TEXT NULL` and `topics.locale TEXT NULL`; both default to NULL meaning "use project default". Add unique index `UNIQUE(project_id, slug, COALESCE(locale, ''))`. Update line 620 to: "Translation execution is out of scope; the schema records the locale of every article so a custom skill can fan-out and a sitemap can `<xhtml:link rel="alternate" hreflang="...">`."
- (Alternative) Drop `projects.locales` and remove line 620's translation reference. Cleaner if multi-locale is truly out.
Pick one. Currently the document is incoherent.

### B7 — Author column on `articles` and an `authors` table

**Finding**: E-E-A-T has Experience, Expertise, Authority columns in the rubric; the strip-map (aaron-he-zhu §3 line 519) requires per-article author attribution for the auditor to evaluate first-person experience and bylines. No `articles.author_id` and no `authors` table exist.
**Location**: lines 288 (no author column), 286 (eeat_criteria has no author binding).
**Severity**: BLOCKER for M1; the rubric is meaningless without authors.
**Fix**: Add table `authors`: `(id, project_id, name, slug, bio_md, headshot_url, role, credentials_md, social_links_json, schema_person_json, created_at, updated_at)`. Add `articles.author_id INTEGER REFERENCES authors(id) ON DELETE SET NULL`. Add `articles.reviewer_author_id INTEGER REFERENCES authors(id) ON DELETE SET NULL` (medical/financial review use case). Update line 278 table count.

### B8 — `compliance_rules.position` is undefined

**Finding**: `compliance_rules` has a `position` column. Position relative to what? Article body? Article footer? Other compliance rules in the same group? Without spec, draft-conclusion (skill #9) can't decide where to insert.
**Location**: line 284.
**Severity**: MAJOR for M7.
**Fix**: After line 284 add: "`position` is an enum: `header|after-intro|footer|every-section|sidebar|hidden-meta`. Within the same position, ordered by id ASC. The draft-conclusion skill renders rules with `position='footer'`; draft-intro renders `position='header'` or `after-intro`."

### B9 — `internal_links` lacks a uniqueness constraint

**Finding**: line 290. No unique index on `(from_article_id, to_article_id, anchor_text, position)`. Strip-map (aaron-he-zhu §5 line 599) says interlinker re-runs and would generate duplicate suggestions.
**Location**: line 290.
**Severity**: MAJOR for M7.
**Fix**: Add `UNIQUE(from_article_id, to_article_id, anchor_text, position) WHERE status != 'dismissed'` (partial unique index supported in SQLite 3.8+). Or add `idempotency_key TEXT` and unique on that.

### B10 — `eeat_criteria.score` is referenced as an MCP tool but no `score` column exists

**Finding**: line 372 lists `eeat.* score`. There's no per-article EEAT score storage. Strip-map says scores should land in `runs.metadata_json.eeat`. But the schema also implies a join to `eeat_criteria` for verdict computation. If a `Pass/Partial/Fail` per criterion per article is the intent, we need a join table.
**Location**: lines 286, 372.
**Severity**: BLOCKER for M1.
**Fix**: Add `eeat_evaluations` table: `(id, article_id, criterion_id, run_id, verdict (pass|partial|fail), notes, evaluated_at)`. Index `(article_id, run_id)`. Computed dimension/system scores still live in `runs.metadata_json.eeat`, but the per-criterion grain is queryable for trend analysis ("our R10 fail rate dropped after we added a sources cheatsheet"). Update line 278 table count.

### B11 — `schema_emits.attached_to_article` ambiguity

**Finding**: line 292. `schema_emits` has `(id, article_id, type, schema_json, validated_at)`. Per article you may emit multiple JSON-LDs (Article + FAQPage + BreadcrumbList). The schema permits this implicitly via separate rows, but the publish step needs a "primary" hint. No `is_primary` or ordering column.
**Location**: line 292.
**Severity**: MINOR.
**Fix**: Add `position INTEGER` and `is_primary BOOLEAN`. Or document order is INSERT order via id ASC.

### B12 — `runs` lacks `procedure_id` / `parent_run_id`

**Finding**: line 295. A procedure run nests skill runs nests integration calls. Currently `runs.kind` is a flat string; there's no parent FK to query "all skill calls under procedure X".
**Location**: line 295.
**Severity**: MAJOR.
**Fix**: Add `runs.parent_run_id INTEGER REFERENCES runs(id) ON DELETE SET NULL` and `runs.procedure_slug TEXT NULL`. Update `runs.start` MCP to take optional `parent_run_id`.

### B13 — `topics.intent` enum unspecified

**Finding**: line 287 lists `intent` column. The strip-map (codex-seo §3 line 100) names four values (informational/commercial/transactional/navigational). PLAN.md never declares these as a status enum.
**Location**: line 287, line 301 (status enums).
**Severity**: MINOR.
**Fix**: Add to enum block: `topics.intent: informational | commercial | transactional | navigational | mixed`.

### B14 — `clusters.type` enum implicit

**Finding**: line 286 lists `type (pillar/spoke)` inline; not in the formal enum list.
**Location**: lines 286, 301.
**Severity**: MINOR.
**Fix**: Add to enum block: `clusters.type: pillar | spoke | hub | comparison | resource`.

### B15 — `article_assets.kind` enum missing

**Finding**: line 289 lists `kind`. No enum values declared.
**Location**: lines 289, 301.
**Severity**: MINOR.
**Fix**: Add: `article_assets.kind: hero | inline | thumbnail | og | twitter | infographic | screenshot | gallery`.

### B16 — Foreign key for `articles.published_url` history

**Finding**: After republish, `published_url` may change (new slug, new locale, new domain). No `published_url_history` and no record of previous URLs for redirect generation.
**Location**: line 288.
**Severity**: MAJOR for refresh procedure (procedure 7).
**Fix**: Add `redirects` table: `(id, project_id, from_url, to_article_id, created_at, kind (301|302))`. Procedures 7 (humanize-pass) and content-refresher write a row when slug or domain changes.

### B17 — Indexes on hot read paths missing

**Finding**: PLAN.md never enumerates indexes beyond `is_active`. Hot queries:
- `articles WHERE project_id=? AND status=?` (every UI table view, every job)
- `topics WHERE project_id=? AND status=? ORDER BY priority DESC, created_at ASC`
- `runs WHERE project_id=? ORDER BY started_at DESC LIMIT 50`
- `gsc_metrics WHERE article_id=? AND captured_at > ?`
- `internal_links WHERE from_article_id=? OR to_article_id=?`
**Location**: implied across DB section.
**Severity**: MAJOR for M1.
**Fix**: After line 309, add an "Indexes" subsection enumerating composite indexes for the queries above. Alembic migration for them is part of M1 deliverables.

---

## C. API SURFACE

### C1 — Monthly cost per project has no endpoint

**Finding**: line 636 says "UI surfaces monthly cost per project" — no REST or MCP endpoint exists for this. The data lives in `runs.metadata_json.cost` but cannot be queried other than via SQL.
**Location**: lines 636, 313–388.
**Severity**: MAJOR.
**Fix**: Add REST `GET /api/v1/projects/{id}/cost?month=YYYY-MM` returning `{by_integration: {dataforseo: $X, firecrawl: $Y, ...}, total_usd: $Z, period_start, period_end}`. Add MCP `cost.queryProject` and `cost.queryAll` tools. Implementation reads `runs.metadata_json.cost` aggregated by month/integration. List under "Ongoing" REST section after line 357.

### C2 — Bulk operations on articles missing

**Finding**: `topic.bulkCreate` exists (line 374). No `article.bulkCreate`, no `article.bulkUpdateStatus`, no `internal_links.bulkApply`. Procedure 5 (bulk launch) needs at least bulk article creation.
**Location**: lines 374, 376, 379.
**Severity**: MAJOR.
**Fix**: Add `article.bulkCreate(topic_ids[]: int) → article_ids[]`, `internal_link.bulkApply(suggestion_ids[]) → applied[]`, `topic.bulkUpdateStatus(topic_ids[], status)`. REST `POST /api/v1/projects/{id}/articles/bulk` and equivalents.

### C3 — List endpoints have no pagination spec

**Finding**: Every `GET ... /list` could return thousands of rows. No `?limit=&cursor=` or `?page=&page_size=` is specified.
**Location**: lines 320–362.
**Severity**: MAJOR.
**Fix**: Add a "Pagination convention" subsection after line 313. State: cursor-based pagination on `id ASC` for stable lists; query params `?limit=50&after=ID`. Response envelope `{items: [], next_cursor: ID|null, total_estimate: N}`. Apply to all list endpoints. MCP equivalents take `limit` and `after_id`.

### C4 — Filtering/sorting on lists not specified

**Finding**: UI views (ProjectsView, ArticlesView, etc.) need to filter by status, source, niche, etc. No `?status=&source=` query params spec.
**Location**: lines 320–362, 188–194.
**Severity**: MAJOR.
**Fix**: After C3 pagination, add: "Filtering: any column listed in schema enums is filterable via `?col=val` (multiple allowed). Sorting: `?sort=col` or `?sort=-col` for desc; default `-created_at`." MCP list tools accept `filter: dict, sort: str, limit, after_id`.

### C5 — Enum / status-flow lookup endpoint missing

**Finding**: An LLM calling `topic.update` doesn't know the legal status transitions. The enums are documented in PLAN.md but not exposed via MCP.
**Location**: lines 301–308, 364.
**Severity**: MAJOR for M3.
**Fix**: Add MCP tool `meta.enums() → {topics_status: [...], articles_status: [...], allowed_transitions: {topics: {queued: [approved, rejected], approved: [drafting], ...}}}`. REST `GET /api/v1/meta/enums`. The repository layer reads from a single source-of-truth Python module; UI also consumes this for dropdowns.

### C6 — REST/MCP coverage gaps vs. each other

**Finding**: spot-check:
- REST has `POST /api/v1/projects/{id}/topics/bulk` (line 338); MCP has `topic.bulkCreate` (line 374). OK.
- REST has `GET /api/v1/articles/{id}/drift` (line 354); no `drift.get(article_id)` MCP, only `drift.snapshot|diff|list` (line 382).
- REST `POST /api/v1/articles/{id}/drift/snapshot` ↔ MCP `drift.snapshot`. OK.
- REST has `GET /api/v1/projects/{id}/runs` (line 356); MCP `run.list` (line 384). OK.
- REST has `POST /api/v1/projects/{id}/interlinks/suggest`; MCP `interlink.suggest`. OK.
- REST has no `GET /api/v1/articles/{id}/eeat`; MCP has `eeat.score`. Asymmetric.
- REST has no equivalent for MCP `article.listDueForRefresh` (line 376).
- REST has no equivalent for MCP `procedure.status`.
- MCP has no equivalent for REST `POST /api/v1/projects/{id}/activate`.
**Location**: lines 313–388.
**Severity**: MAJOR.
**Fix**: Add a "REST/MCP parity table" after line 388 listing every operation with both rows. Plug all the asymmetries above. Specifically: add MCP `project.activate`, REST `GET /api/v1/articles/{id}/eeat`, REST `GET /api/v1/projects/{id}/articles/refresh-due`, REST `GET /api/v1/procedures/runs/{run_id}` (already there) plus `GET /api/v1/procedures/runs/{run_id}/status`.

### C7 — `procedures/{slug}/run` sync vs. async unspecified

**Finding**: line 360 `POST /procedures/{slug}/run` returns what? `run_id` immediately and async, or block until done? Procedures take minutes-to-hours.
**Location**: line 360.
**Severity**: BLOCKER for M3.
**Fix**: After line 362 add: "Procedure runs are always async. `POST /procedures/{slug}/run` returns 202 `{run_id, status_url, started_at}`. Status polled via `GET /procedures/runs/{run_id}` (returns full step list with statuses). MCP `procedure.run` returns the same envelope; `procedure.status(run_id)` polls."

### C8 — Article CRUD on edited content uses `PATCH` but skill writes use specific verbs

**Finding**: line 343 `PATCH /api/v1/articles/{id}` covers everything; MCP has six verbs (`setBrief`, `setOutline`, `setDraft`, `setEdited`, `markEeatPassed`, `markPublished`). The two paths diverge — UI mutates anything, LLM only takes prescribed transitions. State-machine enforcement should live in repositories, but the asymmetry is undocumented.
**Location**: lines 343, 376–377.
**Severity**: MAJOR.
**Fix**: After line 388 add: "All MCP transition tools enforce the `articles.status` state machine; REST PATCH is permissive (UI is the human escape hatch). Both paths write a `runs` row with `kind='manual-edit'` (REST PATCH) or `kind='skill-run'` (MCP)."

### C9 — `voice.* listVariants` exists but no `setActive`

**Finding**: line 369 `voice.* set | get | listVariants`. Multiple voice profiles per project but no way to switch the active one for a draft.
**Location**: lines 283, 369.
**Severity**: MAJOR.
**Fix**: Add `voice.setActive(project_id, voice_id)` MCP and REST `POST /api/v1/projects/{id}/voice/{vid}/activate`. Or pass `voice_id` per draft skill invocation; document which.

---

## D. MCP CONTRACT

### D1 — Pydantic schema discipline not declared

**Finding**: line 388 says "pydantic-validated" but no contract on shape. With ~70 tools, lacking discipline = drift.
**Location**: line 388.
**Severity**: BLOCKER for M3.
**Fix**: Add an "MCP tool contract" subsection after line 388 stating: every tool has `tools/<name>.py` with `class FooInput(BaseModel)`, `class FooOutput(BaseModel)`. Inputs declare project_id explicitly except for `meta.*` and `project.*` global ones. Outputs are the canonical pydantic model from `repositories/`. Add a CI check that validates every MCP tool registers an input+output pydantic class.

### D2 — Idempotency keys absent

**Finding**: line 388 says "idempotent where it makes sense" — vague. Mutating tools (`article.setDraft`, `topic.bulkCreate`) replayed by a flaky client without a key produce duplicates.
**Location**: line 388.
**Severity**: MAJOR.
**Fix**: Add to the MCP tool contract: "Every mutating tool accepts optional `idempotency_key: str`. The repository layer keys (project_id, tool_name, idempotency_key) → run_id and short-circuits on replay within a 24h window. Deduped via a lightweight `idempotency_keys` table or via `runs.metadata_json` lookup." If choosing the table route, add a 20th-or-so table.

### D3 — Long-running tools — streaming model

**Finding**: MCP Streamable HTTP supports SSE. `procedure.run` is long. PLAN.md says "Streamable HTTP only" (locked decision 4) but doesn't specify which tools stream progress events vs. return immediately.
**Location**: lines 364, 605.
**Severity**: MAJOR for M3.
**Fix**: Add to MCP tool contract: "`procedure.run`, `topic.bulkCreate` (when N>50), `gsc.bulkIngest`, `interlink.suggest` are streaming: they emit `progress` events `{step, total, message, partial_data?}` until completion. All other tools are request-response. Tool definitions declare `streaming: true` in registration. Clients that don't consume SSE see only the final result." Reference the official `mcp` SDK's streaming primitives.

### D4 — Error model unspecified

**Finding**: MCP errors have a JSON-RPC error-code structure. PLAN.md doesn't pick error codes, doesn't define retryable vs. permanent classes, doesn't define how repository validation errors map.
**Location**: line 388.
**Severity**: MAJOR for M3.
**Fix**: Add an "Error model" subsection after the MCP tool contract:
- Code mapping: validation → -32602, not-found → -32004, conflict → -32008, integration-down → -32010, rate-limited → -32011, internal → -32603.
- All errors include `data: {run_id, retryable: bool, retry_after?: seconds, hint?: string}`.
- Retryable errors auto-retry up to 3× server-side; non-retryable bubble up immediately.

### D5 — Tool result envelope: bare object vs. envelope

**Finding**: Strip-map and PLAN.md don't agree. Strip-map (cody §5) implies tools return DB-row pydantic objects directly. But every mutating tool also produces a `runs` row that the LLM should be able to reference by `run_id` — that's the audit-trail thread. Without an envelope, the LLM can't easily report "I ran procedure X, run_id=42".
**Location**: line 388.
**Severity**: BLOCKER for M3.
**Fix**: Standardize the envelope. After D1, append: "Every mutating tool returns `{data: T, run_id: int, project_id: int}`. Read tools return `T` bare. The choice MUST be documented per-tool in its frontmatter. CI check enforces that every tool whose name starts with a non-read verb (`create|update|set|mark|add|remove|toggle|approve|reject|apply|dismiss|bulkCreate|bulkUpdate|bulkApply|run|snapshot|ingest|test|validate`) returns the envelope."

### D6 — `project_id` resolution in MCP — implicit vs. explicit

**Finding**: User asked: "How does a skill know the active project at invocation?" PLAN.md has `project.setActive` and `getActive` (line 366) but doesn't clarify the contract. See section E for full treatment; flagged here as an MCP contract issue: every tool accepting project-scoped data MUST accept either explicit `project_id` or fall back to `getActive()` server-side.
**Location**: lines 366, 388.
**Severity**: BLOCKER for M3 (see E1).
**Fix**: See E1.

---

## E. MULTI-PROJECT SEMANTICS

### E1 — Active-project resolution contract is undefined

**Finding**: `project.setActive` and `project.getActive` exist (line 366). MCP is stateless across calls (each call independent). HTTP transport has no session affinity. Two scenarios:
- (Server-side state) Daemon stores "the active project" globally → racy across two MCP clients (one Codex session and one Claude Code session simultaneously editing different projects step on each other).
- (Per-call state) Every tool takes `project_id` explicitly → verbose but correct.
**Location**: line 366.
**Severity**: BLOCKER for M3.
**Fix**: Choose explicitly:
- **Recommended**: Per-call `project_id` parameter on every project-scoped tool. `project.setActive` is REST-UI-only — it sets `projects.is_active` for the UI sidebar, not for MCP. MCP `project.getActive` returns the UI-active project, but tools never depend on it. This eliminates the cross-client race.
- Update lines 313–388: every project-scoped MCP tool takes `project_id: int`. UI continues to use `projects.is_active` for its own sidebar.
- Add a clarification block after line 388: "MCP is stateless. `project.setActive`/`getActive` mutate UI state only. Skills that compose multiple tools must read `project_id` from procedure context (set at procedure-run start by `procedure.run({project_id, slug, args})`) and pass it through every call."

### E2 — Skills don't know how to read "procedure context"

**Finding**: PLAN.md procedures invoke skills (line 446 lists procedure 4). The skill SKILL.md frontmatter is unspecified (also flagged in the strip-map at aaron §7 line 620). How does a skill receive `project_id` and `run_id` and pass them through to MCP calls?
**Location**: lines 392–423, 432–453.
**Severity**: BLOCKER for M7.
**Fix**: Define skill frontmatter and runtime context. After line 437 add: "Every skill's SKILL.md frontmatter declares `inputs: {project_id, run_id, article_id?, topic_id?, ...}`. The procedure runner sets these as environment variables `CONTENT_STACK_PROJECT_ID`, `CONTENT_STACK_RUN_ID`, `CONTENT_STACK_ARTICLE_ID` before delegating to the LLM. Skills MUST pass these through every MCP call. The MCP daemon reads them for trace correlation but does not enforce — the procedure runner is the authority."

### E3 — Cross-project leakage via global integrations

**Finding**: line 297, 469. `integration_credentials.project_id` is "nullable for global". A skill running for project A could reach for a global Reddit credential and leak project A's prefix into project B's quota. No isolation contract.
**Location**: line 297.
**Severity**: MAJOR.
**Fix**: After line 475 add: "Resolution order for credentials: project-scoped first (`WHERE project_id = :p AND kind = :k`), then global (`WHERE project_id IS NULL AND kind = :k`). Project-scoped overrides global. All API calls log `project_id` to vendor logs where vendor APIs allow."

---

## F. OPERATIONS

### F1 — APScheduler concurrency model unspecified

**Finding**: line 109, 168, 631. APScheduler in-process; "per-procedure runs are queued"; no spec of executor (ThreadPoolExecutor? Process pool? Async?), max_instances, misfire policy.
**Location**: lines 109, 631.
**Severity**: MAJOR for M9.
**Fix**: After line 595 (sequencing M9) add: "APScheduler config: `AsyncIOExecutor(max_workers=4)` for short jobs (gsc-pull, drift-check); `ThreadPoolExecutor(max_workers=2)` for long ones (refresh-detector). `coalesce=True`, `max_instances=1` per job_id, `misfire_grace_time=3600` for nightly jobs. Procedure runs go through the same scheduler with `job_id=procedure-{slug}-{project_id}` to enforce serialization per project."

### F2 — Crash recovery mid-procedure undefined

**Finding**: See B5. Mid-procedure 4 crash leaves `runs` row in `running` state forever.
**Location**: lines 295, 446.
**Severity**: BLOCKER for M9.
**Fix**: After F1, append: "On daemon start, `runs` rows with `status='running'` and `started_at < now-15min` are: (a) inspected via `procedure_run_steps`; (b) the last completed step is the resume point if the procedure declares `resumable: true` in PROCEDURE.md frontmatter; otherwise the run is marked `aborted` with `error='daemon restart'` and a fresh run is suggested. Resume is via `procedure.resume(run_id)` MCP."

### F3 — WAL contention claim is hand-wave

**Finding**: line 631 "SQLite WAL contention under heavy parallel skill runs / Repository layer uses short transactions". No transaction discipline specified; no PRAGMAs declared.
**Location**: line 631.
**Severity**: MAJOR for M2.
**Fix**: After line 86 (DB diagram) add: "SQLite PRAGMAs at connect: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`, `foreign_keys=ON`, `temp_store=MEMORY`, `mmap_size=268435456`. Repositories use SQLAlchemy session per request; transactions ≤ 100ms ideally; long-running enrichment writes batched in 100-row chunks."

### F4 — Backup story missing

**Finding**: line 616 "Cloud sync / multi-device DB" out of scope; "Back up via your normal mechanism." Macs differ in backup hygiene; SQLite WAL means a naïve `cp` of `.db` while daemon runs is corrupt.
**Location**: line 616.
**Severity**: MAJOR (the user has months of LLM-generated content sitting in this DB).
**Fix**: Add a "Backup" subsection after line 537. Specify: (a) `make backup` runs `sqlite3 ~/.local/share/content-stack/content-stack.db ".backup /path/to/backup.db"` — safe with WAL; (b) `make restore <file>` halts daemon, copies, restarts; (c) `scripts/doctor.sh` warns if `~/.local/share/content-stack/` is not under Time Machine; (d) auto-backup hook: APScheduler job runs `.backup` weekly to `~/.local/share/content-stack/backups/YYYY-WW.db`, retains 12 weeks.

### F5 — Daemon restart without losing in-flight HTTP requests

**Finding**: When user runs `make install` the second time (e.g., upgrade), the daemon restarts. In-flight HTTP requests die. No graceful-shutdown spec.
**Location**: implicit.
**Severity**: MINOR.
**Fix**: After line 537 add: "`launchctl stop`/`SIGTERM` triggers uvicorn graceful shutdown (30s drain, kills after). In-flight procedure-run steps catch `SIGTERM`, mark step as `aborted`, write `runs.error='shutdown'`. Resume policy from F2 applies on restart."

### F6 — Health endpoint missing

**Finding**: doctor.sh diagnoses (line 534) but no `/healthz` or `/api/v1/health` for monitoring.
**Location**: lines 313–362.
**Severity**: MINOR.
**Fix**: Add `GET /api/v1/health` returning `{daemon_uptime_s, db_status, scheduler_running, integrations_reachable: {...}, version}`. doctor.sh hits this first.

---

## G. DISTRIBUTION

### G1 — Each install script's behavior incomplete

**Finding**: line 247–256 lists 8 scripts. None have specified semantics:
- `install-codex.sh` — `cp -R skills/* ~/.codex/skills/` — what about overwrite? Idempotent? `--with-codex-seo` flag (line 498) interaction?
- `install-launchd.sh` — copies plist. If plist exists with different content?
- `register-mcp-claude.sh` — writes `.mcp.json` — but Claude Code maintains its own `.mcp.json`. Merging vs. overwriting?
**Location**: lines 247–256, 498.
**Severity**: BLOCKER for M10.
**Fix**: After line 537 (Daemon strategy section) or line 562 (MCP registration) add a "Install script semantics" subsection. For each script:
- `install-codex.sh`: `rsync -a --delete skills/ ~/.codex/skills/content-stack/`. Idempotent. `--with-codex-seo` clones AgriciDaniel/codex-seo @pinned-SHA into `~/.codex/skills/codex-seo/` if not present.
- `install-claude.sh`: same with `~/.claude/skills/content-stack/`.
- `install-procedures-{codex,claude}.sh`: copies into `~/.codex/procedures/content-stack/` and `~/.claude/procedures/content-stack/`. (Note: confirm Claude Code respects `~/.claude/procedures/` — strip-map doesn't validate this; verify with Claude Code docs at M0.)
- `register-mcp-codex.sh`: `codex mcp list | grep -q content-stack || codex mcp add content-stack ...`. Idempotent.
- `register-mcp-claude.sh`: reads `~/.claude/.mcp.json` (or per-project), upserts the `content-stack` key, writes back atomically with a backup `.mcp.json.bak`.
- `install-launchd.sh`: writes plist if absent; if present, diffs and either (a) keeps existing if identical, (b) prompts user, (c) `--force` overwrite.
- `doctor.sh`: see G3.

### G2 — Upgrade path v1→v2 not addressed

**Finding**: PLAN.md is v1. No spec for upgrading skills/procedures/db when daemon updates ship.
**Location**: implicit; line 576 mentions auto-migrate on start.
**Severity**: MAJOR (post-launch, but designs hard to retrofit).
**Fix**: Add an "Upgrade strategy" subsection after line 596:
- Daemon upgrades via `uv pip install -U content-stack`. `make install` re-runs all install scripts (idempotent).
- Skills/procedures: `install-{codex,claude}.sh` uses `rsync --delete` so on re-run, retired skills disappear. User-customized skills should live in a separate dir; document this constraint.
- Schema: `alembic upgrade head` on daemon start. Down-migrations supported but discouraged.
- Breaking changes: bump major version; release notes call out manual migrations.

### G3 — `doctor.sh` exit codes & machine-readable output

**Finding**: line 534 — doctor "diagnoses" but no exit-code table, no `--json` flag.
**Location**: lines 255, 534.
**Severity**: MAJOR for M10.
**Fix**: After G1 add: "doctor.sh exit codes: 0 all green, 1 daemon down, 2 MCP not registered, 3 skills not installed, 4 missing API keys, 5 DB schema out of date, 6 launchd plist not loaded. With `--json`, emits `{checks: [{name, status (pass|warn|fail), details}], overall_exit: int}` to stdout." doctor checks read REST `/api/v1/health` first, then filesystem, then runtime configs.

### G4 — `pipx install` path mentioned but install scripts assume repo

**Finding**: line 569 mentions `pipx install content-stack` (post-publish). Install scripts (line 247) reference relative paths like `skills/` — these don't exist if the user `pipx install`'d. Where do the scripts come from in pipx mode?
**Location**: lines 569, 247.
**Severity**: MAJOR.
**Fix**: After line 569 add: "`pipx install content-stack` installs the package + a `content-stack` console script. Skills + procedures are bundled in the wheel under `content_stack/_assets/skills/` and `_assets/procedures/`. The console script wraps `install-codex` etc. as Python subcommands that copy from the wheel. `make install` (clone-mode) and `content-stack install` (pipx-mode) call the same code paths."

### G5 — UI build artifacts in repo conflict with `gitignore`

**Finding**: line 170 says `ui_dist/ # built Vue assets (gitignored)`. line 574–575 says `make build-ui` is built once and committed for installs without pnpm. These contradict.
**Location**: lines 170, 574–575.
**Severity**: MINOR but is a real install-time issue.
**Fix**: Reconcile. Recommended: `ui_dist/` IS committed (drop from .gitignore), with a CI check that the committed bundle matches `ui/src/` source. Update line 170 to remove "(gitignored)". Or drop the "committed bundle" claim and require pnpm at install (raises the floor). Pick one.

---

## H. SECURITY

### H1 — Encryption seed file location not specified in PLAN.md

**Finding**: User's locked decision 5 names "AES-256-GCM with per-machine seed" but `~/.local/state/content-stack/key` (or wherever) is implied not stated. Line 531 mentions `~/.local/state/content-stack/` for logs/PID. The seed file path is unspecified.
**Location**: lines 472–476.
**Severity**: BLOCKER for M2.
**Fix**: After line 476 add: "Per-machine seed lives at `~/.local/state/content-stack/seed.bin`, 32 bytes from `os.urandom`, written with `0600` permissions, owned by current user. On daemon start: if absent, generate; if present and not 0600, refuse to start. Key derivation: HKDF-SHA256 with the seed as IKM and the constant `b'content-stack:integration-credentials:v1'` as info, yielding a 32-byte AES-256-GCM key. AAD per row = `f'project_id={p}|kind={k}'`. Nonce = 12 random bytes per encryption, prepended to ciphertext."

### H2 — Cross-machine DB copy fails silently

**Finding**: Per H1, the seed is per-machine. If user copies `content-stack.db` to a new machine (Time Machine restore, manual move), every `integration_credentials` row is undecryptable. PLAN.md doesn't mention this failure mode.
**Location**: implicit.
**Severity**: BLOCKER for M2 (UX failure mode at restore time).
**Fix**: After H1 add: "Backup hygiene: `make backup` MUST also back up `~/.local/state/content-stack/seed.bin` to the same location. Restoring the DB without the seed prompts the user via doctor.sh: `seed.bin missing — re-enter API keys, all rows in integration_credentials marked stale`. `scripts/doctor.sh` checks seed presence and DB consistency together."

### H3 — Seed rotation undefined

**Finding**: AES-256-GCM with the same seed forever is fine theoretically, but user might want to rotate (e.g., after malware suspicion).
**Location**: implicit.
**Severity**: MINOR.
**Fix**: Add to H1 block: "Rotation: `content-stack rotate-seed --reencrypt` generates a new seed, decrypts every credential row with the old seed in memory, re-encrypts with the new, writes new seed. Old seed kept at `seed.bin.bak` for one boot, then auto-deleted."

### H4 — Localhost binding not enforced in code

**Finding**: line 95 says "Bound to 127.0.0.1." Need code-level guarantee, not just doc claim.
**Location**: line 95.
**Severity**: MAJOR.
**Fix**: After line 95 add: "FastAPI app factory binds uvicorn to `127.0.0.1:5180`. The CLI explicitly forbids `--host 0.0.0.0` (errors with explanation). doctor.sh verifies via `lsof -iTCP:5180 -sTCP:LISTEN`."

### H5 — No authentication contract for adversarial-review hook

**Finding**: codex-plugin-cc adversarial-review (strip-map line 666–675) shells out via `Bash` from a content-stack skill. The article body is passed as an arg. Article bodies can be large; arg-length limits vary. Also, the article body could contain prompts that confuse the Codex sub-agent.
**Location**: line 511, strip-map line 666.
**Severity**: MAJOR for M7.
**Fix**: Add to skill #11 spec: "Adversarial review passes the article via a temp file (`mktemp`) referenced by path, never via argv. Temp file 0600, deleted in `finally`. Article body wrapped in a `<article_under_review>` XML tag in the prompt for prompt-injection hygiene."

### H6 — No rate limiting on the daemon

**Finding**: A misbehaving skill could hit `topic.bulkCreate` 10000 times/sec and exhaust SQLite. No rate limit.
**Location**: implicit.
**Severity**: MINOR (single-user, localhost — but still hardening worth the M2 cost).
**Fix**: After F3 add: "Per-tool rate limits enforced in middleware: 100 calls/minute per tool, 1000 calls/minute aggregate. 429 with `retry_after` on breach."

---

## I. OPEN DECISIONS HIDDEN IN PROSE

These are sub-decisions PLAN.md states ambiguously. Each needs an explicit lock.

### I1 — Humanizer: once or every refresh?

**Finding**: line 410 "AM Media's post-publish pass". Procedure 7 (line 449) is monthly humanize. Strip-map cody §5 line 430 mentions humanizer composes with editor for refresher (skill #24). It's unclear whether humanizer runs once at first publish or every refresh.
**Location**: lines 410, 422, 449.
**Severity**: MAJOR for M7.
**Fix**: After line 410 add: "Humanizer (#12) runs **once per article version**. Procedure 7 generates a new version (incrementing `articles.version`) and humanizer runs against it. Same applies to content-refresher (#24): each refresh = new version = humanizer can run."

### I2 — Editor after every draft step or only after draft-conclusion?

**Finding**: Procedure 4 (line 446) shows `draft-intro → draft-body → draft-conclusion → editor`. Single editor pass at end. But the strip-map (cody §5) says editor reads `articles.draft_md` (assembled, full draft). Confirm and lock.
**Location**: line 446.
**Severity**: MAJOR for M7.
**Fix**: Confirm in PLAN.md: "Editor runs once per draft cycle, after draft-conclusion has assembled the full draft into `articles.draft_md`. Eeat-gate fail loops back to draft-body (re-write affected sections) — not back to a per-section editor."

### I3 — Compliance footer placement

**Finding**: Strip-map (cody §3 line 378) says draft-conclusion inserts compliance footer per `compliance_rules`. PLAN.md row #9 (line 407) says "Inserts compliance footer per `compliance_rules`". But which kinds? `responsible-gambling` is a footer item in iGaming; `affiliate-disclosure` is often a header. `position` column (B8) is the answer.
**Location**: line 407, 284.
**Severity**: BLOCKER for M7 (without the position enum, draft-conclusion doesn't know where to put what).
**Fix**: Resolved by B8 (compliance_rules.position enum). Then update line 407: "Inserts compliance rules with `position='footer'` or `position='after-intro'` (and the equivalent draft-intro skill renders `position='header'`)."

### I4 — eeat-gate verdict on Pass: auto-advance or human review?

**Finding**: Procedure 4 line 446 shows `eeat-gate (11) → fail loops back to draft → image-generator (13) → ...` On Pass, advances directly to image-generator. But strip-map (aaron §3 line 530) names three verdicts: SHIP / FIX / BLOCK. SHIP advances; FIX requires fixes; BLOCK is fatal. PLAN.md collapses to two.
**Location**: line 446.
**Severity**: MAJOR for M7.
**Fix**: Update line 446 to: "`eeat-gate (11)`: verdict SHIP advances; FIX writes `runs.metadata_json.fix_required=[...]` and loops back to `editor` (10) for targeted fixes; BLOCK aborts the procedure with `runs.status='aborted'` and notifies via UI flag." This three-way verdict aligns with the upstream framework and gives FIX a non-discard exit.

### I5 — Article slug uniqueness scope

**Finding**: line 288 — `slug` column on `articles`. Uniqueness scope unstated. Per project? Global? Per project per locale (see B6)?
**Location**: line 288.
**Severity**: BLOCKER for M1.
**Fix**: After line 288 add: "Unique constraint: `UNIQUE(project_id, slug, COALESCE(locale, ''))`. Slug is auto-generated from title (kebab-case, lowercased, alnum + dashes, max 80 chars) but editable. UI/MCP both refuse on conflict with a `409` and a suggestion."

### I6 — `refresh_due` transition: manual, job, or both?

**Finding**: line 304 — `articles.status` has `refresh_due`. line 421 — refresh-detector (#23) "schedules refresh". Procedure 7 (line 449) selects N oldest articles. Two paths to `refresh_due`: refresh-detector marks rows; humans flag manually in UI. Both? Only one?
**Location**: lines 304, 421, 449.
**Severity**: MAJOR for M7.
**Fix**: After line 421 add: "Two entry points: (a) refresh-detector (skill #23, run weekly via `jobs/refresh_detector.py`) selects candidates and writes `articles.status='refresh_due'` and `runs.kind='refresh-detector'`. (b) Human in UI clicks 'flag for refresh' on `ArticleDetailView.vue`, which PATCHes status. Both paths converge on `procedure 7` consuming `WHERE status='refresh_due'`."

### I7 — Voice variants per article — pinned at draft start or live-pulled?

**Finding**: line 283 — multiple `voice_profiles` per project. Drafts in flight could pick up voice changes mid-draft.
**Location**: line 283, 405.
**Severity**: MINOR.
**Fix**: After line 283 add: "Articles snapshot the active voice at brief time: `articles.brief_json.voice_id` records which `voice_profiles.id` was used. Subsequent edits to that voice profile do NOT retroactively affect the draft. Refresh-detector reads the *current* voice for the project, not the historical one."

### I8 — `article.markPublished` — who chooses target if multiple?

**Finding**: `publish_targets` may have multiple active rows per project (e.g., Nuxt + WP). The publish skill is single-target (skills 17/18/19). Procedure 4 (line 446) says "publish skill (17/18/19 per `publish_targets`)" — does it iterate all active targets, or pick one?
**Location**: line 446, 296.
**Severity**: MAJOR for M7.
**Fix**: After line 296 add: "`publish_targets.is_active` plus `publish_targets.is_primary` (BOOLEAN, exactly one per project). Procedure 4 publishes to `is_primary` first; secondary targets are queued via `publish_target.replicate(article_id, target_id)` MCP and the article keeps `articles.published_url` from the primary."

### I9 — Codex-plugin-cc adversarial review — auto or opt-in per project?

**Finding**: Strip-map (line 667–676) suggests adversarial review fires when `integrations.codex_plugin_cc.enabled=true`. PLAN.md doesn't lock this.
**Location**: line 511.
**Severity**: MINOR (decision 8 is locked at "wired"; per-project knob still needed).
**Fix**: After line 511 add: "Adversarial review is opt-in per project. UI Integrations tab toggles `integration_credentials WHERE kind='codex-plugin-cc'.config_json.enabled`. Default off."

### I10 — `niche` column on `projects` — taxonomy or freeform?

**Finding**: line 282 — `projects.niche TEXT`. Used by skills? Taxonomy (igaming/saas/ecom/...) or freeform?
**Location**: line 282.
**Severity**: MINOR.
**Fix**: After line 282 add: "`niche` is freeform TEXT for human display; not used by skills for branching. If skill behavior should differ by niche, encode that in `voice_profiles.voice_md` or `compliance_rules`."

---

## J. STRIP-MAP ALIGNMENT

Cross-check every PLAN.md row 1–24 against `docs/upstream-stripping-map.md`. Format: row → present in strip-map? coverage assessment.

| Row | Skill | In strip-map | Coverage | Verdict |
|---|---|---|---|---|
| 1 | keyword-discovery | yes (codex-seo §3) + Reddit/PAA "authored fresh" notes | full | OK |
| 2 | serp-analyzer | yes (codex-seo §3) | full | OK |
| 3 | topical-cluster | yes (codex-seo §3) | full | OK |
| 4 | content-brief | yes (cody §3) | full | OK |
| 5 | competitor-sitemap-shortcut | "original (n/a)" | strip-map has NO mention of skill #5. PLAN.md row 5 says "Authored from scratch — sitemap.xml + Ahrefs export → topical map". | **GAP**: should be explicitly listed in strip-map under "originals" so future skill authors don't search for upstream files. |
| 6 | outline | yes (cody §3) | full | OK |
| 7 | draft-intro | yes (cody §3) | full | OK |
| 8 | draft-body | yes (cody §3) | full | OK |
| 9 | draft-conclusion | yes (cody §3) | full | OK |
| 10 | editor | yes (cody §3) | full | OK |
| 11 | eeat-gate | yes (aaron §3) | full | OK |
| 12 | humanizer | "original (n/a)" | NO mention in strip-map. | **GAP**: should be listed as original with a brief sketch (sentence-length variation, AI-tell removal beyond editor's, anecdote injection). |
| 13 | image-generator | "original (n/a)" | strip-map mentions OpenAI Images "Authored fresh" (codex-seo §6). | partial — needs its own original-skill section |
| 14 | alt-text-auditor | yes (codex-seo §3) | full | OK |
| 15 | interlinker | yes (aaron §3) | full | OK |
| 16 | schema-emitter | yes (codex-seo §3) | full | OK |
| 17 | nuxt-content-publish | "original (n/a)" | NO mention | **GAP**: list as original. |
| 18 | wordpress-publish | "original (n/a)" | NO mention | **GAP**: list as original. |
| 19 | ghost-publish | "original (n/a)" | NO mention | **GAP**: list as original. |
| 20 | gsc-opportunity-finder | yes (codex-seo §3) | full | OK |
| 21 | drift-watch | yes (codex-seo §3) | full | OK |
| 22 | crawl-error-watch | yes (codex-seo §3) | full | OK |
| 23 | refresh-detector | "original (n/a)" | NO mention | **GAP**: list as original; cite the schema columns it queries. |
| 24 | content-refresher | yes (cody §3) | full | OK |

**Finding J1**: Six "original" skills (5, 12, 13, 17, 18, 19, 23 — that is seven actually) are absent from the strip-map. The strip-map is described as "the bridge between PLAN.md's catalogue and the actual files our skill authors will read for inspiration" — it should list originals too, with a one-paragraph "this is original; here's the rough algorithm" so authors aren't lost.
**Location**: docs/upstream-stripping-map.md (no section for originals), PLAN.md line 421 (refresh-detector) and others.
**Severity**: MAJOR for M7 (the strip-map is the input to skill authoring).
**Fix**: Add a new top-level section "Original skills (no upstream)" to upstream-stripping-map.md. For each of skills 5, 12, 13, 17, 18, 19, 23: 1-paragraph algorithm sketch + DB tables touched + MCP tools used + key risks. PLAN.md should add a forward reference at line 423: "Skills marked 'original (n/a)' are documented in `docs/upstream-stripping-map.md#original-skills`."

---

## K. RECOMMENDED PLAN.md AMENDMENTS

Consolidating the fixes above into concrete line-level edits. Order is by line number to make application easy.

### Foundation

1. **Line 95**: Append "FastAPI explicitly binds 127.0.0.1; `--host 0.0.0.0` is rejected at CLI parse; doctor verifies post-start." (H4)
2. **Line 86 (after diagram)**: Insert PRAGMAs subsection (F3).
3. **After line 119 (Tech stack)**: Insert "Makefile targets" subsection enumerating 14 targets and their semantics. (A1)

### Schema

4. **Line 278 ("14 tables")**: Update count to **20 tables** after additions in steps below.
5. **Line 282**: Append "`niche` is freeform display only" note (I10). Resolve `locales` column meaning (B6).
6. **Line 283**: Append "voice snapshot pinned in `articles.brief_json.voice_id`" (I7).
7. **Line 284**: Define `compliance_rules.position` enum (B8, I3).
8. **Line 287**: Lock `topics.priority` scale and tiebreaker (B2). Specify `topics.intent` enum (B13). Add `topics.locale` column (B6).
9. **Line 288**: Add `articles.author_id`, `articles.reviewer_author_id` (B7); `articles.locale` (B6); `articles.last_evaluated_for_refresh_at` (B1); slug uniqueness `UNIQUE(project_id, slug, COALESCE(locale, ''))` (I5).
10. **Line 289**: Define `article_assets.kind` enum (B15).
11. **Line 290**: Add unique index on `internal_links` (B9).
12. **Line 292**: Add `schema_emits.position` and `is_primary` (B11).
13. **Line 293**: Add `gsc_metrics.dimensions_hash`; declare `gsc_rollup` table (B3).
14. **Line 295**: Add `runs.parent_run_id`, `runs.procedure_slug` (B12). Define `runs.metadata_json` discriminated-union shape (A7).
15. **Line 296**: Add `publish_targets.is_primary` (I8).
16. **After line 297**: Insert four new tables — `authors` (B7), `article_versions` (B4), `procedure_run_steps` (B5), `eeat_evaluations` (B10), `redirects` (B16), and the optional `gsc_rollup` (B3). That's six new tables → row count 16+6 = 22 tables. Reconcile line 278 count to **22**.
17. **After line 309**: Insert "JSON column shapes" subsection (A6, A7) and "Indexes" subsection (B17) and "Seed data" subsection (A10).

### API

18. **Line 313**: Add "Pagination convention" + "Filtering / sorting" subsections (C3, C4).
19. **Line 357 (after Ongoing block)**: Add `GET /api/v1/projects/{id}/cost?month=YYYY-MM` (C1).
20. **Line 360**: Append async semantics for procedure run (C7).
21. **After line 388**: Insert "MCP tool contract" + "Idempotency" + "Streaming" + "Error model" + "Result envelope" + "REST/MCP parity" subsections (D1–D6, C5, C6, C8). Plus C2 (bulk operations) and C9 (`voice.setActive`).
22. **Line 366**: Clarify `project.setActive`/`getActive` are UI-state; MCP tools take explicit `project_id` (E1).
23. **After line 376** (article tools): Add `article.bulkCreate`, `article.refreshDue` (C2, C6).
24. **Line 384** (run tools): Add `run.children(parent_run_id)`, `run.cost` (C1).

### Operations

25. **After line 537 (Daemon section)**: Insert "CLI reference" (A2), "Logging" (A8), "Backup" (F4), "Graceful shutdown" (F5), "Health endpoint" (F6), "Rate limits" (H6) subsections.
26. **After line 562 (MCP registration)**: Insert "Install script semantics" (G1) and "Upgrade strategy" (G2) and "doctor exit codes" (G3).
27. **Line 569**: Reconcile pipx vs. clone install paths (G4).
28. **Line 170**: Reconcile `ui_dist/` gitignore vs. committed-bundle (G5).

### Security

29. **After line 476 (encryption block)**: Insert seed file location, permissions, derivation, AAD spec; cross-machine restore semantics; rotation (H1, H2, H3).
30. **Line 511 (codex-plugin-cc)**: Specify per-project opt-in toggle (I9). Specify temp-file passing for adversarial review (H5).

### Procedures

31. **Line 410 (humanizer)**: Lock "once per article version" (I1).
32. **Line 446 (procedure 4)**: Lock editor placement (I2). Lock three-verdict eeat-gate (I4). Lock publish-target primary (I8).
33. **Line 421 (refresh-detector)**: Lock entry points to `refresh_due` (I6).
34. **Line 423 (after the catalogue)**: Add forward reference to "Original skills" section in strip-map (J1).

### Strip-map (separate document)

35. **upstream-stripping-map.md**: Add top-level section "Original skills (no upstream)" covering skills 5, 12, 13, 17, 18, 19, 23 (J1).

### Sequencing

36. **Line 580 (Implementation sequencing)**: Adjust day estimates upward to reflect new tables and contracts:
    - M1 (DB+repos): 2d → **3d** (more tables, indexes, JSON shape contracts).
    - M3 (MCP server): 2d → **3d** (envelope + idempotency + streaming + error model).
    - M9 (jobs): 1d → **2d** (resume, executor config).
    Total revises 25d → **28d**.

### Risk row

37. **Line 636 (cost runaway)**: Update mitigation to reference the new `GET /projects/{id}/cost` endpoint and `cost.* MCP tools (C1).

---

## Summary

The PLAN.md is structurally sound — vision, scope, and phasing are coherent and the locked decisions are good. But the foundation cannot be built from this document alone. There are **eight BLOCKER items** that must be resolved before M0 sign-off:

1. **A1, A2, A3**: Makefile, CLI, procedure template specs.
2. **B1, B2, B4, B5, B7, B10**: Schema gaps (refresh query, topic ordering, versions, resume points, authors, eeat evaluations).
3. **C7, D1, D5**: MCP contract (sync/async, pydantic, envelope).
4. **E1**: Active-project resolution.
5. **F2, G1**: Crash recovery, install script semantics.
6. **H1, H2**: Encryption seed location and cross-machine recovery.
7. **I3, I5**: Compliance position, slug uniqueness scope.
8. **J1**: Strip-map original-skill coverage.

Once these are addressed PLAN.md will be tight enough that M1 schema, M3 MCP, and M7 skills can be authored without rediscovering them.

The recommended structure of the amended PLAN.md grows by roughly 250 lines (six new tables, three new contract sections, two operations subsections, the strip-map additions). The total page count remains digestible by a senior engineer in one read. Twenty-eight working days remains a realistic estimate.

### Critical Files for Implementation

- /Users/sergeyrura/Bin/content-stack/PLAN.md
- /Users/sergeyrura/Bin/content-stack/docs/upstream-stripping-map.md
- /Users/sergeyrura/Bin/content-stack/.upstream/seo-geo-claude-skills/references/core-eeat-benchmark.md
- /Users/sergeyrura/Bin/content-stack/.upstream/codex-seo/skills/seo-drift/references/comparison-rules.md
- /Users/sergeyrura/Bin/content-stack/.upstream/cody-article-writer/source/cody-article-writer/references/editor-style-guide.md