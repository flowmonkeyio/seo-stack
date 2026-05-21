# StackOS Plugins

Plugins are the boundary between StackOS core and domain/tooling behavior.

StackOS core owns storage, retrieval, schema validation, auth/grant/budget
enforcement, redaction, execution plumbing, audit, and generic UI renderers.
Plugins describe what exists for a domain: capabilities, providers, static
action schemas, resource schemas, workflow templates, and UI contributions.

Agents and humans decide how to use those tools. Plugin manifests must not
encode business strategy such as choosing winners, optimizing campaigns, or
deciding the next topic.

## D02 Manifest Shape

D02 introduces the catalog skeleton. The initial manifest is intentionally
small and metadata-only:

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
    capability: seo-content
    risk_level: write
    input_schema:
      type: object
      additionalProperties: true
    output_schema:
      type: object
      additionalProperties: true
```

Required identifiers use lowercase kebab or dotted form, for example
`seo-content`, `openai-images`, or `catalog.describe`.

## Built-In Plugins

D02 registers three built-ins:

- `core`: domain-neutral StackOS catalog/workflow/project-data primitives.
- `seo`: compatibility facade for the current SEO content operations.
- `utils`: reusable utility capabilities and providers such as image
  generation and web retrieval.

## Agent Exposure

Before D09, normal agents may discover catalog metadata:

- `plugin.list`
- `catalog.list`
- `catalog.describe`
- `capability.list`
- `capability.describe`
- `provider.list`
- `provider.describe`

Project plugin enable/disable is setup/admin-gated:

- `plugin.enable`
- `plugin.disable`

Those mutation tools are registered in the daemon catalog but are not advertised
through the normal agent bridge and are not granted to the system/bootstrap
agent surface before the D09 admin/run-plan grant work.
