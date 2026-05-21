# StackOS Current Setup Gap Analysis

## Purpose

This document maps the current `content-stack` implementation against the
StackOS pivot design in `docs/stackos-pivot-design-and-delivery-plan.md`.

The goal is not to throw away the current system. The daemon, MCP bridge, run
state, credential encryption, local UI, installer, and audit trail are valuable.
The main issue is product shape: SEO and rigid procedures are currently core
platform concepts. StackOS needs those to become plugin-owned capabilities while
core becomes a neutral tool runtime.

Critical boundary:

```text
Agent / human:
  decides strategy, selects context, interprets results, records decisions

StackOS:
  stores, retrieves, validates static contracts, enforces auth/grants/budgets,
  executes external actions, redacts, persists, and audits
```

StackOS should not infer durable learnings, decide which experiment won, choose
campaign structure, choose SEO angle, or optimize on its own.

## Executive Summary

Current setup is strong as a local single-user agent runtime, but the domain
model is SEO-first throughout:

- Product name, README, package metadata, CLI, default ports/dirs, plugin names,
  docs, and tests all describe SEO/content pipelines.
- Database models are mostly SEO tables: topics, clusters, articles, sources,
  schema, EEAT, GSC, drift, interlinks, publish targets, and article assets.
- MCP catalog has 163 tools, but most are domain-specific. The bridge hides
  them behind `toolbox.*`, yet setup grants still expose many SEO operations.
- `procedure.*` is the primary direct workflow surface. Procedures are static
  ordered playbooks, which conflicts with the desired reusable-template plus
  agent-authored-run-plan model.
- Auth storage is good at encryption, but the product API is still
  `integration.set` with plaintext ingestion. The pivot needs provider auth
  flows that never ask agents for secrets.
- UI is observer-first and well structured, but the navigation and views are
  hard-coded around SEO.
- Existing vendor wrappers are useful, but they should become provider actions
  behind a generic action executor and connector layer.

The recommended migration is additive first:

1. Add StackOS core tables and MCP tools beside the current SEO/procedure
   system.
2. Keep legacy `procedure.*`, `article.*`, `topic.*`, etc. as compatibility
   wrappers.
3. Move SEO into `plugins/seo` at the manifest/catalog level before physically
   moving every table.
4. Introduce project context, learnings, experiments, and workflow templates as
   generic storage/retrieval primitives.
5. Port one utility action and one media buying action to prove the new model.
6. Only then rename package/CLI/data directories beyond compatibility aliases.

## Current Inventory

### Runtime Pieces Worth Keeping

These are already aligned with StackOS core:

- Local FastAPI daemon in `content_stack/server.py`.
- Loopback-only binding, bearer-token middleware, and same-origin UI model.
- SQLite/WAL local persistence.
- Alembic migrations and SQLModel models.
- MCP registry/dispatcher in `content_stack/mcp/server.py`.
- Plugin-facing MCP bridge in `content_stack/mcp/bridge.py`.
- Run audit primitives in `runs`, `run_steps`, `run_step_calls`, and
  `idempotency_keys`.
- Encrypted credential storage foundation in `integration_credentials`.
- Cost/rate budget foundation in `integration_budgets`.
- Scheduler foundation in `content_stack/jobs`.
- Install/hydration logic in `content_stack/install.py`.
- Read-only/observer UI principle documented in `docs/ui-design-system.md`.

### Current SEO Core

These should become SEO plugin ownership:

- API routers: `articles`, `clusters`, `topics`, `gsc`, `interlinks`, large
  parts of `projects`, and `procedures`.
- Repositories: `articles`, `clusters`, `eeat`, `gsc`, `interlinks`, and SEO
  parts of `projects`.
- DB models: `Cluster`, `Topic`, `Article`, `ArticleVersion`,
  `ArticleAsset`, `ArticlePublish`, `InternalLink`, `ResearchSource`,
  `SchemaEmit`, `DriftBaseline`, `GscMetric`, `GscMetricDaily`,
  `EeatCriterion`, `EeatEvaluation`, `Redirect`, `VoiceProfile`, `Author`,
  `ComplianceRule`, and `PublishTarget`.
- MCP tools: `article.*`, `asset.*`, `cluster.*`, `topic.*`, `source.*`,
  `schema.*`, `publish.*`, `interlink.*`, `eeat.*`, `gsc.*`, `drift.*`,
  `redirect.*`, `sitemap.fetch`, and SEO-specific setup helpers.
- Skills under `skills/01-research`, `skills/02-content`, `skills/03-assets`,
  `skills/04-publishing`, and `skills/05-ongoing`.
- Top-level `procedures/*`.
- UI views/stores: Clusters, Topics, Articles, GSC, Drift, Interlinks,
  Procedures, article-detail tabs, and project setup tabs for voice,
  compliance, EEAT, targets, schedules.

### Current Tool Catalog Shape

Current MCP tool prefix count:

```text
TOTAL: 163

SEO/domain:
  article: 18
  topic: 8
  cluster: 3
  asset: 4
  source: 3
  schema: 4
  publish: 4
  interlink: 6
  eeat: 8
  gsc: 9
  drift: 4
  redirect: 3
  author: 5
  voice: 4
  compliance: 4
  target: 5
  sitemap: 1

Runtime/control:
  workspace: 5
  project: 8
  run: 14
  procedure: 9
  schedule: 4
  budget: 4
  cost: 2
  integration: 5
  meta: 1

Provider/utility:
  dataforseo: 5
  ahrefs: 2
  firecrawl: 4
  googlePaa: 1
  jina: 1
  openaiImages: 1
  reddit: 2
  gscOauth: 2
```

This confirms the bridge is compacting a very SEO-specific internal catalog,
not exposing a generic StackOS catalog yet.

## Target Layering

The future setup should be:

```text
StackOS Core
  projects/workspaces
  plugin registry
  capability/action/provider catalog
  auth and credential refs
  generic action executor
  generic resources and artifacts
  project context and event timeline
  learnings, experiments, decisions, metrics
  workflow templates and run plans
  runs, steps, calls, schedules, costs, budgets
  MCP bridge and UI shell

Plugins
  seo
  utils
  media-buying
  gtm
  private/internal

Connectors
  DataForSEO
  Ahrefs
  Firecrawl
  GSC
  OpenAI Images
  Meta Ads
  Taboola
  Outbrain
  internal APIs
```

Execution path:

