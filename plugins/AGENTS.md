# Plugin Manifest Agent Notes

Plugin manifests define StackOS' static provider, auth, resource, template, and
action contracts. They are the agent-visible map, so they must be precise.

## Expectations

- Read [`../docs/plugins.md`](../docs/plugins.md),
  [`../docs/action-executor.md`](../docs/action-executor.md), and
  [`../docs/auth-providers.md`](../docs/auth-providers.md) before changing
  executable provider contracts.
- Domain logic belongs to the executing agent and workflow templates, not to
  tools.
- Every executable action must have a connector, operation, input schema,
  output schema, auth requirement, and tests.
- Every non-executable action must have `execution_mode` and `deferred_reason`;
  do not leave it looking ready.
- Provider auth fields must model the real setup shape: API key, OAuth, SMTP,
  basic auth, account refs, manager refs, scope labels, and safe diagnostics.
- Never place secrets in manifest config. Secrets belong in credential payloads.
- Keep provider-specific auth requirements visible to operators and agents
  through safe fields and setup notes.
- If a provider's docs require a special key type, account type, scope, callback,
  webhook, status poll, or rate limit, represent it in the manifest and tests.
- Provider/vendor operations belong in plugin actions executed through
  `action.execute`; do not add provider-specific direct MCP tools for normal
  agents.
- SEO, media buying, GTM, publishing, and utilities are plugins. Core StackOS
  should stay generic.

## Review Checklist

- Manifest schema matches connector validation.
- Action description does not promise post-processing the connector does not do.
- Budget flags match real accounting capability.
- Docs links are present in connector comments or integration-contract docs.
- Tests cover direct action visibility, grant execution, validation, auth, and
  no-secret output for new executable actions.
- New provider actions have an integration contract review or official-doc
  ledger under [`../docs/integration-contracts/`](../docs/integration-contracts/).
