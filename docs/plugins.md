# StackOS Plugins

Plugins are the boundary between StackOS core and domain/tooling behavior.

StackOS core owns storage, retrieval, schema validation, auth/grant/budget
enforcement, redaction, execution plumbing, audit, and generic UI renderers.
Plugins describe what exists for a domain: capabilities, providers, static
action schemas, resource schemas, workflow templates, and UI contributions.

Agents and humans decide how to use those tools. Plugin manifests must not
encode business strategy such as choosing winners, optimizing campaigns, or
deciding the next topic.

Executable action details are documented in
[`action-executor.md`](action-executor.md). StackOS can describe, validate, and
internally execute configured actions through daemon connectors, but normal
agents still see only the granted action surface. Plugin manifests remain
metadata; they do not contain secrets or decision logic.

## Manifest Shape

The catalog manifest is intentionally metadata-only. Built-in plugin manifests
live under `plugins/<plugin>/plugin.yaml` when the plugin owns a domain facade:

```yaml
slug: seo
name: SEO
version: 0.1.0
description: Compatibility plugin facade for current SEO content operations.
source: builtin
capabilities:
  - key: seo-content
    name: SEO Content
    description: Topics, articles, sources, links, schema, and publishing.
    kind: domain
providers:
  - key: gsc
    name: Google Search Console
    description: Search Console OAuth-backed metrics provider.
    auth_type: oauth
actions:
  - key: topic.bulk-create
    name: Create Topic Candidates
    description: Create topic records from agent-selected SEO candidates.
    provider: stackos-seo-compat
    capability: seo-content
    risk_level: write
    input_schema:
      type: object
      additionalProperties: true
    output_schema:
      type: object
      additionalProperties: true
    config:
      legacy_tool: topic.bulkCreate
resources:
  - key: article
    name: Article
    description: Compatibility schema for SEO article records.
    schema:
      type: object
      additionalProperties: true
```

Required identifiers use lowercase kebab or dotted form, for example
`seo-content`, `openai-images`, or `catalog.describe`. Compatibility aliases to
older MCP tools are explicit metadata in `config.legacy_tool` or
`config.legacy_tools`; the old tool names continue to exist until their
workflow migration is complete.

Workflow templates live beside plugin metadata as files:

```text
plugins/<plugin>/workflows/*.yaml
```

The loader treats those files as plugin defaults. They can be overridden by
project/user templates in the DB or by repository/company templates under
`.stackos/workflows`.

## Built-In Plugins

The initial StackOS daemon registers three built-ins:

- `core`: domain-neutral StackOS catalog/workflow/project-data primitives.
- `seo`: compatibility facade for the current SEO content operations.
- `utils`: reusable utility capabilities and providers such as image
  generation and web retrieval.

Built-in resource schemas include:

- `core`: `project-note`, `learning`, `experiment`.
- `seo`: `cluster`, `topic`, `article`, `research-source`, `article-asset`,
  `internal-link`, `gsc-metric`, `drift-baseline`, and other compatibility SEO
  records.
- `utils`: `generated-image`, `web-document`.

## Project Enablement

Plugins are installed globally but enabled per project. If a plugin has no
explicit project row, StackOS treats it as available for compatibility. If a
project disables a plugin, project-scoped catalog reads hide that plugin's
capabilities, providers, actions, resources, and UI nav contribution.

Disabling a plugin does not delete legacy data and does not remove compatibility
routes. For example, disabling `seo` hides SEO from the generic StackOS catalog
and sidebar for that project, while existing SEO routes and old run history
remain readable.

## SEO Facade

`plugins/seo/plugin.yaml` is the SEO ownership boundary. It maps the current
SEO implementation into plugin-owned metadata:

- capabilities for research, content, publishing, and Search Console;
- providers for local SEO compatibility, DataForSEO, Ahrefs, GSC, WordPress,
  and Ghost;
- resources for current SEO tables and sidecar records;
- actions that point at legacy daemon tools through explicit alias metadata;
- the SEO sidebar contribution.

Utility providers used by SEO, such as OpenAI Images, Firecrawl, Jina, and
Reddit, remain owned by the `utils` plugin unless a later task makes them
domain-specific.

## Agent Exposure

Normal agents may discover catalog metadata and bounded generic reads through
the direct bridge surface:

- `action.describe`
- `action.validate`
- `plugin.list`
- `catalog.list`
- `catalog.describe`
- `capability.list`
- `capability.describe`
- `provider.list`
- `provider.describe`
- `auth.status`
- `auth.test`
- `resource.get`
- `resource.query`
- `artifact.get`
- `artifact.query`
- `workflowTemplate.list`
- `workflowTemplate.describe`
- `workflowTemplate.validate`

Setup/admin-gated mutations are registered in the daemon catalog but are not
advertised through the normal agent bridge and are not granted to the
system/bootstrap agent surface:

- `plugin.enable`
- `plugin.disable`
- `auth.start`
- `auth.revoke`
- `workflowTemplate.save`
- `workflowTemplate.fork`

Advanced context reads and generic run-plan writes are bridge-hidden or
daemon-filtered. They become callable only with a started run plan, an active
claimed step, and an explicit step grant:

- `context.query` for fields outside the direct safe set
- `resource.upsert`
- `artifact.create`
- `context.snapshot`
- `learning.create`
- `learning.update`
- `experiment.create`
- `experiment.recordObservation`
- `experiment.recordDecision`
- `decision.record`

Generic execution uses the same grant model:

- `action.execute` with explicit `action_refs`

Credential setup is metadata-driven by plugin providers, but secrets stay
outside agent context. Provider manifests declare `auth_type`; the daemon maps
that declaration into auth-provider rows and opaque credential refs. Agents use
`auth.status` and `auth.test`, while local UI/REST setup handles plaintext or
OAuth. Compatibility tools such as `integration.set` remain daemon-local and are
not part of the normal plugin agent surface.