```text
Agent goal
  -> select workflow template
  -> query project context with bounded filters
  -> produce run plan
  -> StackOS checks static grants/schemas/auth/budgets
  -> agent executes actions through StackOS
  -> StackOS stores redacted traces/resources/artifacts
  -> agent/human records decisions, observations, learnings
```

## Target Repository Architecture

The repo should separate runtime primitives from domain plugins. The current
single `content_stack` package can remain during migration, but ownership should
be clear in the file layout.

Target source layout:

```text
content_stack/
  core/
    settings.py
    server.py
    security.py
    redaction.py
    pagination.py
    errors.py
  db/
    models_core.py
    models_legacy_seo.py
    migrations/
  api/
    core/
      projects.py
      plugins.py
      catalog.py
      auth.py
      actions.py
      resources.py
      artifacts.py
      context.py
      workflows.py
      runs.py
      schedules.py
      costs.py
    legacy_seo/
      articles.py
      topics.py
      clusters.py
      gsc.py
      interlinks.py
  mcp/
    server.py
    bridge.py
    permissions.py
    tools/
      core/
      compatibility/
  plugins/
    manifest.py
    registry.py
    loader.py
    contributions.py
  actions/
    manifest.py
    executor.py
    connectors.py
  auth_providers/
    registry.py
    oauth.py
    api_key.py
  workflows/
    template_schema.py
    template_loader.py
    run_plan_schema.py
    runner.py
  context/
    query.py
    timeline.py
    snapshots.py
  resources/
    repository.py
    schemas.py
  artifacts/
    repository.py
    storage.py
  repositories/
    core/
    compatibility/
```

Target plugin asset layout:

```text
plugins/
  stackos-agent/
    .codex-plugin/
    .claude-plugin/
    .mcp.json
    skills/stackos/SKILL.md

  seo/
    plugin.yaml
    resources/
    capabilities/
    providers/
    actions/
    workflows/
    skills/
    ui/
      nav.yaml
      resource_views.yaml
    docs/

  utils/
    plugin.yaml
    providers/
    actions/
    workflows/
    docs/

  media-buying/
    plugin.yaml
    resources/
    capabilities/
    providers/
    actions/
    workflows/
    ui/
      nav.yaml
      resource_views.yaml
    docs/
```

The important boundary is that `plugins/<domain>` should contain static
definitions: schemas, capabilities, action manifests, workflow templates, skill
instructions, and optional UI contributions. It should not contain hidden
business logic that makes decisions instead of the agent.

Migration-friendly layout:

```text
content_stack/api/legacy_seo/
content_stack/mcp/tools/compatibility/
content_stack/repositories/legacy_seo/
```

This lets the codebase express ownership before every import path is renamed.
Existing routes/tools can be re-exported from compatibility modules while tests
move toward core/plugin boundaries.

## Generic UI Architecture

The UI should not maintain a bespoke page for every workflow. That would simply
replace hard-coded procedures with hard-coded templates. The UI should instead
render a few generic primitives well.

Core UI primitives:

```text
PluginCatalogView
  installed plugins, enabled project plugins, contribution status

CapabilityCatalogView
  searchable capabilities, providers, actions, schemas

AuthConnectionsView
  provider connection status, setup links, scopes, accounts

ResourceExplorerView
  generic list/detail view for plugin resources

ArtifactExplorerView
  generated and imported files/blobs with provenance

WorkflowTemplatesView
  reusable templates with schema, context requirements, policies, outputs

TemplateDetailView
  rendered template sections from manifest/schema, not custom code

RunPlansView
  concrete resolved plans, approval gates, selected context, action drafts

RunDetailView
  execution trace, steps, action calls, artifacts, observations, decisions

ProjectContextView
  context queries, timeline, context snapshots

LearningsView
  learning records with tags, evidence, confidence, review state

ExperimentsView
  experiment records, variants, observations, decisions
```

Plugin UI contributions should be constrained:

- plugins may add navigation entries
- plugins may declare resource columns, filters, detail sections, and metric
  cards
- plugins may provide labels, icons, grouping, and route metadata
- plugins should not ship arbitrary workflow-specific Vue pages as the default
  pattern
- bespoke plugin views are allowed only for high-value operational dashboards
  that cannot be represented by generic resource/template/run renderers

This gives a practical rule:

```text
Workflow UI:
  generic, template/run-plan driven

Resource UI:
  generic by default, plugin-configurable columns/sections

Plugin dashboards:
  rare, explicit exceptions
```

Suggested UI contribution manifest:

```yaml
plugin: media-buying
nav:
  - label: Media Buying
    items:
      - label: Campaigns
        resource: media.campaign
      - label: Creatives
        resource: media.creative
      - label: Experiments
        route: /projects/:id/experiments?domain=media-buying

resource_views:
  media.campaign:
    list:
      columns:
        - key: name
          label: Campaign
        - key: provider
          label: Provider
        - key: status
          label: Status
        - key: budget
          label: Budget
        - key: created_at
          label: Created
      filters:
        - key: provider
          type: select
        - key: status
          type: select
    detail:
      sections:
        - id: summary
          type: description_list
          fields:
            - name
            - provider
            - external_id
            - status
        - id: raw
          type: json
          field: data_json
```

Generic template rendering:

```text
TemplateDetailView
  Header: name, plugin, version, owner, source, enabled state
  Fit: when_to_use, not_for
  Inputs: required and optional input schemas
  Context: context_requirements rendered as bounded queries
  Capabilities: required/preferred capabilities and provider requirements
  Stages: purpose, agent instructions, allowed capabilities, expected outputs
  Policies: static checks and approval gates
  Experiment support: hypothesis/variant/metric requirements
  Outputs: declared output contracts and learning hooks
```

Generic run-plan rendering:

```text
RunPlanDetailView
  Goal and selected template
  Resolved inputs
  Selected context snapshot
  Resolved providers and credential refs
  Stage checklist
  Action draft table
  Approval gates
  Expected resources/artifacts
  Risk notes
      Sanitized raw JSON only
```

Generic run rendering:

```text
RunDetailView
  Summary
  Resolved plan snapshot
  Context snapshot used
  Step timeline
  Action calls with redacted request/response
  Created/updated resources
  Artifacts
  Observations
  Decisions
  Proposed/linked learnings
  Linked experiments
  Raw metadata
```

The current `RunDetail.vue` already points to the right need: it struggles
because only procedure runs expose rich step state. StackOS should fix this in
the backend by making run-plan steps generic, then the UI can render every run
the same way.

