# content-stack Plugin

This is the plugin-first distribution surface for content-stack. The plugin is
intended to be installed once into Codex and/or Claude Code, then used from any
website repository.

The plugin starts a thin MCP bridge (`content-stack mcp-bridge`) that connects
to the singleton local content-stack daemon. The bridge is disposable; the
daemon owns the SQLite database, project bindings, credentials, procedures,
articles, publish targets, and audit trails.

Website repositories should not need content-stack setup files. Repo-specific
knowledge is discovered from the current working directory and persisted in the
daemon through `workspace.*` tools.

The installed plugin is hydrated with the full content-stack skill catalog under
`skills/catalog/` and the procedure catalog under `procedures/`, so runtime
clients load content-stack through one plugin rather than loose per-project
files.
