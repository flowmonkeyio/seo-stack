# StackOS Integration Audit

This audit maps the current integration surface after the StackOS pivot and
identifies the integrations and architecture changes needed to support SEO,
media buying, GTM, utilities, and user-installed plugins without putting
business logic or secrets into the agent context.

## Design Position

StackOS should remain a tool, storage, auth, and audit layer.

Agents and operators decide what to do. StackOS describes available tools,
validates explicit payloads, resolves daemon-held credentials, executes
configured provider operations, stores results, and records audit.

External tools should be exposed through static plugin metadata:

- providers: what external or local systems exist
- auth providers: how credentials are stored and tested
- actions: exact callable operations with input and output schemas
- resources: durable domain records the agent can write or query
- workflow templates: reusable setup, context needs, constraints, and base steps
- run plans: concrete action refs, inputs, scoped grants, and outputs for one run

No action config, run plan, resource, MCP response, UI JSON, or template should
contain plaintext secrets. Agents should only see provider keys, account refs,
and opaque `credential_ref` values.

## Current Integration Surfaces

### Plugin Catalog

Files:

- `content_stack/plugins/manifest.py`
- `plugins/seo/plugin.yaml`
- `plugins/core/workflows/project-memory-review.yaml`
- `plugins/seo/workflows/keyword-research.yaml`
- `plugins/seo/workflows/content-refresh.yaml`

Current built-in plugins:

| Plugin | What It Provides | Current State |
| --- | --- | --- |
| `core` | Local daemon provider, catalog primitives, project data resources, project memory review template | Good generic foundation. |
| `utils` | OpenAI Images, Firecrawl, Jina, Reddit providers; image generation and web retrieval capabilities | Partially wired. `utils.image.generate` is executable through the generic action path. `utils.web.scrape` is catalog-only today. |
| `seo` | DataForSEO and Ahrefs providers, SEO actions, SEO resource schemas, two SEO templates | Good domain package shape, but its actions are not yet executable through the generic connector path. |

Current templates are intentionally small and reusable, but the library is thin:

- `core.project-memory-review`
- `seo.keyword-research`
- `seo.content-refresh`

This explains why the UI shows fewer templates than the older procedure system.
The clean-cut architecture removed hard-coded procedure catalogs. We now need to
rebuild the first-party template library as plugin templates.

### Auth And Credential Boundary

Files:

- `content_stack/auth_providers/repository.py`
- `content_stack/api/auth_providers.py`
- `content_stack/mcp/tools/auth.py`
- `docs/auth-providers.md`

REST routes exist for:

- list providers
- inspect sanitized project auth status
- start local setup
- store a secret through the local-admin path
- test a credential
- revoke a credential

MCP tools exist for:

- `auth.status`
- `auth.start`
- `auth.test`
- `auth.revoke`

The bridge advertises only `auth.status` and `auth.test` to normal agents.
`auth.start` and `auth.revoke` are admin/setup operations.

Auth providers are synced from plugin provider manifests. A daemon wrapper alone
does not make a provider setup-ready. For example, WordPress and Ghost wrappers
are registered in the integration registry, but no first-party plugin provider
manifest currently declares them, so generic auth setup for those providers is
not available yet.

The repository correctly treats plaintext credentials as daemon-only data.
`ResolvedCredential` is an internal dataclass with plaintext hidden from
serialization. `CredentialConnectionOut` returns safe refs and status only.

Current implementation note: the new `credentials` table is still backed by the
older encrypted `integration_credentials` table. That is acceptable as an
internal secret blob store during the clean-cut transition, but it should remain
an implementation detail. Long term we should either promote the new credential
model as the only public concept and keep `integration_credentials` fully
internal, or migrate the encrypted payload columns into the credential model and
remove the duplicate naming.

Current gap: the UI `Connections` page is read-only. The API can store, test,
and revoke secrets, but the operator-facing local setup controls are not yet
present in the generic UI.

### Generic Action Executor

Files:

- `content_stack/actions/connectors.py`
- `content_stack/actions/manifest.py`
- `content_stack/actions/repository.py`
- `content_stack/actions/openai_images.py`
- `content_stack/mcp/tools/actions.py`
- `content_stack/workflows/run_plan_grants.py`
- `docs/action-executor.md`

The action executor is the clean StackOS path:

1. Plugin action manifest defines static schema and connector config.
2. Agent validates an explicit payload.
3. A run-plan step grants `action.execute` for exact `action_refs`.
4. The daemon resolves the credential internally.
5. Connector executes the operation.
6. `action_calls` records redacted request, response, status, cost, and refs.