## Agent Instruction Architecture

`AGENTS.md` should be rewritten around StackOS boundaries, not SEO procedures.
It should tell agents how to use the repo and runtime without teaching
domain-specific business decisions.

Root `AGENTS.md` should cover:

- command conventions and local development commands
- StackOS tool-runtime boundary
- agents own reasoning; StackOS owns storage/execution/audit
- no secrets in chat or prompts
- prefer generic core modules for runtime work
- keep SEO code behind compatibility/plugin boundary
- UI is observer/control-plane by default
- workflow UI is generic template/run rendering
- plugin UI contributions are manifest-driven
- tests required for core surfaces, redaction, permissions, and UI contracts

Plugin-local instruction files can add domain conventions:

```text
plugins/seo/AGENTS.md
plugins/media-buying/AGENTS.md
plugins/utils/AGENTS.md
```

These should describe resource/action/template conventions, not hard-coded
business strategy. For example, a media-buying plugin may state that write
actions must default to paused provider objects unless the agent's run plan and
approval explicitly request active spend. It should not decide which campaign
structure is best.

## What Should Change By Area

### 1. Naming And Compatibility

Current state:

- `pyproject.toml` package name is `content-stack`.
- CLI command is `content-stack`.
- Default data/state dirs are `~/.local/share/content-stack` and
  `~/.local/state/content-stack`.
- FastAPI app title/description are SEO/content oriented.
- Installable plugin name is `content-stack`.
- README is `# SEO Stack`.

Change:

- Introduce StackOS product/runtime naming in docs and UI first.
- Add `stackos` CLI alias while keeping `content-stack`.
- Keep existing data/state dirs during the migration, or support both with a
  clear migration command later.
- Keep current package import path initially. A Python package rename is high
  blast radius and should come after the data/model migration stabilizes.
- Rename plugin display metadata from SEO/content language to StackOS runtime
  language.

Do not change immediately:

- Do not rename DB paths or CLI as a first step. That creates migration churn
  without unlocking the architecture.

### 2. Plugin Registry

Current state:

- There is an installable Codex/Claude plugin package under
  `plugins/content-stack`, but no runtime plugin registry in the daemon.
- `content_stack/install.py` mirrors global `skills`, `procedures`, and
  `plugins`.
- Runtime tools are registered by importing Python modules in
  `content_stack/mcp/tools/__init__.py`.

Change:

- Add daemon-side tables:
  - `plugins`
  - `project_plugins`
  - `capabilities`
  - `providers`
  - `actions`
  - `action_versions`
- Add plugin manifest parsing, independent of Codex/Claude plugin manifests.
- Add `plugin.list`, `plugin.enable`, `plugin.disable`, `catalog.list`, and
  `catalog.describe`.
- Represent SEO as a built-in plugin first, even if the implementation still
  points at current tables/tools.

Suggested plugin manifest roots:

```text
plugins/stackos/              # installable agent plugin package
plugins/seo/plugin.yaml       # daemon plugin manifest
plugins/utils/plugin.yaml
plugins/media-buying/plugin.yaml
```

Important distinction:

- Codex/Claude plugin manifests install the agent integration.
- StackOS plugin manifests describe domain capabilities inside the daemon.

### 3. Generic Resources And Artifacts

Current state:

- SEO resources are represented by dedicated tables.
- `ArticleAsset` and `ResearchSource` are article-scoped.
- Generated image files live under `generated-assets`, but artifact ownership is
  still SEO-shaped.

Change:

- Add:
  - `resources`
  - `resource_records`
  - `artifacts`
- Keep typed SEO tables for now, but register them as SEO resources in the
  catalog.
- Introduce generic `resource.get`, `resource.query`, `resource.upsert`,
  `artifact.create`, `artifact.get`, and `artifact.query`.
- Let plugins define resource schemas while StackOS stores raw records and
  provider refs.

Migration rule:

- Do not force every existing SEO table into generic JSON immediately.
  Start with catalog registration and compatibility aliases.

### 4. Auth And Credentials

Current state:

- `integration_credentials` encrypts payloads at rest.
- `IntegrationCredentialOut` correctly never returns encrypted payload.
- UI/API still accept plaintext credential payloads through project integration
  routes.
- MCP setup surface includes `integration.set`.
- GSC OAuth is its own route family.

Change:

- Add:
  - `auth_providers`
  - `credentials`
  - `credential_scopes`
  - `credential_accounts`
  - `oauth_states`
  - `credential_usage_events`
- Add MCP tools:
  - `auth.status`
  - `auth.start`
  - `auth.test`
  - `auth.revoke`
- Make `integration.set` internal/compat only.
- Convert GSC OAuth into generic auth provider flow.
- Store provider account metadata separately from secret payloads.
- Use opaque `credential_ref`/`credential_id` in action execution.

Invariant:

- Agents never receive API keys, OAuth tokens, refresh tokens, cookies, service
  account keys, or signed secrets.

Tests to add:

- Agent-facing auth tools never return secret-like fields.
- MCP bridge does not advertise `integration.set` in the StackOS direct or
  setup surface after auth tools exist.
- Logs/audit payloads redact secret fields.

### 5. Action Executor And Connectors

Current state:

- Provider wrappers exist in `content_stack/integrations/*`.
- Hidden MCP tools in `content_stack/mcp/tools/vendor_ops.py` call wrappers
  directly.
- Each vendor operation has a bespoke input model and bespoke handler.

Change:

- Introduce generic action manifests:

```text
action_id
provider
capability
input_schema
output_schema
auth_requirements
resource_mapping
artifact_mapping
idempotency
cost/rate policy
redaction
connector_adapter
```

- Add:
  - `action.describe`
  - `action.validate`
  - `action.execute`
- Keep provider-specific connector code for signing, upload flows, pagination,
  retries, rate limits, and normalization.
- Port one simple utility first, such as `openaiImages.generate`.
- Then port one non-SEO action, such as `meta.campaigns.create`.

Boundary:

- Action tools validate and execute. The agent chooses provider, constructs
  arguments, interprets results, and records conclusions.

### 6. Workflow Templates And Run Plans

Current state:

- `procedures/` contains static `PROCEDURE.md` playbooks.
- `content_stack/procedures/parser.py` defines `ProcedureSpec`.
- `content_stack/procedures/runner.py` owns start/resume/fork/current/claim/
  record.
