# content-stack

content-stack is a local SEO content operations control plane for agents.
It lets Codex, Claude Code, and other MCP-capable coding agents manage
multi-site content programs from inside the website repository they are
working on, while a singleton local daemon owns durable state, credentials,
quality gates, procedure runs, and publish records.

The important idea is simple:

- The current agent is the brain. It decides what to do next, writes the
  content, calls subagents when useful, and walks procedures step by step.
- The daemon is the control plane. It stores projects, topics, briefs,
  drafts, assets, schema, credentials, publish targets, audit trails, and run
  state in one local SQLite database.
- The plugin is the developer experience. It makes content-stack available
  from any repository without adding `.env`, `.mcp.json`, `.content-stack/`,
  `AGENTS.md`, or project-specific prompt files to that repository.
- The UI is the human console. It lets the operator inspect projects, approve
  topics, edit data, configure vendors, and review outputs.

The system is local-first and loopback-only by design: one Python daemon,
one SQLite/WAL database, one installed plugin, and one compact MCP bridge per
agent client.

## What It Is For

content-stack is built for sites that need repeatable SEO content work without
turning the agent into a blind automation worker.

It supports:

- Starting a new site content program from repository context.
- Discovering keywords, competitors, SERP patterns, and topical clusters.
- Building article briefs with sources, intent, schema hints, EEAT plans, and
  image directives.
- Drafting, editing, humanizing, and quality-gating articles.
- Generating and auditing image assets.
- Emitting schema and internal-link suggestions.
- Publishing to static content repositories, WordPress, Ghost, and future
  target adapters.
- Refreshing old content based on age, GSC trend data, crawl state, and drift.
- Keeping every step resumable, auditable, and tied to a procedure run.

It is not meant to be a remote SaaS worker, a hidden content farm, or a daemon
that spawns independent writing agents behind the user's back. The operator
starts an agent in the current project, and that agent drives the flow.

## Architecture

```text
Website repo / operator thread
        |
        | Codex or Claude Code loads the content-stack plugin
        v
Plugin MCP bridge
        |
        | Compact direct tools plus toolbox.describe/toolbox.call
        v
content-stack daemon on 127.0.0.1:5180
        |
        | FastAPI REST, MCP Streamable HTTP, Vue UI
        v
SQLite/WAL database at ~/.local/share/content-stack/content-stack.db
        |
        | Encrypted vendor credentials and local project state
        v
Publish targets and vendor APIs
```

The daemon exposes three surfaces:

| Surface | Purpose |
| --- | --- |
| MCP | Agent-facing project, workspace, procedure, run, and toolbox calls. |
| REST API | UI and integration surface under `/api/v1`. |
| Vue UI | Browser console at `http://localhost:5180`. |

Security defaults:

- The daemon binds only to `127.0.0.1`.
- REST and MCP calls use a per-install bearer token from
  `~/.local/state/content-stack/auth.token`.
- Integration credentials are encrypted at rest with a local seed file.
- Website repositories do not need checked-in content-stack config files.

## Core Components

| Component | Path | Role |
| --- | --- | --- |
| Daemon | `content_stack/` | FastAPI app, repositories, integrations, MCP tools, jobs, CLI. |
| Database | `~/.local/share/content-stack/content-stack.db` | Canonical state for all projects and runs. |
| Plugin | `plugins/content-stack/` | Installed into Codex/Claude so agents can use content-stack from any repo. |
| Skills | `skills/` | Agent-readable operating manuals for each specialist step. |
| Procedures | `procedures/` | Ordered playbooks that the current agent walks and records. |
| UI | `ui/` | Vue management console for humans. |
| Docs | `docs/` | Architecture, procedures, extending, security, upgrade, API keys. |
| Scripts | `scripts/` | Install, MCP registration, doctor, launchd, type generation. |

## Agent Model

content-stack is agent-led, not daemon-led.

The normal loop is:

1. The operator opens Codex or Claude Code inside a website repository.
2. The installed content-stack plugin starts a lightweight MCP bridge.
3. The bridge connects to the singleton local daemon.
4. The agent resolves the current repository with `workspace.startSession` or
   `workspace.resolve`.
5. The agent selects or creates a content-stack project and binds the repo with
   `workspace.connect`.
6. The agent opens a procedure run with `procedure.run`.
7. For each step, the agent calls `procedure.claimStep`.
8. The daemon returns the step package: skill body, merged args, previous
   outputs, and allowed tool names.
