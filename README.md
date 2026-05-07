# content-stack

A globally-installed Python daemon that gives any LLM (Codex CLI, Claude Code,
or any MCP client) a stateful CRUD seam for managing multi-project SEO content
pipelines, plus a minimal Vue 3 UI for human inspection.

**One process. One SQLite DB. Three transports: MCP, REST, static UI.**

The LLM authors. The UI mirrors. The DB is canonical.

---

## Status

Pre-implementation. See [`PLAN.md`](./PLAN.md) for the full design and phase plan.

---

## Quickstart (target — not yet implemented)

```bash
# install daemon
uv pip install -e .

# build UI
make build-ui

# start daemon (auto-creates DB at ~/.local/share/content-stack/)
make serve

# register MCP for your runtime(s)
make register-codex
make register-claude

# install skills into your runtime(s)
make install-skills-codex
make install-skills-claude

# open UI
open http://localhost:5180
```

---

## What lives here

| Directory | Purpose |
|---|---|
| `content_stack/` | Python package — FastAPI app, MCP tools, repositories, SQLite models |
| `ui/` | Vue 3 + Vite source for the management UI |
| `skills/` | `SKILL.md` skill bundles, dual-runtime (Codex + Claude Code) |
| `scripts/` | Install + register helpers |
| `tests/` | Unit + integration |

See [`PLAN.md`](./PLAN.md) for the full layout, schema, API surface, and phase plan.
