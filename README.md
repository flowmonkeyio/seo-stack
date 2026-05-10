# content-stack

**v1.0.0 — feature-complete; see [`PLAN.md`](./PLAN.md) for the canonical spec.**

## What is content-stack?

content-stack is a globally-installed Python daemon (FastAPI +
SQLite/WAL + MCP Streamable HTTP) plus Vue 3 UI that gives any LLM
client (Codex CLI, Claude Code, Cursor, Cline, …) a stateful CRUD
seam over multi-project SEO content pipelines. The LLM authors. The
UI mirrors. The DB is canonical.

**One process. One SQLite DB. Three transports: MCP, REST, static UI.**
Bound to `127.0.0.1`; per-install bearer-token auth on every request.
The current REST surface exposes 87 OpenAPI paths.

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
It runs every install step (Python deps, state bootstrap, migrations, UI
bundle, user-local content-stack plugin, MCP registration, doctor). It creates
the auth token on first install; rotate later with `make rotate-token`.

### pipx mode (post-publish)

```bash
pipx install content-stack
content-stack install            # bootstraps state, mirrors assets, registers MCP
content-stack serve              # daemon foreground
```

Token rotation is explicit:

```bash
content-stack rotate-token --yes  # or: make rotate-token
```

After rotating, restart any running daemon so it loads the new token.

### Codex CLI bearer token

The modern Codex CLI reads the bearer token from a named env var
rather than a literal header. After `make install`, add to your shell
rc:

```bash
export CONTENT_STACK_TOKEN="$(cat ~/.local/state/content-stack/auth.token)"
```

Claude Code reads the token directly from `~/.claude/mcp.json`, no
shell env required.

### Verifying an install

```bash
make doctor                                   # human output
bash scripts/doctor.sh --json | jq            # JSON envelope
```

Doctor exit codes:
0 (ok), 1 (daemon down), 4 (DB schema out of date), 7 (auth token
missing or wrong mode), 8 (seed file missing, wrong mode, or unable to
decrypt stored credentials). Optional MCP, skills, procedures, and
launchd checks/counts appear in the JSON `checks`/`info` payload without
changing the exit code; plugin install and marketplace registration are the
default runtime checks.

### Upgrade

See [`docs/upgrade.md`](./docs/upgrade.md). Quick reference:

- pipx: `pipx upgrade content-stack && content-stack install`
- Clone: `git pull && make install`

### Uninstall

```bash
make uninstall                  # removes plugin, legacy assets, MCP entries, launchd
                                # plist; preserves DB + seed + auth.token
```

---

## What lives here

| Directory          | Purpose                                                             |
| ------------------ | ------------------------------------------------------------------- |
| `content_stack/`   | Python package — FastAPI app, MCP tools, repositories, SQLite models |
| `ui/`              | Vue 3 + Vite source for the management UI                            |
| `skills/`          | 24 SKILL.md source catalog bundled into the plugin                   |
| `plugins/`         | Installable runtime plugin exposing content-stack repo workflows     |
| `procedures/`      | 8 PROCEDURE.md source playbooks bundled into the plugin              |
| `scripts/`         | Install + register + doctor helpers                                  |
| `docs/`            | Architecture, extending, procedures-guide, api-keys, security, …    |
| `tests/`           | Unit + integration                                                   |

---

## Documentation

- [`PLAN.md`](./PLAN.md) — the canonical spec. 1650+ lines; vision,
  schema, REST + MCP surface, skills + procedures + plugins, distribution.
- [`docs/architecture.md`](./docs/architecture.md) — system overview;
  process model, lifespan, repository layer, integration seam,
  operational invariants.
- [`docs/extending.md`](./docs/extending.md) — how to add skills,
  procedures, programmatic step handlers, integrations, MCP tools,
  REST routes.
- [`docs/procedures-guide.md`](./docs/procedures-guide.md) —
  PROCEDURE.md frontmatter + DSL + worked examples + failure modes.
- [`docs/api-keys.md`](./docs/api-keys.md) — vendor credential setup
  (DataForSEO, Firecrawl, GSC OAuth, OpenAI Images, Reddit, Jina,
  Ahrefs).
- [`docs/security.md`](./docs/security.md) — threat-model trade-offs;
  bearer-token bootstrap, prompt-injection hygiene, rate limits.
- [`PRIVACY.md`](./PRIVACY.md) — local-first data handling and the
  exact outbound calls the daemon can make.
- [`docs/upgrade.md`](./docs/upgrade.md) — pipx + clone-mode upgrade
  semantics, breaking-change protocol, cross-machine moves.
- [`CHANGELOG.md`](./CHANGELOG.md) — version history.