- `procedure_run_steps` persists procedure cursor state.
- UI and API have procedure routes/views.
- Scheduled procedures are hard-coded through `cron_procedures`.

Change:

- Add workflow templates:
  - plugin templates: `plugins/<plugin>/workflows/*.yaml`
  - repo/company templates: `.stackos/workflows/*.yaml`
  - project/user templates in DB
- Add run plans:
  - concrete resolved snapshot of one execution
  - selected context snapshot
  - selected provider/action payload drafts
  - approval gates
  - outputs and observations
- Add tools:
  - `workflowTemplate.list`
  - `workflowTemplate.describe`
  - `workflowTemplate.validate`
  - `workflowTemplate.save`
  - `workflowTemplate.fork`
  - `runPlan.create`
  - `runPlan.validate`
  - `runPlan.start`
  - `runPlan.get`
  - `runPlan.list`
  - `runPlan.update`
  - `runPlan.claimStep`
  - `runPlan.recordStep`

Keep:

- The existing runner ideas are good: run tokens, step state, scoped grants,
  resume/fork/abort, audit trails.

Replace:

- Product-level `procedure.*` should become compatibility wrappers over
  workflow templates and run plans.
- `ProcedureSpec` should evolve into or be paralleled by a generic
  `WorkflowTemplateSpec`.
- `ProcedureRunStep` should be mirrored/migrated into `RunPlanStep`.

### 7. Project Context, Learnings, Experiments, Decisions

Current state:

- Runs and step calls store evidence.
- There is no generic project memory layer.
- There are no first-class learnings, experiments, decisions, metric snapshots,
  project events, or context snapshots.
- Some SEO history exists in GSC/drift/article/version tables, but it is not
  queryable as generic project context.

Change:

- Add tables:
  - `project_events`
  - `context_index_entries`
  - `context_snapshots`
  - `learnings`
  - `experiments`
  - `experiment_variants`
  - `experiment_observations`
  - `decisions`
  - `metric_snapshots`
- Add tools:
  - `context.query`
  - `context.timeline`
  - `learning.query`
  - `learning.create`
  - `learning.update`
  - `experiment.query`
  - `experiment.create`
  - `experiment.recordObservation`
  - `experiment.recordDecision`
  - `decision.record`
  - `decision.query`

Important:

- These tools are storage/retrieval tools, not reasoning engines.
- `context.query` must support filters, field projection, limits, return modes,
  and provenance.
- StackOS should not auto-promote learnings or decide experiments.

### 8. MCP Bridge Surface

Current state:

- Direct bridge surface is workspace/project/procedure/run.
- Hidden setup toolbox includes many SEO tools and `integration.set`.
- Step grants come from hard-coded skill grants in `permissions.py`.
- Bridge descriptions still talk about content-stack and procedure steps.

Change:

- Direct/discovery surface should become:

```text
workspace.*
project.*
plugin.*
catalog.*
capability.*
provider.*
auth.*
workflowTemplate.list/describe/validate
runPlan.create/validate/start/get/list
run.*
```

- Step-scoped/gated tools should include `action.execute`, mutating
  `resource.*`, `artifact.create`, learning/decision/experiment writes, and
  context queries beyond safe metadata.
- Compatibility tools should include `procedure.*`, `article.*`, `topic.*`,
  and other legacy SEO tools until wrappers are retired.
- Replace skill-only grants with grants derived from:
  - enabled plugin
  - workflow template
  - resolved run plan
  - current run step
  - action/provider auth requirements
  - requested context source/fields

Do not:

- Do not expose every provider action directly in the bridge.
- Do not expose secrets through auth/context/action results.

### 9. Permission Model

Current state:

- `permissions.py` maps skill names to allowed tools.
- `__system__` allows broad product-state operations before a run token exists.
- Vendor tools are hidden unless granted.

Change:

- Keep the grant-checking pattern.
- Generalize from `skill -> tools` to:

```text
run token
  -> run plan step
  -> allowed capabilities/actions/resources/context fields
  -> credential scope checks
```

- Keep compatibility for skill frontmatter during SEO migration.
- Add tests that a run step cannot query ungranted context sources/fields.
- Add tests that disabled plugin actions/resources are not callable.

### 10. UI Restructure

Current state:

- `ui/src/App.vue` hard-codes SEO navigation:
  - Clusters
  - Topics
  - Articles
  - Procedures
  - Interlinks
  - GSC
  - Drift
  - Runs
- `ui/src/router.ts` hard-codes SEO routes.
- Project setup tabs are SEO/content setup: voice, compliance, EEAT, targets,
  integrations, schedules, cost.

Change:

- Core nav:
  - Overview
  - Projects
  - Plugins
  - Capabilities
  - Auth / Connections
  - Runs
  - Workflow Templates
  - Project Data
  - Schedules
  - Costs / Budgets
  - Settings
- Plugin nav should be contributed by plugin manifests.
- SEO nav moves under SEO plugin contribution.
- Media buying and GTM nav are added only when enabled.
- Replace `ProceduresView` with `WorkflowTemplatesView`.
- Replace procedure-specific run detail loading with generic run-plan step
  loading.
- Add generic `ResourceExplorerView` and `ResourceDetailView` so plugin
  resources do not require hand-written list/detail pages by default.
- Add generic `TemplateRenderer`, `RunPlanRenderer`, `ActionSchemaRenderer`,
  `ContextQueryRenderer`, and `ResourceSchemaRenderer` components.
- UI remains observer/control-plane. Mutations continue through agent/MCP
  except auth setup and explicit human approvals.

What should happen to SEO-specific UI:

- Keep high-value SEO resource views initially: Articles, Topics, GSC, Drift,
  and Interlinks are useful and already exist.
- Move them under SEO plugin nav contribution instead of core nav.
- Gradually re-express list/detail surfaces through generic resource-view
  configs where that does not make the UI worse.
- Do not create custom UI per SEO workflow template. For example,
  `topic-to-published`, `weekly-gsc-review`, and `monthly-refresh` should render
  through the same template/run-plan/run-detail views.

UI anti-goal:

- Do not build one bespoke page per workflow. That repeats the procedure
  problem in Vue instead of Python.

### 11. Jobs And Schedules

Current state:

- Scheduler is solid.
- Hard-coded jobs are SEO/GSC/drift oriented.
- Cron-triggered procedures are loaded from current procedure specs and
  `scheduled_jobs`.

Change:

- Keep scheduler infrastructure.
- Move GSC pull and drift rollup into SEO plugin schedules.
- Move OAuth refresh into auth/provider scheduling where possible.
- Generalize scheduled jobs to invoke:
  - action
  - workflow template
  - run plan seed
  - plugin maintenance task
- Schedules cannot make strategic choices. Any risky write schedule must use a
  predeclared workflow template or run-plan seed with grants, auth scopes,
  budgets, and approval policy.
- Keep existing jobs as compatibility tasks until SEO plugin owns them.

### 12. Install And Distribution

Current state:

- Installer mirrors `skills`, `procedures`, and `plugins/content-stack`.
- Wheel package force-includes `skills`, `procedures`, and `plugins`.
- Agent plugin skill assumes SEO procedures.

Change:

- Install a StackOS agent plugin whose entry skill describes the generic
  runtime.
- Bundle daemon plugin manifests/workflows separately from Codex/Claude plugin
  package metadata.
- Stop treating all skills/procedures as globally installed root assets.
- Put SEO skills under `plugins/seo/skills`.
- Put SEO workflow templates under `plugins/seo/workflows`.
- Add `plugins/utils` and `plugins/media-buying` skeletons.
- Add or rewrite root `AGENTS.md` to describe StackOS architecture, repo layout,
  UI generic-rendering rules, no-secrets policy, and tool-runtime boundary.
- Add plugin-local `AGENTS.md` files only where domain-specific file ownership
  and testing guidance are needed.

Compatibility:

- Keep old `plugins/content-stack` during transition.
- Add `plugins/stackos` when the generic surface exists.

### 13. Tests

Current test suite is valuable but SEO/procedure-shaped.

Add new tests for:

- Plugin manifest parsing and project enable/disable.
- Catalog listing and plugin filtering.
- Plugin UI contribution validation.
- Auth tools returning no secrets.
- Generic action description/validation/execution.
- Connector secret injection without agent exposure.
- Context query limits, field projection, provenance, and redaction.
- Learning/experiment/decision CRUD as data-only tools.
- Workflow template parsing and `.stackos/workflows` override precedence.
- Workflow template renderer fixture coverage.
- Run plan snapshot immutability once execution starts.
- Run-plan detail rendering for any run kind, not only procedure runs.
- Generic resource explorer list/detail rendering from resource-view manifests.
- Legacy `procedure.*` wrappers mapping to workflow/run plan primitives.
- UI nav contributions changing when plugins are enabled/disabled.
- Read-only UI contract still forbids product mutation calls outside explicit
  auth/approval paths.
- Root and plugin-local `AGENTS.md` files mention the StackOS tool-runtime
  boundary and no-secrets rule.

Update existing tests:

- `test_mcp_bridge.py`: direct surface should move away from `procedure.*`.
- `test_mcp_permissions.py`: grants become action/context aware.
- `test_plugin_package.py`: plugin naming and default prompt.
- Procedure runner tests: migrate to workflow/run-plan tests, keeping legacy
  wrapper coverage.
- Route/UI tests: SEO views should be plugin-owned instead of core nav.
- `read-only-ui.spec.ts`: keep the mutation scan, but allow narrowly scoped
  auth setup and human approval components if they are introduced.

## Cleanup Register

This is the concrete cleanup list that should guide implementation. The UI
should become simpler after this pivot: fewer bespoke SEO/procedure screens,
more generic renderers over templates, run plans, runs, resources, artifacts,
context, learnings, and experiments.

### Product And Naming Cleanup

- Replace "SEO Stack" product copy with StackOS framing.
- Keep `content-stack` as compatibility while stopping new SEO-branded product
  surfaces.
- Update README, package description, plugin descriptions, UI labels, docs
  titles, and app metadata.
- Add a future `stackos` CLI/plugin alias without rushing package/data-dir
  renames.
- Keep compatibility docs explicit so existing users understand the old names.

### Procedure Cleanup

- Deprecate procedures as the product model.
- Keep `procedure.*` only as compatibility wrappers.
- Stop adding new `PROCEDURE.md` files.
- Convert existing SEO procedures into workflow templates.
- Move top-level `procedures/` ownership into `plugins/seo/workflows/` or a
  legacy compatibility asset path.
- Replace `ProcedureSpec` with, or parallel it by, `WorkflowTemplateSpec`.
- Replace `procedure_run_steps` for new execution with `run_plan_steps`.
- Rename UI "Procedures" to "Workflow Templates".

### Template And Run Cleanup

- Add generic workflow template schema.
- Add generic run plan schema.
- Add run-plan steps so every run has renderable step state, not only procedure
  runs.
- Store resolved run plan snapshots once execution starts.
- Store context snapshots used by each run.
- Add approval-gate records as generic run-plan state.
- Keep legacy procedure resume/fork semantics only through wrappers.

### UI Cleanup

- Remove hard-coded core SEO nav entries:
  - Clusters
  - Topics
  - Articles
  - GSC
  - Drift
  - Interlinks
  - Procedures
- Move SEO nav under SEO plugin contribution.
- Replace `ProceduresView` with `WorkflowTemplatesView`.
- Replace procedure-specific run detail loading with generic run-plan step
  loading.
- Add generic views:
  - Plugins
  - Capabilities
  - Auth / Connections
  - Workflow Templates
  - Runs
  - Project Data
  - Resource Explorer
- Add generic renderers:
  - `TemplateRenderer`
  - `RunPlanRenderer`
  - `ActionSchemaRenderer`
  - `ResourceViewRenderer`
  - `ContextQueryRenderer`
  - `PluginNavRenderer`
- Keep UI observer/control-plane first.
- Keep direct UI mutations limited to auth setup and explicit human approvals.
- Do not build one custom page per workflow.
- Allow bespoke plugin dashboards only when generic resource/template/run
  renderers are insufficient.

### SEO UI Cleanup

- Keep useful SEO views temporarily while the generic shell matures.
- Move Articles, Topics, GSC, Drift, and Interlinks under the SEO plugin.
- Gradually express SEO list/detail pages through generic resource-view
  manifests where that preserves usability.
- Do not create custom UI for each SEO workflow template.
- Treat SEO-specific setup tabs such as voice, compliance, EEAT, authors, and
  publish targets as SEO/plugin-owned or shared-plugin candidates, not core
  project setup.

### MCP And Tool Cleanup

- Replace direct `procedure.*` as the main workflow surface with
  `workflowTemplate.*` and `runPlan.*`.
