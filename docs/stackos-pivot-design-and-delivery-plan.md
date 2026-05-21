# StackOS Pivot Design And Delivery Plan

## Purpose

This document captures the planned pivot from an SEO-focused product into
StackOS: a local, extensible agent operating system for business tooling.

The current system already contains a useful runtime: daemon, MCP bridge, run
state, scoped permissions, credentials, budgets, schedules, UI shell, and audit
trail. The problem is that SEO concepts and hard-coded procedures are currently
first-class platform concepts. StackOS should keep the runtime, move SEO into a
first-party plugin, replace rigid procedures with reusable workflow templates
and agent-authored run plans, and make future domains such as media buying, GTM,
and internal tools installable through the same plugin model.

## Product Direction

StackOS is a local execution kernel for agent-operated business systems.

Users install StackOS once, connect projects/workspaces, then install the domain
plugins they need:

- SEO
- Media buying
- GTM
- Utility providers such as image generation, video generation, scraping,
  extraction, transcription, and artifact storage
- Custom/internal plugins for private business systems

The operating principle:

- Plugins define what exists.
- Agents decide what should be done.
- Actions execute safely.
- Secrets never leave the daemon or connector boundary.

Critical boundary: StackOS is a tool runtime, not an operator. It should expose
static definitions, storage, retrieval, validation, permissions, auth, audit,
and external tool execution. It should not contain business decision logic such
as which campaign to launch, which SEO angle to choose, which experiment won, or
which learning is true. Agents and humans make those calls and write their
decisions back into StackOS as data.

## Current System Breakdown

### Runtime Pieces To Keep In Core

These current surfaces are mostly domain-neutral and should become StackOS core:

- `workspace.*`: workspace/session/repository binding.
- `project.*`: project lifecycle and active project selection.
- `procedure.*`: current durable agent-led procedure control; migrate this
  into workflow template and run plan primitives.
- `run.*`: run lifecycle, audit trail, heartbeats, resume/fork/abort.
- `schedule.*`: recurring work.
- `budget.*` and `cost.*`: spend controls and cost reporting.
- MCP bridge: direct orchestration tools plus hidden toolbox calls.
- Current procedure runner primitives: step state, scoped grants, run tokens,
  resume, fork, failure policies, and programmatic steps. These should be
  reframed as the workflow/run-plan engine, not exposed as rigid product
  procedures.
- Local daemon: FastAPI, SQLite/WAL, migrations, localhost-only auth.
- UI shell and reusable Vue components.
- Encrypted credential storage foundation.

### Current SEO Pieces To Move Into An SEO Plugin

These are currently built in, but should become `plugins/seo`:

- `cluster.*`: topical maps.
- `topic.*`: SEO/content opportunity queue.
- `article.*`: article lifecycle and content state.
- `asset.*`: article-scoped assets, later backed by generic artifacts.
- `source.*`: research sources/citations.
- `schema.*`: JSON-LD and structured data.
- `publish.*`: content publishing records.
- `interlink.*`: internal linking.
- `eeat.*`: content quality/trust gate.
- `gsc.*`: Search Console metrics and operations.
- `drift.*`: published page drift baselines.
- `redirect.*`: site redirect records.
- `sitemap.fetch`: SEO/site discovery.
- Existing SEO skills, legacy procedures, workflow templates, docs, and UI
  routes.

### Current Provider/Utility Pieces

These should become provider actions under SEO or utility plugins:

- `dataforseo.*`: SEO/search provider actions.
- `ahrefs.*`: SEO/search provider actions.
- `googlePaa.extract`: SEO/search provider action.
- `gscOauth.*`: auth flow for Google Search Console.
- `openaiImages.generate`: utility media provider action.
- `firecrawl.*`: utility web crawl/scrape/extract actions.
- `jina.read`: utility web reader action.
- `reddit.*`: utility/community research actions, usable by SEO and GTM.

## Target Architecture

StackOS should be layered as:

```text
StackOS Core
  plugin registry
  project/workspace state
  auth and credential storage
  capability/action catalog
  generic action executor
  resource/artifact storage
  project memory and context index
  learnings, experiments, decisions, and event timeline
  workflow template and run plan engine
  MCP bridge/toolbox
  schedules, budgets, audit trail
  UI shell

Plugins
  SEO
  Media Buying
  GTM
  Utils
  Private/internal plugins

Providers
  Meta Ads
  Google Ads
  Taboola
  Outbrain
  WordPress
  Ghost
  DataForSEO
  Firecrawl
  OpenAI Images
  Internal APIs
```

## Core Abstractions

### Plugin

A plugin is an installable package of capabilities, resources, actions,
workflow templates, skills/instructions, UI contributions, docs, migrations, and
provider bindings.

Suggested plugin structure:

```text
plugins/<plugin-id>/
  plugin.json
  resources/
  capabilities/
  actions/
  providers/
  workflows/
  skills/
  ui/
  migrations/
  docs/
  permissions.json
```

### Capability

A capability describes a business thing that can be done, without binding it to
one provider or implementation.

Examples:

```text
seo.article.publish
seo.keyword.discover
media.campaign.create
media.report.fetch
creative.variant.generate
gtm.sequence.launch
utils.image.generate
utils.web.scrape
```

### Provider

A provider describes where/how a capability can be executed.

Examples:

```text
meta
taboola
outbrain
google-ads
wordpress
ghost
dataforseo
firecrawl
openai-images
internal-buying-api
```

### Action

An action is a configured executable operation. It binds a capability to a
provider operation, input schema, output schema, auth scheme, persistence
mapping, cost/rate policy, and redaction rules.

Example:

```text
Capability: media.campaign.create

Actions:
  meta.campaigns.create
  taboola.campaigns.create
  outbrain.campaigns.create
  internal-buying-api.launchCampaign
```

### Resource

A resource is a plugin-defined business object that StackOS can store/query.

Examples:

```text
seo.article
seo.topic
media.campaign
media.creative
media.experiment
gtm.account
gtm.sequence
```

Resources should be plugin-defined and schema-driven where possible. Core should
not need a Python model for every business object.

### Artifact

An artifact is any produced or consumed file/blob/structured output:

- image
- video
- CSV
- transcript
- campaign payload
- creative variant set
- article draft
- report snapshot
- scraped page content

SEO `asset.*` and `source.*` should eventually be backed by generic artifact
storage.

### Workflow Template

A workflow template is a reusable operating recipe. It is not a hard-coded list
of API calls, and it is not the final execution plan.

The template must not contain final action payloads, provider object ids, or
one company's concrete task list. Those belong in the resolved run plan. The
template should describe the setup, constraints, stages, policies, and expected
shape of the work so an agent has a strong default without being trapped by it.

