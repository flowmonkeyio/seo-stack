# Agent Presets

Agent presets are reusable operating contracts for agents that call StackOS
tools. They are not daemon-run agents, not hidden orchestration, and not final
project prompts.

Every bundled preset is generic and must be adapted before use:

- `generic_preset: true`
- `project_adaptation.required: true`
- `project_adaptation.do_not_use_verbatim: true`
- required adaptation references such as `AGENTS.md`, `stackos:stackos`, and
  project-local docs or skills when present
- a prompt assembly order:
  `generic_agent_preset -> project_adaptation_overlay -> workflow_agent_requirements -> current_tracker_or_run_plan_context -> user_request`

The adapting agent must rewrite the generic role for the current project:
technology stack, rules, documentation references, available MCP tools,
workflow/run-plan model, tracker task/ticket conventions, verification
commands, and release expectations.

`recommended_tools` are StackOS operation references. Some hosts mount those
operations as direct MCP tools, while the StackOS bridge may expose only
`workspace.startSession`, `workspace.resolve`, `toolbox.describe`, and
`toolbox.call`. Treat the operation refs as the intent-level tool list: call
them directly only when the host exposes them, otherwise inspect the exact names
with `toolbox.describe` and invoke them through `toolbox.call`.

Bundled presets must not assume customer repositories contain StackOS' own
documentation files. StackOS operating guidance comes from the installed
`stackos:stackos` skill and MCP tool descriptions. Repo-local docs such as
`docs/README.md`, `docs/task-tracker.md`, or local skills should be used when
they exist, but absence of those files is a project-context gap, not a broken
StackOS install.

## Engineering Setup

StackOS presets are not local agent files and they are not registered back into
StackOS as daemon-managed agents. They are generic contracts that a main agent
may adapt into whatever the host/project supports: `.codex` agents, markdown
frontmatter files, plugin-specific agent files, or no local files at all.

SDLC setup uses the same workflow path as other domains. Start with
`workflowTemplate.describe({ "key": "engineering.tracked-delivery",
"plugin_slug": "engineering" })`, resolve its agents with
`agentPreset.resolveForWorkflow`, then create/start a run plan when executing
the work. The workflow references `stackos.sdlc.*` presets as required and
recommended roles, but the workflow owns the SDLC flow.

The main agent should detect or read the host convention before writing local
agents. If no convention is available, it should use the resolved workflow
agents as operating guidance in the current session or ask the operator which
host format to use.

## StackOS Skill

Workflow templates declare `skill_requirements`. The built-in workflows
recommend `stackos:stackos`, the host-side skill that teaches an agent how to
use StackOS MCP, operations, workflows, run plans, tracker tasks/tickets,
dependencies, and evidence.

This is explicit setup guidance. The main agent decides whether its host can
load the skill. If the host cannot, the agent should read the same project docs
and still follow the tracker/run-plan model.

## Tracker Use

All presets are expected to work through the existing StackOS tracker:

- planning agents create scoped tasks/tickets
- dependencies are encoded so ready work and blockers are visible
- delivery agents claim/update tickets as work starts and completes
- reviewers verify evidence before closeout
- release agents compare signoff claims with tracker state

Planning agents should produce deliverable tickets with logical sequencing,
clear dependencies, no dangling loose ends, and concrete definition of done.

## Operations

Use these operations through MCP, REST, or CLI:

- `agentPreset.list`: discover available generic presets
- `agentPreset.describe`: read one preset and its adaptation contract
- `agentPreset.resolveForWorkflow`: resolve a workflow template into required
  and recommended agents plus skill requirements

Example:

```text
agentPreset.resolveForWorkflow({ "workflow_key": "core.project-memory-review" })
```

The response includes:

- workflow summary
- `agent_requirements`
- `skill_requirements`
- resolved required/recommended/optional presets
- unresolved preset refs, if any
- setup guidance that reminds the caller to adapt presets and use tracker state

## Workflow Relationship

Workflow templates are inert reusable contracts. They do not act by themselves.
An agent selects a workflow template, resolves its preset/skill guidance, then
creates a concrete run plan with `runPlan.create`. Work execution then happens
through the run plan, granted tools, provider actions, and tracker tickets.

New workflow authoring is contract-driven today:

- validate with `workflowTemplate.validate`
- save project/user templates with `workflowTemplate.save`
- fork built-ins with `workflowTemplate.fork`
- create executable workflow state with `runPlan.create`

The UI can inspect and use templates, but it is not yet a full visual workflow
builder.