- Add `plugin.*`, `catalog.*`, `capability.*`, and `provider.*`.
- Add generic `auth.*`.
- Add `action.describe`, `action.validate`, and `action.execute`.
- Add `resource.*` and `artifact.*`.
- Add `context.*`, `learning.*`, `experiment.*`, and `decision.*`.
- Move `article.*`, `topic.*`, `gsc.*`, `drift.*`, `interlink.*`, `eeat.*`,
  and related SEO tools behind SEO plugin ownership or compatibility aliases.
- Stop advertising `integration.set` to agents.
- Keep hidden operational tools behind the bridge/toolbox pattern.

### Auth Cleanup

- Replace integration setup with generic provider auth flows.
- Return credential refs, scopes, accounts, and setup URLs to agents, never
  secrets.
- Move GSC OAuth into generic auth provider flow.
- Add credential scopes, provider accounts, OAuth state, and usage events.
- Add secret-redaction tests for auth, action, context, logs, and audits.
- Keep `integration_credentials` as a backing store only until new credential
  tables are stable.

### Data Model Cleanup

- Add plugin/catalog/action/provider/resource/artifact tables.
- Add workflow template, workflow template version, run plan, and run plan step
  tables.
- Add project context tables:
  - project events
  - context index entries
  - context snapshots
  - learnings
  - experiments
  - experiment variants
  - experiment observations
  - decisions
  - metric snapshots
- Keep existing typed SEO tables initially, but mark them as SEO plugin-owned.
- Avoid replacing working typed SEO tables with generic JSON too early.

### Integration / Provider Cleanup

- Rename integrations conceptually to providers/connectors.
- Move vendor wrappers behind action manifests.
- Keep connector adapters for signing, retries, pagination, uploads, rate
  limits, and response normalization.
- Port utility actions first: OpenAI Images, Firecrawl, Jina.
- Add Meta as the first media-buying proof action after auth/action foundations
  exist.
- Keep provider tools data-only and execution-only; the agent chooses strategy.

### Jobs And Schedule Cleanup

- Move GSC pull and drift rollup under SEO plugin schedules.
- Generalize scheduled jobs around actions, workflow templates, run plan seeds,
  and plugin maintenance tasks.
- Keep current jobs as compatibility tasks until plugin ownership exists.
- Avoid adding new SEO-specific core jobs.

### Install And Asset Cleanup

- Stop treating root `skills/` and `procedures/` as universal assets.
- Move SEO skills into `plugins/seo/skills`.
- Move SEO workflow templates into `plugins/seo/workflows`.
- Add `plugins/utils`.
- Add `plugins/media-buying`.
- Add a generic StackOS agent plugin package.
- Keep `plugins/content-stack` during transition.
- Update wheel force-includes to reflect plugin-owned assets.

### Docs And AGENTS Cleanup

- Rewrite root `AGENTS.md` around StackOS architecture and repo layout.
- Document the StackOS tool-runtime boundary:
  - agent/human decides
  - StackOS stores/retrieves/checks/executes/audits
- Document no-secrets-to-agent as a hard invariant.
- Add plugin-local `AGENTS.md` only where file ownership and test guidance are
  useful.
- Replace procedure authoring docs with workflow template and run plan docs.
- Add docs for plugin manifests, action manifests, auth providers, project
  context, generic UI renderers, and compatibility migration.

### Test Cleanup

- Migrate procedure tests into workflow-template/run-plan tests.
- Keep compatibility tests for `procedure.*`.
- Add plugin manifest tests.
- Add plugin UI contribution tests.
- Add generic UI renderer tests.
- Add run-plan detail tests for any run kind.
- Add generic resource explorer tests.
- Add auth/action/context no-secret tests.
- Add permission tests for action/resource/context grants.
- Keep the read-only UI contract, with narrow exceptions for auth setup and
  human approvals.

## Delivery Governance

The pivot is broad enough that implementation must be run with explicit
alignment checks. The process should be:

```text
1. Maintain the vision/design docs.
2. Self-verify the docs with a separate review pass.
3. Break the work into dependency-aware deliverable tasks.
4. Self-verify the task breakdown before implementation.
5. Deliver one task at a time.
6. Verify each task against tests, docs, and the StackOS boundary.
7. Get signoff.
8. Commit each successful signed-off delivery.
```

### Self-Verification Pass

Before breaking work into deliverables, run an independent verification pass
against the docs. The verifier should check:

- Does every proposed change preserve the StackOS tool-runtime boundary?
- Are agents/humans still responsible for decisions?
- Are secrets still hidden from agents?
- Are workflow templates reusable and run plans specific?
- Is project memory stored as data, not hidden decision logic?
- Does the UI avoid per-workflow bespoke pages?
- Is SEO plugin-owned instead of core-owned?
- Are compatibility paths explicit?
- Are tests identified for every risky boundary?

### Deliverable Task Rules

Every deliverable task should include:

- goal
- scope
- non-goals
- affected files/modules
- data model changes
- API/MCP changes
- UI changes
- tests to add/update
- dependencies
- compatibility requirements
- rollback/migration concerns
- acceptance criteria
- verification commands
- signoff notes

No task should be considered ready if it cannot explain how it preserves:

- no secrets to agents
- agent/human decision ownership
- StackOS as storage/retrieval/execution/audit tool
- plugin ownership for domain-specific behavior
- generic UI rendering for templates/runs/resources
- compatibility for existing SEO flows

### Commit Rule

Each successful and signed-off delivery should be committed separately. The
commit should represent one coherent deliverable, not a pile of unrelated
cleanup.

Suggested commit message shape:

```text
stackos: add plugin catalog skeleton
stackos: add auth provider refs
stackos: add workflow template parser
stackos: migrate procedures view to workflow templates
seo: register legacy article tools as plugin actions
```

## Legacy Mapping Matrix

This matrix should be expanded during implementation. Its job is to prevent
half-migrated concepts from drifting back into StackOS core.