Current executable connector registry:

| Connector | Action Ref | Provider | Status |
| --- | --- | --- | --- |
| `openai-images` | `utils.image.generate` | `openai-images` | Ready and connected to generic `action.execute`. |

Everything else is either catalog-only or still exposed through hidden vendor
MCP tools.

Important response-shape gap: `ActionCallAuditOut` correctly hides internal
`credential_id`, but `ActionCallOut` still includes it and is used in the
`action.execute` response. Since `action.execute` is agent-callable inside
run-plan grants, that result should return the public audit shape or otherwise
omit internal database identifiers. Agents should see `credential_ref`, not
internal credential primary keys.

### Hidden Vendor MCP Tools

File:

- `content_stack/mcp/tools/vendor_ops.py`

Current hidden vendor tools:

- `dataforseo.serp`
- `dataforseo.keywordVolume`
- `dataforseo.domainIntersection`
- `dataforseo.keywordsForSite`
- `dataforseo.paa`
- `firecrawl.scrape`
- `firecrawl.crawl`
- `firecrawl.map`
- `firecrawl.extract`
- `openaiImages.generate`
- `reddit.searchSubreddit`
- `reddit.topQuestions`
- `googlePaa.extract`
- `jina.read`
- `ahrefs.keywordsForSite`
- `ahrefs.topBacklinks`

These wrappers are useful implementation assets, but they are not the desired
long-term agent surface. Run-plan grants currently allow `action.execute`, not
direct vendor tools. That means the clean-cut path is to migrate these vendor
operations into action connectors and plugin action manifests, then retire the
vendor MCP path as an agent execution mechanism.

The hidden vendor result payloads also include internal `credential_id`. Even
though that is not a secret, it violates the opaque-reference posture and should
be removed or replaced with `credential_ref` before any vendor tool remains
agent-reachable.

### Daemon Integration Wrappers

Files:

- `content_stack/integrations/__init__.py`
- `content_stack/integrations/dataforseo.py`
- `content_stack/integrations/ahrefs.py`
- `content_stack/integrations/firecrawl.py`
- `content_stack/integrations/openai_images.py`
- `content_stack/integrations/reddit.py`
- `content_stack/integrations/google_paa.py`
- `content_stack/integrations/jina_reader.py`
- `content_stack/integrations/wordpress.py`
- `content_stack/integrations/ghost.py`
- `content_stack/integrations/sitemap.py`

Wrapper inventory:

| Provider | Wrapper Operations | Current Exposure | Readiness |
| --- | --- | --- | --- |
| `openai-images` | `generate`, `test_credentials` | Generic action connector and hidden vendor tool | Ready, but hidden duplicate should be removed after migration. |
| `dataforseo` | SERP, keyword volume, domain intersection, keywords for site, PAA, credential test | SEO plugin actions plus hidden vendor MCP tools | Partial. Needs action connector and tighter schemas. |
| `ahrefs` | keywords for site, top backlinks, credential test | SEO plugin actions plus hidden vendor MCP tools | Partial. Needs action connector and tighter schemas. |
| `firecrawl` | scrape, crawl, map, extract, credential test | Utils provider plus hidden vendor MCP tools | Partial. `utils.web.scrape` lacks connector config. |
| `jina` | read URL, credential test | Utils provider plus hidden vendor MCP tool | Partial. Needs action manifest, connector, and explicit optional-auth semantics. |
| `reddit` | search subreddit, top questions, credential test | Utils provider plus hidden vendor MCP tools | Partial. Needs action manifests and connector. |
| `google-paa` | PAA extraction through Firecrawl | Hidden vendor MCP tool only | Partial. No provider/action manifest; dependency on Firecrawl should be explicit. |
| `wordpress` | current user, credential test | Wrapper registered only; no plugin provider manifest | Not setup-ready. Needs publishing plugin provider manifest, post/media actions, and connector. |
| `ghost` | users, credential test | Wrapper registered only; no plugin provider manifest | Not setup-ready. Needs publishing plugin provider manifest, post/image actions, and connector. |
| sitemap | sitemap fetch | Project REST/MCP setup utility | Useful core utility. Could remain core or become a utility action for run-plan use. |

## Key Gaps

### 1. Connector Coverage Is Too Narrow

