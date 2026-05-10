# SEO Stack

SEO content operations for teams who want an AI agent to research, write,
publish, and refresh content without losing control of the process.

SEO Stack lets you open Codex or Claude Code inside any website repository and
ask for normal marketing work:

- "Find content opportunities for this site."
- "Turn these keywords into an article plan."
- "Write and publish the next approved article."
- "Tell me which old pages need a refresh."
- "Set up WordPress publishing and tell me what credentials are missing."

The agent does the work. SEO Stack keeps the memory: projects, topics, drafts,
images, links, schema, publishing targets, credentials, approvals, and the
history of what happened.

You do not need to teach every website repo about SEO Stack. Install it once,
start the agent from the site you are working on, and let the agent connect
that site to the local SEO workspace.

## Table of Contents

- [Install](#install)
- [Quick Start](#quick-start)
- [What You Can Ask For](#what-you-can-ask-for)
- [How It Works](#how-it-works)
- [Article Creation Flow](#article-creation-flow)
- [Site Workflows](#site-workflows)
- [Operations Console](#operations-console)
- [Integrations](#integrations)
- [Publishing](#publishing)
- [Requirements](#requirements)
- [Uninstall](#uninstall)
- [Troubleshooting](#troubleshooting)
- [Technical Reference](#technical-reference)

## Install

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

`make install` sets up the local app, database, plugin, agent connection, and
doctor checks. It is safe to rerun.

### Codex Token Setup

Codex reads the local app token from an environment variable. Add this after
install:

```bash
export CONTENT_STACK_TOKEN="$(cat ~/.local/state/content-stack/auth.token)"
```

Restart Codex after install so it reloads plugins and tools.

### Optional Auto-Start On macOS

```bash
make install-launchd
```

Foreground mode with `make serve` still works fine.

### Package Install

Once a package release is available:

```bash
pipx install content-stack
content-stack install
content-stack serve
```

## Quick Start

Start from the website repository, not from the SEO Stack repository.

```bash
cd /path/to/your-site
codex
```

Then ask:

```text
Connect this repo to SEO Stack and set up the project.
```

After that, you can ask for real work:

```text
Find content opportunities and build a topic queue.
```

```text
Take the next approved topic and publish the article.
```

```text
Review Search Console and tell me what needs attention.
```

If a vendor connection is missing, the agent should send you a link to the
right setup screen, for example:

```text
http://localhost:5180/projects/1/integrations?required=dataforseo,firecrawl,gsc
```

Secrets belong in the console setup flow, not in chat and not in the website
repository.

## What You Can Ask For

| Ask For | What SEO Stack Helps The Agent Do |
| --- | --- |
| Set up a new site | Create the project, connect the repo, define voice, compliance, authors, integrations, schedules, and publishing. |
| Find content ideas | Research keywords, competitors, SERPs, audience questions, and topic clusters. |
| Plan an article | Create the title, angle, search intent, outline, source list, schema plan, and image plan. |
| Write an article | Draft the article in sections, edit it, humanize it, and check it against quality gates. |
| Create SEO assets | Generate image prompts/assets, write alt text, and keep image metadata organized. |
| Add schema | Create and validate JSON-LD for the article. |
| Improve internal links | Suggest links between related articles and repair stale links. |
| Publish content | Push to a static content repo, WordPress, or Ghost and record the publish result. |
| Refresh old pages | Find decaying content, snapshot the old version, update the page, and republish. |
| Monitor the site | Review Search Console, crawl issues, page drift, and refresh opportunities. |

## How It Works

Think of SEO Stack as a local workspace for SEO operations.

```text
You talk to the agent in a website repo
        |
        v
The SEO Stack plugin gives the agent the right tools
        |
        v
The local SEO Stack app remembers projects, credentials, content, and runs
        |
        v
The console lets you review, approve, configure, and debug
```

The important part: **you stay in the loop**. The agent can write, research,
publish, and call specialist tools, but SEO Stack keeps the work visible and
recoverable.

The local app stores:

- Sites and repository bindings.
- Topic queues and clusters.
- Briefs, drafts, edited content, sources, images, schema, and versions.
- Publishing targets and publish records.
- Vendor credentials and integration status.
- Work history, errors, approvals, and resumable runs.

Website repositories do not need SEO Stack config files unless you explicitly
want to add project-specific notes.

## Article Creation Flow

The article workflow is described in plain English inside the product. The
technical step names are listed later for maintainers.

| Step | Plain-English Meaning |
| --- | --- |
| Research the article | Understand the keyword, search intent, competitors, sources, and angle. |
| Build the structure | Create the H1/H2/H3 plan and decide what each section must prove. |
| Write the opening | Explain the promise of the article and why the reader should keep going. |
| Write the main sections | Draft the substance section by section using the research and source plan. |
| Write the ending | Close the loop, summarize the decision, and include any required disclosure or reference footer. |
| Edit for quality | Remove weak claims, improve flow, tighten headings, and check usefulness. |
| Make it sound natural | Remove robotic phrasing and align the piece with the site's voice. |
| Check trust signals | Score the article for experience, expertise, authority, and trust. |
| Create images | Generate or attach hero, inline, and social images when needed. |
| Check image accessibility | Audit alt text, dimensions, format, and placement. |
| Add structured data | Create article schema so search engines understand the page. |
| Suggest internal links | Find relevant pages to link to and from. |
| Publish | Send the final article to the selected publishing target. |

The quality gate can return:

| Result | Meaning |
| --- | --- |
| Ship | The article is ready to publish. |
| Fix | The article needs another edit pass. |
| Block | The article should not publish until a serious issue is resolved. |

## Site Workflows

| Workflow | Plain-English Name | What It Does |
| --- | --- | --- |
| New site setup | Set up this site | Connects the repository and prepares voice, compliance, authors, integrations, schedules, and publishing. |
| Existing site import | Bring this site into SEO Stack | Pulls an existing site into the topic and content workflow. |
| Keyword planning | Turn keywords into content ideas | Converts seed keywords and competitor inputs into a topic queue. |
| Article production | Write and publish one article | Takes one approved topic through research, writing, quality checks, assets, links, schema, and publishing. |
| Batch launch | Publish a batch carefully | Runs multiple article workflows while keeping progress and approvals visible. |
| Weekly review | Find this week's SEO opportunities | Reviews Search Console, crawl issues, drift, and internal-link opportunities. |
| Monthly refresh | Keep content from going stale | Finds older pages that need updates, refreshes them, and republishes. |
| Add another site | Add a new site to the workspace | Connects another repo/project without changing the current site setup. |

## Operations Console

The console runs at:

```text
http://localhost:5180
```

Use it to:

- Create and manage projects.
- Connect integrations.
- Review and approve topics.
- Inspect clusters and content plans.
- Track article status.
- Edit briefs, drafts, sources, images, schema, and publish records.
- Review internal-link suggestions.
- Inspect Search Console data.
- Track drift and refresh candidates.
- Debug agent runs.

## Integrations

Integrations are optional. Connect only what a project needs.

| Integration | What It Helps With |
| --- | --- |
| DataForSEO | Keyword ideas, SERP data, and ranking intelligence. |
| Firecrawl | Crawling pages and capturing live page state. |
| Google Search Console | Queries, clicks, indexing, crawl inspection, and refresh opportunities. |
| OpenAI Images | Hero images, inline images, and social previews. |
| Reddit | Audience language, pain points, and question mining. |
| Google People Also Ask | Question discovery and intent expansion. |
| Jina Reader | Clean extraction when pages are hard to parse. |
| Ahrefs exports | Competitor and sitemap inputs when you already have exports. |

The agent should tell you which integrations are useful for the task and link
you to the setup page.

## Publishing

SEO Stack supports target-based publishing. A project has one primary target
and can have optional secondary targets.

| Target | What Happens |
| --- | --- |
| Static content repo | Writes markdown/frontmatter and assets into a local content repository, then records the publish. |
| WordPress | Uploads media and creates or updates posts through the WordPress API. |
| Ghost | Uploads images and creates or updates posts through the Ghost Admin API. |

Publishing targets keep their own settings: content folder, image folder,
branch, remote, URL pattern, frontmatter template, API endpoint, and credential
reference.

## Requirements

- Python 3.12 or newer.
- `uv` for clone-mode development.
- Node package tooling when changing `ui/`.
- Codex CLI and/or Claude Code for agent access.
- Optional macOS launchd for auto-start.
- Vendor accounts only for integrations you enable.

## Uninstall

Remove installed plugin, skills, procedures, MCP entries, and launchd job while
preserving the local database, seed, and auth token:

```bash
make uninstall
```

State is preserved under:

```text
~/.local/share/content-stack/
~/.local/state/content-stack/
```

## Troubleshooting

### The agent says SEO Stack is unavailable

Start the local app:

```bash
make serve
make doctor
```

Then restart Codex or Claude Code.

### The plugin is installed but not showing up

Restart the agent client. In Codex, run:

```text
/plugins
```

The installed plugin should be named `content-stack`.

### The token was rotated

Restart the local app and the agent client. The app reads the token at startup.

### The site repo is not detected

Run the agent from the website repository root and ask it to connect the repo
again.

### Publishing refuses because the target repo is dirty

SEO Stack avoids overwriting uncommitted local changes. Commit, stash, or clean
the target repository, then rerun or resume the publish step.

### Vendor credentials are missing

Add credentials through the console integrations page. Mocked or skipped vendor
calls are fine for development, but production workflows should use configured
integrations.

## Technical Reference

The top of this README uses product language. This section keeps the exact
implementation names for developers and agent maintainers.

### Architecture

| Component | Path | Role |
| --- | --- | --- |
| Local app / daemon | `content_stack/` | FastAPI app, repositories, integrations, MCP tools, jobs, and CLI. |
| Database | `~/.local/share/content-stack/content-stack.db` | Local state for projects, content, credentials, runs, and publish records. |
| Plugin | `plugins/content-stack/` | Repo-agnostic Codex/agent plugin. |
| Skills | `skills/` | Agent-readable task guidance. |
| Procedures | `procedures/` | Playbooks with durable step state. |
| UI source | `ui/` | Vue operations console. |
| Packaged UI | `content_stack/ui_dist/` | Built console assets served by the local app. |
| Docs | `docs/` | Architecture, extending, procedures, security, upgrade, and vendor setup. |

### Developer Commands

Useful commands:

```bash
make install          # Full local install pipeline
make serve            # Run the local app on 127.0.0.1:5180
make doctor           # Diagnose local install
make test             # Python tests + UI unit tests
make test-ui-unit     # Vitest unit tests
make test-ui-e2e      # Playwright e2e tests
make lint             # Ruff checks
make typecheck        # Mypy
make build-ui         # Build UI bundle into content_stack/ui_dist/
make gen-types        # Regenerate ui/src/api.ts from the local API spec
```

Focused UI checks:

```bash
pnpm --dir ui type-check
pnpm --dir ui lint
pnpm --dir ui test
pnpm --dir ui build
```

Restart after backend, token, or packaged UI changes:

```bash
content-stack restart
content-stack restart --force
```

### Exposed Agent Tools

These tools are visible to the agent at startup:

| Tool | Plain-English Use |
| --- | --- |
| `workspace.startSession` | Start work from the current website repo. |
| `workspace.resolve` | Check whether this repo is already connected. |
| `workspace.connect` | Connect this repo to a project. |
| `workspace.listBindings` | Show repo-to-project bindings. |
| `workspace.updateProfile` | Update saved repo profile hints. |
| `project.list` | List SEO projects. |
| `project.create` | Create a project. |
| `project.get` | Read one project. |
| `project.update` | Update project details. |
| `project.setActive` | Mark a project as active in the UI. |
| `project.getActive` | Read the active project. |
| `meta.enums` | Read legal statuses and enum values. |
| `procedure.list` | List available playbooks. |
| `procedure.run` | Start a playbook run. |
| `procedure.status` | Check playbook progress. |
| `procedure.resume` | Resume a paused run. |
| `procedure.fork` | Fork a run from an earlier step. |
| `procedure.currentStep` | See the current step package. |
| `procedure.claimStep` | Claim the next step for the agent to perform. |
| `procedure.recordStep` | Save the result of a completed step. |
| `procedure.executeProgrammaticStep` | Run a built-in non-writing step. |
| `run.get` | Read one run. |
| `run.list` | List runs. |
| `run.heartbeat` | Keep a run marked alive while work continues. |
| `run.abort` | Stop a run. |
| `toolbox.describe` | Inspect hidden setup or step-specific tools. |
| `toolbox.call` | Call one hidden setup or step-specific tool. |

### Setup Tools Available Through The Toolbox

These are not shown as direct tools, but the agent can call them through
`toolbox.call` during setup:

| Tool | Plain-English Use |
| --- | --- |
| `integration.list` | List connected vendors. |
| `integration.set` | Add or update vendor credentials. |
| `integration.test` | Test a vendor connection. |
| `integration.testGsc` | Test Google Search Console access. |
| `integration.remove` | Remove a vendor credential. |
| `voice.set` | Save the site's writing voice. |
| `voice.get` | Read the active writing voice. |
| `voice.listVariants` | List available voice variants. |
| `voice.setActive` | Choose the active voice. |
| `target.list` | List publishing targets. |
| `target.add` | Add a publishing target. |
| `target.update` | Update a publishing target. |
| `target.remove` | Remove a publishing target. |
| `target.setPrimary` | Choose the primary publishing target. |
| `compliance.list` | List disclosure/compliance rules. |
| `compliance.add` | Add a compliance rule. |
| `compliance.update` | Update a compliance rule. |
| `compliance.remove` | Remove a compliance rule. |
| `eeat.list` | List quality criteria. |
| `eeat.toggle` | Enable or disable a criterion where allowed. |
| `eeat.bulkSet` | Update criteria in bulk. |
| `schedule.list` | List schedules. |
| `schedule.set` | Add or update a schedule. |
| `schedule.toggle` | Enable or disable a schedule. |
| `sitemap.fetch` | Fetch and store sitemap URLs. |

Playbook steps can expose additional step-specific tools through the same
toolbox. The agent receives those grants only when the current step needs them.

### Internal Skill Names

| User-Friendly Name | Internal Skill |
| --- | --- |
| Find keyword ideas | `keyword-discovery` |
| Analyze search results | `serp-analyzer` |
| Import competitor sitemap ideas | `competitor-sitemap-shortcut` |
| Build topic clusters | `topical-cluster` |
| Create the article plan | `content-brief` |
| Build the article structure | `outline` |
| Write the opening | `draft-intro` |
| Write the main sections | `draft-body` |
| Write the ending | `draft-conclusion` |
| Edit for quality | `editor` |
| Make it sound natural | `humanizer` |
| Check trust and expertise | `eeat-gate` |
| Create images | `image-generator` |
| Audit image alt text | `alt-text-auditor` |
| Create structured data | `schema-emitter` |
| Suggest internal links | `interlinker` |
| Publish to a static repo | `nuxt-content-publish` |
| Publish to WordPress | `wordpress-publish` |
| Publish to Ghost | `ghost-publish` |
| Find Search Console opportunities | `gsc-opportunity-finder` |
| Watch for live page drift | `drift-watch` |
| Watch crawl/indexing problems | `crawl-error-watch` |
| Detect content that needs refresh | `refresh-detector` |
| Refresh an existing article | `content-refresher` |

### Internal Procedure Names

| User-Friendly Workflow | Internal Procedure |
| --- | --- |
| Set up this site | `01-bootstrap-project` |
| Bring one existing site into SEO Stack | `02-one-site-shortcut` |
| Turn keywords into content ideas | `03-keyword-to-topic-queue` |
| Write and publish one article | `04-topic-to-published` |
| Launch a batch of articles | `05-bulk-content-launch` |
| Run the weekly SEO review | `06-weekly-gsc-review` |
| Refresh/humanize old content monthly | `07-monthly-humanize-pass` |
| Add another site | `08-add-new-site` |

### Documentation Map

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
