# content-stack — Plan

> Single source of truth for what we are building, why, and how it consolidates upstream.
> This document is the first commit of the repository.

---

## Vision

A **globally-installed Python daemon** that gives any LLM (Codex CLI, Claude Code,
or any MCP client) a stateful CRUD seam for managing **multi-project SEO content
pipelines end-to-end**, plus a **minimal Vue 3 UI** for human inspection and edits,
plus a **`procedures/` directory** of canonical playbooks the agents follow.

Three audiences:

1. **The LLM** — calls MCP tools, follows procedures, writes content.
2. **The human operator** — opens the UI, registers projects, approves topics,
   reviews articles, edits voice / compliance / EEAT criteria.
3. **The end user (any developer)** — `make install` and they have the full
   pipeline running for any number of sites without writing prompts or processes
   themselves.

**No project-specific defaults.** The repository is generic. Every project
registers its own voice, compliance rules, EEAT criteria, and publish targets.

---

## The flow this implements

The system implements the canonical "agentic SEO" flow plus humanization plus
multi-site coordination. The five phases:

```
Phase 1 — Research & Planning   (keyword discovery, SERP analysis,
                                 topical clustering, content briefs)
Phase 2 — Content Production    (outline → draft → editor → EEAT gate)
Phase 3 — Assets                (image generation, alt-text audit)
Phase 4 — Publishing            (interlinking, schema emit, CMS push)
Phase 5 — Ongoing Operations    (GSC opportunities, drift detection,
                                 refresh queue, humanization pass)
```

Plus **two cross-cutting procedures**:

- **Bootstrap** — first-run setup of a project (voice, compliance, EEAT, targets).
- **Add new site** — repeat bootstrap with new project context; zero code change.

Every agent in this flow exists. No phase is deferred. No "MVP cuts."

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │  LLM clients (any of):              │
                    │   - Codex CLI                       │
                    │   - Claude Code                     │
                    │   - Cursor / Cline / Continue / …   │
                    └──────────────┬──────────────────────┘
                                   │  MCP (Streamable HTTP)
                                   ▼
        ┌──────────────────────────────────────────────────────┐
        │  content-stack daemon (single Python process)        │
        │   uvicorn + FastAPI                                  │
        │                                                      │
        │   ┌─────────┬──────────────┬─────────────────────┐  │
        │   │  /mcp   │   /api/v1    │   /  (static UI)    │  │
        │   │  MCP    │   REST       │   Vue 3 + Vite      │  │
        │   └────┬────┴──────┬───────┴──────────┬──────────┘  │
        │        └───────────┴──────────────────┘             │
        │                    ▼                                │
        │   ┌────────────────────────────────────────────┐   │
        │   │ repositories  +  integrations              │   │
        │   │ (SQLModel)    (DataForSEO, Ahrefs,         │   │
        │   │                Firecrawl, GSC, OpenAI      │   │
        │   │                Images, Reddit, PAA)        │   │
        │   └────────────────────┬───────────────────────┘   │
        │                        ▼                            │
        │   ┌──────────────────────────────────────┐         │
        │   │ ~/.local/share/content-stack/        │         │
        │   │   content-stack.db (SQLite + WAL)    │         │
        │   └──────────────────────────────────────┘         │
        └──────────────────────────────────────────────────────┘
                                ▲
                                │  http://localhost:5180
                                │
                    ┌───────────┴────────────┐
                    │  Browser (human)       │
                    └────────────────────────┘
```

One process. One DB. Three transports (MCP, REST, static). Bound to
`127.0.0.1`.

**Localhost binding (enforced in code).** The FastAPI app factory binds uvicorn
to `127.0.0.1:5180`. `python -m content_stack serve --host 0.0.0.0` is rejected
at CLI parse with exit code 1 and a one-line explanation. The HTTP middleware
rejects any request whose `Host:` header is not `localhost`, `127.0.0.1`, or
`[::1]` with 421 Misdirected Request. CORS is `same-origin` only; the UI is
served from the same origin so cross-origin browser fetches fail. `doctor.sh`
verifies via `lsof -iTCP:5180 -sTCP:LISTEN` and a `curl -H 'Host: example.com' …`
probe.

**Authentication (per-install bearer token).** Every REST and MCP request must
carry `Authorization: Bearer <token>` where `<token>` is read from
`~/.local/state/content-stack/auth.token` (32 bytes, base64-url, mode 0600,
generated at first run). The install scripts inject the token into Codex's MCP
config and Claude Code's `.mcp.json`. The token rotates on every `make install`
re-run; install scripts overwrite the MCP configs to match. `doctor.sh` checks
the file exists and is mode 0600. Multi-user is out of scope; this token
enforces single-user binding only.

**SQLite PRAGMAs (set at every connect).**

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;
```

Repositories use one SQLAlchemy session per request; transactions target
≤100 ms; long-running enrichment writes batched in 100-row chunks. `MAX_CONCURRENCY`
env var caps simultaneous procedure runs (default 4) to keep the writer mutex
healthy for the daemon's own jobs and the UI.

---

## Tech stack

| Concern | Choice | Why |
|---|---|---|
| Runtime | Python 3.12+ | Strong MCP SDK; pydantic v2; mature SQLite tooling |
| Web framework | FastAPI + uvicorn | Async; OpenAPI native; ergonomic with SQLModel |
| ORM | SQLModel (pydantic v2 + SQLAlchemy 2) | Same models drive REST and MCP IO |
| Database | SQLite stdlib in WAL mode | Embedded; no daemon; concurrent reads |
| Migrations | Alembic | Industry standard for SQLAlchemy |
| MCP | `mcp` Python SDK (Streamable HTTP) | Official, dual-runtime |
| Background jobs | APScheduler | In-process cron for ongoing procedures |
| HTTP client | `httpx` | Async, idiomatic in FastAPI |
| Scraping | `firecrawl-py` (primary) + `playwright` (fallback) | JS-rendered + simple HTML |
| UI framework | Vue 3 + Vite + TypeScript | Fast dev; matches modern toolchains |
| UI styling | Tailwind CSS | Minimal, fast, no design system overhead |
| Python deps | `uv` | Fastest; modern; lockfile |
| UI deps | `pnpm` | Standard |
| Process supervision | macOS launchd plist (optional) | Auto-start; manual `serve` always works |

---

## Makefile targets

`make install` is the canonical onboarding command. README quickstart MUST be
regenerated from this list to stay in sync. All targets below are idempotent
unless noted.

| Target | Idempotent | Daemon-required | Semantics |
|---|---|---|---|
| `install` | yes | no | Wraps: `uv sync`, `alembic upgrade head`, `make build-ui`, `make register-codex`, `make register-claude`, `make install-skills-codex`, `make install-skills-claude`, `make install-procedures-codex`, `make install-procedures-claude`, `scripts/doctor.sh --json`. Re-running rotates the auth token and updates MCP configs. |
| `serve` | n/a | starts it | `python -m content_stack serve --port 5180`. Foreground; `Ctrl-C` graceful. |
| `build-ui` | yes | no | `cd ui && pnpm install --frozen-lockfile && pnpm build`. Output committed at `content_stack/ui_dist/`. CI verifies the committed bundle matches `ui/src/`. |
| `register-codex` | yes | no | `scripts/register-mcp-codex.sh`: idempotent upsert of `content-stack` MCP server with current auth token. |
| `register-claude` | yes | no | `scripts/register-mcp-claude.sh`: parse `.mcp.json`, upsert `content-stack`, atomic write with `.bak`. |
| `install-skills-codex` | yes | no | `rsync -a --delete skills/ ~/.codex/skills/content-stack/`. Retired skills removed; user-customised files preserved with `.bak` suffix on conflict. |
| `install-skills-claude` | yes | no | Same against `~/.claude/skills/content-stack/`. |
| `install-procedures-codex` | yes | no | `rsync -a --delete procedures/ ~/.codex/procedures/content-stack/`, excluding `_template/`. |
| `install-procedures-claude` | yes | no | Same against `~/.claude/procedures/content-stack/`. |
| `install-launchd` | yes | no | Writes plist to `~/Library/LaunchAgents/com.content-stack.daemon.plist`. If present and identical, no-op; if different, `--force` overwrites with `.bak`. |
| `doctor` | yes | optional | `scripts/doctor.sh`; see "doctor.sh check list" below. |
| `test` | yes | no | `uv run pytest`. |
| `migrate` | yes | no | `uv run alembic upgrade head`. |
| `lint` | yes | no | `uv run ruff check . && uv run ruff format --check .`. |
| `clean` | yes | no | Removes `.venv`, `content_stack/ui_dist/`, `__pycache__`, `node_modules`. Does NOT touch `~/.local/share/content-stack/` (use `make uninstall` for that). |
| `uninstall` | yes | no | `rsync` removes installed skills/procedures from `~/.codex/` and `~/.claude/`, removes MCP entries, unloads launchd plist. Does NOT remove `~/.local/share/content-stack/content-stack.db` (preserves user content). |
| `backup` | yes | optional | `sqlite3 content-stack.db ".backup ~/.local/share/content-stack/backups/<timestamp>.db"`; copies `seed.bin` and `auth.token` alongside. |
| `restore <file>` | n/a | stops it | Halts daemon, copies file over current DB, restarts daemon. |

---

## Repository layout

```
content-stack/
├── README.md
├── PLAN.md                          ← this file
├── pyproject.toml
├── uv.lock
├── Makefile
│
├── content_stack/                   # Python package
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                       # serve | init | migrate | install | doctor
│   ├── config.py                    # paths, env, port, db
│   ├── server.py                    # FastAPI app factory
│   │
│   ├── db/
│   │   ├── connection.py
│   │   ├── models.py                # all 28 SQLModel tables
│   │   ├── seed.py
│   │   └── migrations/versions/
│   │
│   ├── repositories/                # business logic, transport-agnostic
│   │   └── ... (one per table)
│   │
│   ├── api/                         # FastAPI routers (REST for UI)
│   │   └── ... (one per resource)
│   │
│   ├── mcp/                         # MCP tool definitions
│   │   ├── server.py
│   │   └── tools/
│   │       └── ... (one per resource)
│   │
│   ├── integrations/                # external API wrappers
│   │   ├── dataforseo.py
│   │   ├── ahrefs.py
│   │   ├── firecrawl.py
│   │   ├── gsc.py                   # Google Search Console
│   │   ├── openai_images.py
│   │   ├── reddit.py                # PRAW
│   │   ├── google_paa.py            # People Also Ask scraper
│   │   └── jina_reader.py           # markdown extraction fallback
│   │
│   ├── jobs/                        # APScheduler jobs
│   │   ├── gsc_pull.py              # nightly
│   │   ├── drift_check.py           # weekly
│   │   ├── refresh_detector.py      # weekly
│   │   └── runs.py
│   │
│   └── ui_dist/                     # built Vue assets (committed; CI verifies match with ui/src/)
│
├── ui/                              # Vue 3 source
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.ts
│       ├── App.vue
│       ├── router.ts
│       ├── api.ts                   # auto-generated from FastAPI OpenAPI
│       ├── views/
│       │   ├── ProjectsView.vue
│       │   ├── ProjectDetailView.vue           # tabs: Overview, Voice, Compliance, EEAT, Authors, Targets, Integrations, Budgets, Schedules
│       │   ├── ClustersView.vue
│       │   ├── TopicsView.vue
│       │   ├── ArticlesView.vue
│       │   ├── ArticleDetailView.vue           # subviews: Brief, Outline, Draft, Edited, Assets, Sources, Schema, Interlinks (incoming + outgoing), EEAT report, Activity (run_steps timeline), Versions, Publishes
│       │   ├── InterlinksView.vue
│       │   ├── GscView.vue                     # raw table, last 30d
│       │   ├── DriftView.vue
│       │   ├── RunsView.vue                    # audit trail
│       │   └── ProceduresView.vue              # browse + run procedures
│       └── components/
│           ├── DataTable.vue
│           ├── StatusBadge.vue
│           ├── MarkdownView.vue
│           ├── MarkdownEditor.vue
│           ├── TabBar.vue
│           ├── ProjectSwitcher.vue
│           └── KvList.vue
│
├── skills/                          # SKILL.md sources (dual-runtime)
│   ├── 01-research/
│   │   ├── keyword-discovery/
│   │   ├── serp-analyzer/
│   │   ├── topical-cluster/
│   │   ├── content-brief/
│   │   └── competitor-sitemap-shortcut/
│   ├── 02-content/
│   │   ├── outline/
│   │   ├── draft-intro/
│   │   ├── draft-body/
│   │   ├── draft-conclusion/
│   │   ├── editor/
│   │   ├── eeat-gate/
│   │   └── humanizer/
│   ├── 03-assets/
│   │   ├── image-generator/
│   │   └── alt-text-auditor/
│   ├── 04-publishing/
│   │   ├── interlinker/
│   │   ├── schema-emitter/
│   │   ├── nuxt-content-publish/
│   │   ├── wordpress-publish/
│   │   └── ghost-publish/
│   └── 05-ongoing/
│       ├── gsc-opportunity-finder/
│       ├── drift-watch/
│       ├── crawl-error-watch/
│       ├── refresh-detector/
│       └── content-refresher/
│
├── procedures/                      # ordered playbooks (PROCEDURE.md)
│   ├── README.md
│   ├── 01-bootstrap-project/
│   ├── 02-one-site-shortcut/
│   ├── 03-keyword-to-topic-queue/
│   ├── 04-topic-to-published/
│   ├── 05-bulk-content-launch/
│   ├── 06-weekly-gsc-review/
│   ├── 07-monthly-humanize-pass/
│   ├── 08-add-new-site/
│   └── _template/
│
├── scripts/
│   ├── install-codex.sh             # cp -R skills/* ~/.codex/skills/
│   ├── install-claude.sh            # cp -R skills/* ~/.claude/skills/
│   ├── install-procedures-codex.sh  # cp -R procedures/* ~/.codex/procedures/
│   ├── install-procedures-claude.sh
│   ├── register-mcp-codex.sh        # codex mcp add ...
│   ├── register-mcp-claude.sh       # writes .mcp.json
│   ├── install-launchd.sh           # macOS auto-start
│   └── doctor.sh                    # diagnose: daemon? skills? mcp? api keys?
│
├── docs/
│   ├── attribution.md               # upstream credit + license check
│   ├── architecture.md
│   ├── extending.md                 # adding skills / procedures / integrations
│   ├── api-keys.md                  # required keys per integration
│   └── procedures-guide.md          # how to author procedures
│
├── tests/
│   ├── unit/
│   ├── integration/                 # FastAPI + real SQLite
│   ├── fixtures/
│   └── conftest.py
│
├── .github/workflows/
│   └── ci.yml
│
└── .gitignore
```