9. The agent reads the skill guidance, does the work directly with granted
   tools, and may call caller-owned subagents for bounded subtasks.
10. The agent records the result with `procedure.recordStep`.
11. The daemon advances the durable cursor and the agent claims the next step.

The daemon does not secretly launch writer agents. It owns state, permissions,
credentials, validation, and audit trails. The current operator agent owns
judgment and execution.

## User Flows

### New Site Setup

Use this when a repository has not been connected to content-stack yet.

1. Start an agent in the website repository.
2. Resolve workspace context.
3. Create or select a content-stack project.
4. Bind the repository to the project.
5. Configure voice, compliance, author, EEAT criteria, integrations, schedule,
   sitemap, and publish targets.
6. Run `01-bootstrap-project` or `08-add-new-site` depending on whether this is
   a bare project setup or a larger launch flow.

### New Article

Use this when the project needs one article from an approved topic.

1. Create or approve a topic.
2. Run `04-topic-to-published`.
3. The agent walks brief, outline, draft, edit, humanize, EEAT, assets, schema,
   links, and publish.
4. The daemon records every step and artifact.

### Bulk Launch

Use this when launching a batch of approved topics.

1. Populate and approve a topic queue.
2. Run `05-bulk-content-launch`.
3. The procedure opens child `04-topic-to-published` runs.
4. The current agent decides how much parallelism is appropriate and records
   child progress back to the parent run.

### Content Refresh

Use this when existing content needs updates.

1. `refresh-detector` scores published articles using age, GSC trend, and drift.
2. Articles above the threshold become `refresh_due`.
3. `content-refresher` snapshots the old article version, refreshes the body,
   re-runs quality and publishing steps, repairs stale links, and records the
   republish.

### Ongoing SEO Operations

Use this after a site has published content.

1. `weekly-gsc-review` finds opportunities from Search Console data.
2. Drift and crawl watchers detect live-page regressions.
3. Refresh procedures keep older content from decaying.
4. Internal linking procedures improve cluster coverage and orphan handling.

## Tools

The plugin intentionally exposes a compact direct MCP surface. The daemon still
has a larger internal tool catalog for the UI, tests, and advanced flows, but
agents should not carry that whole surface in context.

### Direct Agent Tools

These are the tools agents should see and use directly:

| Family | Examples | Purpose |
| --- | --- | --- |
| Workspace | `workspace.startSession`, `workspace.resolve`, `workspace.connect`, `workspace.listBindings`, `workspace.updateProfile` | Connect the current repository to a content-stack project without writing repo files. |
| Projects | `project.create`, `project.get`, `project.list`, `project.update`, `project.setActive`, `project.getActive` | Create, select, and inspect projects. |
| Procedures | `procedure.list`, `procedure.run`, `procedure.currentStep`, `procedure.claimStep`, `procedure.recordStep`, `procedure.resume`, `procedure.fork`, `procedure.executeProgrammaticStep` | Start and walk agent-led procedures. |
| Runs | `run.get`, `run.list`, `run.heartbeat`, `run.abort` | Inspect and control durable work. |
| Meta | `meta.enums` | Read canonical enum values and legal transitions. |
| Toolbox | `toolbox.describe`, `toolbox.call` | Inspect and invoke hidden setup or step-scoped tools. |

### Hidden Tool Families

Hidden tools are reached through `toolbox.describe` and `toolbox.call`.
The bridge only grants setup tools or the current step's allowed tools.

| Family | What it covers |
| --- | --- |
| Voice and compliance | Voice profiles, disclosure rules, custom validators. |
| EEAT | Criteria lists, bulk evaluations, scoring, SHIP/FIX/BLOCK gating. |
| Topics and clusters | Topic queue, approvals, topical maps, cluster membership. |
| Articles and sources | Briefs, outlines, drafts, edited markdown, versions, research sources. |
| Assets | Image asset rows, alt text, dimensions, format metadata. |
| Schema | JSON-LD creation, primary-row invariant, validation. |
| Interlinks | Suggestions, apply/dismiss/repair workflows. |
| Publishing | Publish targets, previews, canonical target, publish records. |
| Integrations | DataForSEO, Firecrawl, Google Search Console, OpenAI Images, Reddit, PAA, Jina, Ahrefs. |
| Cost | Integration budgets and pre-call spend checks. |
| Sitemap and GSC | Sitemap ingestion, URL inspection, performance rollups. |
| Drift | Live HTML capture and drift baseline state. |

Each skill has a narrow grant list. If a step is not allowed to call a tool,
the MCP bridge rejects the call.