| Legacy surface | Current location | Target owner/model | Delivery phase | Tests | Removal condition |
|---|---|---|---|---|---|
| `procedure.*` MCP tools | `content_stack/mcp/tools/runs.py` | Compatibility wrappers over workflow templates and run plans | D07, D12 | MCP procedure compatibility, run-plan tests | New agents use `workflowTemplate.*` / `runPlan.*`; old runs still readable |
| `procedures/*` assets | top-level `procedures/` | `plugins/seo/workflows/*` plus compatibility bundle | D12 | workflow template parser, procedure wrapper tests | Every shipped procedure has SEO workflow equivalent |
| SEO skills | top-level `skills/` | `plugins/seo/skills/*` | D11, D12 | skill frontmatter/manifest tests | SEO plugin package owns skills and installer bundles them from plugin path |
| `article.*`, `topic.*`, `cluster.*` | MCP SEO tools | SEO plugin actions/resources plus compatibility aliases | D11 | SEO MCP compatibility, catalog tests | Catalog exposes SEO resources/actions and old aliases are documented |
| `gsc.*`, `drift.*`, `interlink.*`, `eeat.*` | MCP SEO tools/jobs | SEO plugin actions/resources/schedules | D11, D15 | GSC/drift/interlink tests, schedule tests | SEO plugin owns schedules and actions |
| SEO REST routes | `content_stack/api/articles.py`, `topics.py`, etc. | SEO plugin REST compatibility or generic resource APIs | D10, D11 | route tests, UI API contract | Generic resource APIs cover common views; SEO routes remain compatibility |
| SEO UI nav | `ui/src/App.vue`, `router.ts` | SEO plugin nav contribution | D10, D11 | plugin nav UI tests | Disabling SEO hides SEO nav |
| SEO UI stores/views | `ui/src/stores/*`, `ui/src/views/*` | generic resource/renderers or SEO plugin views | D10, D11 | renderer tests, existing view tests | Generic views cover the workflow/resource surface without UX loss |
| Voice/compliance/EEAT/authors/targets setup tabs | project detail tabs | SEO plugin or shared plugin resources | D11 | project setup compatibility tests | Core project setup no longer requires SEO concepts |
| `integration.*` MCP tools | project tools and bridge setup toolbox | `auth.*` plus compatibility-only integration APIs | D04 | no-secret auth tests, bridge tests | Agents no longer need `integration.set` |
| Vendor operation tools | `vendor_ops.py` | utility/SEO/provider action manifests plus connector adapters | D08, D13 | action executor and integration tests | Action executor covers ported providers |
| GSC pull / drift rollup jobs | `content_stack/jobs/*` | SEO plugin schedules | D15 | job registration tests | Core startup has no SEO-only job requirement |
| `integration_credentials` table | core project credential table | backing compatibility or migrated `credentials` model | D04, D16 | credential migration/no-secret tests | New auth provider tables are stable and old rows migrate safely |
| `procedure_run_steps` table | procedure step state | `run_plan_steps` plus legacy read compatibility | D07, D12 | run detail/run-plan tests | Existing procedure histories remain readable |

## Module-Level Change Map

### Core Modules To Keep And Generalize

```text
content_stack/server.py
  Keep daemon lifecycle, auth middleware, scheduler, MCP mount, UI mount.
  Generalize app title/description and job registration.

content_stack/config.py
  Keep paths and loopback rules.
  Add compatibility path strategy before renaming dirs.

content_stack/mcp/server.py
  Keep registry, envelope discipline, dispatcher, idempotency path.
  Add generic tools through new modules.

content_stack/mcp/bridge.py
  Keep compact bridge idea and toolbox.
  Replace procedure-centric direct list with StackOS direct surface.

content_stack/mcp/permissions.py
  Keep grant enforcement.
  Generalize from skill grants to run-plan/action/context grants.

content_stack/repositories/runs.py
  Keep run/run_step/run_step_call/idempotency logic.
  Add run plan links and context snapshot links.

content_stack/repositories/projects.py
  Split generic project/plugin/auth/budget pieces from SEO project setup.
```

### New Core Modules To Add

```text
content_stack/plugins/
  manifest.py
  registry.py
  loader.py

content_stack/actions/
  manifest.py
  executor.py
  connectors.py
  redaction.py
  validation.py

content_stack/auth_providers/
  flows.py
  credential_refs.py
  oauth.py

content_stack/context/
  query.py
  timeline.py
  index.py

content_stack/workflows/
  templates.py
  run_plans.py
  runner.py

content_stack/mcp/tools/
  catalog.py
  plugins.py
  auth.py
  actions.py
  resources.py
  artifacts.py
  context_tools.py
  workflows.py
```

### New UI Modules To Add

```text
ui/src/stores/plugins.ts
ui/src/stores/catalog.ts
ui/src/stores/auth-connections.ts
ui/src/stores/actions.ts
ui/src/stores/resources.ts
ui/src/stores/artifacts.ts
ui/src/stores/context.ts
ui/src/stores/learnings.ts
ui/src/stores/experiments.ts
ui/src/stores/workflow-templates.ts
ui/src/stores/run-plans.ts

ui/src/views/PluginsView.vue
ui/src/views/CapabilitiesView.vue
ui/src/views/AuthConnectionsView.vue
ui/src/views/ResourceExplorerView.vue
ui/src/views/ResourceDetailView.vue
ui/src/views/ArtifactExplorerView.vue
ui/src/views/WorkflowTemplatesView.vue
ui/src/views/WorkflowTemplateDetailView.vue
ui/src/views/RunPlanDetailView.vue
ui/src/views/ProjectContextView.vue
ui/src/views/LearningsView.vue
ui/src/views/ExperimentsView.vue

ui/src/components/renderers/TemplateRenderer.vue
ui/src/components/renderers/RunPlanRenderer.vue
ui/src/components/renderers/ActionSchemaRenderer.vue
ui/src/components/renderers/ResourceSchemaRenderer.vue
ui/src/components/renderers/ContextQueryRenderer.vue
ui/src/components/renderers/ResourceViewRenderer.vue
ui/src/components/renderers/PluginNavRenderer.vue
```

These components should be boring renderers over schemas/manifests. They should
not own workflow decisions or call write endpoints directly.

### SEO Modules To Move Behind Plugin Boundary

```text
content_stack/api/articles.py
content_stack/api/clusters.py
content_stack/api/gsc.py
content_stack/api/interlinks.py
content_stack/api/topics.py
content_stack/mcp/tools/articles.py
content_stack/mcp/tools/clusters.py
content_stack/mcp/tools/gsc.py
content_stack/mcp/tools/interlinks.py
content_stack/mcp/tools/sitemap.py
content_stack/repositories/articles.py
content_stack/repositories/clusters.py
content_stack/repositories/eeat.py
content_stack/repositories/gsc.py
content_stack/repositories/interlinks.py
skills/**
procedures/**
ui/src/views/* SEO views
ui/src/stores/* SEO stores
```

