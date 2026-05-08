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
+ procedures into Codex + Claude Code, MCP registration, doctor) and
rotates the auth token.

### pipx mode (post-publish)

```bash
pipx install content-stack
content-stack install            # mirrors skills/procedures + registers MCP
content-stack serve              # daemon foreground
```

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
0 (ok), 1 (daemon down), 2 (MCP not registered), 3 (skills not
installed), 4 (missing API keys), 5 (DB schema out of date),
6 (launchd plist not loaded), 7 (auth token missing or wrong mode),
8 (seed file missing or wrong mode).

### Upgrade

See [`docs/upgrade.md`](./docs/upgrade.md). Quick reference:

- pipx: `pipx upgrade content-stack && content-stack install`
- Clone: `git pull && make install`

### Uninstall

```bash
make uninstall                  # removes skills, procedures, MCP entries, launchd
                                # plist; preserves DB + seed + auth.token
```

---

## What lives here

| Directory          | Purpose                                                             |
| ------------------ | ------------------------------------------------------------------- |
| `content_stack/`   | Python package — FastAPI app, MCP tools, repositories, SQLite models |
| `ui/`              | Vue 3 + Vite source for the management UI                            |
| `skills/`          | 24 SKILL.md skill bundles, dual-runtime (Codex + Claude Code)       |
| `procedures/`      | 8 PROCEDURE.md playbooks + `_template/` scaffold                    |
| `scripts/`         | Install + register + doctor helpers                                  |
| `docs/`            | Architecture, extending, procedures-guide, api-keys, security, …    |
| `tests/`           | Unit + integration                                                   |

---

## Documentation

- [`PLAN.md`](./PLAN.md) — the canonical spec. 1650+ lines; vision,
  schema, REST + MCP surface, skills + procedures, distribution.
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
  Ahrefs, codex-plugin-cc, daemon-side LLM keys).
- [`docs/security.md`](./docs/security.md) — threat-model trade-offs;
  bearer-token bootstrap, prompt-injection hygiene, rate limits.
- [`docs/upgrade.md`](./docs/upgrade.md) — pipx + clone-mode upgrade
  semantics, breaking-change protocol, cross-machine moves.
- [`docs/attribution.md`](./docs/attribution.md) — upstream credit +
  license posture (clean-room rule per D1 / D2).
- [`docs/upstream-stripping-map.md`](./docs/upstream-stripping-map.md) —
  per-skill KEEP / ADAPT / Risks summary; drives clean-room
  authoring.
- [`CHANGELOG.md`](./CHANGELOG.md) — version history.

---

## Acknowledgements

content-stack is a stand-alone implementation. We do not vendor any
upstream code or prompts; we learn from the upstream repos referenced
below — patterns, taxonomies, threshold heuristics — and re-author
every skill against our own DB schema and MCP contract. For two of
the three skill-source repos (Cody, codex-seo) we apply a stricter
**clean-room** rule: skill authors do not read upstream files at all
when authoring the corresponding skills.

| Upstream                                                          | Role                                                              | License posture                                                  |
| ----------------------------------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------- |
| [`AgriciDaniel/codex-seo`](https://github.com/AgriciDaniel/codex-seo)                           | Pattern reference for skills #1, #2, #3, #14, #16, #20, #21, #22  | Clean-room per locked decision **D2**.                            |
| [`ibuildwith-ai/cody-article-writer`](https://github.com/ibuildwith-ai/cody-article-writer)     | Pattern reference for skills #4, #6, #7, #8, #9, #10, #24         | Clean-room per locked decision **D1**.                            |
| [`aaron-he-zhu/seo-geo-claude-skills`](https://github.com/aaron-he-zhu/seo-geo-claude-skills)   | Pattern reference for skills #11 (eeat-gate) and #15 (interlinker) | Apache-2.0; reference with attribution.                            |
| [`openai/codex-plugin-cc`](https://github.com/openai/codex-plugin-cc)                             | Optional adversarial-EEAT-review feature seam                     | Apache-2.0; user-installed; runtime-conditional.                   |

See [`docs/attribution.md`](./docs/attribution.md) for pinned SHAs,
license analysis, and the clean-room procedure. See
[`NOTICE`](./NOTICE) for the Apache-2.0 attributions.