Templates should define the shape of work:

- when to use the workflow
- when not to use it
- required and optional inputs
- context the agent should load
- required and preferred capabilities
- provider/auth requirements
- stages and their purpose
- instructions for the agent
- expected outputs
- policies and constraints
- approval gates
- risk classification
- failure handling
- what should be captured as reusable learnings

Templates should reference capabilities rather than concrete provider actions
where possible. Capabilities are stable across providers; actions are resolved
at run time.

Example:

```text
Template: media.campaign-launch
Capability references:
  media.account.discover
  media.campaign.create
  media.creative.variant.generate
  utils.web.scrape

Run-time action resolution:
  meta.campaigns.create
  taboola.campaigns.create
  internal-buying-api.launchCampaign
```

Templates can come from several places:

```text
Plugin defaults:
  plugins/media-buying/workflows/campaign-launch.yaml

Repository/company overrides:
  .stackos/workflows/campaign-launch.yaml

Project/user templates:
  stored in the StackOS DB
```

Precedence should be:

```text
repo/company template > project/user template > plugin template > ad hoc agent plan
```

### Run Plan

A run plan is a concrete, one-time execution plan produced by the agent from a
workflow template plus current project context.

The run plan resolves:

- selected provider(s)
- selected credential refs
- resolved inputs
- context snapshots and artifacts
- concrete stages
- proposed action payloads
- approval gates
- resource/artifact outputs
- current status per stage/action

The important distinction:

```text
Workflow template = reusable operating recipe.
Run plan = concrete execution plan for one run.
Run = audited execution record of what actually happened.
```

Most work should start from a reusable workflow template so agents do not invent
the workflow every time. Agents should still be able to extend or fork templates
for a company, repository, or project.

The user-facing product may call both objects "plans", but the system should
keep them separate:

```text
Reusable plan/template:
  durable, versioned, generic, shared across runs

Specific run instance:
  concrete, contextual, provider-resolved, immutable once execution starts
```

### Agent Flow

The flexible flow should be:

1. Agent receives a goal, such as "launch a Meta test for Offer X".
2. Agent searches enabled plugins and workflow templates.
3. Agent selects the best predefined template or starts an ad hoc draft if no
   template fits.
4. Agent loads template-declared context: project profile, enabled plugins,
   connected providers, prior runs, relevant resources, and artifacts.
5. Agent checks auth status and receives only credential refs, scopes, accounts,
   and setup URLs.
6. Agent resolves capabilities to provider actions, such as
   `media.campaign.create` to `meta.campaigns.create`.
7. Agent produces a concrete run plan with inputs, stages, action payload
   drafts, approvals, expected outputs, and risk notes.
8. StackOS checks the run plan against template policies, action schemas,
   auth scopes, budgets, and approval rules.
9. Human approves only where policy requires approval or missing context cannot
   be inferred safely.
10. Agent executes the run step by step through `runPlan.claimStep`,
    `action.validate`, `action.execute`, and `runPlan.recordStep`.
11. StackOS stores artifacts, resource refs, redacted action calls, costs, and
    decision records supplied by the agent or human.
12. Agent captures reusable learnings and may propose a template fork/update for
    future runs.

Agent-created template extensions should be allowed, but controlled:

- extensions must declare `based_on`, version, owner, and scope
- extensions can narrow policies freely but need validation before broadening
  permissions, providers, or relaxing/removing approval gates
- extensions should live in `.stackos/workflows` for repo/company-specific
  behavior or in the DB for project/user-specific behavior
- extensions should be reviewable as normal repository changes when stored in a
  repo

### Project Memory And Context

Templates should not own history. Runs should not be treated as memory either;
they are evidence. Project memory is the layer that turns prior evidence into
useful operating context for the next run.

The practical hierarchy should be:

```text
Project
  resources
  artifacts
  runs
  experiments
  learnings
  decisions
  metrics
  event timeline
  context index

Workflow Templates
  instructions
  required context queries
  stages
  policies
  approvals
  output contracts
  learning hooks

Runs
  resolved context snapshot
  concrete action plan
  execution trace
  observations
  outputs
  proposed learnings
```

The template's job is to tell the agent what kind of context to retrieve. The
project's job is to store the actual context. The run's job is to snapshot the
context it used so the result remains explainable later.

StackOS should remain a tool layer here. It stores, indexes, filters, validates,
redacts, and triggers external tools. It should not decide what the history
means, which lesson is true, which experiment won, or what action to take next.
Those judgments belong to the agent and, where required, the human operator.

This matters because SEO, media buying, GTM, and internal operations are not
one-time workflows. They compound:

- previous SEO refreshes affect the next refresh
- previous ad tests affect the next creative brief
- previous outbound results affect the next ICP and messaging run
- previous incidents affect future approval and rollout policy

The agent should be able to ask for relevant history without flooding its
context window. Context retrieval needs filters, field selection, compact stored
views, and hard limits. If semantic summarization is needed, the agent should do
that as part of the run and store the resulting summary as an artifact or
learning candidate.

Example context query declaration inside a template:

```yaml
context_requirements:
  - id: recent_related_runs
    source: runs
    filters:
      template_ids:
        - media.campaign-launch
        - media.creative-test
      providers:
        - meta
      statuses:
        - completed
      lookback:
        runs: 10
    fields:
      - goal
      - selected_provider
      - budget
      - created_resources
      - outcome_summary
      - failures
      - learnings
    max_items: 10
    return_mode: compact

  - id: active_experiments
    source: experiments
    filters:
      domain: media-buying
      statuses:
        - running
        - pending-decision
    fields:
      - hypothesis
      - variants
      - metric_targets
      - current_results
      - next_decision_at
    max_items: 20

  - id: reusable_learnings
    source: learnings
    filters:
      tags:
        - creative
        - offer
        - meta
      confidence_min: medium
    fields:
      - statement
      - evidence_summary
      - confidence
      - source_run_ids
      - applies_to
    max_items: 20
    return_mode: compact
```

Context retrieval should support:

- source filters: runs, resources, artifacts, experiments, learnings, decisions,
  metrics, events
- time filters: date range, last N runs, last N days, since last decision
- semantic filters: tags, provider, domain, template id, resource id, offer,
  market, channel, status, outcome
- field projection: only return the requested fields
- static return modes: compact, detailed, timeline, or raw
- budgets: max items, max tokens, max artifacts, max age
- provenance: every compact item should point back to source rows/artifacts

The platform should avoid implicit "load all history" behavior. Agents should
request context through explicit declarations or explicit `context.query` calls.

### Learnings

A learning is a durable project-level statement derived from one or more runs,
experiments, decisions, metrics, or human notes.

