# content-stack — agent guide

You are working on **content-stack**: a globally-installed Python daemon (FastAPI + SQLite/WAL + MCP Streamable HTTP) plus Vue 3 UI that gives any LLM client a stateful CRUD seam over multi-project SEO content pipelines. Single process, three transports (`/mcp`, `/api/v1`, `/`), bound to `127.0.0.1`, per-install bearer-token auth.

This file overlays your global `~/.claude/CLAUDE.md` for this project. Project-specific rules below take precedence.

## Canonical references — read these before any non-trivial work

- **`PLAN.md`** — the spec. 1650+ lines covering vision, architecture, schema (28 tables), REST + ~80 MCP tools, 24 skills, 8 procedures, 9 integrations, security, ops, distribution. Always reread the relevant section before changing related code.
- **`docs/upstream-stripping-map.md`** — maps our 24 skills to patterns in 3 cloned upstream reference repos (read-only at `.upstream/`, gitignored). Drives M7 skill authoring.
- **`docs/plan-audit.md`** — the pre-M0 audit. Closed but useful for understanding *why* the current spec is shaped the way it is.

## Locked decisions (do NOT relitigate)

The eight original locks plus the eight D-locks from the audit. The full canonical list lives in PLAN.md's "Decisions locked" section. Quick reference:

- **Stack**: Python 3.12+ / FastAPI / uvicorn / SQLModel / SQLite (WAL) / Alembic / mcp Python SDK (Streamable HTTP) / Vue 3 + Vite + TS + Tailwind / uv / launchd
- **D1 Cody license**: clean-room re-author from PLAN.md only. Skill authors for #4, #6, #7, #8, #9, #10, #24 do **NOT** read `cody-article-writer/` files. CI fingerprint check rejects substrings from cody verbatim text.
- **D2 codex-seo**: same clean-room rule for #1, #2, #3, #14, #16, #20, #21, #22. **No `--with-codex-seo` install flag.**
- **D3 Multi-locale**: singular `projects.locale TEXT NOT NULL`. Multi-locale = separate project per locale. Translation pipeline out of scope.
- **D4 Procedures**: daemon-orchestrated. `procedure.run` enqueues a server-side runner that dispatches fresh per-skill LLM sessions. Daemon holds its own LLM credentials. The user's LLM only kicks off and polls.
- **D5 Auth**: per-install bearer token at `~/.local/state/content-stack/auth.token` (32 bytes, 0600). Every REST + MCP request requires `Authorization: Bearer <token>`. CORS same-origin. Host header check rejects non-localhost. Install scripts inject into MCP configs. Rotates on `make install`.
- **D6 Articles versioning**: separate `article_versions` table. `articles` keeps current row only.
- **D7 EEAT floor**: `eeat_criteria.tier ENUM('core','recommended','project')`. T04/C01/R10 seeded as `tier='core'`; cannot be deactivated; cannot have `required` toggled off. Procedure 4 EEAT gate refuses to score if any dimension has 0 active items.
- **D8 UI dist**: `content_stack/ui_dist/` is **committed** (drop from `.gitignore`). CI verifies committed bundle matches `ui/src/`. No `pnpm` at user install.

## Working style (project-specific overrides)

- **No `AskUserQuestion` tool in this project.** Ask plain text in chat. Always.
- **UI verification protocol is mandatory before any UI is "done":** Playwright screenshots at 360 / 640 / 768 / 1024 / 1280 / 1440 + axe a11y scan + zero console errors. Type checks and tests verify code correctness, not feature correctness — if you can't run the visual checks, say so explicitly.
- **Codex is a product feature, not a dev agent.** `codex-plugin-cc` is wired *inside* content-stack as the optional adversarial-EEAT-review feature for end users. Do **not** spawn `codex:codex-rescue` / `codex:rescue` / any codex-family subagent for our own dev/review work in this session — use Claude agents only (Plan / general-purpose / Explore). Heterogeneity comes from prompt framing, not from calling a different model.
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
│   ├── integrations/                # DataForSEO, Firecrawl, GSC, OpenAI Images, Reddit, PAA, Jina, codex_plugin_cc
│   ├── jobs/                        # APScheduler jobs (gsc_pull, drift_check, refresh_detector, oauth_refresh, ...)
│   ├── procedures/                  # daemon-orchestrated procedure runner
│   └── ui_dist/                     # committed Vue build (per D8)
│
├── ui/                              # Vue 3 + Vite + TS + Tailwind source
├── skills/                          # 24 SKILL.md (clean-room authored per D1/D2)
├── procedures/                      # 8 PROCEDURE.md playbooks + _template/
├── scripts/                         # install + register + doctor + launchd helpers
├── docs/
│   ├── attribution.md               # upstream credit + license posture (D1/D2)
│   ├── architecture.md
│   ├── extending.md                 # adding skills / procedures / integrations + tool-grant matrix
│   ├── api-keys.md                  # per-integration setup incl. GSC OAuth flow
│   ├── procedures-guide.md          # PROCEDURE.md frontmatter + DSL
│   ├── plan-audit.md                # closed pre-M0 audit
│   └── upstream-stripping-map.md    # M7 skill-authoring guide
├── tests/                           # unit + integration + fixtures
├── .github/workflows/ci.yml         # ruff + pytest + mypy + UI build + parity table
├── NOTICE                           # Apache-2.0 attributions (codex-plugin-cc)
└── .upstream/                       # cloned reference repos (gitignored, read-only)
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
4. If touching skills, read `docs/upstream-stripping-map.md` for the relevant skill's KEEP/STRIP/ADAPT.
5. If touching M0–M3 (foundation/DB/REST/MCP), the spec answers nearly every question — there should be no unspecified work.
