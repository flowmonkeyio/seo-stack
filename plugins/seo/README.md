# SEO Plugin Facade

`plugins/seo/plugin.yaml` is the StackOS catalog boundary for the existing SEO
implementation.

The current SEO code remains in the existing repositories, API routes, MCP
tools, skills, and legacy procedure files. This facade makes ownership explicit
without forcing a risky physical move:

- SEO capabilities, providers, actions, resources, and nav live in the plugin
  manifest.
- Existing SEO routes remain reachable for compatibility.
- Existing SEO MCP tools remain callable under their legacy names.
- Action entries map to legacy tools through `config.legacy_tool` or
  `config.legacy_tools`; the manifest is metadata only.

Future migration work should move SEO workflow templates and skills under this
directory while keeping compatibility wrappers for older runs.
