# content-stack — agent guide

You are working on **content-stack**: a globally-installed Python daemon (FastAPI + SQLite/WAL + MCP Streamable HTTP) plus Vue 3 UI that gives any LLM client a stateful CRUD seam over multi-project SEO content pipelines. Single process, three transports (`/mcp`, `/api/v1`, `/`), bound to `127.0.0.1`, per-install bearer-token auth.

This file overlays your global `~/.claude/CLAUDE.md` for this project. Project-specific rules below take precedence.

## Canonical references — read these before any non-trivial work

- **`PLAN.md`** — the spec. 1600+ lines covering vision, architecture, schema (28 tables), REST + ~80 MCP tools, 24 skills, 8 procedures, security, ops, distribution. Always reread the relevant section before changing related code.

## Locked decisions (do NOT relitigate)

The full canonical list lives in PLAN.md's "Decisions locked" section. Quick reference:

- **Stack**: Python 3.12+ / FastAPI / uvicorn / SQLModel / SQLite (WAL) / Alembic / mcp Python SDK (Streamable HTTP) / Vue 3 + Vite + TS + Tailwind / uv / launchd
- **D3 Multi-locale**: singular `projects.locale TEXT NOT NULL`. Multi-locale = separate project per locale. Translation pipeline out of scope.
- **D4 Procedures**: daemon-orchestrated. `procedure.run` enqueues a server-side runner that dispatches fresh per-skill LLM sessions. Daemon holds its own LLM credentials. The user's LLM only kicks off and polls.
- **D5 Auth**: per-install bearer token at `~/.local/state/content-stack/auth.token` (32 bytes, 0600). Every REST + MCP request requires `Authorization: Bearer <token>`. CORS same-origin. Host header check rejects non-localhost. Install scripts inject into MCP configs. Rotates on `make install`.
- **D6 Articles versioning**: separate `article_versions` table. `articles` keeps current row only.
- **D7 EEAT floor**: `eeat_criteria.tier ENUM('core','recommended','project')`. T04/C01/R10 seeded as `tier='core'`; cannot be deactivated; cannot have `required` toggled off. Procedure 4 EEAT gate refuses to score if any dimension has 0 active items.

## Working style (project-specific overrides)

- **No `AskUserQuestion` tool in this project.** Ask plain text in chat. Always.
- **UI verification protocol is mandatory before any UI is "done":** Playwright screenshots at 360 / 640 / 768 / 1024 / 1280 / 1440 + axe a11y scan + zero console errors. Type checks and tests verify code correctness, not feature correctness — if you can't run the visual checks, say so explicitly.
- **Quality > MVP shortcuts.** PLAN.md is "full scope from day 1, no MVP cuts." Resist suggesting trims to ship faster.
- **Delegate non-trivial implementation.** Main coordinates and never improvises silently. If you intend to deviate from PLAN.md or add scope, surface it in chat first.
- **Self-review at every checkpoint** (type purity, no hacks, no over-engineering). Commit incrementally per logical step rather than batching.

## Repo layout (target — built incrementally per PLAN.md sequencing)

```
content-stack/
├── PLAN.md                          # canonical spec
├── README.md                        # end-user quickstart
├── CLAUDE.md                        # this file
├── pyproject.toml                   # uv-managed
├── uv.lock                          # pinned deps (committed)
├── Makefile                         # install / serve / build-ui / test / lint / migrate / doctor / etc.
├── alembic.ini
│
├── content_stack/                   # Python package
│   ├── cli.py                       # serve | init | migrate | install | doctor | rotate-seed | rotate-token | backup | restore
│   ├── server.py                    # FastAPI app factory
│   ├── config.py                    # XDG paths, port, env
│   ├── db/                          # connection + 28 SQLModel tables + Alembic migrations + seed
│   ├── repositories/                # business logic, transport-agnostic
│   ├── api/                         # FastAPI routers (REST for UI)
│   ├── mcp/                         # MCP tool definitions (~80 tools)
│   ├── integrations/                # DataForSEO, Firecrawl, GSC, OpenAI Images, Reddit, PAA, Jina, Ahrefs
│   ├── jobs/                        # APScheduler jobs (gsc_pull, drift_check, refresh_detector, oauth_refresh, ...)
│   ├── procedures/                  # daemon-orchestrated procedure runner
│   └── ui_dist/                     # committed Vue build (per D8)
│
├── ui/                              # Vue 3 + Vite + TS + Tailwind source
├── skills/                          # 24 SKILL.md
├── procedures/                      # 8 PROCEDURE.md playbooks + _template/
├── scripts/                         # install + register + doctor + launchd helpers
├── docs/
│   ├── architecture.md
│   ├── extending.md                 # adding skills / procedures / integrations + tool-grant matrix
│   ├── api-keys.md                  # per-integration setup incl. GSC OAuth flow
│   ├── procedures-guide.md          # PROCEDURE.md frontmatter + DSL
│   └── upgrade.md                   # version-to-version upgrade semantics
├── tests/                           # unit + integration + fixtures
└── .github/workflows/ci.yml         # ruff + pytest + mypy + UI build + parity table
```

## Common commands (target)

```
uv sync                                  # install Python deps
make build-ui                            # rebuild content_stack/ui_dist/ from ui/
make serve                               # daemon on 127.0.0.1:5180
make dev-ui                              # Vite dev server alongside daemon
make test                                # pytest
make lint                                # ruff
make migrate                             # alembic upgrade head
make doctor                              # diagnose install + return exit codes per PLAN.md
curl -H "Authorization: Bearer $(cat ~/.local/state/content-stack/auth.token)" \
  http://localhost:5180/api/v1/health
```

## When picking up a session

1. Read this file.
2. Read the relevant PLAN.md section for the task at hand. Don't trust memory of the spec — reread.
3. Check `git log --oneline` and `git status` for branch state.
4. If touching M0–M3 (foundation/DB/REST/MCP), the spec answers nearly every question — there should be no unspecified work.