## Skills

Skills are the agent-readable instructions for doing a specific piece of SEO
work. They live in `skills/` and are bundled into the installed plugin under
`skills/catalog/`.

| Phase | Skills |
| --- | --- |
| Research | `keyword-discovery`, `serp-analyzer`, `competitor-sitemap-shortcut`, `topical-cluster`, `content-brief` |
| Content | `outline`, `draft-intro`, `draft-body`, `draft-conclusion`, `editor`, `eeat-gate`, `humanizer` |
| Assets | `image-generator`, `alt-text-auditor` |
| Publishing | `schema-emitter`, `interlinker`, `nuxt-content-publish`, `wordpress-publish`, `ghost-publish` |
| Ongoing | `gsc-opportunity-finder`, `drift-watch`, `crawl-error-watch`, `refresh-detector`, `content-refresher` |

The plugin also includes a root `content-stack` skill that tells the agent how
to resolve a workspace, connect a project, and use direct tools versus the
toolbox bridge.

Good skill content includes:

- When to use the skill and when not to.
- Required inputs and the tables or fields they come from.
- Step-by-step execution guidance.
- Allowed tools and why they are needed.
- Output shape for the daemon audit trail.
- Failure handling and retry/skip/abort semantics.
- SEO quality expectations, anti-spam guardrails, and evidence requirements.

Shared skill contracts live in:

- `skills/references/skill-operating-contract.md`
- `skills/references/seo-quality-baseline.md`

## Procedures

Procedures are ordered playbooks. The current agent walks them; the daemon
persists the run state and enforces grants.

| Procedure | Purpose |
| --- | --- |
| `01-bootstrap-project` | Create the base project setup: voice, compliance, EEAT, integrations, publish targets, and scheduling inputs. |
| `02-one-site-shortcut` | Shortcut for importing one site into the topic workflow. |
| `03-keyword-to-topic-queue` | Turn seed keywords and discovery inputs into a deduplicated topic queue. |
| `04-topic-to-published` | Workhorse flow from approved topic to published article. |
| `05-bulk-content-launch` | Spawn and monitor multiple topic-to-published child runs. |
| `06-weekly-gsc-review` | Scheduled opportunity, drift, and crawl review loop. |
| `07-monthly-humanize-pass` | Scheduled refresh/humanization pass over eligible published content. |
| `08-add-new-site` | Umbrella procedure for connecting and launching another site. |

### Workhorse Flow

`04-topic-to-published` is the canonical article flow:

```text
brief
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
  -> publish
```

Important behavior:

- `eeat-gate` returns `SHIP`, `FIX`, or `BLOCK`.
- `FIX` loops back to `editor`, capped by the procedure runner.
- `BLOCK` aborts the publish flow.
- Image generation, alt-text audit, and interlink suggestions are
  skip-on-failure quality enhancers.
- Schema and final publish are abort-on-failure.
- The final `publish` step resolves to the project's primary target adapter:
  Nuxt Content, WordPress, or Ghost.

## Publishing Targets

The publishing model is target-based. A project can have one primary target
and optional secondary targets.

Supported target skills:

- `nuxt-content-publish`: writes markdown/frontmatter and assets into a local
  static content repository, commits, pushes, and records the publish.
- `wordpress-publish`: uploads media and posts through the WordPress REST API.
- `ghost-publish`: uploads images and posts through the Ghost Admin API.

The target row stores target-specific config, such as repository path,
content subdirectory, public image directory, branch, remote, URL pattern,
frontmatter template, API endpoint, and credential reference.

## Integrations

Vendor credentials belong to the daemon, not the website repo. Operators add
them through the UI or setup tools; agents use wrapper tools with grants.

Supported integration families:

- DataForSEO for keyword and SERP data.
- Firecrawl for page crawl and drift capture.
- Google Search Console for performance, indexing, and crawl inspection.
- OpenAI Images for article images.
- Reddit and Google PAA for audience questions.
- Jina Reader for extraction.
- Ahrefs exports for enterprise competitor workflows.

Runtime prose-generation keys are intentionally not stored in content-stack.
The current agent's own runtime is responsible for writing prose.

## Install

### Prerequisites

- Python 3.12 or newer.
- `uv` for clone-mode development.
- Node package tooling for UI development when changing `ui/`.
- Codex CLI and/or Claude Code if you want MCP agent access.
- macOS launchd is optional; foreground daemon mode works everywhere the
  Python package supports.

### Clone Mode