Learnings are not just run notes. They should be queryable, scoped, and
confidence-bearing:

```yaml
id: learning_123
project_id: 1
statement: Founder-led creative outperformed product-demo creative for Offer X.
domain: media-buying
tags:
  - creative
  - meta
  - offer-x
applies_to:
  providers:
    - meta
  markets:
    - US
  resources:
    - offer_x
confidence: medium
evidence:
  source_run_ids:
    - run_201
    - run_244
  source_experiment_ids:
    - exp_88
  metric_summary: CPA improved 24 percent across two comparable tests.
status: active
created_by: agent
review_state: accepted
```

Agents can propose learnings at the end of a run, and humans or agents can set
the review state. StackOS should store states such as proposed, accepted,
rejected, stale, and superseded, but it should not promote a learning by itself.
This keeps the memory useful without turning the platform into a hidden
decision-maker.

### Experiments

Experiments should be first-class project objects, not hidden inside templates.
A template can support experimentation, and a run can create or update an
experiment, but the experiment itself belongs to the project because it may span
multiple runs, providers, and resources.

Experiment shape:

```yaml
id: exp_88
project_id: 1
domain: media-buying
hypothesis: Founder-led creative will reduce CPA versus product-demo creative.
status: running
linked_template_ids:
  - media.creative-test
linked_run_ids:
  - run_201
  - run_244
variants:
  - id: founder_led
    resources:
      - artifact_10
      - media_ad_45
  - id: product_demo
    resources:
      - artifact_11
      - media_ad_46
metric_targets:
  primary: cpa
  secondary:
    - ctr
    - spend
decision_policy:
  min_observation_window_days: 7
  min_spend: 500
current_results:
  summary: Inconclusive; spend threshold not met.
decision:
  status: pending
```

Templates can declare experiment support:

```yaml
experiment:
  supported: true
  default_type: creative_test
  hypothesis_required: true
  variant_schema: media.creative_variant
  metric_requirements:
    - cpa
    - ctr
    - spend
  decision_policy:
    min_observation_window_days: 7
    min_spend: 500
```

This keeps experimentation generic enough for SEO title tests, media buying
creative tests, GTM sequence tests, landing page tests, and private operational
tests.

### Workflow Template Schema

A generic workflow template should be broad enough for SEO, media buying, GTM,
utilities, and private systems:

```yaml
id: media.campaign-launch
name: Campaign Launch
version: 1.0.0
owner: media-buying

scope:
  plugins:
    - media-buying
    - utils
  domains:
    - paid-acquisition

description: Launch a new paid media test with human approval before spend.

when_to_use:
  - Launching a new offer, channel, provider, or test campaign.
  - Testing new creative or audience hypotheses.

not_for:
  - Scaling existing campaigns.
  - Emergency incident response.

required_inputs:
  - key: offer
    type: object
    required: true
  - key: budget_cap
    type: money
    required: true
  - key: target_market
    type: string
    required: true

optional_inputs:
  - key: provider
    type: provider
  - key: landing_page_url
    type: url
  - key: audience_notes
    type: markdown
  - key: creative_constraints
    type: object

context_requirements:
  - id: project_setup
    source: project
    fields:
      - profile
      - enabled_plugins
      - connected_providers
      - policies
  - id: recent_campaign_runs
    source: runs
    filters:
      template_ids:
        - media.campaign-launch
        - media.creative-test
      lookback:
        runs: 10
      statuses:
        - completed
    fields:
      - goal
      - provider
      - budget
      - outcome_summary
      - failures
      - learnings
    max_items: 10
    return_mode: compact
  - id: active_related_experiments
    source: experiments
    filters:
      domain: media-buying
      statuses:
        - running
        - pending-decision
    fields:
      - hypothesis
      - variants
      - metric_targets
      - current_results
    max_items: 20
  - id: relevant_learnings
    source: learnings
    filters:
      tags:
        - media-buying
        - creative
      confidence_min: medium
    fields:
      - statement
      - evidence_summary
      - confidence
      - applies_to
    max_items: 20
    return_mode: compact

required_capabilities:
  - media.account.discover
  - media.campaign.create
  - media.creative.variant.generate

preferred_capabilities:
  - utils.web.scrape
  - utils.image.generate

provider_requirements:
  any_of:
    - provider: meta
      scopes:
        - campaign.read
        - campaign.write
    - provider: taboola
      scopes:
        - campaign.read
        - campaign.write

stages:
  - id: discovery
    name: Discovery
    purpose: Understand the offer, project context, tracking, and provider state.
    agent_instructions:
      - Load project context and prior related runs.
      - Verify required auth and scopes.
      - Identify missing inputs before creating provider-side objects.
    allowed_capabilities:
      - media.account.discover
      - resource.query
      - artifact.query
    expected_outputs:
      - launch_context
      - missing_info

  - id: planning
    name: Launch Planning
    purpose: Create a provider-specific launch plan without writing to provider yet.
    agent_instructions:
      - Choose provider and account.
      - Draft campaign structure.
      - Define creative variant requirements.
      - Validate budget cap and tracking requirements.
    expected_outputs:
      - launch_plan
      - action_payload_drafts
      - risk_notes

  - id: approval
    name: Approval
    purpose: Get human approval before external writes or spend.
    approval:
      required: true
      reason: Provider-side campaign objects may be created.
    expected_outputs:
      - approval_decision

  - id: execution
    name: Execution
    purpose: Execute approved provider writes in safe paused state.
    agent_instructions:
      - Execute only approved payloads.
      - Create campaign/ad objects paused unless explicitly approved active.
      - Record provider ids as resources.
    expected_outputs:
      - created_resources
      - execution_summary

policies:
  - id: require_budget_cap
    severity: block
    rule: budget_cap must be present before execution.
  - id: no_active_spend_without_approval
    severity: block
    rule: Do not set paid media entities to ACTIVE unless approval explicitly permits active spend.
  - id: redact_secrets
    severity: block
    rule: Never request or print credentials.

approval_gates:
  - id: before_provider_write
    before_stage: execution
    required: true
  - id: before_active_spend
    trigger: any action would set status=ACTIVE
    required: true

outputs:
  - key: run_summary
    type: markdown
  - key: created_resources
    type: resource_refs
  - key: observations
    type: structured_list
  - key: reusable_learnings
    type: markdown
  - key: follow_up_recommendations
    type: markdown

learning_hooks:
  propose_at_run_end: true
  required_fields:
    - statement
    - evidence
    - applies_to
    - confidence

experiment:
  supported: true
  default_type: creative_test
  hypothesis_required: true
  variant_schema: media.creative_variant
  metric_requirements:
    - cpa
    - ctr
    - spend
  decision_policy:
    min_observation_window_days: 7
    min_spend: 500

success_criteria:
  - Required provider-side objects are created in paused state.
  - Created resource refs are stored.
  - Human can inspect what was created.
  - No secrets were exposed.

failure_handling:
  - If auth is missing, pause and return setup URL.
  - If provider validation fails, revise payload and retry after explaining the change.
  - If budget policy fails, stop before writes.
```