Only OpenAI Images is on the generic connector path. DataForSEO, Ahrefs,
Firecrawl, Jina, Reddit, Google PAA, WordPress, and Ghost still need connector
adapters so agents can call them through `action.execute` with explicit
`action_refs`.

### 2. SEO Actions Are Catalog Contracts, Not Executable Tools Yet

`plugins/seo/plugin.yaml` defines:

- `keyword.research`
- `serp.analyze`
- `competitor.keywords`
- `backlink.research`

Those actions have `operation`, credential, and budget config, but no
`connector`. The action executor will currently report "action has no connector
configured for execution" for these actions.

The input and output schemas are also broad objects. That is acceptable for a
first catalog pass, but not for reliable tool execution. Each action should
define required fields, allowed fields, and normalized outputs.

### 3. Hidden Vendor Tools Duplicate The New Model

`vendor_ops.py` still contains provider-specific MCP tools. That was useful for
the SEO-era procedure model, but the StackOS architecture should converge on:

- direct discovery: `action.describe`, `action.validate`
- run-plan execution: `action.execute`
- plugin metadata: provider/action/resource/template contracts
- daemon connectors: provider wrappers, auth, rate limits, budgets, retries

The agent should not need `dataforseo.serp` or `firecrawl.scrape` as a direct
tool name. It should call `seo.serp.analyze`, `utils.web.scrape`, or another
plugin action ref selected by the run plan.

### 4. Auth UI Needs Local-Admin Controls

The backend supports secret storage, testing, and revocation. The UI currently
shows provider status and credential refs only.

Needed UI controls:

- choose provider
- enter or paste secret in a local-only secret input
- enter safe config fields such as account label, login, site URL, base URL, or scopes
- store credential
- test credential
- revoke credential
- show provider account metadata when available

This must remain local-admin UI. The agent can inspect status and test results,
but should never see secret values.

### 5. Provider Catalog And Wrapper Registry Are Not Fully Aligned

Some wrappers exist without first-class plugin provider/action definitions:

- `wordpress`
- `ghost`
- `google-paa`

Some plugin providers exist without generic executable actions:

- `firecrawl`
- `jina`
- `reddit`
- `dataforseo`
- `ahrefs`

For a clean plugin system, every external provider should have matching:

- plugin provider manifest
- auth provider metadata
- daemon wrapper
- action connector
- action manifest
- tests
- docs

Jina also exposes an auth modeling issue. The utils plugin declares `jina` as an
`api-key` provider, while the current hidden wrapper can run without a
credential. The clean action path should either model Jina as optional auth or
set each Jina action to `requires_credential: false` and `allows_credential:
true` so agents are not blocked when no key is configured.

### 6. Campaign And Variant Operations Need Provider-Specific Depth

The old "one level" shape is not enough. "Create campaign" is not one universal
operation. It might mean Meta, Google Ads, Outbrain, Taboola, TikTok, LinkedIn,
Microsoft Ads, or a user's internal campaign tool.

The clean model is provider-specific action refs with shared resource schemas:

- `media-buying.meta.campaign.create`
- `media-buying.meta.ad-set.create`
- `media-buying.meta.creative.upload`
- `media-buying.outbrain.campaign.create`
- `media-buying.taboola.campaign.create`
- `media-buying.local.campaign.create`

The shared `campaign`, `ad-group`, `creative`, `audience`, and `performance`
resources can store normalized durable records. The provider-specific actions
own request shape, auth, idempotency, and output normalization.

"Generate variants" has the same issue. A template can say the workflow may
generate variants, but the run plan must specify:

- variant type: copy, image, video, landing page, audience, bid, offer, title, CTA
- source assets or source records
- constraints: brand, channel, dimensions, policy rules, exclusions
- count and axes
- required output schema
- whether the result is only a resource, an artifact, or an external platform mutation
- which action refs are allowed

The tool should not decide those axes. The agent decides and passes explicit
configuration to a utility or domain action.

### 7. Action Availability Needs To Be Visible

Operators and agents need to know whether a catalog action is actually
executable before starting a run. `action.describe` already returns connector
availability, but the UI does not yet surface action status such as:

- executable
- missing connector
- missing credential
- provider disabled
- budget blocked

This is important while the repo contains a mix of migrated actions and
catalog-only contracts.

## Integration Contract For New Providers

Every new external provider should ship with the same checklist:

1. Plugin manifest provider entry with `auth_type`, scopes, and safe metadata.
2. Resource schemas for durable records the agent can store and query.
3. Action manifests with exact input/output schemas, risk level, connector,
   operation, credential policy, and budget kind.