```bash
git clone https://github.com/flowmonkey-io/content-stack
cd content-stack
make install
make serve
open http://localhost:5180
```

`make install` is idempotent. It installs Python dependencies, bootstraps
state, applies migrations, builds or mirrors assets, installs the user-local
plugin, registers MCP entries, and runs doctor.

Optional macOS auto-start:

```bash
make install-launchd
```

### pipx Mode

After a release is published:

```bash
pipx install content-stack
content-stack install
content-stack serve
```

### Restart Agent Clients

After install or upgrade, restart Codex or Claude Code so they reload plugin
and MCP configuration.

For Codex, inspect the plugin with:

```text
/plugins
```

The installed plugin should be named `content-stack`.

### Token Setup

Codex's HTTP MCP registration reads the bearer token through an environment
variable name. Add this to your shell rc after install:

```bash
export CONTENT_STACK_TOKEN="$(cat ~/.local/state/content-stack/auth.token)"
```

Claude Code registration reads from its MCP config and does not require this
shell export.

Rotate the token explicitly:

```bash
make rotate-token
# or
content-stack rotate-token --yes
```

Restart any running daemon after rotation.

## Setup A Website Repository

Use this flow from the site repo, not from the content-stack repo.

1. Start Codex or Claude Code in the website repository.
2. Confirm the `content-stack` plugin is enabled.
3. Ask the agent to connect this repository to content-stack.
4. The agent should call `workspace.startSession` or `workspace.resolve`.
5. If no binding exists, the agent should create or select a project and call
   `workspace.connect`.
6. Configure the project's voice, compliance rules, authors, integrations,
   publish target, sitemap, and schedule through the UI or setup tools.
   For vendors, the agent should share a direct integrations link such as
   `http://localhost:5180/projects/1/integrations?required=dataforseo,firecrawl`
   instead of asking for secrets in chat.
7. Run `01-bootstrap-project` or `08-add-new-site`.
8. Approve topics in the UI when a procedure pauses for human review.
9. Run `04-topic-to-published` for a single approved topic or
   `05-bulk-content-launch` for a batch.

Repository setup should not add content-stack files to the website repo unless
the operator explicitly asks for checked-in hints.

## Development

Useful commands from this repository:

```bash
make install          # Full local install pipeline
make serve            # Run daemon on 127.0.0.1:5180
make doctor           # Diagnose local install
make test             # Python test suite
make test-ui-unit     # UI unit tests
make test-ui-e2e      # UI e2e tests
make lint             # Lint checks
make build-ui         # Build UI bundle
```

For focused Python tests:

```bash
uv run pytest tests/integration/test_procedure_runner/test_agent_led_controller.py
```

## Troubleshooting

### MCP says connection refused

The daemon is not listening yet, or the plugin bridge could not auto-start it.

```bash
make serve
make doctor
```

Then restart the agent client.

### Plugin is installed but unavailable

Restart Codex or Claude Code after install. In Codex, run `/plugins` and make
sure `content-stack` is enabled.

### Token mismatch after rotation

Restart the daemon and agent client. The daemon reads the token at startup.

### Website repo is not detected

Run from the website repository root. The agent should resolve workspace
context and then call `workspace.connect` if no binding exists.

### Publish refuses because the target repo is dirty

The static publishing skills are designed to avoid clobbering local changes.
Commit, stash, or clean the target repository, then rerun or resume the
procedure.

### Vendor credentials are missing

Keep credentials in content-stack, not in the website repo. Add them through
the UI or daemon setup tools, then rerun the affected step. Mocked or skipped
vendor calls are acceptable in development flows, but production procedures
should use real configured integrations.

## Documentation Map

- `PLAN.md`: canonical product and implementation spec.
- `docs/architecture.md`: system architecture and invariants.
- `docs/procedures-guide.md`: procedure authoring contract and examples.
- `docs/extending.md`: adding skills, procedures, integrations, MCP tools, and
  REST routes.
- `docs/api-keys.md`: vendor credential setup.
- `docs/security.md`: local security model.
- `docs/upgrade.md`: upgrade, rollback, and migration notes.
- `PRIVACY.md`: data handling and outbound calls.
- `CHANGELOG.md`: release history.

## Current Status

The project is designed around the plugin-first, repo-agnostic flow:

- Install content-stack once on the machine.
- Start agents from whichever website repository needs work.
- Let the current agent drive procedures using plugin skills and MCP tools.
- Keep durable state, credentials, and audit history in the local daemon.
- Improve procedures and skills over time without polluting website repos.