### Run Plan / Run Instance Schema

A run instance should store the resolved version of the reusable template:

```yaml
template_id: media.campaign-launch
template_version: 1.0.0
run_id: run_123
project_id: 1
goal: Launch a Meta test for Offer X

resolved_inputs:
  offer: {}
  budget_cap: 500
  provider: meta

resolved_context:
  credential_ref: cred_42
  account_id: act_123
  landing_page_snapshot: artifact_88
  context_snapshot_id: ctxsnap_55
  loaded_context:
    recent_campaign_runs:
      source: context.query
      item_count: 8
      summary_artifact: artifact_120
    active_related_experiments:
      source: experiment.query
      item_count: 2
    relevant_learnings:
      source: learning.query
      item_count: 12

resolved_stages:
  - discovery
  - planning
  - approval
  - execution

action_plan:
  - action_id: utils.web.scrape
    status: completed
  - action_id: meta.campaigns.create
    status: pending
    approval_gate: before_provider_write

outputs:
  created_resources: []
  observations: []
  proposed_learnings: []
  linked_experiment_ids: []
  risk_notes: []

status: running
```

## MCP Design

### Current Problem

The current MCP catalog exposes many domain-specific tools. This worked for SEO
but does not scale to media buying, GTM, and arbitrary private tools.

StackOS should avoid hard-coding one-level tools such as:

```text
media.campaign.create
```

as a single implementation. A campaign could be created in Meta, Taboola,
Outbrain, Google Ads, or an internal API. The platform needs another level of
depth.

### Tool Runtime Boundary

StackOS tools should be deliberately boring:

- store static definitions and records
- retrieve records with explicit filters and field lists
- validate payloads against schemas and static policies
- enforce auth, scopes, grants, budgets, redaction, and idempotency
- trigger external provider actions
- persist sanitized results, artifacts, resources, events, and audit records

StackOS tools should not:

- choose the strategy
- decide which provider to use
- decide which campaign, article, or lead list is good
- decide which experiment won
- infer durable learnings on their own
- auto-optimize or mutate user assets without an agent-authored run plan

The agent is the operator. StackOS is the instrument panel, vault, catalog,
execution adapter, and audit log.

### Bridge Exposure Levels

The agent-facing surface should be generic, but not flat. Discovery and safe
setup tools can be direct. Riskier write/execution tools should be step-scoped
and gated by run plan grants.

Direct/discovery tools:

```text
catalog.list
catalog.describe

plugin.list
plugin.enable
plugin.disable

capability.list
capability.describe

provider.list
provider.describe

auth.status
auth.start
auth.test
auth.revoke

workflowTemplate.list
workflowTemplate.describe
workflowTemplate.validate

runPlan.create
runPlan.validate
runPlan.start
runPlan.get
runPlan.list

run.get
run.list
run.abort
run.heartbeat
```

Step-scoped/gated tools:

```text
action.describe
action.validate
action.execute

resource.get
resource.query
resource.upsert

artifact.create
artifact.get
artifact.query

context.query
context.timeline

learning.query
learning.create
learning.update

experiment.query
experiment.create
experiment.recordObservation
experiment.recordDecision

decision.record
decision.query

workflowTemplate.save
workflowTemplate.fork

runPlan.update
runPlan.claimStep
runPlan.recordStep
```

Compatibility tools:

```text
procedure.*
article.*
topic.*
cluster.*
gsc.*
drift.*
interlink.*
eeat.*
publish.*
```

Plugin-specific tools may exist as generated aliases or compatibility wrappers,
but core agents should be able to work through the generic surface.
Legacy `procedure.*` tools can remain during migration as wrappers around
workflow templates and run plans, but they should not be the product model.

### Action Execution Shape

An agent should call an action by provider/action id with a full argument object:

```json
{
  "action_id": "meta.campaigns.create",
  "credential_ref": "cred_42",
  "arguments": {
    "account_id": "act_123",
    "name": "US | Broad | Trial | 2026-05-21",
    "objective": "OUTCOME_SALES",
    "status": "PAUSED",
    "daily_budget": 10000,
    "buying_type": "AUCTION",
    "special_ad_categories": []
  }
}
```

The action validates the input schema, injects auth internally, executes through
the connector, persists mapped resources/artifacts, writes audit records, and
returns a sanitized result.

### Context Query Shape

Agents should request project memory through bounded queries:

```json
{
  "source": "runs",
  "filters": {
    "template_ids": ["media.campaign-launch", "media.creative-test"],
    "providers": ["meta"],
    "statuses": ["completed"],
    "lookback": { "runs": 10 }
  },
  "fields": [
    "goal",
    "provider",
    "budget",
    "outcome_summary",
    "failures",
    "learnings"
  ],
  "max_items": 10,
  "return_mode": "compact",
  "include_provenance": true
}
```

The response should be compact and source-backed, without the tool inventing
interpretation:

```json
{
  "return_mode": "compact",
  "items": [
    {
      "run_id": "run_244",
      "goal": "Launch Offer X broad test",
      "outcome_summary": "Paused campaign created; later activated manually.",
      "failures": ["missing UTM check before approval"],
      "learnings": ["founder-led creative had lower CPA in early data"]
    }
  ],
  "provenance": [
    { "type": "run", "id": "run_244" },
    { "type": "learning", "id": "learning_123" }
  ],
  "truncated": false
}
```

Context tools should never return secrets. They should also avoid returning full
artifacts unless explicitly requested and allowed; compact fields and references
are the default. If the agent wants a synthesis, it should produce one and store
it back as an artifact, learning candidate, decision record, or run output.

## Auth And Secret Handling

### Non-Negotiable Rule

Agents must never receive secrets.

Agents do not get:

- API keys
- OAuth access tokens
- refresh tokens
- cookies
- service account private keys
- signed request secrets
- database passwords

Agents may receive:

- provider names
- auth status
- missing-scope information
- local setup URLs
- opaque credential refs
- sanitized provider/account metadata
- sanitized execution results

### Current Problem

Current `integration.set` accepts `plaintext_payload_b64`. That should not be an
agent-facing setup path in StackOS. It is acceptable as an internal/admin
mechanism during migration, but the product model should use local UI or OAuth
flows where the human enters secrets directly into the daemon.

### Target Auth Tools

```text
auth.status
auth.start
auth.test
auth.revoke
```