4. Daemon integration wrapper for provider API calls, retries, rate limits,
   cost accounting, response normalization, and safe errors.
5. Action connector that adapts static action payloads to the wrapper without
   deciding strategy.
6. Auth test implementation and local-admin setup requirements.
7. Run-plan grant tests proving `action.execute` only works for declared
   `action_refs`.
8. UI rendering through generic catalog, connection, resource, action-call,
   template, and run-plan pages.
9. Documentation for setup, action schemas, output schemas, and known limits.

## Needed Integrations

### P0: Finish The Existing Integration Migration

These are needed before adding many new domains:

| Need | Why |
| --- | --- |
| Firecrawl action connector | Makes `utils.web.scrape`, crawl, map, and extract run through `action.execute`. |
| Jina action connector | Gives a lightweight web-reader utility action. |
| Reddit action connector | Moves audience/question research out of hidden vendor tools. |
| DataForSEO action connector | Makes SEO templates actually executable without old procedure paths. |
| Ahrefs action connector | Enables competitor keyword and backlink research through the generic action path. |
| Google PAA action contract | Decide whether it is a DataForSEO action, Firecrawl-derived utility action, or SEO action that depends on Firecrawl. |
| WordPress publishing connector | Current wrapper only tests credentials. Publishing needs post/media actions. |
| Ghost publishing connector | Current wrapper only tests credentials. Publishing needs post/image actions. |
| Credential setup UI | Backend exists; operators need a clean local-admin setup screen. |
| Custom HTTP/Webhook connector | Allows user-owned internal tools to become StackOS actions without hard-coding each one into core. |

### P1: Utilities Plugin Expansion

Utilities should be available to any domain:

- image generation: already started with OpenAI Images
- video generation: provider-neutral action contracts for prompt-to-video,
  image-to-video, and video edits
- web retrieval: Firecrawl, Jina, browser/screenshot capture
- file storage: S3, R2, GCS, local artifact store
- document parsing: PDF, HTML, CSV, spreadsheet ingestion
- notifications: Slack, email, webhook
- data export/import: Google Sheets, Airtable, CSV, database query adapters
- media processing: resize, transcode, extract frames, transcription

These should live under `utils` unless a domain-specific plugin needs a tighter
contract.

### P1: Media Buying Plugin

Start as `plugins/media-buying/plugin.yaml`.

Providers to plan:

- Meta Marketing API
- Google Ads
- TikTok Ads
- LinkedIn Ads
- Microsoft Ads
- Outbrain
- Taboola
- custom/internal campaign tools through the generic HTTP/Webhook connector

Resource schemas:

- ad account
- campaign
- ad set or ad group
- ad
- creative
- audience
- landing page
- conversion event
- performance snapshot
- budget change
- experiment

Action groups:

- account.list
- campaign.create/update/pause/resume
- ad-set.create/update
- ad-group.create/update
- creative.upload/create
- ad.create/update
- audience.sync
- insight.fetch
- conversion-event.fetch
- budget.update

Templates:

- launch paid campaign
- generate creative variants
- diagnose campaign performance
- budget reallocation review
- landing page and ad creative experiment

Important rule: do not expose one generic `campaign.create` action unless it is
a local abstraction configured by the user. First-party provider actions should
be provider-specific so schemas, constraints, and outputs are precise.

### P1: GTM And RevOps Plugin

Use `GTM` here as go-to-market systems, not Google Tag Manager.

Providers to plan:

- HubSpot
- Salesforce
- Pipedrive
- Apollo
- Clay
- Clearbit or enrichment provider
- Outreach
- Salesloft
- Gmail/Google Workspace
- Microsoft 365

Resource schemas:

- account
- company
- contact
- lead
- opportunity or deal
- sequence
- task
- touchpoint
- enrichment record
- pipeline snapshot

Action groups:

- lead.import
- contact.upsert
- company.upsert
- enrichment.run
- sequence.add
- task.create
- crm.note.create
- pipeline.fetch
- touchpoint.record

Templates:

- account research
- lead enrichment and scoring
- outbound sequence preparation
- CRM hygiene pass
- pipeline risk review

### P1: Analytics And Measurement Plugin

Providers to plan:

- GA4 Data API
- Google Search Console
- Google Ads reporting
- Meta insights
- BigQuery
- Snowflake
- Postgres
- Google Sheets

Resource schemas:

- metric snapshot
- report
- attribution touchpoint
- conversion event
- search performance snapshot
- paid performance snapshot

Action groups:

- metric.fetch
- report.fetch
- query.run
- conversion.import
- snapshot.record

This plugin becomes the shared measurement layer for SEO, media buying, and
GTM templates.

### P1: Publishing And CMS Plugin

Providers to plan:

- WordPress
- Ghost
- Webflow
- Shopify
- Contentful
- Sanity
- custom Git/repository publishing

Action groups:

- post.create/update/publish
- media.upload
- page.create/update/publish
- product-content.update
- redirect.create
- canonical.update

Current WordPress and Ghost wrappers should be promoted from credential probes
to real publishing connectors.

### P2: SEO Plugin Expansion

SEO is now one plugin, not the product itself.

Needed next integrations:

- Google Search Console for query/page performance and indexing signals
- GA4 for landing-page engagement and conversion context
- PageSpeed or CrUX style performance evidence
- CMS publishing through the publishing plugin
- sitemap and crawl imports through utility/core actions
- SERP and competitor research migrated from hidden MCP tools to connectors

Templates to add:

- new content brief
- technical crawl triage
- internal link opportunity review
- refresh performance follow-up
- search performance opportunity finder
- publishing QA

## UI Implications

The UI should stay generic:

- plugin catalog
- capabilities
- providers
- connections
- actions
- action call audit
- resources
- workflow templates
- run plans
- runs
- context, learnings, experiments, decisions
- artifacts

Avoid per-workflow pages. Plugin nav should point into generic pages with
filters such as `plugin_slug`, `resource_key`, `template_key`, or `action_ref`.

The biggest UI integration gap is local-admin credential setup. Action calls are
already visible in run detail and through the project action-call API, but the
catalog still needs broader action availability signals: executable, missing
connector, missing credential, disabled provider, and budget blocked.

## Cleanup And Refactor Map

1. Migrate hidden vendor MCP operations into generic action connectors.
2. Add connector config to SEO and utility action manifests.
3. Tighten broad object schemas for executable actions.
4. Keep `auth.status` and `auth.test` agent-visible; keep secret setup local-admin only.
5. Add credential setup/test/revoke UI using existing REST routes.
6. Remove internal `credential_id` from agent-visible action and vendor responses.
7. Decide whether `integration_credentials` remains only an internal encrypted blob store or is migrated into the new credential model.
8. Promote WordPress and Ghost from credential-test wrappers to publishing actions.
9. Decide the long-term home for sitemap fetch: core setup tool, utility action, or both.
10. Add a custom HTTP/Webhook connector for user-owned tools.
11. Expand first-party templates after connectors exist.
12. Treat `action_calls` as the primary external-operation audit ledger for new work.

## Delivery Order

### Phase 1: Existing Integrations On The Clean Path

Deliver connectors and manifests for Firecrawl, Jina, Reddit, DataForSEO, and
Ahrefs. Add tests for:

- manifest parsing rejects secrets
- connector validation accepts and rejects expected payloads
- credential resolution stays daemon-only
- `action.execute` requires run-plan grants and exact `action_refs`
- action-call audit redacts secret-shaped fields

### Phase 2: Credential Setup UX

Deliver generic local-admin controls for provider credential setup, test, and
revoke. This unlocks real operator use without agent secret exposure.

### Phase 3: Publishing Plugin

Create a publishing plugin and promote WordPress/Ghost wrappers into post and
media actions. Use generic resources and action audit instead of hard-coded SEO
publishing flows.

### Phase 4: Media Buying And GTM Plugin Scaffolds

Add manifests, resource schemas, templates, and initial connector stubs for the
highest-priority providers. Start with one provider per domain, but design action
refs so additional providers slot in without changing templates or UI.

### Phase 5: Analytics And Measurement

Add measurement connectors that SEO, media buying, and GTM templates can all use
for context and experiment evaluation.

## Acceptance Criteria For Any Integration

An integration is not considered complete until:

- it has a provider manifest
- auth setup and `auth.test` are supported, or the provider explicitly needs no auth
- no plaintext secret can be returned through REST, MCP, UI JSON, resources, artifacts, or audit
- executable actions have connector config
- executable actions have meaningful input and output schemas
- the connector is decision-free
- run plans can grant exact action refs
- action calls are audited with redaction, status, cost, and provider refs
- generic UI surfaces can render provider, action, connection, resource, template, run, and audit state
- docs explain setup, schemas, and limitations
