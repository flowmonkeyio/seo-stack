# SEO Plugin Agent Notes

The SEO plugin is the first-party StackOS domain package for SEO work.

- Own SEO catalog metadata here: capabilities, providers, actions, resources,
  UI nav, and workflow templates.
- SEO is not the core product shape. Keep reusable platform behavior in core or
  shared utility plugins, and keep SEO-specific contracts in this plugin.
- Read [`../../docs/plugins.md`](../../docs/plugins.md),
  [`../../docs/workflow-templates.md`](../../docs/workflow-templates.md), and
  [`../../docs/resources-and-artifacts.md`](../../docs/resources-and-artifacts.md)
  before changing SEO manifests or templates.
- Treat `config.connector` and `config.operation` entries as static
  daemon-side action bindings. The manifest describes the binding; execution
  remains daemon-side and grant-checked.
- Keep utility providers such as image generation, web scraping, Jina, and
  Reddit under the `utils` plugin unless the provider is SEO-specific.
- Secrets never belong in plugin files. Provider auth metadata is declarative;
  credentials are resolved by daemon-side auth providers/connectors.