`auth.start` returns a local setup URL or OAuth authorization URL. The human
completes the flow in the browser. The daemon stores encrypted credentials and
returns an opaque reference.

API key example:

```json
{
  "provider": "taboola",
  "auth_scheme": "api_key",
  "setup_url": "http://localhost:5180/auth/connect/taboola?project_id=1",
  "credential_handle": "pending_abc"
}
```

OAuth example:

```json
{
  "provider": "meta",
  "auth_scheme": "oauth2",
  "authorization_url": "https://www.facebook.com/dialog/oauth?...",
  "credential_handle": "pending_xyz"
}
```

Connected status example:

```json
{
  "provider": "meta",
  "credential_ref": "cred_42",
  "status": "connected",
  "scopes": ["campaign.read", "campaign.write"],
  "expires_at": "2026-06-21T00:00:00Z"
}
```

### Execution Boundary

Execution flow:

```text
agent -> action.execute
core checks run grant and action schema
core resolves credential_ref
core decrypts secret in memory
connector process receives secret privately
connector calls provider
core redacts logs/results
core stores resources/artifacts/audit rows
agent receives sanitized result
```

Sanitized result example:

```json
{
  "provider": "meta",
  "operation": "campaigns.create",
  "resource_ref": "media.campaign:meta:123456",
  "provider_id": "123456",
  "status": "created",
  "raw_response_redacted": {}
}
```

### Credential Storage Requirements

Credential storage must support:

- project-scoped credentials
- global credentials
- encrypted payloads
- credential refs instead of exposed secrets
- OAuth state and callback handling
- token refresh jobs
- provider scopes and account bindings
- credential tests/probes
- credential usage audit
- redacted request/response logging
- per-action scope checks
- revocation/removal

Suggested core tables:

```text
auth_providers
credentials
credential_scopes
credential_accounts
oauth_states
credential_refresh_jobs
credential_usage_events
```

Existing `integration_credentials` and `integration_budgets` can be migrated
toward this shape.

## Action Manifest Design

Actions should be mostly configuration. Tools should not contain business
strategy logic.

Example action manifest:

```json
{
  "id": "meta.campaigns.create",
  "plugin": "media-buying",
  "capability": "media.campaign.create",
  "provider": "meta",
  "transport": "http",
  "method": "POST",
  "path": "/v20.0/{account_id}/campaigns",
  "auth": {
    "credential_kind": "meta-ads",
    "inject": "bearer_token",
    "required_scopes": ["campaign.write"]
  },
  "input_schema": {
    "type": "object",
    "required": ["account_id", "name", "objective", "status"],
    "properties": {
      "account_id": { "type": "string" },
      "name": { "type": "string" },
      "objective": { "type": "string" },
      "status": { "type": "string", "enum": ["ACTIVE", "PAUSED"] },
      "daily_budget": { "type": "number" },
      "buying_type": { "type": "string" },
      "special_ad_categories": {
        "type": "array",
        "items": { "type": "string" }
      }
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "provider_campaign_id": { "type": "string" },
      "status": { "type": "string" }
    }
  },
  "idempotency": {
    "fields": ["account_id", "name"]
  },
  "persistence": {
    "resource_type": "media.campaign",
    "provider_id_path": "$.id",
    "fields": {
      "name": "$.request.name",
      "status": "$.response.status"
    }
  },
  "redaction": {
    "request": ["access_token", "authorization"],
    "response": ["access_token"]
  },
  "cost": {
    "estimate_usd": 0
  },
  "rate_limit": {
    "bucket": "meta-ads",
    "qps": 2
  }
}
```

If a provider needs custom signing, pagination, upload handling, or response
normalization, that belongs in a connector adapter. The action manifest should
still describe the public contract.

## Agent Responsibility

The agent owns reasoning and orchestration:

- choose the provider
- choose the action
- construct the arguments
- decide campaign structure
- decide variant count/types
- interpret reporting
- decide what to pause, scale, launch, or revise
- request discretionary human approval when useful

The tool/action owns execution mechanics:

- validate schema
- inject auth
- call provider
- retry safely
- respect rate/cost limits
- persist outputs
- redact secrets
- write audit records

StackOS still enforces all template/run-plan approval gates and policy-required
approvals. Agents may ask for extra approval; they cannot bypass required gates.

## SEO Plugin Restructure

The existing SEO system should become a first-party plugin.

Suggested layout:

```text
plugins/seo/
  plugin.json
  resources/
    cluster.json
    topic.json
    article.json
    article_version.json
    source.json
    schema_emit.json
    interlink.json
    redirect.json
    gsc_metric.json
    drift_baseline.json
  capabilities/
    keyword.discover.json
    topic.cluster.json
    article.brief.json
    article.draft.json
    article.publish.json
    article.refresh.json
    site.monitor.json
  actions/
    topic.bulkCreate.json
    article.create.json
    article.setBrief.json
    article.setDraft.json
    article.setEdited.json
    article.markPublished.json
    gsc.queryProject.json
    gsc.inspectUrl.json
  providers/
    dataforseo.json
    ahrefs.json
    google-paa.json
    gsc.json
  workflows/
    seo-project-setup.yaml
    one-site-shortcut.yaml
    keyword-to-topic-queue.yaml
    topic-to-published.yaml
    bulk-content-launch.yaml
    weekly-gsc-review.yaml
    monthly-refresh.yaml
  skills/
    keyword-discovery/
    serp-analyzer/
    content-brief/
    outline/
    draft-body/
    editor/
    eeat-gate/
    schema-emitter/
    interlinker/
    content-refresher/
  ui/
    nav.json
    views/
  docs/
```

Existing tools can be kept as compatibility aliases during migration:

```text
article.setBrief -> action.execute(seo.article.setBrief)
topic.bulkCreate -> action.execute(seo.topic.bulkCreate)
gsc.queryProject -> action.execute(seo.gsc.queryProject)
```

## Utility Plugin Restructure

Utilities should be reusable by every domain plugin.

Suggested capabilities:

```text
utils.image.generate
utils.video.generate
utils.web.scrape
utils.web.crawl
utils.web.extract
utils.web.read
utils.community.search
utils.transcribe
utils.asset.store
```

Current mappings:

```text
openaiImages.generate -> utils.image.generate
firecrawl.scrape     -> utils.web.scrape
firecrawl.crawl      -> utils.web.crawl
firecrawl.extract    -> utils.web.extract
jina.read            -> utils.web.read
reddit.searchSubreddit -> utils.community.search
reddit.topQuestions    -> utils.community.questions
```

## Media Buying Plugin Reference Design

The media buying plugin is the forcing function proving StackOS is not just
renamed SEO.

### Resources

