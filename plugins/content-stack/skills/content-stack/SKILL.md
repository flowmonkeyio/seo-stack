---
name: content-stack
description: Use when working from any website repository to connect the repo to content-stack, resolve the current project, run SEO content procedures, or publish through daemon-managed targets without writing setup files into the repo.
---

# content-stack Plugin Entrypoint

Use the current repository as source context and the local content-stack daemon
as durable state. The daemon owns projects, credentials, articles, procedure
runs, publish targets, and audit trails.

The plugin includes the full skill catalog under `skills/catalog/` and
procedures under `procedures/`. Treat those files as the local operating manual
for step-level SEO work; use the daemon's `procedure.*` and `workspace.*` tools
for durable state.

The MCP bridge intentionally exposes a compact direct tool list. Use direct
tools for workspace/project/procedure control. Use `toolbox.describe` to inspect
hidden setup or current-step tools, then `toolbox.call` to invoke exactly one
hidden tool by name. Do not try to call hidden daemon tools directly.

## Operating Rules

1. Do not create `.env`, `.mcp.json`, `AGENTS.md`, `CLAUDE.md`, or
   `.content-stack/*` in the current repository unless the user explicitly asks
   for checked-in hints.
2. Start by resolving the current workspace with `workspace.startSession` or
   `workspace.resolve` using repo hints supplied by the plugin MCP bridge.
3. If no binding exists, guide the user through `workspace.connect`; the binding
   is stored in the daemon DB, not in the website repo.
4. Use `toolbox.describe`/`toolbox.call` for credential, voice, compliance,
   EEAT, publish-target, schedule, sitemap, article, and publishing tools that
   are not in the direct list.
5. When a procedure needs missing vendor credentials, do not ask the user to
   paste secrets into chat. Name the missing vendors and give the user the
   project integrations URL:
   `http://localhost:5180/projects/{project_id}/integrations?required=<comma-separated-kinds>`.
   Use canonical kinds such as `dataforseo`, `firecrawl`, `gsc`,
   `openai-images`, `reddit`, `jina`, and `ahrefs`. After the user connects
   them in the UI, call `integration.test` / `integration.testGsc` through the
   toolbox before continuing.
6. For static/workspace publishing, apply rendered bundles in the current repo
   only after previewing and understanding the repository conventions.
7. For WordPress, Ghost, admin API, or direct DB publishing, let the daemon use
   stored credentials and record the publish result.

## Common Flows

- Connect repo: resolve workspace, create/select project, call
  `workspace.connect`, then inspect content conventions.
- Connect vendors: inspect the procedure or skill's needed integrations, share
  `/projects/{project_id}/integrations?required=...`, wait for the operator to
  connect them in the UI, then run the relevant health probes.
- Continue work: call `workspace.startSession`, resolve the project, then claim
  the next procedure step.
- Execute a step: read the step package, follow the referenced skill guidance,
  call `toolbox.describe` for needed `allowed_tools`, invoke them with
  `toolbox.call`, then `procedure.recordStep`.
- Publish: preview through the daemon, apply or push via the selected publisher,
  run repo checks when files changed, and record the result.
