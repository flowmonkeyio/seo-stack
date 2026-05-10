# Changelog

All notable changes to content-stack are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-05-07

Feature-complete v1. The 11 milestones (M0 through M10) consolidate
into a single release that satisfies every "What 'done' looks like
for v1" criterion in `PLAN.md`.

### Added

- **M0 Foundation** — repo scaffold, Python package, FastAPI app
  factory, alembic, Makefile, doctor stub, auth-token + seed
  generation, Vue UI scaffold.
- **M1 Database** — 28 SQLModel tables, migrations, indexes,
  repository layer with optimistic concurrency on the articles fat
  row (per audit B-07), tested against in-memory SQLite.
- **M2 REST API** — 16 routers, 77 OpenAPI paths, error envelope,
  pagination + filtering conventions, REST/MCP parity table, Swagger
  UI at `/api/docs`, auto-generated TS types committed at
  `ui/src/api.ts`.
- **M3 MCP server** — tools registered over Streamable HTTP at
  `/mcp`, tool-grant matrix as the load-bearing security seam,
  idempotency keys (24 h dedup), streaming for 4 long-running tools,
  JSON-RPC error model, mutating-verb envelope discipline.
- **M4 Integrations** — 8 vendor wrappers (DataForSEO, Firecrawl,
  GSC + OAuth, OpenAI Images, Reddit, Google PAA, Jina Reader,
  Ahrefs).
  AES-256-GCM at-rest credentials with per-machine seed + HKDF +
  per-row nonce + project-bound AAD. Token-bucket rate limits + budget
  pre-emption (audit M-25).
- **M5 UI** — 11 views + 12 article-detail tabs + ProjectSwitcher +
  MarkdownEditor with optimistic concurrency. Playwright + axe
  verified at 6 breakpoints (360 / 640 / 768 / 1024 / 1280 / 1440)
  with zero console errors.
- **M6 Skills** — 24 SKILL.md files authored across 5
  phases. Tool-grant matrix populated.
- **M7 Procedures** — daemon-orchestrated runner per locked decision
  D4. 8 PROCEDURE.md playbooks (bootstrap-project,
  one-site-shortcut, keyword-to-topic-queue, topic-to-published,
  bulk-content-launch, weekly-gsc-review, monthly-humanize-pass,
  add-new-site) + `_template/` scaffold. Programmatic step registry
  for non-LLM work (project-create, gsc-pull, child-run spawn).
  AnthropicSession + StubDispatcher + 5 failure modes.
- **M8 Jobs + scheduling** — APScheduler with `SQLAlchemyJobStore`,
  4 background jobs (runs_reaper every 5 min, oauth_refresh every
  50 min, gsc_pull daily 03:15 UTC, drift_rollup daily 04:00 UTC),
  cron-triggered procedures 6 + 7 registered per active project,
  resumable runs, crash-recovery sweep.
- **M9 Distribution** — `make install` orchestrator (idempotent),
  per-runtime install scripts, MCP registration helpers (auth token
  injection), launchd plist, doctor.sh with 16 check items, pipx
  wheel layout (skills + procedures bundled under
  `content_stack/_assets/`).
- **M10 Documentation** —
  [`docs/architecture.md`](./docs/architecture.md),
  [`docs/extending.md`](./docs/extending.md),
  [`docs/procedures-guide.md`](./docs/procedures-guide.md);
  README polish; PLAN.md amendments (eeat_criteria 8-letter
  category, schema_emits 6-template seed, modern Codex CLI
  registration with `--bearer-token-env-var`).

### Decisions locked

- **D3 Multi-locale** — singular `projects.locale TEXT NOT NULL`.
  Multi-locale = separate project per locale.
- **D4 Daemon-orchestrated procedures** — `procedure.run` enqueues
  a server-side runner that dispatches fresh per-skill LLM
  sessions. Daemon holds its own LLM credentials.
- **D5 Per-install bearer token** — 32 random bytes at
  `~/.local/state/content-stack/auth.token` (mode 0600). Every
  REST + MCP request requires `Authorization: Bearer <token>`.
  Rotates on `make install` re-run.
- **D6 article_versions** — separate table; `articles` keeps the
  current row only.
- **D7 EEAT core floor** — `eeat_criteria.tier ENUM('core','recommended','project')`.
  T04 / C01 / R10 seed as `tier='core'`; cannot be deactivated.
- **D8 Committed ui_dist** — `content_stack/ui_dist/` is checked in
  per the build artifact; release checks verify the committed bundle
  matches `ui/src/`. No `pnpm` required at user install.

### Roadmap

The "Out of scope (deliberate cuts)" section in PLAN.md documents
features that v1 will NOT pursue: multi-user authentication, cloud
sync / multi-device DB, real-time WebSocket UI updates, becoming a
CMS, multi-locale per project, ads / affiliate-link insertion,
Perplexity research, telemetry / phone-home, rubber-stamp EEAT mode.

Future minor versions may relax some of these (notably read-only
observer tokens and a hardening flag to disable the UI bootstrap),
but the core posture stands.