```text
media.ad_account
media.campaign
media.ad_set
media.ad
media.creative
media.audience
media.pixel
media.offer
media.experiment
media.report
```

### Capabilities

```text
media.account.discover
media.campaign.create
media.campaign.update
media.adset.create
media.ad.create
media.creative.upload
media.creative.variant.generate
media.report.fetch
media.pacing.review
media.experiment.launch
media.experiment.evaluate
```

### Providers

```text
meta
google-ads
taboola
outbrain
tiktok
internal-buying-api
```

### Campaign Create Example

`media.campaign.create` is a capability. It should not be implemented once in
core.

Provider actions:

```text
meta.campaigns.create
taboola.campaigns.create
outbrain.campaigns.create
internal-buying-api.launchCampaign
```

The agent selects the provider and passes arguments that match that provider's
schema. StackOS schema-checks, executes, persists, and audits.

## Variant Generation Design

Variant generation must be configurable by the agent. The generator should not
hard-code what variants mean.

The agent should pass:

- variant types
- count
- source material
- target audience
- platform/channel
- compliance constraints
- forbidden claims
- tone/style constraints
- output schema

Example:

```json
{
  "capability": "creative.variant.generate",
  "arguments": {
    "variant_types": ["headline", "primary_text", "image_prompt"],
    "count": 12,
    "source": {
      "offer": "Free trial for analytics SaaS",
      "audience": "founders running paid acquisition",
      "landing_page_url": "https://example.com"
    },
    "constraints": {
      "headline_max_chars": 40,
      "tone": "direct",
      "platform": "meta",
      "forbidden_claims": ["guaranteed ROI"]
    },
    "output_schema": {
      "variants": [
        {
          "angle": "string",
          "headline": "string",
          "primary_text": "string",
          "image_prompt": "string",
          "risk_notes": "string[]"
        }
      ]
    }
  }
}
```

The tool returns structured artifacts. The agent decides how to use them.

## UI Restructure

The UI should become a core shell plus plugin-contributed sections.

Core navigation:

```text
Overview
Projects
Plugins
Capabilities
Auth / Connections
Runs
Workflow Templates
Project Data
Schedules
Costs / Budgets
Settings
```

`Project Data` should group context snapshots, learnings, experiments,
decisions, artifacts, metrics, and event timeline views so the core navigation
does not become a long list of primitives.

Plugin navigation examples:

```text
SEO
  Topics
  Articles
  Search Console
  Drift
  Interlinks

Media Buying
  Accounts
  Campaigns
  Creatives
  Experiments
  Reports

GTM
  Accounts
  Contacts
  Sequences
  Pipeline
```

Plugin UI contributions should come from manifests such as:

```json
{
  "plugin": "media-buying",
  "nav": [
    {
      "label": "Media Buying",
      "items": [
        { "label": "Accounts", "route": "/projects/:id/media/accounts" },
        { "label": "Campaigns", "route": "/projects/:id/media/campaigns" },
        { "label": "Creatives", "route": "/projects/:id/media/creatives" },
        { "label": "Reports", "route": "/projects/:id/media/reports" }
      ]
    }
  ]
}
```

Project readiness should be plugin-specific, not hard-coded to voice,
compliance, EEAT, targets, topics, and articles.

## Data Model Plan

### Core Tables To Add

```text
plugins
project_plugins
capabilities
providers
actions
action_versions
resources
resource_records
artifacts
project_events
context_index_entries
context_snapshots
learnings
experiments
experiment_variants
experiment_observations
decisions
metric_snapshots
workflow_templates
workflow_template_versions
project_workflow_templates
run_plans
run_plan_steps
approval_requests
auth_providers
credentials
credential_scopes
credential_accounts
oauth_states
credential_usage_events
```

### Existing Tables To Keep

```text
projects
workspace_bindings
agent_sessions
runs
run_steps
run_step_calls
idempotency_keys
scheduled_jobs
integration_budgets
```

`procedure_run_steps` should be treated as a legacy table and migrated or
mirrored into `run_plan_steps`.

### Existing Tables To Move Under SEO Ownership

```text
clusters
topics
articles
article_versions
article_assets
article_publishes
research_sources
schema_emits
internal_links
redirects
gsc_metrics
gsc_metrics_daily
drift_baselines
eeat_criteria
eeat_evaluations
voice_profiles
authors
compliance_rules
publish_targets
```

Some of these, such as authors, compliance, voice, and publish targets, may
eventually become shared plugins or core-adjacent resources, but they should not
remain hard-coded as the universal project setup model.

## Permission Model

Current per-skill grants are useful and should survive, but grants need to be
plugin/action aware.

Target grant shape:

```json
{
  "skill": "media-buying/campaign-launch",
  "allowed": {
    "capabilities": [
      "media.campaign.create",
      "media.adset.create",
      "media.creative.upload"
    ],
    "actions": [
      "meta.campaigns.create",
      "meta.adsets.create",
      "meta.creatives.upload"
    ],
    "resources": [
      "media.campaign",
      "media.creative",
      "media.experiment"
    ],
    "context_sources": [
      "runs",
      "resources",
      "artifacts",
      "experiments",
      "learnings",
      "decisions",
      "metrics"
    ],
    "credentials": [
      {
        "provider": "meta",
        "scopes": ["campaign.write"]
      }
    ]
  }
}
```

The bridge should only allow `action.execute` when:

- the run token maps to the current workflow run step
- the workflow template and resolved run plan grant the capability/action
- the workflow template and resolved run plan grant the requested context source
  and fields
- the project has the plugin enabled
- the credential ref is available to the project
- the credential has required scopes
- the provider/action is installed and active

## Workflow Fit Simulations

These simulations are used to pressure-test the architecture against real
agent/person workflows. In every case StackOS remains the tool layer: it stores
and retrieves data, validates static contracts, triggers external actions, and
records audit trails. The agent decides what to do and what the evidence means.

### 1. SEO Article Refresh

Goal: improve CTR or ranking for an existing page.

The template asks for the article resource, GSC trend, prior refresh runs for
the URL, title/meta history, ranking movements, and learnings tagged `seo`,
`ctr`, `title`, or `intent`.

The run creates a refresh plan, updates content/meta/schema through approved
actions, records before/after snapshots, and may create an SEO experiment for a
title or meta change.

Architecture lesson: the article needs project-level history. The template only
declares which history to retrieve.

### 2. New SEO Content Cluster

Goal: build a topic cluster around a commercial theme.

The template asks for existing clusters, published articles, keyword gaps,
internal-link graph state, and prior cluster outcomes.

The run creates or updates topic resources, briefs, publishing sequence, and
interlinking tasks. The agent may record learnings such as which intent types
worked in this niche.

