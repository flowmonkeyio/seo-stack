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

## Operating Rules

1. Do not create `.env`, `.mcp.json`, `AGENTS.md`, `CLAUDE.md`, or
   `.content-stack/*` in the current repository unless the user explicitly asks
   for checked-in hints.
2. Start by resolving the current workspace with `workspace.startSession` or
   `workspace.resolve` using repo hints supplied by the plugin MCP bridge.
3. If no binding exists, guide the user through `workspace.connect`; the binding
   is stored in the daemon DB, not in the website repo.
4. Use content-stack MCP tools for durable writes and credential/publish
   operations. Use local repo inspection for templates, schemas, routes, tests,
   and build conventions.
5. For static/workspace publishing, apply rendered bundles in the current repo
   only after previewing and understanding the repository conventions.
6. For WordPress, Ghost, admin API, or direct DB publishing, let the daemon use
   stored credentials and record the publish result.

## Common Flows

- Connect repo: resolve workspace, create/select project, call
  `workspace.connect`, then inspect content conventions.
- Continue work: call `workspace.startSession`, resolve the project, then claim
  the next procedure step.
- Publish: preview through the daemon, apply or push via the selected publisher,
  run repo checks when files changed, and record the result.
