# Agent Presets

Agent presets are reusable operating contracts for agents that call StackOS
tools. They are not daemon-run agents, not hidden orchestration, and not final
project prompts.

Every bundled preset is generic and must be adapted before use:

- `generic_preset: true`
- `project_adaptation.required: true`
- `project_adaptation.do_not_use_verbatim: true`
- required project references, such as `AGENTS.md`, `docs/README.md`,
  `docs/agent-operating-model.md`, and `docs/task-tracker.md`
- a prompt assembly order:
  `generic_agent_preset -> project_adaptation_overlay -> workflow_agent_requirements -> current_tracker_or_run_plan_context -> user_request`

The adapting agent must rewrite the generic role for the current project:
technology stack, rules, documentation references, available MCP tools,
workflow/run-plan model, tracker task/ticket conventions, verification
commands, and release expectations.

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