Architecture lesson: context queries need filters by resource type, theme,
intent, and outcome.

### 3. Media Buying Campaign Launch

Goal: launch a paused campaign for a new offer.

The template asks for connected ad accounts, prior launches for the same offer
or category, budget policies, compliance artifacts, and creative learnings.

The agent builds campaign/ad set/ad payloads, validates auth/scopes through
StackOS, requests approval, and creates paused provider objects through
`action.execute`.

Architecture lesson: campaign creation is a provider action selected by the
agent. Experiments track what is being tested across runs.

### 4. Creative Variant Generation

Goal: generate and store creative variants for a campaign.

The template asks for brand rules, offer positioning, platform specs, previous
winners/losers, and existing assets.

The agent generates variants through utility actions, stores them as artifacts,
and optionally pushes approved variants to a media provider.

Architecture lesson: learnings need confidence, tags, source runs, and negative
evidence. The tool stores the learning candidate; the agent or human decides
whether to trust it.

### 5. Media Buying Optimization

Goal: review active campaigns and suggest or execute approved changes.

The template asks for active campaign resources, spend/performance metrics,
previous optimization runs, active experiments, and guardrails such as minimum
data thresholds and budget caps.

The agent produces recommendations, then executes only approved
budget/status/bid changes.

Architecture lesson: experiments need states such as running, inconclusive,
winner, loser, paused, and needs-more-data. StackOS stores the state; the agent
or human records the decision.

### 6. GTM Lead List Build

Goal: create a prospect list for a segment.

The template asks for ICP definition, prior lead lists, exclusion lists,
enrichment provider status, and conversion learnings.

The agent finds accounts/contacts, enriches them, stores lead resources, and
exports or pushes to CRM through StackOS actions.

Architecture lesson: project memory must support cross-domain context. GTM can
reuse learnings from SEO and media buying about markets, offers, and audience
language.

### 7. GTM Outreach Sequence

Goal: create and launch an outbound sequence.

The template asks for ICP, existing messaging, past reply-rate outcomes,
compliance rules, connected CRM/sequencer providers, and active experiments.

The agent drafts variants, requests approval, and pushes approved assets to the
sequencer through StackOS actions.

Architecture lesson: templates need approval policies and channel compliance,
but experimentation remains project-level.

### 8. Landing Page Test

Goal: create or update a landing page for paid traffic.

The template asks for offer details, existing pages, prior conversion learnings,
active media experiments, brand rules, and compliance artifacts.

The agent generates page copy/assets, opens a PR or updates CMS through a
provider action, and links the page to campaigns and experiments.

Architecture lesson: runs need linked resources across plugins: campaign,
landing page, creative, article, and CRM sequence.

### 9. Weekly Business Review

Goal: summarize what happened across SEO, media buying, and GTM.

The template asks for last 7 days of runs, active experiments, KPI metrics, new
learnings, failed runs, pending approvals, and notable decisions.

The agent produces a report artifact and records decision items supplied by the
agent or human.

Architecture lesson: `context.query` must support strict field selection and
limits. Otherwise project memory will flood the agent context window.

### 10. Incident Or Regression Investigation

Goal: investigate traffic drops, spend spikes, lead-quality regressions, or
publishing failures.

The template asks for recent project events, recent runs across all plugins,
provider errors, resource diffs, metric anomaly windows, and recent decisions.

The agent builds a timeline, identifies likely causes, recommends remediation,
and executes approved fixes through StackOS actions.

Architecture lesson: the project needs an event timeline. Runs alone are not
enough to understand operational causality.

## Delivery Plan

Delivery must follow the governance in
`docs/stackos-current-setup-gap-analysis.md` and the dependency-aware task plan
in `docs/stackos-deliverable-task-plan.md`: verify docs, break work into
signed-off deliverables, verify each deliverable, and commit each successful
signed-off delivery separately.

### Phase 0: Naming And Compatibility Decision

Goal: Set the direction without breaking existing users.

Tasks:

- Adopt StackOS as product/runtime name in new docs.
- Keep `content-stack` CLI/data-dir compatibility during migration.
- Add `stackos` command alias later.
- Decide package rename timing separately from architecture work.

Deliverables:

- New StackOS design docs.
- README framing update.
- Compatibility policy for old names and paths.

Acceptance criteria:

- Existing install still works.
- New docs clearly describe StackOS as a plugin runtime.

### Phase 1: Catalog And Plugin Registry

Goal: Introduce first-class plugins and installed capabilities.

Tasks:

- Add `plugins` and `project_plugins` tables.
- Add plugin manifest parser.
- Register built-in `core`, `seo`, and `utils` plugin manifests.
- Add `plugin.list`, `plugin.enable`, `plugin.disable`.
- Add `catalog.list` and `catalog.describe`.
- Surface installed/enabled plugins in UI.

Acceptance criteria:

- StackOS can list installed plugins.
- Projects can enable/disable plugins.
- SEO can be represented as an enabled plugin, even before full extraction.

### Phase 2: Auth Boundary

Goal: Remove agent-facing secret ingestion.

Tasks:

- Add `auth.status`, `auth.start`, `auth.test`, `auth.revoke`.
- Add local UI screens for API-key entry and OAuth setup.
- Store credentials encrypted, returning only `credential_ref`.
- Add credential scopes/accounts metadata.
- Add credential usage audit events.
- Keep old `integration.set` internal/compat only, not advertised to agents.
- Convert GSC OAuth into the generic auth model.

Acceptance criteria:

- Agent can initiate setup but never sees a secret.
- Human can connect API key and OAuth providers through local UI.
- Action/provider execution receives secrets internally.
- Logs and MCP responses are redacted.

### Phase 3: Generic Action Executor

Goal: Make provider operations configurable.

Tasks:

- Add `actions` and `action_versions` tables or manifest registry.
- Add `action.describe`, `action.validate`, `action.execute`.
- Implement JSON-schema validation for action arguments.
- Implement credential resolution and secret injection.
- Implement redaction rules.
- Implement idempotency from action config.
- Implement resource/artifact persistence mapping.
- Port one utility action, such as `openaiImages.generate`, to the new model.

Acceptance criteria:

- Agent can discover an action schema.
- Agent can validate payload before execution.
- Agent can execute action with a credential ref.
- Returned result contains no secrets.
- Audit trail records action id, provider, credential ref, redacted request,
  redacted response, cost, and duration.

### Phase 4: Project Context, Learnings, And Experiments

Goal: Add the project memory primitives without turning StackOS into a decision
engine.

Tasks:

- Add project event, context index, context snapshot, learning, experiment,
  observation, decision, and metric snapshot tables.
- Add `context.query` with filters, field projection, limits, return modes, and
  provenance.
