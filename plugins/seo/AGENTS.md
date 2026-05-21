# SEO Plugin Agent Notes

The SEO plugin is a compatibility facade for the current content-stack SEO
implementation.

- Own SEO catalog metadata here first: capabilities, providers, actions,
  resources, UI nav, and workflow templates.
- Do not move legacy tables, routes, MCP tools, skills, or procedures in this
  facade task unless a later delivery explicitly requires it.
- Treat every `config.legacy_tool` or `config.legacy_tools` entry as a
  compatibility alias to an existing daemon tool. The manifest describes the
  alias; it does not execute it.
- Keep utility providers such as image generation, web scraping, Jina, and
  Reddit under the `utils` plugin unless the provider is SEO-specific.
- Secrets never belong in plugin files. Provider auth metadata is declarative;
  credentials are resolved by daemon-side auth providers/connectors.
