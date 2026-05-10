# content-stack

Agent-led SEO content operations for Codex, Claude Code, and other MCP-capable
coding agents.

content-stack turns the agent already working in a website repository into the
SEO operator for that site. The agent researches topics, writes and edits
content, creates assets, emits schema, suggests links, publishes, and refreshes
old pages. A local daemon keeps the durable state: projects, topics, runs,
credentials, quality gates, publish targets, and audit history.

The split is intentional:

- **The current agent is the brain.** It decides what should happen next,
  follows procedures, writes content, and may delegate bounded work to
  caller-owned subagents.
- **The daemon is the control plane.** It owns SQLite state, encrypted
  credentials, permissions, validation, run cursors, schedules, and audit
  records.
- **The plugin is the developer experience.** It lets agents use content-stack
  from any website repository without adding `.env`, `.mcp.json`,
  `.content-stack/`, or prompt files to that repo.
- **The UI is the human console.** It gives the operator a place to configure
  projects, connect vendors, approve topics, inspect runs, and review outputs.

content-stack is local-first and loopback-only: one Python daemon, one
SQLite/WAL database, one installed plugin, and one compact MCP bridge per
agent client.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Commands](#commands)
- [How The Agent Flow Works](#how-the-agent-flow-works)
- [Workflows](#workflows)
- [Agent Tools](#agent-tools)
- [Skills](#skills)
- [Procedures](#procedures)
- [Features](#features)
- [Architecture](#architecture)
- [Integrations](#integrations)
- [Publishing Targets](#publishing-targets)
- [Operations Console](#operations-console)
- [Development](#development)
- [Requirements](#requirements)
- [Uninstall](#uninstall)
- [Documentation](#documentation)
- [Status](#status)

## Installation

### Clone Install

```bash
git clone https://github.com/flowmonkeyio/seo-stack.git content-stack
cd content-stack
make install
make serve
```

Open the console:

```bash
open http://localhost:5180
```

`make install` is idempotent. It installs Python dependencies, initializes
daemon state, applies migrations, verifies the packaged UI bundle, installs the
content-stack plugin, registers MCP entries for Codex and Claude Code, and runs
doctor checks.

### Codex Token Setup

Codex's HTTP MCP registration reads the daemon bearer token from an environment
variable name. Add this after install:

```bash
export CONTENT_STACK_TOKEN="$(cat ~/.local/state/content-stack/auth.token)"
```

Restart Codex after installing or rotating the token so it reloads plugin and
MCP configuration.

### Optional macOS Auto-Start

Foreground daemon mode works everywhere the package supports. On macOS you can
also install a launchd job:

```bash
make install-launchd
```

### Package Install

Once a package release is available:

```bash
pipx install content-stack
content-stack install
content-stack serve
```

## Quick Start

Start from the website repository, not from the content-stack repository.

```bash
cd /path/to/your-site
codex
```

Then ask the agent for the operation you want:

```text
Connect this repo to content-stack and set up the SEO project.
```

```text
Find keyword opportunities and build a topic queue for this site.
```

```text
Take the next approved topic and publish the article.
```

```text
Review published content and tell me which articles need refresh.
```

The agent should:

1. Resolve the current workspace.
2. Create or select a content-stack project.
3. Bind the repository to the project.
4. Start the right procedure.
5. Claim each step, read the relevant skill guidance, call the allowed tools,
   and record the result.
6. Pause for human review when the procedure requires it.

If integrations are missing, the agent should share the relevant console link,
for example:

```text
http://localhost:5180/projects/1/integrations?required=dataforseo,firecrawl,gsc
```

Credentials belong in the content-stack daemon, not in chat and not in the
website repository.

## Commands

content-stack does not require a slash-command vocabulary. The main interface
is a normal agent conversation backed by procedures and MCP tools.

### Operator Prompts

| Ask The Agent | Typical Procedure |
| --- | --- |
| "Connect this repo to content-stack." | Workspace resolve/connect, then project setup if needed. |
| "Set up this site for SEO content operations." | `01-bootstrap-project` or `08-add-new-site` |
| "Find content opportunities for this niche." | `03-keyword-to-topic-queue` |
| "Write and publish the next approved article." | `04-topic-to-published` |
| "Launch this batch of approved topics." | `05-bulk-content-launch` |
| "Review GSC and tell me what to do next." | `06-weekly-gsc-review` |
| "Refresh decaying content." | `07-monthly-humanize-pass` plus `content-refresher` |

### Local CLI

| Command | Purpose |
| --- | --- |
| `make install` | Install dependencies, initialize state, install plugin, register MCP, and run doctor. |
| `make serve` | Run the daemon in the foreground on `127.0.0.1:5180`. |
| `content-stack restart` | Restart the daemon after backend/UI/token changes. |
| `make doctor` | Diagnose local install, daemon, token, plugin, and MCP state. |
| `make build-ui` | Rebuild `content_stack/ui_dist/` from `ui/`. |
| `make uninstall` | Remove installed plugin/MCP entries while preserving DB and token state. |

## How The Agent Flow Works

content-stack is agent-led, not daemon-led.

```text
Website repository
  |
  | Codex / Claude Code loads the content-stack plugin
  v
Plugin MCP bridge
  |
  | compact direct tools + toolbox.describe/toolbox.call
  v
Local content-stack daemon on 127.0.0.1:5180
  |
  | FastAPI REST, MCP Streamable HTTP, Vue console
  v
SQLite/WAL database at ~/.local/share/content-stack/content-stack.db
  |
  | encrypted credentials, project state, runs, publish records
  v
Vendor APIs and publishing targets
```

The normal loop:

1. The operator opens an agent inside a website repository.
2. The installed plugin starts a lightweight MCP bridge.
3. The bridge connects to the singleton local daemon.
4. The agent calls `workspace.startSession` or `workspace.resolve`.
5. The agent creates/selects a project and calls `workspace.connect`.
6. The agent starts a run with `procedure.run`.
7. For each step, the agent calls `procedure.claimStep`.
8. The daemon returns the step package: skill body, inputs, prior outputs, and
   allowed tools.
9. The agent does the work directly and records the result with
   `procedure.recordStep`.
10. The daemon advances the cursor and preserves the audit trail.

The daemon does not secretly launch writer agents. It stores state and enforces
contracts. The current agent owns judgment and execution.

## Workflows

| Workflow | What The Agent Does |
| --- | --- |
| New site setup | Connects the repo, creates the project, configures voice, compliance, EEAT, integrations, publish targets, sitemap, and schedule. |
| Keyword discovery | Expands seed keywords into SERP-informed topics, clusters, and approval queues. |
| Single article | Runs brief, outline, draft, edit, humanize, EEAT, assets, schema, links, and publish for one approved topic. |
| Bulk launch | Opens child article runs for a batch of approved topics and manages parallelism intentionally. |
| Content refresh | Scores old articles, snapshots versions, updates content, repairs links, rechecks quality, and republishes. |
| Weekly review | Uses GSC, crawl, drift, and internal-link data to find opportunities and regressions. |
| Integration setup | Detects missing vendor credentials and routes the operator to the console setup flow. |

### Workhorse Article Flow

`04-topic-to-published` is the canonical article workflow:

```text
content-brief
  -> outline
  -> draft-intro
  -> draft-body
  -> draft-conclusion
  -> editor
  -> humanizer
  -> eeat-gate
  -> image-generator
  -> alt-text-auditor
  -> schema-emitter
  -> interlinker
  -> publish target
```

Important behavior:

- `eeat-gate` returns `SHIP`, `FIX`, or `BLOCK`.
- `FIX` loops back to editing, with retry limits.
- `BLOCK` prevents publishing.
- Asset, alt-text, and interlink steps can be skipped when appropriate.
- Schema and publish steps are abort-on-failure.
- The publish step resolves to the project's primary target adapter.

## Agent Tools

The plugin keeps the direct MCP surface compact so agents do not carry a huge
tool catalog in context. Advanced and step-scoped tools are available through
the toolbox bridge only when granted.

### Direct Tools

| Family | Examples | Purpose |
| --- | --- | --- |
| Workspace | `workspace.startSession`, `workspace.resolve`, `workspace.connect`, `workspace.listBindings`, `workspace.updateProfile` | Connect the current repo to a project without writing repo-local setup files. |
| Projects | `project.create`, `project.get`, `project.list`, `project.update`, `project.setActive`, `project.getActive` | Create, select, inspect, and update projects. |
| Procedures | `procedure.list`, `procedure.run`, `procedure.currentStep`, `procedure.claimStep`, `procedure.recordStep`, `procedure.resume`, `procedure.fork`, `procedure.executeProgrammaticStep` | Start and walk durable agent-led procedures. |
| Runs | `run.get`, `run.list`, `run.heartbeat`, `run.abort` | Inspect and control active or historical work. |
| Meta | `meta.enums` | Read canonical enum values and legal state transitions. |
| Toolbox | `toolbox.describe`, `toolbox.call` | Discover and invoke hidden setup or step-scoped tools. |

### Toolbox Families

| Family | What It Covers |
| --- | --- |
| Voice and compliance | Voice profiles, disclosure rules, validators, and policy text. |
| EEAT | Criteria, evaluations, scoring, and SHIP/FIX/BLOCK gates. |
| Topics and clusters | Topic queue, approvals, topical maps, and cluster membership. |
| Articles and sources | Briefs, outlines, drafts, edited markdown, versions, and source ledgers. |
| Assets | Image rows, alt text, dimensions, formats, placement, and prompts. |
| Schema | JSON-LD creation, primary-row invariants, validation, and publish freezing. |
| Interlinks | Suggested links, approval, apply/dismiss, and repair flows. |
| Publishing | Targets, previews, canonical target records, and publish rows. |
| Integrations | DataForSEO, Firecrawl, GSC, OpenAI Images, Reddit, PAA, Jina, and Ahrefs inputs. |
| Cost | Budgets, usage checks, and pre-call spend controls. |
| GSC and sitemap | Sitemap ingestion, URL inspection, performance rollups, and opportunity detection. |
| Drift | Live HTML capture, baseline comparison, and regression state. |

If a procedure step is not granted a tool, the bridge rejects the call.

## Skills

Skills are agent-readable operating manuals. They explain how to perform a
specific SEO task, what evidence is required, which tools are allowed, and what
output must be recorded.

| Phase | Skills |
| --- | --- |
| Research | `keyword-discovery`, `serp-analyzer`, `competitor-sitemap-shortcut`, `topical-cluster`, `content-brief` |
| Content | `outline`, `draft-intro`, `draft-body`, `draft-conclusion`, `editor`, `humanizer`, `eeat-gate` |
| Assets | `image-generator`, `alt-text-auditor` |
| Publishing | `schema-emitter`, `interlinker`, `nuxt-content-publish`, `wordpress-publish`, `ghost-publish` |
| Ongoing | `gsc-opportunity-finder`, `drift-watch`, `crawl-error-watch`, `refresh-detector`, `content-refresher` |

The installed plugin also includes a root `content-stack` skill that teaches
the agent how to resolve workspaces, pick procedures, use direct tools, and
invoke toolbox calls.

Skill quality contracts live in:

- `skills/references/skill-operating-contract.md`
- `skills/references/seo-quality-baseline.md`

## Procedures

Procedures are durable playbooks. The current agent walks them; the daemon
stores state, step outputs, and audit records.

| Procedure | Purpose |
| --- | --- |
| `01-bootstrap-project` | Create base project setup: voice, compliance, EEAT, integrations, publish targets, and scheduling inputs. |
| `02-one-site-shortcut` | Import one site into the topic workflow. |
| `03-keyword-to-topic-queue` | Turn seed keywords and discovery inputs into a deduplicated topic queue. |
| `04-topic-to-published` | Move one approved topic to a published article. |
| `05-bulk-content-launch` | Run and monitor multiple topic-to-published child runs. |
| `06-weekly-gsc-review` | Find opportunities, drift, crawl issues, and refresh candidates. |
| `07-monthly-humanize-pass` | Refresh and humanize eligible published content. |
| `08-add-new-site` | Connect and launch another site. |

## Features

### Research and Planning

- Keyword expansion from seeds.
- SERP analysis and intent classification.
- Competitor sitemap shortcuts.
- Topical clustering and pillar/spoke planning.
- Briefs with source ledgers, schema hints, EEAT plans, and asset directives.

### Content Production

- Structured outline generation.
- Intro, body, and conclusion drafting.
- Editorial pass and humanizer pass.
- EEAT scoring with core criteria.
- Version snapshots before refresh.

### Assets and Schema

- Article image generation prompts and asset records.
- Alt-text audits with format, size, placement, and loading guidance.
- JSON-LD generation and validation.
- Canonical primary schema row enforcement.

### Publishing and Linking

- Internal-link suggestions with approval before apply.
- Nuxt Content/static markdown publishing.
- WordPress REST publishing.
- Ghost Admin API publishing.
- Publish records and canonical target tracking.

### Ongoing SEO Operations

- GSC opportunity discovery.
- Crawl error monitoring.
- Drift detection against live pages.
- Refresh scoring based on age, trend, and drift.
- Scheduled review procedures.

## Architecture

| Component | Path | Role |
| --- | --- | --- |
| Daemon | `content_stack/` | FastAPI app, repositories, integrations, MCP tools, jobs, and CLI. |
| Database | `~/.local/share/content-stack/content-stack.db` | Canonical local state for projects, runs, artifacts, credentials, and publish records. |
| Plugin | `plugins/content-stack/` | Repo-agnostic Codex/agent plugin surface. |
| Skills | `skills/` | Agent-readable task guidance. |
| Procedures | `procedures/` | Agent-led playbooks with durable step state. |
| UI | `ui/` | Vue operations console source. |
| Packaged UI | `content_stack/ui_dist/` | Built console assets served by the daemon. |
| Docs | `docs/` | Architecture, extending, procedures, security, upgrade, and vendor setup. |
| Scripts | `scripts/` | Install, registration, doctor, launchd, and type generation helpers. |

Security defaults:

- Daemon binds to `127.0.0.1`.
- REST and MCP require a per-install bearer token.
- Integration credentials are encrypted at rest.
- Website repositories do not need checked-in content-stack config.
- Runtime prose-generation keys stay with the agent runtime, not in
  content-stack.

## Integrations

Vendor integrations are configured in the daemon and used through granted
tools. The agent should never ask the operator to paste secrets into chat.

Supported integration families:

| Integration | Use |
| --- | --- |
| DataForSEO | Keyword, SERP, and ranking data. |
| Firecrawl | Page crawl, extraction, and drift capture. |
| Google Search Console | Performance, indexing, crawl inspection, and opportunity discovery. |
| OpenAI Images | Article images, OG assets, and inline visual assets. |
| Reddit | Audience language and question mining. |
| Google People Also Ask | Question discovery and intent expansion. |
| Jina Reader | Markdown extraction fallback. |
| Ahrefs exports | Enterprise competitor inputs and sitemap shortcuts. |

The console integrations page is the preferred setup flow.

## Publishing Targets

A project can have one primary target and optional secondary targets.

| Target | What Happens |
| --- | --- |
| Nuxt Content / static repo | Writes markdown/frontmatter and assets into a local content repo, then commits, pushes, and records the publish. |
| WordPress | Uploads media and posts through the WordPress REST API. |
| Ghost | Uploads images and posts through the Ghost Admin API. |

Target rows store adapter-specific config such as repo path, content directory,
image directory, branch, remote, URL pattern, frontmatter template, API
endpoint, and credential reference.

## Operations Console

The console runs at:

```text
http://localhost:5180
```

Main areas:

| Area | Purpose |
| --- | --- |
| Projects | Create and select sites. |
| Overview | Inspect project state and setup completeness. |
| Integrations | Add and test vendor credentials. |
| Topics | Review, approve, reject, and cluster topics. |
| Clusters | Inspect topical maps and pillar/spoke structure. |
| Articles | Track article status and refresh state. |
| Article detail | Edit brief, outline, draft, edited body, assets, schema, publishes, EEAT, versions, links, and drift. |
| Interlinks | Review suggestions and repair broken links. |
| GSC | Inspect performance, rollups, and redirects. |
| Drift | Compare live page state against baselines. |
| Runs | Debug procedure and tool execution. |
| Procedures | Browse and start procedure runs. |

## Development

Useful commands:

```bash
make install          # Full local install pipeline
make serve            # Run daemon on 127.0.0.1:5180
make doctor           # Diagnose local install
make test             # Python tests + UI unit tests
make test-ui-unit     # Vitest unit tests
make test-ui-e2e      # Playwright e2e tests
make lint             # Ruff checks
make typecheck        # Mypy
make build-ui         # Build UI bundle into content_stack/ui_dist/
make gen-types        # Regenerate ui/src/api.ts from the daemon OpenAPI spec
```

Focused examples:

```bash
uv run pytest tests/integration/test_procedure_runner/test_agent_led_controller.py
pnpm --dir ui type-check
pnpm --dir ui lint
pnpm --dir ui test
pnpm --dir ui build
```

Restart the daemon after backend or packaged UI changes:

```bash
content-stack restart
content-stack restart --force
```

## Requirements

- Python 3.12 or newer.
- `uv` for clone-mode development.
- Node package tooling when changing `ui/`.
- Codex CLI and/or Claude Code for agent access.
- Optional macOS launchd for auto-start.
- Vendor accounts only for integrations you enable.

## Uninstall

Remove installed plugin, skills, procedures, MCP entries, and launchd job while
preserving the local DB, seed, and auth token:

```bash
make uninstall
```

State is preserved under:

```text
~/.local/share/content-stack/
~/.local/state/content-stack/
```

## Documentation

- `PLAN.md`: canonical product and implementation spec.
- `docs/architecture.md`: architecture, security model, and invariants.
- `docs/procedures-guide.md`: procedure authoring contract and DSL.
- `docs/extending.md`: adding skills, procedures, integrations, MCP tools, and
  REST routes.
- `docs/api-keys.md`: vendor credential setup.
- `docs/security.md`: local security model.
- `docs/upgrade.md`: upgrade, rollback, and migration notes.
- `PRIVACY.md`: data handling and outbound calls.
- `CHANGELOG.md`: release history.

## Troubleshooting

### MCP says connection refused

The daemon is not listening yet, or the plugin bridge could not auto-start it.

```bash
make serve
make doctor
```

Then restart the agent client.

### Plugin is installed but unavailable

Restart Codex or Claude Code after install. In Codex, run:

```text
/plugins
```

The installed plugin should be named `content-stack`.

### Token mismatch after rotation

Restart the daemon and the agent client. The daemon reads the token at startup.

### Website repo is not detected

Run the agent from the website repository root. The agent should resolve the
workspace and call `workspace.connect` if no binding exists.

### Publish refuses because the target repo is dirty

Static publishing skills avoid clobbering local changes. Commit, stash, or
clean the target repository, then rerun or resume the procedure.

### Vendor credentials are missing

Add credentials through the console integrations page. Mocked or skipped vendor
calls are fine for development, but production procedures should use configured
integrations.

## Status

content-stack is built around a plugin-first, repo-agnostic flow:

1. Install content-stack once on the machine.
2. Start an agent from whichever website repository needs work.
3. Let that agent choose and run procedures using content-stack tools and
   skills.
4. Keep state, credentials, and audit history in the local daemon.
5. Improve skills and procedures without polluting website repositories.