- Add `context.timeline` for bounded event retrieval.
- Add `learning.query`, `learning.create`, and `learning.update`.
- Add `experiment.query`, `experiment.create`, `experiment.recordObservation`,
  and `experiment.recordDecision`.
- Add `decision.record` and `decision.query`.
- Ensure every context response is secret-redacted and bounded by explicit
  limits.
- Keep interpretation outside the daemon: agents or humans write summaries,
  decisions, learnings, and experiment outcomes as data.

Acceptance criteria:

- Agents can retrieve the last N relevant runs with selected fields only.
- Agents can query active experiments and accepted learnings for a project.
- Runs can store the context snapshot they used.
- StackOS never decides which learning is true or which experiment won.

### Phase 5: Workflow Templates And Run Plans

Goal: Replace hard-coded procedures with reusable templates and agent-resolved
run plans.

Tasks:

- Add workflow template registry/parser for plugin, project, and repo-local
  templates.
- Support `.stackos/workflows/*.yaml` so agents can extend company-specific
  workflows inside the user's repository.
- Add `workflowTemplate.list`, `workflowTemplate.describe`,
  `workflowTemplate.validate`, `workflowTemplate.save`, and
  `workflowTemplate.fork`.
- Add `runPlan.create`, `runPlan.validate`, `runPlan.start`,
  `runPlan.update`, `runPlan.claimStep`, and `runPlan.recordStep`.
- Add schema validation for template inputs, stages, capabilities, policies,
  approvals, outputs, and failure handling.
- Store the resolved run plan and context snapshot for every run so execution is auditable
  even when the reusable template changes later.
- Implement approval gate handling as first-class run state.
- Keep old `procedure.*` endpoints as compatibility wrappers where needed.

Acceptance criteria:

- A built-in workflow template can produce a concrete run plan.
- An agent can fork or extend a template without changing core code.
- Run execution uses the resolved plan snapshot, not mutable template state.
- Existing procedure-backed SEO flows can be represented as workflow templates.

### Phase 6: SEO Plugin Boundary

Goal: Move current SEO concepts behind a plugin boundary.

Tasks:

- Create `plugins/seo` manifest.
- Move or mirror current SEO skills and legacy procedures into plugin-owned
  workflow templates.
- Register SEO resources/capabilities/actions.
- Add compatibility aliases for current MCP tool names.
- Move SEO nav into plugin UI contribution config.
- Update the run plan engine to load plugin and repo-local workflow templates.
- Update permissions to load template, skill, and action grants.

Acceptance criteria:

- Existing SEO flows still run.
- SEO appears as a plugin in the UI.
- Disabling SEO hides SEO nav/capabilities for that project.
- New generic catalog can describe SEO capabilities/actions.

### Phase 7: Utility Plugin Boundary

Goal: Make media/web utility providers reusable by every plugin.

Tasks:

- Create `plugins/utils`.
- Register utility capabilities: image generation, web scrape, web extract,
  web read, community search, artifact store.
- Convert OpenAI Images, Firecrawl, Jina, and Reddit wrappers into provider
  actions.
- Update SEO workflow templates to consume utility capabilities instead of direct
  vendor tools where practical.

Acceptance criteria:

- SEO can call utility capabilities through granted actions.
- Media buying/GTM can reuse the same utilities without SEO coupling.

### Phase 8: Media Buying MVP Plugin

Goal: Prove StackOS supports a non-SEO domain.

Tasks:

- Add `plugins/media-buying`.
- Define resources: ad account, campaign, ad set, ad, creative, audience,
  pixel, offer, experiment, report.
- Define providers: Meta first, plus placeholder manifests for Taboola,
  Outbrain, and internal API.
- Implement auth flow for Meta.
- Implement read-only account discovery.
- Implement one write action: create campaign as paused.
- Implement creative variant generation as configurable utility-backed action.
- Add media buying UI nav and basic resource views.
- Add a workflow template: launch paused campaign draft for human review.

Acceptance criteria:

- Project can enable media buying plugin.
- Agent can discover Meta campaign creation schema.
- Human connects Meta credential without exposing token to agent.
- Agent can create a paused campaign through `action.execute`.
- Run audit shows all action calls and sanitized payloads.

### Phase 9: UI Shell And Plugin-Contributed Navigation

Goal: Stop hard-coding SEO navigation.

Tasks:

- Replace static app nav with core nav plus plugin nav contributions.
- Add plugin readiness panels.
- Add generic action/resource/artifact browser.
- Keep SEO views available through the SEO plugin nav.
- Add auth/connections hub.

Acceptance criteria:

- Enabling/disabling plugins changes navigation.
- Core UI remains useful with no domain plugins enabled.
- SEO and media buying can coexist in one project.

### Phase 10: Deprecation And Cleanup

Goal: Retire SEO-shaped core assumptions.

Tasks:

- Deprecate direct `article.*`, `topic.*`, etc. as core tools.
- Deprecate product-level `procedure.*` in favor of workflow templates and run
  plans.
- Keep aliases for one or more releases.
- Move jobs such as GSC pull and drift rollup under plugin schedules.
- Rename docs and package surfaces where appropriate.
- Add migration docs for existing local DBs.

Acceptance criteria:

- No SEO-only table/tool is required by StackOS core startup.
- Existing users can migrate without data loss.
- New installs present StackOS plus optional plugins.

## Key Risks

- Over-generalizing too early. Mitigation: build the generic model by porting
  current SEO actions and one real media buying action.
- Plugin migrations may become complex. Mitigation: start with manifest-driven
  registration and keep existing tables until the new model is stable.
- Generic `action.execute` may become too opaque. Mitigation: require
  `action.describe`, explicit schemas, validation, previews, and strong audit
  records.
- Auth mistakes could leak secrets. Mitigation: make no-secrets-to-agent a test
  invariant, with redaction checks on every action result and audit payload.
- UI could become too abstract. Mitigation: core UI for platform state, plugin UI
  for domain workflows.

## Immediate Next Steps

1. Add StackOS naming/design docs.
2. Draft plugin manifest schema.
3. Draft auth provider/credential schema.
4. Draft action manifest schema.
5. Draft project context, learning, experiment, decision, and event schemas.
6. Draft workflow template and run plan schemas, including
   `context_requirements`.
7. Add tests that assert agent-facing auth and context tools never return
   secret fields.
8. Add a skeleton `plugins/seo/plugin.json` that maps current SEO catalog.
9. Add skeleton SEO workflow templates under `plugins/seo/workflows`.
10. Add repo-local `.stackos/workflows` loading and validation.
11. Add a skeleton `plugins/media-buying/plugin.json` with Meta campaign create
   as the first non-SEO target.
