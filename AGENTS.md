# content-stack agent notes

## Content-Stack Tooling Architecture

The daemon owns the full MCP catalog for the UI, tests, jobs, and automation.
The installable Codex plugin must not expose that full catalog to agents. It
talks to the daemon through `content-stack mcp-bridge`, which keeps the
agent-facing surface intentionally small.

### Relationship Map

- `content_stack/mcp/tools/*` registers the daemon's full internal tool catalog.
- `content_stack/mcp/bridge.py` filters that catalog for plugin clients.
- `_AGENT_VISIBLE_TOOL_ORDER` is the direct tool surface: workspace/project
  setup, procedure/run control, and status inspection.
- `toolbox.describe` and `toolbox.call` are bridge-local virtual tools. They
  are the only path from the plugin to hidden daemon tools.
- `_AGENT_SETUP_TOOLBOX_NAMES` lists setup helpers that can be described/called
  through the toolbox without a procedure step, such as `integration.set`,
  `integration.test`, `target.add`, `voice.set`, and `sitemap.fetch`.
- `content_stack/mcp/permissions.py` is the grant matrix for step-scoped hidden
  tools. `procedure.claimStep` binds the run token to the current skill; the
  bridge refreshes that step and injects the token only when `toolbox.call`
  targets one of that step's granted tools.
- `skills/**/SKILL.md` frontmatter `allowed_tools` must mirror the permission
  grant for that skill, and the prompt must name the actual hidden tool names.

### Direct Tools vs Toolkit Tools

Direct tools are only for navigation and orchestration: resolve/connect the
workspace, create/select a project, start/resume/fork/abort a procedure,
inspect/claim the current step, record the step result, and check run status.

Hidden daemon tools are called through the toolkit:

1. Call `toolbox.describe` with exact hidden tool names, or with `run_id` to
   inspect the active step's available tools.
2. Call `toolbox.call` with `tool_name`, `arguments`, and `run_id` for
   step-scoped tools.
3. Let the bridge inject `run_token`; do not ask the agent or skill prompt to
   pass it manually for claimed procedure steps.

Do not add operational tools to `_AGENT_VISIBLE_TOOL_ORDER` unless they are
workspace/project/procedure/run controls. Article, asset, source, publishing,
compliance, GSC, cost, and external-vendor operations belong behind
`toolbox.call`.

### External Vendor Pattern

External integrations such as DataForSEO, Firecrawl, GSC, OpenAI Images,
Reddit, Jina, Ahrefs, WordPress, and Ghost must follow this relationship:

- `content_stack/integrations/*` contains the vendor wrapper: auth, retries,
  rate limits, budget checks, cost logging, and vendor-specific request shape.
- `content_stack/mcp/tools/*` may expose a thin daemon operation such as
  `dataforseo.serp`, `firecrawl.scrape`, or `openaiImages.generate`.
- Those operation tools stay hidden from the direct plugin list. Do not add
  vendor operations to `_AGENT_VISIBLE_TOOL_ORDER`.
- `content_stack/mcp/permissions.py` grants the hidden vendor operation only to
  the skill that needs it.
- The skill's frontmatter lists that same operation in `allowed_tools`, and the
  prompt tells the agent to use `toolbox.describe` / `toolbox.call`.
- When a vendor returns non-URL artifacts, the daemon wrapper must normalize
  them before skill state is written. For example, OpenAI Images GPT models
  return base64 image data; `openaiImages.generate` persists that data under
  `generated-assets` and returns `/generated-assets/...` URLs for
  `asset.create`.

If a prompt mentions an external operation, the actual callable hidden tool must
exist and be granted. Do not tell the agent to call Python wrapper classes,
native network fetches, browser fetches, or imaginary vendor methods.

### Article Writing Flow

Procedure 4, `04-topic-to-published`, is the canonical article flow. The agent
uses direct bridge tools to start/resume the run, then repeats this per step:

1. `procedure.currentStep` or `procedure.claimStep` returns the step package.
2. The agent reads the referenced skill and its `allowed_tools`.
3. The agent calls hidden tools through `toolbox.describe` and `toolbox.call`.
4. The skill writes durable state through the hidden article/source/asset/schema
   tools granted to that step.
5. The agent finishes the step with `procedure.recordStep`.

The procedure-4 step order is:

1. `01-research/content-brief` creates or resumes the article, collects source
   evidence through granted vendor tools when needed, persists
   `articles.brief_json`, and writes `research_sources`.
2. `02-content/outline` turns the brief into the section contract.
3. `02-content/draft-intro`, `02-content/draft-body`, and
   `02-content/draft-conclusion` assemble `articles.draft_md`.
4. `02-content/editor` writes `articles.edited_md`.
5. `02-content/humanizer` makes the final voice pass.
6. `02-content/eeat-gate` returns `SHIP`, `FIX`, or `BLOCK`; `FIX` loops back
   to `editor`, while `BLOCK` aborts the run.
7. `03-assets/image-generator` and `03-assets/alt-text-auditor` are skippable
   quality steps.
8. `04-publishing/schema-emitter` writes JSON-LD.
9. `04-publishing/interlinker` emits internal-link suggestions and is skippable.
10. `publish` defaults to `04-publishing/agent-publish`: the main operator
    agent publishes through whatever external repo/API/DB/tooling is available,
    then records the targetless result with `publish.recordExternal`.
    If the project has a primary active target whose kind is fully wired, the
    runner swaps the step package to that concrete publisher. Today only
    `nuxt-content` is auto-swapped. WordPress and Ghost have doc-backed
    credential probes and wrapper foundations, but they must not be used as
    primary procedure publishers until their media/post operations are exposed
    behind `toolbox.call` and granted to the publish skills.

The daemon stores state and enforces grants; it does not spawn hidden writer
LLM sessions. The current operator agent is responsible for reading the skill,
doing the writing/thinking, calling the granted tools, and recording the step.

### Change Checklist

When changing any flow, update all of these together:

1. Daemon tool or integration wrapper.
2. Bridge visibility: direct only for orchestration, hidden for operations.
3. Permission grant in `content_stack/mcp/permissions.py`.
4. Skill frontmatter `allowed_tools`.
5. Skill/procedure prompt text that tells the agent which real tools to call.
6. Focused tests proving hidden tools are not advertised directly and are
   available through the toolbox only when granted.

## TPF Token Proxy Filter

Prefix shell commands with `TPF_LLM_TOOL=codex tpf` unless the command is one of:
`cd`, `echo`, `cat`, `head`, `tail`, `mkdir`, `rm`, `mv`, `cp`, `chmod`,
`pwd`, `export`, `source`, `set`, `unset`, `alias`, `read`, `printf`,
`test`, `true`, `false`, `which`, `touch`.

For piped commands, put the pipe in `TPF_PIPE`:

```bash
TPF_PIPE='head -20' TPF_LLM_TOOL=codex tpf git log --oneline
```

Do not wrap redirections, logical OR, background jobs, or subshells.

## Serena MCP

Use this project's dedicated Serena MCP server, not the shared/global `serena`
server:

- Codex MCP name: `serena-content-stack`
- URL: `http://localhost:9123/mcp`
- launchd label: `com.oraios.serena-mcp.content-stack`
- launchd plist: `~/Library/LaunchAgents/com.oraios.serena-mcp-content-stack.plist`
- project: `/Users/sergeyrura/Bin/content-stack`
- log: `~/Library/Logs/serena-mcp-content-stack.log`

Do not call `activate_project` on the shared `serena` MCP to switch it to
content-stack. That server is used by other projects and can expose stale
project memory. Do not write, rename, edit, or delete Serena memories unless
the user explicitly asks.