This does not require immediate physical relocation. First register these as
SEO plugin resources/actions/views while the code stays where it is.

## Recommended Delivery Order

### Phase A: StackOS Core Catalog Skeleton

- Add plugin/capability/provider/action/resource/artifact tables.
- Add plugin manifest loader.
- Register `core`, `seo`, and `utils` built-ins.
- Add catalog/plugin MCP tools.
- Add UI read-only Plugins/Capabilities shell.

Why first:

- This creates the boundary without breaking current SEO flows.

### Phase B: Auth Boundary

- Add generic auth provider tables/tools.
- Keep `integration_credentials` as backing storage initially.
- Wrap current integrations behind `auth.status/start/test/revoke`.
- Stop advertising `integration.set` through the agent bridge.
- Convert GSC OAuth to generic provider flow.

Why second:

- Secret safety is foundational before media buying or other high-risk
  providers are added.

### Phase C: Project Memory Primitives

- Add project events, context snapshots, learnings, experiments, decisions, and
  metric snapshots.
- Add bounded context and memory tools.
- Ensure tools only retrieve/store data and do not infer conclusions.

Why third:

- Reusable templates and media buying workflows need historical context.

### Phase D: Workflow Templates And Run Plans

- Add `WorkflowTemplateSpec` and `RunPlan` models.
- Add plugin/repo/project template loaders.
- Add `.stackos/workflows` discovery.
- Add run plan tools and tables.
- Keep `procedure.*` wrappers.

Why fourth:

- This replaces rigid procedures while preserving the current runner value.

### Phase E: Generic Action Executor

- Add action manifests and executor.
- Port `openaiImages.generate` as first utility action.
- Port one simple read action, such as Jina read or Firecrawl scrape.
- Add redaction/idempotency/action-call audit tests.

Why fifth:

- It proves the provider/action shape before media buying.

### Phase F: Generic UI Shell And Renderers

- Replace hard-coded core navigation with plugin contribution rendering.
- Add Plugins, Capabilities, Auth, Workflow Templates, Project Data, and
  Artifacts/resource views.
- Add generic template, run-plan, context-query, resource-view, and action
  schema renderers.
- Update run detail to render run-plan steps and action calls generically.
- Keep SEO views reachable through SEO plugin nav while generic renderers
  mature.

Why sixth:

- The UI should reflect the architecture early. Otherwise users and tests will
  keep reinforcing procedure/SEO as core product concepts.

### Phase G: SEO Plugin Facade

- Create `plugins/seo/plugin.yaml`.
- Map current SEO tables/tools/views/skills/workflows into plugin manifest.
- Move SEO nav under plugin contribution.
- Add compatibility aliases.

Why seventh:

- Existing product keeps working while the platform boundary becomes real.

### Phase H: Media Buying MVP

- Create `plugins/media-buying/plugin.yaml`.
- Add provider manifest for Meta.
- Add resources: account, campaign, ad set, ad, creative, experiment, report.
- Add `meta.campaigns.create` action with paused-only default safety policy.
- Add media buying workflow template for campaign launch draft.

Why eighth:

- This validates StackOS beyond SEO.

### Phase I: Product Rename And Cleanup

- Add `stackos` CLI alias.
- Rename UI product copy.
- Add `plugins/stackos` agent package.
- Keep `content-stack` compatibility command and data paths for at least one
  release.
- Deprecate root `procedures/` and direct SEO core tools.

Why ninth:

- Rename after architecture, not before.

## Highest-Risk Areas

### Risk: Over-Generalizing The Data Model

Do not immediately replace typed SEO tables with generic JSON records. That
would lose useful constraints and break working flows.

Mitigation:

- Keep typed tables.
- Register them as plugin resources.
- Introduce generic resources for new domains first.

### Risk: Turning StackOS Into A Hidden Decision Engine

Project memory and experiments are tempting places to add "smart" logic.

Mitigation:

- Tools only store/retrieve/check static contracts.
- Agents/humans write decisions, learnings, and experiment outcomes.
- Avoid tool names like `learning.promote` or `experiment.decide`.

### Risk: Secret Leakage During Auth Refactor

Media buying and GTM providers make this more serious.

Mitigation:

- No agent-facing plaintext credential ingestion.
- Redaction tests for every auth/action/context response.
- Credential refs only.

### Risk: Breaking Existing SEO Users

Current SEO flows are extensive and tested.

Mitigation:

- Add generic surfaces beside existing surfaces.
- Keep compatibility wrappers.
- Move ownership in manifest/catalog first, physical files later.

## Current Capability Fit Against 10 Workflow Simulations

```text
SEO Article Refresh:
  Current support: partial/good via articles, GSC, drift, refresh procedures.
  Missing: generic experiments, learnings, context snapshots.

New SEO Content Cluster:
  Current support: good via clusters/topics/procedures.
  Missing: plugin boundary and generic context query.

Media Buying Campaign Launch:
  Current support: none except runtime/auth/run concepts.
  Missing: media plugin, Meta provider, action executor, resources.

Creative Variant Generation:
  Current support: partial via OpenAI Images and article assets.
  Missing: generic artifacts and configurable utility action.

Media Buying Optimization:
  Current support: none.
  Missing: metrics, experiments, campaign resources, provider actions.

GTM Lead List Build:
  Current support: none.
  Missing: GTM resources/actions/providers and cross-domain context.

GTM Outreach Sequence:
  Current support: none.
  Missing: GTM plugin, experiment resources, approval flow reuse.

Landing Page Test:
  Current support: partial via publishing/targets/articles.
  Missing: generic web/page resource, experiments, linked resources.

Weekly Business Review:
  Current support: partial via runs/costs/GSC.
  Missing: bounded context query across plugins and decision records.

Incident / Regression Investigation:
  Current support: partial via runs, drift, GSC, logs.
  Missing: project event timeline and cross-plugin resource diffs.
```

## Bottom Line

The current implementation is not a bad foundation. It is a good local agent
runtime wearing an SEO product skin.

The most important changes are:

1. Add a real plugin/catalog layer.
2. Replace procedures as the product model with workflow templates and run
   plans.
3. Add project memory as data-only context tools.
4. Replace `integration.*` with generic no-secret auth tools.
5. Replace bespoke vendor tools with action manifests plus connector adapters.
6. Move SEO into a first-party plugin boundary.
7. Restructure UI around core shell plus plugin-contributed navigation.

The migration should preserve current working SEO flows while StackOS core
emerges underneath them.
