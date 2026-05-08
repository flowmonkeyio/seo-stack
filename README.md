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

## Quickstart

Clone the repo, run one command, open the UI:

```bash
git clone https://github.com/flowmonkey-io/content-stack
cd content-stack
make install
make serve              # foreground; or:
make install-launchd    # macOS only — auto-start on login
open http://localhost:5180
```

`make install` is idempotent: re-running produces the same end state.
It runs every install step (Python deps, migrations, UI bundle, skills
+ procedures into Codex + Claude Code, MCP registration, doctor).

### pipx mode (post-publish)

```bash
pipx install content-stack
content-stack install            # mirrors skills/procedures + registers MCP
content-stack serve              # daemon foreground
```

### Upgrade

See [`docs/upgrade.md`](./docs/upgrade.md). Quick reference:

- pipx: `pipx upgrade content-stack && content-stack install`
- Clone: `git pull && make install`

### Verifying an install

```bash
make doctor                                   # human output
bash scripts/doctor.sh --json | jq            # JSON envelope
```

Doctor exit codes:
0 (ok), 1 (daemon down), 2 (MCP not registered), 3 (skills not
installed), 4 (missing API keys), 5 (DB schema out of date),
6 (launchd plist not loaded), 7 (auth token missing or wrong mode),
8 (seed file missing or wrong mode).

### Codex CLI bearer token

Codex CLI reads the bearer token from an environment variable rather
than a literal header. After `make install`, add to your shell rc:

```bash
export CONTENT_STACK_TOKEN="$(cat ~/.local/state/content-stack/auth.token)"
```

Claude Code reads the token directly from `~/.claude/mcp.json`, no
shell env required.

### Uninstall

```bash
make uninstall                  # removes skills, procedures, MCP entries, launchd
                                # plist; preserves DB + seed + auth.token
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