---

## Database schema (28 tables — full scope)

### Core project + content tables

| Table | Columns (essential) | Purpose |
|---|---|---|
| `projects` | id, slug (UNIQUE global), name, domain, niche, locale, is_active, schedule_json, created_at, updated_at | Site registrations. `niche` is freeform TEXT for human display; not used by skills for branching. `locale` is singular (e.g., `en-US`); multi-locale = separate project per locale. |
| `voice_profiles` | id, project_id, name, voice_md, is_default, version, created_at | Voice/tone variants. Articles snapshot the active voice at brief time via `articles.brief_json.voice_id` and `voice_id_used`; subsequent edits do NOT retroactively affect the draft. |
| `authors` | id, project_id, name, slug, bio_md, headshot_url, role, credentials_md, social_links_json, schema_person_json, created_at, updated_at | Per-article author attribution required by E-E-A-T (Experience/Expertise). Self-describing for `schema.org/Person` JSON-LD. |
| `compliance_rules` | id, project_id, kind, title, body_md, jurisdictions, position, params_json, validator, is_active | RG / affiliate / jurisdiction / age-gate. `position` enum (see below) governs render placement. `params_json` carries structured fields for built-in kinds; `validator` names a registered Python callable (built-in for predefined kinds; required for `custom`). |
| `eeat_criteria` | id, project_id, code, text, category (C/O/R/E/Exp/Ept/A/T), tier, description, weight, required, active, version, created_at | Project-specific quality gate. The 8-letter category form matches the 8-dimension rubric used by the gate (Content / Organisation / Recency / Experience / Expertise / Authority / Trust + a fallback ``E`` shared with the eeat-audit metadata at L444 + L1620). `tier` ENUM(`core`,`recommended`,`project`); rows with `tier='core'` cannot have `required=false` or `active=false` (repository invariant; 422 on mutation). T04, C01, R10 seeded as `tier='core'`. |
| `clusters` | id, project_id, name, type, parent_id, created_at | Topical map. `type` enum: `pillar | spoke | hub | comparison | resource`. |
| `topics` | id, project_id, cluster_id, title, primary_kw, secondary_kws, intent, status, priority, source, created_at, updated_at | Topic queue with provenance. `priority` INTEGER 0–100; NULL=50; higher=sooner; tiebreaker `(priority DESC, created_at ASC, id ASC)`. |
| `articles` | id, project_id, topic_id, author_id, reviewer_author_id, slug, title, status, brief_json, outline_md, draft_md, edited_md, voice_id_used, eeat_criteria_version_used, canonical_target_id, last_refreshed_at, last_evaluated_for_refresh_at, last_link_audit_at, version, owner_run_id, current_step, step_started_at, step_etag (UUID, regenerates each step), lock_token, last_completed_step, created_at, updated_at | Content lifecycle (single fat row, current version only). `slug` UNIQUE(`project_id`, `slug`); auto-generated kebab-case from title (alnum + dashes, max 80 chars), editable. UI/MCP refuse on conflict with 409 + suggestion. `slug` is immutable post-`status='published'` (CHECK + repository invariant); slug change pre-publish only. Every `article.set*` MCP tool requires `expected_etag`; mismatch → 409. |
| `article_versions` | id, article_id, version, brief_json, outline_md, draft_md, edited_md, frontmatter_json (per-target snapshot), published_url, published_at, voice_id_used, eeat_criteria_version_used, created_at, refreshed_at, refresh_reason | Historical bodies. `articles` keeps current; `article.createVersion` MCP copies live row → `article_versions` BEFORE mutating. Each refresh = one new version row. |
| `article_assets` | id, article_id, kind, prompt, url, alt_text, width, height, position, created_at | Hero + inline images. `kind` enum: `hero | inline | thumbnail | og | twitter | infographic | screenshot | gallery`. |
| `article_publishes` | id, article_id, target_id, version_published, published_url, frontmatter_json, published_at, status, error | Per-target publish records. PK `(article_id, target_id, version_published)`. Procedure 4 publish step fans out across `publish_targets WHERE is_active=true`. `frontmatter_json` is per-target (Nuxt vs. WP vs. Ghost differ) and snapshots at publish time. |
| `internal_links` | id, project_id, from_article_id, to_article_id, anchor_text, position, status, created_at, updated_at | Interlink graph. `status` includes `broken` (set when target transitions out of `published`). Partial unique index `(from_article_id, to_article_id, anchor_text, position) WHERE status != 'dismissed'`. |
| `redirects` | id, project_id, from_url, to_article_id, kind, created_at | 301/302 records. Procedures 7 (humanize-pass) and content-refresher (#24) write a row when slug or domain changes pre-publish. `kind` enum: `301 | 302`. |
| `research_sources` | id, article_id, url, title, snippet, fetched_at, used | Citation tracking. |
| `schema_emits` | id, article_id, type, schema_json, position, is_primary, version_published, validated_at | JSON-LD blobs. `is_primary` BOOLEAN (exactly one per article); `position` INTEGER orders multiple emits. `version_published` pins to a specific article version (NULL = current). |
| `drift_baselines` | id, article_id, baseline_md, baseline_at, current_score | Drift detection. Targets the article's `canonical_target_id` URL. |
| `gsc_metrics` | id, project_id, article_id, captured_at, query, query_normalized (lowercase NFC), page, country, device, dimensions_hash (SHA-1), impressions, clicks, ctr, avg_position | Search Console snapshots (raw, retained 90 days). `dimensions_hash` over `query_normalized\|page\|country\|device\|date_bucket` for dedup. UNIQUE(`project_id`, `article_id`, `captured_at`, `dimensions_hash`). |
| `gsc_metrics_daily` | id, project_id, article_id, day, impressions_sum, clicks_sum, ctr_avg, avg_position_avg, queries_count | Aggregation for fast UI reads. Populated by nightly job after raw pull. UNIQUE(`project_id`, `article_id`, `day`). |
| `eeat_evaluations` | id, article_id, criterion_id, run_id, verdict (pass/partial/fail), notes, evaluated_at | Per-criterion EEAT result grain. Computed dimension/system scores still in `runs.metadata_json.eeat`; per-item rows queryable for trend ("our R10 fail rate dropped"). Index `(article_id, run_id)`. |
| `publish_targets` | id, project_id, kind, config_json, is_primary, is_active, created_at | Per-project publish destinations. `kind` enum: `nuxt-content | wordpress | ghost | hugo | astro | custom-webhook`. Exactly one `is_primary=true` per project (CHECK). Procedure 4 publishes to primary first; secondaries via `publish_target.replicate`. |
| `integration_credentials` | id, project_id (nullable for global), kind, encrypted_payload, nonce (BLOB, 12 bytes), expires_at, last_refreshed_at, config_json, created_at, updated_at | API keys per integration. Resolution order project-scoped → global; project-scoped overrides global. AES-256-GCM with per-row nonce; AAD = `f'project_id={p}|kind={k}'`. `kind` discriminates wire format (e.g., `gsc` payload holds `{access_token, refresh_token, oauth_redirect_uri}`). |
| `integration_budgets` | id, project_id, kind, monthly_budget_usd, alert_threshold_pct, current_month_spend, current_month_calls, qps, last_reset, created_at, updated_at | Pre-emptive cost cap + rate limit tokens. Per-integration token bucket reads `qps`. Defaults: DataForSEO 5 qps, Firecrawl 2 qps, GSC 1 qps, OpenAI Images 10 qps. UNIQUE(`project_id`, `kind`). |

### Run + audit-trail tables

| Table | Columns (essential) | Purpose |
|---|---|---|
| `runs` | id, project_id, kind, parent_run_id, procedure_slug, client_session_id, started_at, ended_at, status, error, heartbeat_at, last_step, last_step_at, metadata_json | Top-level pipeline audit. `parent_run_id` lets `run.children`/`run.abort(cascade=true)` traverse. `heartbeat_at` updated every 30 s by APScheduler; on startup, daemon scans `running AND heartbeat_at < now()-5min` → mark `aborted` with `error='daemon-restart-orphan'`. |
| `procedure_run_steps` | id, run_id, step_index, step_id, status (pending/running/success/failed/skipped), started_at, ended_at, output_json, error | One row per procedure step, written BEFORE invoking the skill. On daemon restart, the last `running OR pending` row tells the resume cursor when `PROCEDURE.md` declares `resumable: true`. |
| `run_steps` | id, run_id, step_index, skill_name, started_at, ended_at, status, input_snapshot_json, output_snapshot_json, error, cost_cents | Per-skill audit grain (cost lives here, not in `runs.metadata_json`). UI's RunsView shows step list; clicking opens input/output diff. |
| `run_step_calls` | id, run_step_id, mcp_tool, request_json, response_json, duration_ms, error, cost_cents | Per-MCP-call audit grain inside a skill step. Enables "show me what step 7 sent to GSC". |
| `idempotency_keys` | id, project_id, tool_name, idempotency_key, run_id, response_json, created_at | Mutating-tool dedup. UNIQUE(`project_id`, `tool_name`, `idempotency_key`). Replays within 24 h short-circuit to the cached response. |
| `scheduled_jobs` | id, project_id, kind, cron_expr, next_run_at, last_run_at, last_run_status, enabled | Per-project schedules. UI tab "Schedules" toggles `enabled`. APScheduler reads on startup. |

**28 tables total.**

### Status enums (string columns, validated by pydantic)

- `topics.status`: `queued | approved | drafting | published | rejected`
- `topics.source`: `manual | dataforseo | ahrefs | reddit | paa | competitor-sitemap | gsc-opportunity | refresh-detector`
- `topics.intent`: `informational | commercial | transactional | navigational | mixed`
- `articles.status`: `briefing | outlined | drafted | edited | eeat_passed | published | refresh_due | aborted-publish`
- `articles.current_step`: tracks current procedure step name (free-form, set by procedure runner; e.g., `outline`, `draft-body`, `eeat-gate`)
- `runs.status`: `running | success | failed | aborted`
- `runs.kind`: `procedure | skill-run | gsc-pull | drift-check | refresh-detector | eeat-audit | eeat-gate | publish-push | manual-edit | crawl-error-watch | humanize-pass | bulk-launch | interlink-suggest | scheduled-job | maintenance | adversarial-review`
- `internal_links.status`: `suggested | applied | dismissed | broken`
- `compliance_rules.kind`: `responsible-gambling | affiliate-disclosure | jurisdiction | age-gate | privacy | terms | custom`
- `compliance_rules.position`: `header | after-intro | footer | every-section | sidebar | hidden-meta`. Within position, ordered by id ASC.
- `clusters.type`: `pillar | spoke | hub | comparison | resource`
- `article_assets.kind`: `hero | inline | thumbnail | og | twitter | infographic | screenshot | gallery`
- `article_publishes.status`: `pending | published | failed | reverted`
- `publish_targets.kind`: `nuxt-content | wordpress | ghost | hugo | astro | custom-webhook`
- `procedure_run_steps.status`: `pending | running | success | failed | skipped`
- `run_steps.status`: `pending | running | success | failed | skipped`
- `eeat_evaluations.verdict`: `pass | partial | fail`
- `eeat_criteria.tier`: `core | recommended | project`
- `eeat_criteria.category`: `C | O | R | E | Exp | Ept | A | T` (Content, Organisation, Recency, Experience, Expertise, Authority, Trust — matches the 8 keys used in `runs.metadata_json.eeat.dimension_scores` at L444 + the coverage-floor invariant at L1620)
- `redirects.kind`: `301 | 302`

### JSON column shapes

#### `articles.brief_json`

```json
{
  "voice_id": 12,
  "primary_kw": "...",
  "secondary_kws": ["..."],
  "target_word_count": 1800,
  "intent": "informational",
  "audience": "...",
  "outline_hint_md": "...",
  "research_summary": "...",
  "compliance_jurisdictions": ["GB", "DE"],
  "schema_types": ["Article", "FAQPage"]
}
```

- `image_directives` (optional): `{ count: int, style?: string, alt_text_hints?: string[], allow_real_persons?: bool }` — guidance for `image-generator` (skill #13)

#### `article_publishes.frontmatter_json` (per-target, snapshot at publish time)

Flat key→value map computed from the active `publish_targets.config_json`
template + article fields. Required keys vary by target kind; common: `title`,
`slug`, `description`, `canonical_url`, `og_image`, `og_description`,
`schema_ref` (FK-like into `schema_emits.id`), `tags`, `categories`, `author`
(from `articles.author_id`), `published_at_iso`, `last_refreshed_at_iso`.

#### `runs.metadata_json` (discriminated union by `runs.kind`)

| `runs.kind` | Required keys |
|---|---|
| `procedure` | `slug`, `args`, `step_count`, `concurrency`, `started_by`, `budget_cap_usd?` |
| `skill-run` | `skill`, `inputs_summary`, `model?`, `tokens?` |
| `gsc-pull` | `window_days`, `dimensions[]`, `articles_pulled`, `rows_pulled` |
| `drift-check` | `articles_checked`, `drifted_count`, `top_drifts[]` |
| `refresh-detector` | `articles_evaluated`, `marked_refresh_due`, `criteria` |
| `eeat-audit` | `dimension_scores: {C,O,R,E,Exp,Ept,A,T → 0-100}`, `system_scores: {GEO, SEO}`, `verdict (SHIP/FIX/BLOCK)`, `vetoes: string[]`, `top_issues: {item_id, severity, finding}[]` |
| `eeat-gate` | `eeat_audit_run_id`, `verdict`, `fix_required: string[]?` |
| `publish-push` | `target_id`, `published_url`, `bytes_pushed` |
| `manual-edit` | `column`, `prev_hash`, `new_hash`, `user_agent` |
| `crawl-error-watch` | `errors_found[]` |
| `humanize-pass` | `articles_processed`, `version_bumps` |
| `bulk-launch` | `topics`, `concurrency`, `child_run_ids[]`, `budget_cap_usd?` |
| `interlink-suggest` | `from_article_id`, `suggestions_count` |
| `scheduled-job` | `cron_expr`, `executor` |
| `maintenance` | `op` (e.g., `vacuum`, `seed-rotate`, `backup`) |
| `adversarial-review` | `runtime`, `duration_ms`, `skipped?: 'timeout' \| 'plugin-disabled' \| 'wrong-runtime'` |

#### `runs.metadata_json.cost` (universal sub-key)

```json
{ "by_integration": { "dataforseo": 1.20, "firecrawl": 0.80, "openai-images": 0.04 }, "total_usd": 2.04 }
```

Aggregated cost-of-truth lives in `run_steps.cost_cents` summed per run; the
`runs.metadata_json.cost` key is denormalised for fast UI display.

### Indexes (composite, hot-path)

```sql
CREATE INDEX idx_articles_status_project ON articles(project_id, status);
CREATE INDEX idx_articles_canonical_target ON articles(canonical_target_id);
CREATE INDEX idx_articles_refresh_eval ON articles(project_id, status, last_evaluated_for_refresh_at);
CREATE INDEX idx_topics_queue ON topics(project_id, status, priority DESC, created_at ASC);
CREATE INDEX idx_runs_project_started ON runs(project_id, started_at DESC);
CREATE INDEX idx_runs_parent ON runs(parent_run_id);
CREATE INDEX idx_runs_running_heartbeat ON runs(status, heartbeat_at) WHERE status='running';
CREATE INDEX idx_gsc_metrics_article_time ON gsc_metrics(article_id, captured_at);
CREATE INDEX idx_gsc_metrics_daily_lookup ON gsc_metrics_daily(project_id, article_id, day);
CREATE INDEX idx_internal_links_from ON internal_links(from_article_id);
CREATE INDEX idx_internal_links_to ON internal_links(to_article_id);
CREATE UNIQUE INDEX uq_internal_links_unique ON internal_links(from_article_id, to_article_id, anchor_text, position) WHERE status != 'dismissed';
CREATE INDEX idx_eeat_evals_article ON eeat_evaluations(article_id, run_id);
CREATE INDEX idx_run_steps_run ON run_steps(run_id, step_index);
CREATE INDEX idx_run_step_calls_step ON run_step_calls(run_step_id);
CREATE UNIQUE INDEX uq_idempotency ON idempotency_keys(project_id, tool_name, idempotency_key);
CREATE UNIQUE INDEX uq_article_slug ON articles(project_id, slug);
CREATE UNIQUE INDEX uq_publish_targets_primary ON publish_targets(project_id) WHERE is_primary=true;
```

### Seed data

`db/seed.py` is **idempotent** (uses `INSERT OR IGNORE` keyed on stable
identifiers) and runs on every daemon start. It populates:

1. Zero rows in any project-scoped table at DB-init time. Projects bootstrap
   themselves via procedure 1.
2. Default `eeat_criteria` rows are seeded **at project-creation time** (not at
   DB init): the canonical 80-item rubric, with `T04` / `C01` / `R10` set as
   `tier='core'` (cannot deactivate); the rest `tier='recommended'`. Each row
   carries `text` (the human-readable standard) so future rubric renumbering
   doesn't break references.
3. Default `schema_emits` templates per project: `Article`, `BlogPosting`,
   `FAQPage`, `Product`, `Organization`, `Review` placeholders. (HowTo
   was deprecated by Google in 2023-09 and is no longer eligible for
   rich results; BreadcrumbList is generated per-article inline by the
   schema-emitter rather than seeded as a project-level template.)
4. Default `integration_budgets` per kind on first integration setup (monthly
   $50 cap, 80% alert threshold by default).
5. No default voice / compliance / publish targets — those are user-supplied
   per project in procedure 1.

### Canonical refresh-detector query

```sql
SELECT a.id FROM articles a
WHERE a.status = 'published'
  AND a.project_id = :project_id
  AND (a.last_refreshed_at IS NULL OR a.last_refreshed_at < date('now','-90 days'))
  AND (a.last_evaluated_for_refresh_at IS NULL
       OR a.last_evaluated_for_refresh_at < date('now','-7 days'))
ORDER BY COALESCE(a.last_refreshed_at, a.created_at) ASC
LIMIT :n;
```

The `last_evaluated_for_refresh_at` timestamp is updated even when the detector
decides NOT to mark for refresh, preventing thrash.

---

## API surface

REST and MCP expose the **same operations** on the **same repository layer**.
The REST API drives the UI; MCP drives the LLM. No duplicated business logic.

### Pagination convention

Cursor-based on `id ASC` for stable lists. Query params: `?limit=50&after=<id>`
(default `limit=50`, max `200`). Response envelope:

```json
{ "items": [...], "next_cursor": 12345, "total_estimate": 17204 }
```

`next_cursor` is `null` when the page is the last. MCP list tools accept
`limit` and `after_id`; same envelope.

### Filtering / sorting convention

Any column listed in the schema enums is filterable via `?col=val` (multiple
allowed; repeated keys mean OR within column, AND across columns). Sorting:
`?sort=col` ASC or `?sort=-col` DESC; default per-resource is `-created_at`.
MCP list tools accept `filter: dict, sort: str, limit, after_id`.

### REST (`/api/v1/...`)

```
# Projects
GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}
POST   /api/v1/projects/{id}/activate
DELETE /api/v1/projects/{id}             # cascade — see "DELETE cascade" below

# Presets per project
GET / PUT  /api/v1/projects/{id}/voice
POST  /api/v1/projects/{id}/voice/{vid}/activate
GET / POST / PATCH / DELETE  /api/v1/projects/{id}/compliance[/{cid}]
GET / PUT / PATCH  /api/v1/projects/{id}/eeat[/{eid}]
GET / POST / PATCH / DELETE  /api/v1/projects/{id}/authors[/{aid}]
GET / POST / PATCH / DELETE  /api/v1/projects/{id}/publish-targets[/{tid}]
POST  /api/v1/projects/{id}/publish-targets/{tid}/primary
GET / POST / PATCH / DELETE  /api/v1/projects/{id}/integrations[/{iid}]
GET / POST / PATCH / DELETE  /api/v1/projects/{id}/budgets[/{bid}]
GET / POST / PATCH  /api/v1/projects/{id}/schedules

# Research / planning
GET / POST  /api/v1/projects/{id}/clusters
GET / POST / PATCH  /api/v1/projects/{id}/topics
POST  /api/v1/projects/{id}/topics/bulk
PATCH  /api/v1/topics/{id}                # status transitions; permissive (UI escape hatch)

# Content
GET / POST  /api/v1/projects/{id}/articles
POST  /api/v1/projects/{id}/articles/bulk
GET / PATCH  /api/v1/articles/{id}        # PATCH is permissive (UI); MCP enforces state machine
GET  /api/v1/projects/{id}/articles/refresh-due
POST  /api/v1/articles/{id}/refresh-due   # mark for refresh manually
POST  /api/v1/articles/{id}/assets
GET / POST  /api/v1/articles/{id}/sources
GET / PUT  /api/v1/articles/{id}/schema
GET  /api/v1/articles/{id}/eeat            # rubric scores per dimension + failed items
GET  /api/v1/articles/{id}/versions
GET  /api/v1/articles/{id}/publishes

# Linking
GET / POST  /api/v1/projects/{id}/interlinks
POST  /api/v1/projects/{id}/interlinks/suggest
POST  /api/v1/projects/{id}/interlinks/bulk-apply
POST  /api/v1/articles/{id}/interlinks/repair

# Ongoing
POST  /api/v1/gsc/bulk
GET  /api/v1/articles/{id}/drift
POST  /api/v1/articles/{id}/drift/snapshot
GET  /api/v1/projects/{id}/runs
GET  /api/v1/runs/{id}                    # step list with run_steps + run_step_calls
POST  /api/v1/runs/{id}/abort             # ?cascade=true
GET  /api/v1/projects/{id}/cost?month=YYYY-MM
                                           # → { by_integration, total_usd, period_start, period_end }

# Adversarial review (codex-plugin-cc helper)
POST  /api/v1/adversarial-review          # daemon-side helper; runtime-conditional

# Procedures
GET  /api/v1/procedures
POST  /api/v1/procedures/{slug}/run        # 202 → { run_id, status_url, started_at }
GET  /api/v1/procedures/runs/{run_id}
GET  /api/v1/procedures/runs/{run_id}/status
POST  /api/v1/procedures/runs/{run_id}/resume
POST  /api/v1/procedures/runs/{run_id}/fork

# Meta + observability
GET  /api/v1/meta/enums                    # see "Enum lookup" below
GET  /api/v1/health                        # daemon uptime, db, scheduler, integrations
```

#### Procedure runs are async

`POST /api/v1/procedures/{slug}/run` always returns 202
`{run_id, status_url, started_at}`. Polling: `GET /api/v1/procedures/runs/{run_id}`
returns the full step list with statuses; `GET .../status` returns
`{status, last_step, last_step_at, percent_complete}` for cheap polling.
Streaming clients can subscribe via SSE on `GET .../status?stream=true`. See
"Streaming" below.

#### DELETE cascade

`DELETE /api/v1/projects/{id}` is a **soft delete**: sets `is_active=false` and
appends `[archived <ts>]` to the slug to free the unique constraint. Hard
delete is `?hard=true`, which cascades through `articles`, `topics`,
`gsc_metrics`, `gsc_metrics_daily`, `internal_links`, `schema_emits`,
`drift_baselines`, `runs`, `run_steps`, `run_step_calls`, `eeat_evaluations`,
`article_versions`, `article_publishes`, `article_assets`, `research_sources`,
`redirects`, `compliance_rules`, `eeat_criteria`, `voice_profiles`, `authors`,
`publish_targets`, `integration_credentials`, `integration_budgets`,
`scheduled_jobs`, `idempotency_keys`. Repository runs the cascade in
chunked transactions (10 000 rows per chunk) to avoid locking the DB for
minutes; UI shows a progress modal driven by `runs.kind='maintenance'`,
`metadata_json.op='project-hard-delete'`.

### MCP tools (mirror REST; project-scoped tools take explicit `project_id`)

```
project.*       create | list | get | update | delete | activate | setActive | getActive
voice.*         set | get | listVariants | setActive
compliance.*    list | add | update | remove
eeat.*          bulkSet | list | toggle | score | getReport
author.*        create | list | get | update | delete
target.*        list | add | update | remove | setPrimary
integration.*   list | set | test | remove | testGsc
budget.*        list | set | update | queryProject
cluster.*       create | list | get
topic.*         create | bulkCreate | list | approve | reject | get | bulkUpdateStatus
article.*       create | bulkCreate | get | list | listDueForRefresh | markRefreshDue | refreshDue
                setBrief | setOutline | setDraft | setEdited
                markEeatPassed | markPublished | createVersion | listVersions | listPublishes
asset.*         create | list | update | remove
interlink.*     suggest | apply | list | dismiss | bulkApply | repair
source.*        add | list
schema.*        set | get | validate
gsc.*           bulkIngest | queryArticle | queryProject
drift.*         snapshot | diff | list | get
run.*           start | finish | list | get | heartbeat | resume | fork | abort | children | cost
procedure.*     list | run | status | resume | fork
publish.*       preview
schedule.*      list | set | toggle
cost.*          queryProject | queryAll
meta.*          enums
```

### MCP tool contract

Every tool has `tools/<name>.py` with `class FooInput(BaseModel)` and
`class FooOutput(BaseModel)` (pydantic v2). Input models declare `project_id:
int` explicitly except for `meta.*` and globally-scoped `project.*` tools.
Output models are the canonical pydantic models exported from
`repositories/`. A CI check fails the build if any registered MCP tool lacks
matching Input/Output classes.

**Per-call `project_id` is mandatory** on every project-scoped tool. MCP is
stateless across calls; `project.setActive` and `project.getActive` mutate the
**UI sidebar state only** (a row in `projects.is_active`). Skills MUST read
`project_id` from procedure context (env var `CONTENT_STACK_PROJECT_ID` set by
the procedure runner) and pass it through every call. This eliminates the
two-client active-project race.

### Tool-grant matrix (whitelist per skill)

`run.start` returns a `run_token` (signed) that every subsequent tool call
must carry as a request header. The server resolves `run_token` to the
calling skill name and enforces:

```
tool ∉ whitelist[skill]   →   403 Forbidden, code -32007, hint=...
```

The matrix lives in `docs/extending.md`. Examples:

- `outline` (#6): `voice.get`, `compliance.list`, `eeat.list`, `article.get`,
  `article.setOutline`, `source.list`. Cannot call `article.markPublished`,
  `project.delete`, `eeat.toggle`.
- `eeat-gate` (#11): `article.get`, `eeat.list`, `eeat.score`, `compliance.list`,
  `article.markEeatPassed` (only on SHIP verdict). Cannot call
  `article.markPublished`.
- `publish` skills (#17/18/19): `article.get`, `schema.get`, `target.list`,
  `publish.preview`, `article.markPublished`, `article_publish.create` (internal
  only via repository, not raw MCP).

State-machine invariant on `articles.status`: transition to `published`
requires the prior status was `eeat_passed` AND a corresponding
`runs.kind='eeat-gate', status='success', metadata_json.verdict='SHIP'` row
exists for the same `(article_id, version)`. Enforced in `repositories/articles.py`
and as a SQLite trigger.

### Idempotency

Every mutating MCP tool accepts an optional `idempotency_key: str`. The
repository layer keys `(project_id, tool_name, idempotency_key)` →
`idempotency_keys.id` and short-circuits replays within a 24 h window with
the cached response (HTTP 200 + same envelope). Replays beyond 24 h are
treated as fresh calls. The dedicated `idempotency_keys` table makes the
window queryable for support.

### Streaming

`procedure.run`, `topic.bulkCreate` (when N>50), `gsc.bulkIngest`,
`interlink.suggest`, `article.bulkCreate` (when N>20) are streaming: they emit
`progress` events `{step, total, message, partial_data?}` until completion.
All other tools are request-response. Tool definitions declare
`streaming: true` in registration. Clients that don't consume SSE see only
the final result. Reference the `mcp` SDK's streaming primitives.

### Error model

JSON-RPC error code mapping; every error includes
`data: {run_id?: int, retryable: bool, retry_after?: seconds, hint?: string}`.

| Code | Meaning | Retryable |
|---|---|---|
| -32602 | validation failed | no |
| -32004 | not found | no |
| -32007 | forbidden (tool-grant matrix violation) | no |
| -32008 | conflict (etag mismatch, slug duplicate, state-machine violation) | no |
| -32010 | integration down | yes |
| -32011 | rate-limited | yes (server-side auto-retry up to 3×; non-retryable bubbles up) |
| -32012 | budget exceeded | no (operator action required) |
| -32603 | internal | sometimes |

### Result envelope

Mutating tools (whose name starts with `create|update|set|mark|add|remove|toggle|approve|reject|apply|dismiss|bulkCreate|bulkUpdate|bulkApply|run|snapshot|ingest|test|validate|abort|resume|fork|activate|setPrimary|setActive`) return:

```json
{ "data": <T>, "run_id": <int>, "project_id": <int> }
```

Read tools return `T` bare. CI check enforces this convention against the
verb prefix list.

### REST/MCP parity table

| Operation | REST | MCP |
|---|---|---|
| Activate project | `POST /projects/{id}/activate` | `project.activate` |
| Get EEAT report | `GET /articles/{id}/eeat` | `eeat.getReport` |
| List articles due for refresh | `GET /projects/{id}/articles/refresh-due` | `article.listDueForRefresh` |
| Procedure status | `GET /procedures/runs/{run_id}/status` | `procedure.status` |
| Resume procedure | `POST /procedures/runs/{run_id}/resume` | `procedure.resume` |
| Fork procedure | `POST /procedures/runs/{run_id}/fork` | `procedure.fork` |
| Abort run (cascade) | `POST /runs/{id}/abort?cascade=true` | `run.abort(cascade=true)` |
| Project cost | `GET /projects/{id}/cost?month=YYYY-MM` | `cost.queryProject` |
| All-project cost | `GET /cost?month=YYYY-MM` | `cost.queryAll` |
| Bulk article create | `POST /projects/{id}/articles/bulk` | `article.bulkCreate` |
| Bulk topic status | n/a (batch via `PATCH /topics/{id}` × N) | `topic.bulkUpdateStatus` |
| Bulk interlink apply | `POST /projects/{id}/interlinks/bulk-apply` | `interlink.bulkApply` |
| Interlink repair | `POST /articles/{id}/interlinks/repair` | `interlink.repair` |
| Voice setActive | `POST /projects/{id}/voice/{vid}/activate` | `voice.setActive` |
| Target setPrimary | `POST /projects/{id}/publish-targets/{tid}/primary` | `target.setPrimary` |
| Publish preview | n/a (UI calls MCP) | `publish.preview` |
| Test GSC integration | n/a (UI calls MCP) | `integration.testGsc` |
| Enum lookup | `GET /meta/enums` | `meta.enums` |
| Health | `GET /health` | n/a (use HTTP) |

CI generates this table from registrations in both transports and fails on
gaps.

### Article CRUD: REST permissive vs. MCP state-machine

`PATCH /api/v1/articles/{id}` (REST) accepts arbitrary column updates and
writes a `runs` row with `kind='manual-edit'`. This is the human escape
hatch in the UI. MCP tools (`setBrief`, `setOutline`, `setDraft`,
`setEdited`, `markEeatPassed`, `markPublished`, `createVersion`) enforce
the `articles.status` state machine and the etag check (see schema).
Procedure runs always go through MCP; humans can bypass via UI if they
accept the audit-trail consequence (`runs.kind='manual-edit'`).

### Optimistic concurrency on UI saves

`MarkdownEditor` PUT/PATCH against `/api/v1/articles/{id}` carries an
`If-Match: <updated_at iso>` header. Server returns 409 Conflict on stale
write with `data.current_updated_at` and `data.current_etag`; UI prompts
"remote changed — reload or overwrite". Manual save creates a `runs` row
with `kind='manual-edit'` and increments `articles.version` only if
`edited_md` differs by ≥ 1 line.

### TypeScript type generation

`ui/src/api.ts` is auto-generated via `openapi-typescript` invoked from
`make build-ui`. Lockfile committed; CI fails if regeneration would produce
a diff against the committed `api.ts`.

### Logging

Logs use Python's `logging` with `structlog` for JSON output. Format
`{ts, level, logger, run_id?, project_id?, msg, kv}`. Rotation via
`RotatingFileHandler` at 10 MB × 5 to
`~/.local/state/content-stack/daemon.log`. `runs.id` is set in a
`contextvars.ContextVar` at procedure-run start so all downstream calls
inherit it without explicit threading.

### Per-tool rate limits

Middleware enforces 100 calls/minute per tool, 1000 calls/minute aggregate
per `Authorization: Bearer` token. Breach returns 429 with `retry_after`
seconds and code -32011. Bulk tools count as N calls.

---

## Skills catalogue (24 skills, full upstream attribution)

Each skill is a directory: `skills/<phase>/<name>/SKILL.md` plus optional `scripts/`.
Same directory works for Codex (`~/.codex/skills/`) and Claude Code (`~/.claude/skills/`).

| # | Skill | Upstream source | What we keep | What we change |
|---|---|---|---|---|
| 1 | `01-research/keyword-discovery` | codex-seo `seo-dataforseo` + `seo-cluster` + custom Reddit/PAA | API wiring, query templates | Add Reddit (PRAW) + PAA scrapers; persist results to `topics` |
| 2 | `01-research/serp-analyzer` | codex-seo `seo-firecrawl` + `seo-page` | Scrape recipe, on-page audit checklist (word count, tone, LSI) | Output structured JSON to DB instead of file |
| 3 | `01-research/topical-cluster` | codex-seo `seo-cluster` | Clustering algo (SERP-based) | Persist `clusters` + `topics` rows with parent/child relationships |
| 4 | `01-research/content-brief` | cody-article-writer (Research Planning + Style + Title/Thesis) | Brief structure, citation handling | Read voice/compliance/EEAT from MCP; persist `articles.brief_json` |
| 5 | `01-research/competitor-sitemap-shortcut` | original (AM Media's trick) | n/a | Authored from scratch — sitemap.xml + Ahrefs export → topical map |
| 6 | `02-content/outline` | cody-article-writer (Outline phase) | H1/H2/H3 structure logic | Read brief from `articles.brief_json`; persist `articles.outline_md` |
| 7 | `02-content/draft-intro` | cody-article-writer (Write phase, intro) | Hook patterns, thesis restatement | Separate skill per AM Media's "separate prompts for intro/body/outro" |
| 8 | `02-content/draft-body` | cody-article-writer (Write phase, body) | Section expansion, evidence injection | Reads sources from `research_sources` |
| 9 | `02-content/draft-conclusion` | cody-article-writer (Write phase, outro) | Summary + CTA pattern | Inserts compliance footer per `compliance_rules` |
| 10 | `02-content/editor` | cody-article-writer (Editor Pass) | AI-pattern strip, white space, polish | Persist to `articles.edited_md` |
| 11 | `02-content/eeat-gate` | aaron-he-zhu `content-quality-auditor` (CORE-EEAT 80-item) | The 80-item framework | Use **project-specific** criteria from `eeat_criteria` (not hardcoded) |
| 12 | `02-content/humanizer` | original (AM Media's post-publish pass) | n/a | Authored — re-edit pass that varies sentence length, removes "AI tells". Runs **once per article version**: procedure 7 generates a new version (incrementing `articles.version`) and humanizer runs against it. Same applies to content-refresher (#24): each refresh = new version = humanizer can run. |
| 13 | `03-assets/image-generator` | original | n/a | OpenAI Images API wrapper; persists to `article_assets` |
| 14 | `03-assets/alt-text-auditor` | codex-seo `seo-images` (audit subset) | Alt-text rubric | Apply to `article_assets`; flag missing/weak |
| 15 | `04-publishing/interlinker` | aaron-he-zhu `internal-linking-optimizer` | Anchor selection + relevance scoring | Use `internal_links` table for graph; suggest before apply |
| 16 | `04-publishing/schema-emitter` | codex-seo `seo-schema` | JSON-LD generation for Article / Product / FAQ / Review / HowTo | Persist `schema_emits`, validate, attach to article |
| 17 | `04-publishing/nuxt-content-publish` | original | n/a | Write `.md` + frontmatter to `content/` repo, git commit, git push |
| 18 | `04-publishing/wordpress-publish` | original | n/a | WordPress REST API (`/wp-json/wp/v2/posts`) |
| 19 | `04-publishing/ghost-publish` | original | n/a | Ghost Admin API |
| 20 | `05-ongoing/gsc-opportunity-finder` | codex-seo `seo-google` + custom heuristics | API wiring | Detect "striking distance" queries, low-CTR rank-1, missing intents → write to `topics` queue with `source=gsc-opportunity` |
| 21 | `05-ongoing/drift-watch` | codex-seo `seo-drift` | Baseline diff logic | Persist `drift_baselines`; flag articles whose live HTML drifted from `articles.edited_md` |
| 22 | `05-ongoing/crawl-error-watch` | codex-seo `seo-google` (subset) | API wiring for indexing errors | Persist incidents to `runs`; raise alerts |
| 23 | `05-ongoing/refresh-detector` | original | n/a | Authored — uses canonical query (Schema § "Canonical refresh-detector query") over `articles.last_refreshed_at`, GSC trend (via `gsc_metrics_daily`), drift score → marks `articles.status='refresh_due'`. Two entry points to `refresh_due`: (a) this skill (run weekly via `jobs/refresh_detector.py`); (b) human in UI clicks "flag for refresh" on `ArticleDetailView.vue`. Both converge on procedure 7 consuming `WHERE status='refresh_due'`. |
| 24 | `05-ongoing/content-refresher` | cody-article-writer (Editor pass) + humanizer | Re-edit prompts | Persist new `articles.version`; bump `last_refreshed_at` |

**Originals (skills #5, #12, #13, #17, #18, #19, #23) are documented in
`docs/upstream-stripping-map.md#original-skills` with algorithm sketches, DB
tables touched, MCP tools used, and key risks.** Skill authors do NOT read
`cody-article-writer/` files when authoring skills #4, #6, #7, #8, #9, #10,
#24 (clean-room re-author per D1); CI fingerprint check rejects substrings
from cody verbatim text. Same clean-room rule applies to codex-seo–derived
skills #1, #2, #3, #14, #16, #20, #21, #22.

---

## Procedures (8 canonical playbooks)

A **procedure** is an ordered, named playbook. Each procedure is a directory
with `PROCEDURE.md` (markdown + YAML frontmatter).

### Procedure orchestration model

**Procedures are daemon-orchestrated.** The MCP tool `procedure.run(slug,
project_id, args)` enqueues a server-side runner (APScheduler) which dispatches
each step as a fresh per-skill LLM session with a tight prompt. The daemon
holds its own LLM credentials (one of OpenAI/Anthropic, separate from the
runtime's). Each skill step:

1. The runner pre-writes a `procedure_run_steps` row with `status='pending'`.
2. The runner spawns a subprocess running the LLM with the skill's SKILL.md
   loaded, sets env `CONTENT_STACK_PROJECT_ID`, `CONTENT_STACK_RUN_ID`,
   `CONTENT_STACK_ARTICLE_ID?`, `CONTENT_STACK_TOPIC_ID?`, and the
   `Authorization` token; instructs the skill to call MCP via Streamable HTTP.
3. On step completion the runner updates the step row to `success|failed`,
   advances the cursor, and continues.

The calling LLM client only kicks off via `procedure.run` and polls with
`procedure.status(run_id)`. Context window per skill stays tight; no
9-step transcript explosion. `POST /api/v1/procedures/{slug}/run` returns
202 + `{run_id, status_url, started_at}`.

### PROCEDURE.md canonical YAML frontmatter

```yaml
---
name: topic-to-published
version: 1
triggers:
  - { kind: manual, command: "/procedure topic-to-published <topic_id>" }
  - { kind: parent_procedure, parent: bulk-content-launch }
prerequisites:
  - { table: topics, predicate: "id=:topic_id AND status='approved'" }
  - { table: voice_profiles, predicate: "project_id=:project_id AND is_default=true" }
  - { table: publish_targets, predicate: "project_id=:project_id AND is_active=true" }
produces:
  - articles
  - article_versions
  - article_publishes
  - article_assets
  - schema_emits
  - internal_links
  - eeat_evaluations
  - run_steps
  - run_step_calls
steps:
  - { id: brief, skill: content-brief, mcp_calls: [voice.get, compliance.list, eeat.list, source.list, article.setBrief], on_failure: abort }
  - { id: outline, skill: outline, mcp_calls: [article.get, voice.get, article.setOutline], on_failure: retry(2) }
  - { id: draft-intro, skill: draft-intro, mcp_calls: [article.get, voice.get, article.setDraft], on_failure: retry(2) }
  - { id: draft-body, skill: draft-body, mcp_calls: [article.get, source.list, article.setDraft], on_failure: retry(2) }
  - { id: draft-conclusion, skill: draft-conclusion, mcp_calls: [article.get, compliance.list, article.setDraft], on_failure: retry(2) }
  - { id: editor, skill: editor, mcp_calls: [article.get, voice.get, article.setEdited], on_failure: retry(2) }
  - { id: eeat-gate, skill: eeat-gate, mcp_calls: [article.get, eeat.list, eeat.score, eeat.getReport, article.markEeatPassed], on_failure: { SHIP: continue, FIX: loop_back(editor), BLOCK: abort } }
  - { id: image, skill: image-generator, mcp_calls: [article.get, asset.create], on_failure: retry(1) }
  - { id: alt-text, skill: alt-text-auditor, mcp_calls: [asset.list, asset.update], on_failure: continue }
  - { id: schema, skill: schema-emitter, mcp_calls: [article.get, schema.set, schema.validate], on_failure: retry(1) }
  - { id: interlinks, skill: interlinker, mcp_calls: [article.get, interlink.suggest, interlink.apply], on_failure: continue }
  - { id: publish, skill: nuxt-content-publish | wordpress-publish | ghost-publish, mcp_calls: [article.get, schema.get, target.list, publish.preview, article.markPublished], on_failure: { 4xx: abort, 5xx: retry(3, backoff=exponential) } }
variants:
  - { name: pillar, overrides: { brief.target_word_count: 4000 } }
  - { name: short, overrides: { brief.target_word_count: 800 } }
concurrency_limit: 4
resumable: true
---
```

Frontmatter keys: `name`, `version`, `triggers`, `prerequisites`, `produces`,
`steps`, `variants`, `concurrency_limit`, `resumable`. Markdown body holds the
human-readable narrative ("When to use", "Failure handling commentary",
"Variants comparison").

### Skill SKILL.md frontmatter (relevant excerpt)

Every skill's frontmatter declares:

```yaml
---
name: outline
description: Generate a hierarchical H1/H2/H3 outline from the brief
derived_from: cody-article-writer @ <commit-sha>   # or "original (n/a)"
license: <upstream-license>                         # or "n/a (clean-room original)"
inputs:
  - { name: project_id, source: env, var: CONTENT_STACK_PROJECT_ID, required: true }
  - { name: run_id, source: env, var: CONTENT_STACK_RUN_ID, required: true }
  - { name: article_id, source: env, var: CONTENT_STACK_ARTICLE_ID, required: true }
allowed_tools: [article.get, voice.get, article.setOutline]
---
```

`allowed_tools` mirrors the tool-grant matrix; the daemon double-enforces.

### Procedure catalogue

| # | Procedure | Triggers | Steps (high-level) | Outputs |
|---|---|---|---|---|
| 1 | `bootstrap-project` | First run for a new site | `project.create` → prompt for + persist voice → compliance rules → EEAT criteria (seeded with `tier='core'` rows for T04/C01/R10) → publish target → integration creds | New project row + seeded `eeat_criteria` + default `integration_budgets` |
| 2 | `one-site-shortcut` | User has 1 site, wants topical map fast | Pull competitor sitemap.xml → Ahrefs ranking export → cluster via skill 3 → write `clusters` + `topics` → present queue for approval | Approved topic queue |
| 3 | `keyword-to-topic-queue` | Periodic / on demand | keyword-discovery (skill 1) → serp-analyzer (skill 2) on top 10 → topical-cluster (skill 3) → human approves topics in UI | Approved topic queue; briefs deferred to procedure 4 |
| 4 | `topic-to-published` | Per topic; the workhorse | content-brief (4) → outline (6) → draft-intro (7) → draft-body (8) → draft-conclusion (9) → **editor (10) runs once per draft cycle on the assembled `articles.draft_md`** → **eeat-gate (11) three-way verdict: SHIP advances; FIX writes `runs.metadata_json.fix_required=[…]` and loops back to editor (10); BLOCK aborts with `articles.status='aborted-publish'` and `runs.status='aborted'`** → image-generator (13) → alt-text-auditor (14) → schema-emitter (16) → interlinker (15) → **publish to `is_primary` target first; secondary targets queued via `publish_target.replicate(article_id, target_id)`** → `article.markPublished` (writes one `article_publishes` row per target) | Published URL(s), full audit trail in `runs` + `run_steps` + `run_step_calls`; `eeat_evaluations` per criterion |
| 5 | `bulk-content-launch` | First 20–100 articles for a new site | For each approved topic: spawn procedure 4 as a child run (`runs.parent_run_id=<bulk_id>`); `concurrency_limit` from frontmatter (default 4); `--budget-cap-usd` flag refuses to start if estimated cost > cap; `run.abort(parent_run_id, cascade=true)` aborts all children | N published articles, parent + N child run rows |
| 6 | `weekly-gsc-review` | Weekly cron | gsc-pull job (raw + `gsc_metrics_daily` rollup) → gsc-opportunity-finder (20) → drift-watch (21) → crawl-error-watch (22) → write opportunities to `topics` queue with `source=gsc-opportunity`; flag drifted articles | Refreshed topic queue + drift list |
| 7 | `monthly-humanize-pass` | Monthly cron | refresh-detector (23) selects N candidates `WHERE status='refresh_due'` → for each: `article.createVersion` (snapshots live row → `article_versions`) → humanizer (12) on the new version's `edited_md` → editor (10) → republish via primary target (writes new `article_publishes` row, `version_published+1`); slug change pre-publish writes `redirects` row | New article versions (incrementing `articles.version`) |
| 8 | `add-new-site` | Operator onboards a new site | procedure 1 (bootstrap) → optionally procedure 2 (sitemap shortcut) → procedure 5 (bulk launch) | Fully operational new project |

`procedures/_template/PROCEDURE.md` is the scaffold for users to author custom
procedures (e.g., "promotional-bonus-page", "news-article-fast-publish"). The
template is excluded from `install-procedures-{codex,claude}.sh` (authoring
artifact, not runtime).

### Failure-handling primitives (callable from `on_failure:`)

- `abort` — mark the run aborted; stop.
- `retry(n, backoff=linear|exponential)` — re-run the same step.
- `loop_back(<step_id>)` — set cursor back to a previous step. Used by
  `eeat-gate FIX → editor`.
- `continue` — log warning, advance to next step. Used for non-blocking
  failures (e.g., interlinker had nothing to suggest).
- `human_review` — pause the run; UI shows "needs review" badge; runs row
  goes to `status='running'` with `metadata_json.human_review_at` set.

### Compliance footer placement

The draft-conclusion skill (#9) reads `compliance_rules` and renders rules
where `position='footer'` or `position='after-intro'`. The draft-intro
skill (#7) renders `position='header'` and `position='after-intro'` rules.
Other positions (`every-section`, `sidebar`, `hidden-meta`) are rendered by
the schema-emitter (#16) and the publish skill respectively. The EEAT gate
(#11) checks "compliance footer present per active jurisdictions" as a
separate gate immediately before scoring; failure is FIX-class, not BLOCK.

### EEAT gate three-verdict logic

The eeat-gate skill (#11) computes per-criterion verdicts (`pass|partial|fail`)
into `eeat_evaluations`, then aggregates per-dimension and per-system scores
into `runs.metadata_json.eeat`. Final verdict:

- **BLOCK**: any criterion with `tier='core'` (T04/C01/R10) is `fail`. Aborts
  the procedure with `articles.status='aborted-publish'`, `runs.status='aborted'`,
  notifies via UI flag.
- **FIX**: ≥1 `required=true` criterion is `fail`, OR aggregate dimension
  score < 70 on any of the 8 dimensions. Loops back to `editor` (#10) with
  `runs.metadata_json.fix_required = [{criterion_id, finding, severity}]`.
  Editor reads this list and targets fixes; re-runs eeat-gate.
- **SHIP**: all `tier='core'` rows are `pass`, no `required=true` row is `fail`,
  all 8 dimensions ≥ 70. Advances to image-generator.

Coverage floor: the gate refuses to score (returns code -32008 conflict) if
any of the 8 dimensions has 0 active items. Procedure 1 seed prevents this;
manual deactivation that drops a dimension to 0 is rejected at the
`eeat.toggle` repository invariant.

---

## Integrations (external APIs)

`content_stack/integrations/*.py` — pure wrappers, no business logic. Each
wrapper enforces a token-bucket rate limit (read from
`integration_budgets.qps`) and consults `integration_budgets` before each
call (refuses if month-to-date spend would exceed `monthly_budget_usd`,
returns code -32012). Wrappers update `integration_budgets.current_month_*`
post-call.

| Integration | Used by skills | Credential | Rate limit (default) |
|---|---|---|---|
| **DataForSEO** | keyword-discovery, serp-analyzer | `kind='dataforseo'`: `{login, password}` | 5 qps |
| **Ahrefs** (Enterprise-only) | keyword-discovery, one-site-shortcut | `kind='ahrefs'`: `{api_key}` | 1 qps |
| **Firecrawl** | serp-analyzer, content-brief, drift-watch | `kind='firecrawl'`: `{api_key}` | 2 qps |
| **Google Search Console** | gsc-opportunity-finder, crawl-error-watch | `kind='gsc'`: `{access_token, refresh_token, oauth_redirect_uri, expires_at}` | 1 qps |
| **OpenAI Images** | image-generator | `kind='openai-images'`: `{api_key}` (daemon-side, separate row from runtime LLM key) | 10 qps |
| **OpenAI** (procedure runner LLM) | daemon-orchestrated procedures (per D4) | `kind='openai'` or `kind='anthropic'`: `{api_key}` (daemon-side, used by the procedure runner to dispatch per-skill sessions) | n/a |
| **Reddit** (PRAW) | keyword-discovery | `kind='reddit'`: `{client_id, client_secret, user_agent}` | 5 qps |
| **Google PAA** (scraper, no key) | keyword-discovery | n/a | 0.5 qps |
| **Jina Reader** (markdown fallback) | serp-analyzer fallback | optional `kind='jina'`: `{api_key}` | 5 qps |
| **Codex-plugin-cc** (adversarial review) | eeat-gate (Claude Code only) | `kind='codex-plugin-cc'`: `{config_json: {enabled: bool}}` (per project, default off) | n/a |

**LLM credentials clarification.** The daemon needs LLM credentials directly
to drive the **procedure runner** (per D4) — those are stored as
`integration_credentials` rows with `kind='openai'` or `kind='anthropic'`,
**separate from any runtime config**. The user's Codex/Claude Code runtime
remains independent; runtime LLM calls (the user typing `/procedure …`)
continue to use the runtime's own credentials. Image generation always uses
the daemon-side `kind='openai-images'` row regardless of runtime.

### Integration first-run flows

- **DataForSEO / Firecrawl / Ahrefs / Reddit / Jina**: API key entry in UI
  Integrations tab; `integration.test` MCP tool verifies the key.
- **GSC**: 12-step OAuth setup documented in `docs/api-keys.md` with
  screenshots:
  1. User creates a Google Cloud project and OAuth client (Web app type).
  2. UI shows the redirect URI to register:
     `http://localhost:5180/api/v1/integrations/gsc/callback`.
  3. User clicks "Connect GSC" in UI.
  4. Daemon opens browser to Google's consent screen with `state=<run_id>`.
  5. Google redirects back; daemon swaps `code` for tokens.
  6. Daemon encrypts and stores `{access_token, refresh_token,
     oauth_redirect_uri, expires_at}` in `integration_credentials`.
  7. `integration.testGsc` does a `searchanalytics.query` with `rowLimit=1`;
     401 surfaces "re-auth needed".
- **OpenAI / Anthropic (procedure runner LLM)**: API key entry in UI; tested
  by dispatching a 1-token completion.
- **OpenAI Images**: same; tested by generating a 1×1 dummy image and
  refunding via API only if Avalon quota allows (otherwise just verifies
  auth).
- **codex-plugin-cc**: per-project toggle in UI (`integration_credentials`
  row with `kind='codex-plugin-cc'`, `config_json.enabled=true`); requires
  the user to have run `claude plugin install` separately.

### OAuth refresh job

`jobs/oauth_refresh.py` runs every 50 minutes via APScheduler. It scans
`integration_credentials WHERE kind='gsc' AND expires_at < now() + 10 min`,
refreshes via `refresh_token`, re-encrypts the new pair, updates
`expires_at` and `last_refreshed_at`. Failures are logged and surfaced via
`/api/v1/health.integrations_reachable.gsc=false`; the UI prompts re-auth.

Credentials are stored in `integration_credentials` (AES-256-GCM with
per-row 12-byte nonce; AAD = `f'project_id={p}|kind={k}'`; key derived from
seed via HKDF-SHA256). Resolution order: project-scoped row first, then
global; project-scoped overrides global. All integration calls log
`project_id` to vendor logs where supported.

---

## Security

### Encryption-at-rest for integration credentials

- **Seed file**: `~/.local/state/content-stack/seed.bin`, 32 bytes from
  `os.urandom`, mode 0600, owned by current user. Generated at first daemon
  start if absent. On daemon start: if present and not 0600, daemon refuses
  to start with a clear error.
- **Key derivation**: HKDF-SHA256 with the seed as IKM and the constant
  `b'content-stack:integration-credentials:v1'` as info, yielding a 32-byte
  AES-256-GCM key.
- **Per-row nonce**: 12 random bytes generated at encrypt time, stored in
  the `integration_credentials.nonce` column.
- **AAD**: `f'project_id={p}|kind={k}'` (where `p` is the integer
  `project_id` or the string `global`). Binds the ciphertext to its row
  context; tampering with `kind` or `project_id` renders the row
  undecryptable.
- **Wire format**: `encrypted_payload = ciphertext + auth_tag` (16 bytes
  GCM tag at the end); `nonce` separate.

### Cross-machine backup hygiene

`make backup` copies `seed.bin` and `auth.token` alongside the DB. Restore
without the seed renders all `integration_credentials` rows undecryptable;
the daemon refuses to start and `doctor.sh` prompts:
`seed.bin missing — run 'content-stack reset-integrations' to clear and
re-enter API keys`. No silent decryption-to-garbage.

### Seed rotation

`content-stack rotate-seed --reencrypt`:

1. Generate new seed (32 random bytes).
2. Decrypt every `integration_credentials` row with the old seed in memory.
3. Re-encrypt with the new seed (new nonce per row).
4. Atomically swap `seed.bin` (write to `seed.bin.new`, rename, fsync dir).
5. Keep `seed.bin.bak` for one daemon boot, then auto-delete on next start.

### Auth token

Per-install bearer token at `~/.local/state/content-stack/auth.token`
(32 bytes, base64-url, mode 0600). Generated at first run. Required on
every REST + MCP request as `Authorization: Bearer <token>`. Rotates on
every `make install` re-run; install scripts overwrite Codex / Claude MCP
configs to match. Read-only observer: `content-stack rotate-token --readonly`
generates a second token entry that the auth middleware honours as
GET-only; documented in `docs/extending.md`.

### Localhost binding + Host header check

The HTTP middleware rejects any request whose `Host:` header is not
`localhost`, `127.0.0.1`, or `[::1]` with 421 Misdirected Request. The CLI
rejects `--host 0.0.0.0` at parse time. CORS is `same-origin` only — the
UI is served from the same origin; cross-origin browser fetches fail.
`doctor.sh` verifies via `lsof` and a probe.

### Adversarial-review prompt-injection hygiene

The eeat-gate skill (#11) optional codex-plugin-cc adversarial review
passes the article body via a temp file (`tempfile.NamedTemporaryFile`
with mode 0600), referenced by path in the helper invocation, never via
argv. The temp file is deleted in `finally`. The article body is wrapped
in a `<article_under_review>` XML tag in the helper's prompt for prompt-
injection hygiene. Wall-clock budget per call: 90 s; on timeout, the
gate logs `runs.metadata_json.adversarial_review.skipped='timeout'` and
proceeds — slow plugins do not block the article.

### Codex-plugin-cc seam (runtime-conditional)

The seam is invoked **daemon-side**, not via Bash from the skill prompt.
The eeat-gate skill checks `runtime == 'claude-code' AND
integration_credentials.kind='codex-plugin-cc'.config_json.enabled = true`
before calling. The daemon helper at `integrations/codex_plugin_cc.py`
POSTs to `/api/v1/adversarial-review` which spawns the codex-companion
subprocess and returns a job_id; the eeat-gate polls. Default per-project
toggle: **off**. The user enables in UI Integrations tab. NOTICE file at
content-stack root credits OpenAI for the Apache-2.0 plugin.

---

## Sourcing strategy: clean-room re-author, never vendor

We **do not vendor** the upstream repos and we do not paraphrase them.
Instead:

1. **Each derived skill names its source** in its `SKILL.md` frontmatter:

   ```yaml
   ---
   name: content-brief
   description: Generate a research-backed content brief
   derived_from: ibuildwith-ai/cody-article-writer @ <commit-sha>   # informational only
   license: clean-room-original (n/a — never read upstream files)
   ---
   ```

2. **Cody clean-room re-author (D1).** Skill authors for #4, #6, #7, #8,
   #9, #10, #24 do **NOT** read any `cody-article-writer/` file. They
   author from PLAN.md's data model + general editorial knowledge only.
   The clean-room procedure is documented in `docs/attribution.md`. CI
   fingerprint check (`tests/fixtures/upstream-fingerprints.json`) fails
   the build if any `skills/02-content/*/SKILL.md` contains substrings
   from cody verbatim text.

3. **codex-seo clean-room re-author.** Same rule applies to skills #1, #2,
   #3, #14, #16, #20, #21, #22 — authors do not paraphrase codex-seo's
   prompt text. The upstream LICENSE is internally inconsistent (Avalon
   Reset proprietary in `LICENSE`, MIT in metadata); we treat it as
   proprietary and behave as if no license-grant exists.

4. **No `--with-codex-seo` install flag.** Users who want codex-seo as a
   peer install it themselves; documented in `docs/extending.md` with a
   one-paragraph "license is unclear; install at your own risk" notice.
   The install scripts will not clone or recommend cloning.

5. **`docs/attribution.md`** lists every upstream reference repo, the
   commit/version reviewed, and the license posture. Updated whenever a
   derived skill is touched. Clean-room authors do NOT cite line ranges.

6. **`docs/upstream-stripping-map.md`** uses "ideas, not lines" language;
   no "approximate volume kept: ~N LOC" claims. Original-skill section
   covers #5, #12, #13, #17, #18, #19, #23.

**Upstream repositories referenced (informationally only):**

| Repo | Role | Posture |
|---|---|---|
| `AgriciDaniel/codex-seo` | Idea source for: keyword-discovery, serp-analyzer, topical-cluster, alt-text-auditor, schema-emitter, gsc-opportunity-finder, drift-watch, crawl-error-watch | Clean-room; CI fingerprint check; no install induction |
| `ibuildwith-ai/cody-article-writer` | Idea source for: content-brief, outline, draft-intro, draft-body, draft-conclusion, editor, content-refresher | Clean-room; CI fingerprint check; license forbids competing frameworks, so we author independently |
| `aaron-he-zhu/seo-geo-claude-skills` | Idea source for: eeat-gate (CORE-EEAT framework), interlinker (internal-linking-optimizer) | Apache-2.0; clean-room re-author for prompt text; framework structure (8 dimensions, veto items) reused as common-domain knowledge |
| `openai/codex-plugin-cc` | Optional adversarial EEAT review helper; runtime-conditional (Claude Code only) | Apache-2.0; NOTICE file at content-stack root credits OpenAI; daemon-side helper invocation, not Bash-from-skill |
| `perplexityai/modelcontextprotocol` | **Explicitly not used** | Research via Firecrawl + DataForSEO + runtime's built-in WebSearch |

---

## Daemon strategy

**Manual** (always works):
```bash
python -m content_stack serve --port 5180
# or
make serve
```

**Auto-start on macOS** (optional):
```bash
make install-launchd
launchctl load ~/Library/LaunchAgents/com.content-stack.daemon.plist
```

The daemon writes logs to `~/.local/state/content-stack/daemon.log` and PID
to `~/.local/state/content-stack/daemon.pid`.

### CLI reference

```
python -m content_stack <subcommand> [flags]
```

| Subcommand | Args / flags | Side effects | Exit codes |
|---|---|---|---|
| `serve` | `--port=5180` (default), `--host=127.0.0.1` (rejected if not loopback) | Starts uvicorn; writes PID; logs to `daemon.log`; loads APScheduler. | 0 ok, 1 misuse (e.g., `--host 0.0.0.0`), 2 dependency missing, 3 DB locked. |
| `init` | `--force` (overwrite config) | Creates XDG dirs (`~/.local/share/content-stack/`, `~/.local/state/content-stack/`); generates `seed.bin` if absent (32 bytes, mode 0600); generates `auth.token` if absent (32 bytes, mode 0600); runs `alembic upgrade head`; writes default config at `~/.config/content-stack/config.toml`. Idempotent except `--force`. | 0 ok, 1 misuse, 2 deps missing, 4 migration failed. |
| `migrate` | `up`, `down <rev>`, `current`, `history` | Runs alembic. | 0 ok, 1 misuse, 4 migration failed. |
| `install` | (none) | Wraps `make install`. | 0 ok, 1 misuse, 2 deps missing, 3 DB locked, 4 migration failed. |
| `doctor` | `--json` | Reads-only checks (see "doctor.sh check list" below); never mutates. | 0 all green, 1 daemon down, 2 MCP not registered, 3 skills not installed, 4 missing API keys, 5 DB schema out of date, 6 launchd plist not loaded, 7 auth token missing or wrong mode, 8 seed file missing or wrong mode. |
| `rotate-seed` | `--reencrypt` (required for safety) | Generates new `seed.bin`; decrypts every `integration_credentials` row with old seed, re-encrypts with new; writes new seed; keeps `seed.bin.bak` for one boot then auto-deletes. | 0 ok, 1 misuse, 9 reencryption failed (rolls back). |
| `rotate-token` | (none) | Generates new `auth.token`; updates Codex + Claude MCP configs. | 0 ok, 1 misuse. |
| `export-credentials` | `--out PATH` | Emits passphrase-encrypted (user-supplied) backup of `integration_credentials` for machine migration. | 0 ok, 1 misuse, 9 cipher failure. |
| `reset-integrations` | `--yes` | Clears `integration_credentials`, regenerates `seed.bin`. User must re-add. | 0 ok, 1 misuse. |

### Logging

Logs use Python's `logging` with `structlog` for JSON output. Format:
`{ts, level, logger, run_id?, project_id?, msg, kv}`. Rotation via
`RotatingFileHandler` at 10 MB × 5 to
`~/.local/state/content-stack/daemon.log`. `runs.id` is set in a
`contextvars.ContextVar` at procedure-run start so all downstream calls
inherit it without explicit threading.

### Backup

`make backup` runs:

```bash
sqlite3 ~/.local/share/content-stack/content-stack.db \
  ".backup ~/.local/share/content-stack/backups/$(date +%Y-%m-%d-%H%M).db"
cp ~/.local/state/content-stack/seed.bin   <backup-dir>/seed.bin
cp ~/.local/state/content-stack/auth.token <backup-dir>/auth.token
```

WAL-safe via the `.backup` command. `make restore <file>` halts the daemon,
copies the file over the current DB, restarts the daemon. APScheduler job
`jobs/auto_backup.py` runs weekly at 03:00 local time, retains 12 weeks.
`scripts/doctor.sh` warns if `~/.local/share/content-stack/` is not under
Time Machine on macOS.

### Cross-machine restore

If `seed.bin` is missing on restore (e.g., DB copied without the seed),
the daemon refuses to start and `doctor.sh` emits:
`seed.bin missing — run 'content-stack reset-integrations' to clear and
re-enter API keys`. The DB itself remains intact; only the
`integration_credentials` rows are unrecoverable. This is by design — no
silent decryption-to-garbage path.

### Graceful shutdown

`launchctl stop` / `SIGTERM` triggers uvicorn graceful shutdown (30 s drain,
then SIGKILL). In-flight procedure-run steps catch `SIGTERM`, mark the step
`status='aborted'`, write `runs.error='shutdown'`. Resume policy from
"Crash recovery" applies on restart.

### Health endpoint

`GET /api/v1/health` returns:

```json
{
  "daemon_uptime_s": 12345,
  "version": "0.1.0",
  "db_status": "ok",
  "scheduler_running": true,
  "auth_token_mode_ok": true,
  "seed_file_ok": true,
  "integrations_reachable": {
    "dataforseo": true,
    "firecrawl": true,
    "gsc": true,
    "reddit": true,
    "openai-images": true
  }
}
```

`doctor.sh` hits this first; if 200, falls through to filesystem and runtime
config checks.

### APScheduler config

```python
executors = {
  "default": AsyncIOExecutor(),
  "long":    ThreadPoolExecutor(max_workers=2),
}
job_defaults = {
  "coalesce":           True,
  "max_instances":      1,
  "misfire_grace_time": 3600,
}
jobstores = {
  "default": SQLAlchemyJobStore(url=db_url, tablename="apscheduler_jobs"),
}
```

Procedure runs go through APScheduler with `job_id=procedure-{slug}-{project_id}`
to enforce per-project serialization. Catch-up: if the daemon was offline for
a week and missed a Monday GSC review, on next start it runs once (not seven)
thanks to `coalesce=True`. Per-project cron lives in `scheduled_jobs.cron_expr`.

### Crash recovery

On daemon start, the recovery sweep runs:

```sql
UPDATE runs
SET status = 'aborted', error = 'daemon-restart-orphan', ended_at = now()
WHERE status = 'running'
  AND heartbeat_at < datetime('now', '-5 minutes');
```

For each aborted parent run, the recovery sweep also marks all child runs
(`parent_run_id`) as `aborted`. Then for each `runs` row with the procedure
declaring `resumable: true` in PROCEDURE.md frontmatter:

1. The sweep inspects `procedure_run_steps` for the run's last
   `success` row.
2. The next step (`status='pending'` or `'running'`) is the resume point.
3. The sweep does NOT auto-resume; it surfaces a "Resumable" badge in the
   UI's RunsView. The user clicks "Resume" to call
   `procedure.resume(run_id)`.

Resume policy: re-run failed step from scratch (idempotent skills) by
default; per-skill opt-out flag in skill frontmatter. `procedure.fork(run_id,
from_step)` creates a new child run for "redo from step N onward".

Heartbeat: APScheduler updates `runs.heartbeat_at` every 30 s. Skill steps
also call `run.heartbeat(run_id)` on every transition.

### Per-tool rate limits

(Reproduced from API surface for ops convenience.) Middleware enforces
100 calls/min per tool, 1000 calls/min aggregate per Authorization token.
Breach returns 429 with `retry_after` and code -32011.

---

## MCP registration

**Codex CLI:**

```bash
codex mcp add content-stack \
  --transport http \
  --url http://localhost:5180/mcp \
  --bearer-token-env-var CONTENT_STACK_TOKEN
```

The modern Codex CLI contract reads bearer tokens from a named env var
rather than a literal header string (per the M9 finding); export it
from the operator's shell rc with
``export CONTENT_STACK_TOKEN="$(cat ~/.local/state/content-stack/auth.token)"``
so each Codex session resolves the current per-install token without
re-running ``mcp add`` on rotation.

**Claude Code (`.mcp.json`):**

```json
{
  "mcpServers": {
    "content-stack": {
      "transport": "http",
      "url": "http://localhost:5180/mcp",
      "headers": {
        "Authorization": "Bearer <token-from-~/.local/state/content-stack/auth.token>"
      }
    }
  }
}
```

Both wired by `scripts/register-mcp-{codex,claude}.sh`. The scripts read the
auth token at registration time; on `make install` re-run the token rotates
and the configs are rewritten.

### Install script semantics

| Script | Behaviour | Idempotency |
|---|---|---|
| `install-codex.sh` | `rsync -a --delete skills/ ~/.codex/skills/content-stack/`. User-customised files preserved with `.bak` suffix on conflict. | yes |
| `install-claude.sh` | Same against `~/.claude/skills/content-stack/`. | yes |
| `install-procedures-codex.sh` | `rsync -a --delete --exclude='_template' procedures/ ~/.codex/procedures/content-stack/`. | yes |
| `install-procedures-claude.sh` | Same against `~/.claude/procedures/content-stack/`. | yes |
| `register-mcp-codex.sh` | `codex mcp list \| grep -q content-stack && codex mcp remove content-stack; codex mcp add content-stack ... --header Authorization`. Effectively upsert. | yes |
| `register-mcp-claude.sh` | Reads target `.mcp.json` (or per-project), parses JSON, upserts the `content-stack` key, writes back atomically with `.bak` backup. Never `>` overwrites. | yes |
| `install-launchd.sh` | Writes plist if absent. If present, diffs: identical → no-op; different → prompts user; `--force` overwrites with `.bak`. | yes |
| `doctor.sh` | Reads-only diagnose; see check list below. | yes (read-only) |
| `seed.py` | `INSERT OR IGNORE` on stable identifiers. Runs at every daemon start; safe to invoke repeatedly. | yes |

`make install` is the canonical onboarding command. README quickstart MUST
be regenerated from the Makefile target list to stay in sync.

### Upgrade strategy

- **Daemon upgrades** via `uv pip install -U content-stack` (or
  `pipx upgrade content-stack`). Re-running `make install` is idempotent
  and rotates the auth token.
- **Skills / procedures** ship with the wheel. `install-{codex,claude}.sh`
  uses `rsync --delete` so retired skills disappear. User-customised skills
  should live under a separate `<runtime>/skills/<user-name>/` directory;
  this constraint is documented in `docs/extending.md`.
- **Schema** migrates via `alembic upgrade head` on daemon start.
  Down-migrations supported but discouraged. Breaking changes bump the
  major version; release notes call out manual migrations.
- **Auth token** rotates on every `make install` re-run; MCP configs are
  regenerated to match.

### `doctor.sh` check list and exit codes

`doctor.sh` performs the following checks in order. Output is human-readable
by default; `--json` emits `{checks: [{name, status (pass|warn|fail),
details}], overall_exit: int}`.

1. Daemon up? (`curl -fsS http://localhost:5180/api/v1/health`). Fail → exit 1.
2. Auth token file present and mode 0600? Fail → exit 7.
3. Seed file present and mode 0600? Fail → exit 8.
4. MCP registered exactly once in Codex (`codex mcp list`). Fail → exit 2.
5. MCP registered exactly once in Claude Code (`.mcp.json`). Fail → exit 2.
6. Skills count = 24 in `~/.codex/skills/content-stack/`. Fail → exit 3.
7. Skills count = 24 in `~/.claude/skills/content-stack/`. Fail → exit 3.
8. Procedures count = 8 (excluding `_template`) in both runtimes. Fail → exit 3.
9. Required API keys present per active project (`integration_credentials`
   resolved via project + global). Warn (not fail) on missing optional keys.
   Fail → exit 4.
10. Alembic at head (`alembic current` matches latest revision). Fail → exit 5.
11. All `integration_credentials` rows decrypt cleanly via daemon API
    (`integration.test`). Fail → exit 4.
12. `eeat_criteria` rows with `tier='core'` count = 3 per project. Fail → exit 5.
13. Launchd plist loaded (`launchctl list | grep com.content-stack.daemon`).
    Warn → exit 0 (plist optional). Fail (loaded but not running) → exit 6.
14. Localhost binding verified (`lsof -iTCP:5180 -sTCP:LISTEN` shows 127.0.0.1
    only). Fail → exit 1.
15. Streamable HTTP MCP client compatibility: Codex CLI ≥ X, Claude Code ≥ Y
    (versions pinned in `tests/fixtures/runtime-versions.json`). Warn → exit 0
    if older but compatible; fail → exit 0 if known-broken (loud message).
16. Time Machine status (macOS only). Warn if `~/.local/share/content-stack/`
    is not in the inclusion list.

---

## Distribution model

- **The daemon** is installable via `uv pip install -e .` or
  `pipx install content-stack` (post-publish).
- **`pipx` mode**: skills + procedures are bundled in the wheel under
  `content_stack/_assets/skills/` and `content_stack/_assets/procedures/`.
  The console script wraps `install-codex` / `install-claude` /
  `install-procedures-{codex,claude}` as Python subcommands that copy from
  the wheel. `make install` (clone-mode) and `content-stack install`
  (pipx-mode) call the same code paths.
- **Skills + procedures** are copied into the runtime's expected paths by
  `scripts/install-{codex,claude}.sh` (clone-mode) or the equivalent
  console-script subcommands (pipx-mode). Each runs in ~2 seconds.
- **The UI** is built at `make build-ui` and **committed** to
  `content_stack/ui_dist/` (D8). `ui_dist/` is NOT in `.gitignore`. CI
  verifies the committed bundle matches `ui/src/` source by rebuilding and
  diffing; mismatch fails the build. This lowers the install floor — no
  `pnpm` required at user install time.
- **Database** auto-migrates on daemon start (`alembic upgrade head`).
- **Auth token + seed** generated on first `serve` if absent; both at
  `~/.local/state/content-stack/`, mode 0600.

---

## Implementation sequencing

Not "MVP cuts" — full scope, sequenced by dependency:

1. **Foundation** — repo init, pyproject, FastAPI app factory, alembic, Makefile, CI, doctor script, auth-token generation, seed-file generation. (1d)
2. **DB + repositories** — all 28 tables, SQLModel models, migrations, indexes, seed. Repository layer tested against in-memory SQLite. JSON column shape contracts. M2 acceptance benchmark: 100 sequential `article.setDraft` of 200 KB markdown each completes < 2 s on a 2020 MBP. (3d)
3. **REST API** — all routers, OpenAPI generation, UI type generation, pagination/filter conventions, REST/MCP parity table. (3d)
4. **MCP server** — all tools, transport mounted at `/mcp`, end-to-end test from a Codex session, idempotency keys, streaming, error model, result envelope, tool-grant matrix. (3d)
5. **Integrations** — DataForSEO, Firecrawl, GSC (with OAuth flow + refresh job), OpenAI Images, OpenAI/Anthropic procedure-runner, Reddit, PAA, Jina wrappers. Each unit-tested with VCR-style cassettes. Token-bucket rate limits + budget caps. (3d)
6. **UI** — all views per spec, ProjectSwitcher in sidebar, MarkdownView, MarkdownEditor (textarea + If-Match optimistic concurrency), DataTable. ArticleDetailView subviews (EEAT report, Activity, Interlinks). InterlinksView bulk apply/dismiss. (4d)
7. **Skills (all 24)** — authored against schema; clean-room per D1; CI fingerprint check; each tested with a stub project. (5d)
8. **Procedures (all 8)** — `PROCEDURE.md` for each, daemon-orchestrated runner, tested by running against a seed project. (3d)
9. **Jobs + scheduling** — APScheduler in-process for weekly GSC review, monthly humanize, OAuth refresh, auto-backup; resumable runs; crash-recovery sweep. (2d)
10. **Distribution** — install scripts (idempotent), MCP registration helpers (auth token injection), launchd plist, doctor.sh, attribution doc, NOTICE file, pipx wheel layout. (1d)
11. **Documentation** — README, architecture, extending guide, procedures guide, api-keys guide (incl. GSC OAuth screenshots), attribution, PRIVACY.md. (1d)

**Total: ~29 working days for everything.** Sequencing is dependency-driven;
some tracks parallelize across agents. Original audit baseline was 25d; the
post-audit patch added +4d: M2 +1d (more tables, indexes, JSON contracts,
benchmark), M3 +1d (envelope + idempotency + streaming + error model), M4
+1d (tool-grant matrix, result envelope, end-to-end transport tests), M9 +1d
(resume, executor config, OAuth refresh). 25 + 4 = 29.

---

## Decisions locked (post-audit)

The eight architectural decisions surfaced by the audit are locked as below.
The remaining items are either covered by these locks or by elsewhere in this
document.

| # | Decision | Locked at |
|---|---|---|
| D1 | **Cody license** — clean-room re-author from PLAN.md only; skill authors for #4, #6, #7, #8, #9, #10, #24 do NOT read `cody-article-writer/` files; CI fingerprint check rejects substrings from cody verbatim text | Sourcing strategy + Risks |
| D2 | **codex-seo `--with-codex-seo` flag** — DROP entirely. Users who want codex-seo install it themselves; documented in `docs/extending.md` | Sourcing strategy |
| D3 | **Multi-locale** — SINGULAR. `projects.locale TEXT NOT NULL`. Translation = separate project per locale | Schema § Core projects |
| D4 | **Procedure orchestration** — DAEMON-ORCHESTRATED. Daemon holds its own LLM credentials (one of OpenAI/Anthropic, separate from the runtime's). LLM client only kicks off and polls | Procedures § Procedure orchestration model |
| D5 | **Daemon auth** — per-install bearer token at `~/.local/state/content-stack/auth.token` (32 bytes, 0600). Every REST + MCP request requires `Authorization: Bearer <token>`. Host header check + same-origin CORS. Install scripts inject. Rotates on `make install` re-run | Architecture + Security |
| D6 | **Articles versioning** — separate `article_versions` table. `articles` keeps current. `article.createVersion` MCP copies live → versions before mutating | Schema § Core projects |
| D7 | **EEAT floor** — `eeat_criteria.tier ENUM('core','recommended','project')`. T04/C01/R10 seeded as `tier='core'`; cannot be deactivated; gate refuses to score if any dimension has 0 active items | Schema § Core projects + Procedures § EEAT gate |
| D8 | **UI dist** — COMMIT `ui_dist/` bundle. Drop from `.gitignore`. CI verifies committed bundle matches `ui/src/` | Distribution model |

Other previously-open items, all now locked:

- **Python deps manager** — `uv`.
- **Process supervision** — launchd plist on macOS (optional); manual `serve` always works.
- **UI bundling** — built and committed (D8).
- **MCP transport** — Streamable HTTP only.
- **Encryption-at-rest** — AES-256-GCM with HKDF-derived key from per-machine seed (Security § Encryption-at-rest).
- **DB location** — `~/.local/share/content-stack/content-stack.db` (XDG).
- **Repo visibility** — operator's call; not a technical decision.
- **codex-plugin-cc adoption** — wired runtime-conditionally; per-project opt-in default off (Security § Codex-plugin-cc seam).

---

## Out of scope (deliberate cuts)

- **Multi-user authentication.** Localhost-only daemon; per-install bearer
  token at `~/.local/state/content-stack/auth.token` enforces single-user
  binding (every REST + MCP request must carry it). A read-only second
  token is available for observer scenarios (see Security § Auth token).
  Per-user roles, OIDC, SSO are not provided.
- **Cloud sync / multi-device DB.** `make backup` is WAL-safe and copies
  the seed + auth token alongside; `make restore` halts the daemon and
  swaps. Cross-machine migration requires both DB and `seed.bin`.
- **Real-time WebSocket UI updates.** Refresh-on-demand suffices; SSE on
  `/api/v1/procedures/runs/{run_id}/status?stream=true` covers progress.
- **Asset hosting.** Images go to your CDN; we store URL + alt + dims +
  width/height + position in `article_assets`.
- **Becoming a CMS.** We coordinate; the CMS (Nuxt Content / WP / Ghost) is
  a publish target via `publish_targets` + `article_publishes`.
- **Multi-locale per project (D3).** `projects.locale` is **singular**.
  Translation = separate project per locale. No cross-project article-link
  awareness, no `hreflang` orchestration. Out of scope.
- **Ads / affiliate-link insertion.** Out of scope; if you want it, write a
  custom skill that mutates `articles.edited_md` post-editor.
- **Perplexity research agent.** Cost; replaced by Firecrawl + DataForSEO +
  runtime's built-in WebSearch.
- **Telemetry / phone-home.** The daemon does not transmit anything outside
  `127.0.0.1` except the explicit integration calls the user configures.
  Documented in `PRIVACY.md`; default (and only) mode is off.
- **Rubber-stamp EEAT mode.** Not provided. Every project must run with all
  8 dimensions and the 3 `tier='core'` veto items (T04/C01/R10) active. The
  schema invariant blocks deactivation.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| MCP Streamable HTTP not yet supported by all client versions | stdio fallback documented; can be added in <1d if needed; doctor.sh check 15 verifies runtime version pin |
| SQLite WAL contention + same-article concurrent writes | Per-step etag (`articles.step_etag`); every `article.set*` requires `expected_etag`; mismatch → 409 conflict (-32008). `MAX_CONCURRENCY` env caps procedure runs (default 4). M2 acceptance benchmark: 100 sequential 200 KB `setDraft` calls < 2 s. `articles.lock_token` for procedure-duration advisory locks. UI `If-Match` header for optimistic concurrency on manual edits |
| Vue UI drifts from API shape | Auto-generate TS types via `openapi-typescript` from FastAPI OpenAPI; CI fails on diff |
| Skills out of sync between Codex and Claude installs | Single `skills/` directory + `rsync --delete` install scripts; doctor.sh checks 6+7 verify count = 24 in both runtimes |
| LLM corrupts DB via bad input | All MCP tools pydantic-validated; status enums enforced; tool-grant matrix per skill (-32007 forbidden); state-machine triggers; full audit via `run_steps` + `run_step_calls`; idempotency keys for replay safety |
| Upstream license incompatibility (Cody, codex-seo) | Clean-room re-author per D1/D2; CI fingerprint check rejects substrings from upstream verbatim; no `--with-codex-seo` install induction; `docs/attribution.md` documents posture |
| EEAT gate rubber-stamp by project owner | `eeat_criteria.tier` ENUM(`core`,`recommended`,`project`); rows with `tier='core'` cannot be deactivated (repository invariant + 422); EEAT gate refuses to score if any of 8 dimensions has 0 active items; coverage floor enforced |
| Cost runaway on integrations | Pre-emptive `integration_budgets` table per project + kind; per-integration token-bucket rate limit; bulk-launch `--budget-cap-usd` flag refuses to start above cap; `run.abort(run_id, cascade=true)` for runaways; `GET /api/v1/projects/{id}/cost?month=` + `cost.queryProject` MCP for live monthly view |
| Daemon crash mid-procedure leaves orphan `runs` | `runs.heartbeat_at` updated every 30 s; startup sweep marks `running AND heartbeat_at < now-5min` as `aborted` with `error='daemon-restart-orphan'`; cascade to children; `procedure_run_steps` cursor enables `procedure.resume(run_id)` for procedures with `resumable: true` |
| Browser CSRF / cross-process drive-bys on localhost | Bearer token required on every request (mode 0600); CORS same-origin; Host header check rejects non-loopback; doctor.sh verifies token mode |
| Multi-target publish drift between `articles.published_url` and `publish_targets` | New `article_publishes` table per `(article_id, target_id, version_published)`; `articles.canonical_target_id` tells interlinker which URL is authoritative; procedure 4 publishes to primary target first, secondaries via `publish_target.replicate` |
| GSC OAuth token expiry mid-procedure | `jobs/oauth_refresh.py` runs every 50 min, refreshes any token expiring within 10 min; failure surfaces via `/api/v1/health.integrations_reachable.gsc=false`; UI prompts re-auth |
| Procedure runner context-window blow-up | Daemon-orchestrated procedures (D4); per-skill subprocess sessions; tight prompts; LLM client only kicks off via `procedure.run` and polls |

---

## What "done" looks like for v1

- `make install` brings up the daemon, generates the auth token + seed file,
  registers MCP for both runtimes (with bearer auth header), copies skills +
  procedures, and runs doctor with all green (exit 0).
- `http://localhost:5180` shows the UI; I can register a project end-to-end
  (procedure 1) including voice, compliance, EEAT seed (3 `tier='core'`
  rows present), publish target (one `is_primary=true`), and integration
  creds (encrypted).
- Codex CLI (and Claude Code) auto-discover all 24 skills + 8 procedures.
- I can run `/procedure topic-to-published <topic-id>` and the article goes
  brief → outline → draft → editor → EEAT (three-verdict; FIX loops back) →
  image → schema → interlink → published, all logged to `runs` + `run_steps`
  + `run_step_calls`.
- The UI's ArticleDetailView shows the EEAT report (per-dimension scores,
  failed items with one-line standards highlighted), Activity timeline,
  and Interlinks subviews.
- I can register a second project via the same procedures with no code change.
- I can interrupt a bulk launch with `run.abort(parent_run_id, cascade=true)`
  and the UI immediately reflects all child runs as aborted.
- I can let the laptop sleep mid-procedure, restart the daemon, and the
  RunsView shows "Resumable" for procedures with `resumable: true`.
- `scripts/doctor.sh --json` reports overall_exit=0 on a fresh machine
  after `make install`.
