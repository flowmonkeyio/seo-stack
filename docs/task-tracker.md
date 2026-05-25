# Task Tracker

The StackOS task tracker is project-scoped work state for agents and human
navigation. It is inspired by `llm-tracker`, but it lives inside StackOS and
uses the same operation registry, project isolation, run-plan audit, and
no-secret boundary as the rest of the platform.

The tracker does not decide what work should happen. Agents decide strategy and
use tracker operations to persist tasks, tickets, dependencies, ownership,
status, provenance, and verification state.

## Model

```text
project
-> task tracker
-> task
-> ticket
-> dependency/reference/link/revision
```

- **Task**: durable work objective. A task can come from a workflow run,
  manual agent setup, an agent request, or an external issue.
- **Ticket**: executable work unit under a task. This is the agent-facing unit
  for `next`, `pick`, `brief`, `execute`, and `verify`.
- **Dependency**: graph edge from the prerequisite ticket to the dependent
  ticket. Dependencies are first-class state so agents can ask for ready work
  without guessing.
- **Link**: typed provenance to StackOS or external objects, such as run plans,
  run-plan steps, runs, agent requests, resources, artifacts, and action calls.
- **Revision**: append-only tracker history. Agents can use `tracker.changed`
  to refresh context from a known revision.

Statuses are intentionally small and generic:

- `not-started`
- `in-progress`
- `complete`
- `deferred`

## Workflow Mirroring

`runPlan.create` automatically creates a tracker task and one ticket per
run-plan step. Step dependencies become ticket dependencies.

Lifecycle mirroring is mechanical:

| Run-plan event | Tracker effect |
| --- | --- |
| `runPlan.create` | creates `workflow-{run_plan_id}` task and `workflow-{run_plan_id}-{step_id}` tickets |
| `runPlan.start` | marks workflow task `in-progress` and links the run id |
| `runPlan.claimStep` | marks the matching ticket `in-progress`, assigns the claimer, and stores run id |
| `runPlan.recordStep(success)` | marks the ticket `complete` and stores the step outcome |
| `runPlan.recordStep(skipped)` | marks the ticket `deferred` |
| `runPlan.recordStep(failed)` | keeps the ticket open with `blocker_reason` |

StackOS only mirrors state. It does not invent tickets beyond the concrete
run-plan steps and it does not decide how to repair failures.

Lifecycle timestamps follow the visible state. Moving a task or ticket into
`complete` or `deferred` sets `completed_at`; reopening it to `in-progress` or
`not-started` clears `completed_at` so audits do not treat active work as
historically complete.

## Operations

Tracker behavior is registered once as StackOS operations. MCP, REST, CLI, and
UI consume the same contracts.

Agent read operations:

- `tracker.status`
- `tracker.get` (full snapshot; use for UI/debug/import audits, not routine
  agent context)
- `tracker.next`
- `tracker.blockers`
- `tracker.brief`
- `tracker.why`
- `tracker.execute`
- `tracker.verify`
- `tracker.history`
- `tracker.changed`
- `tracker.search`

Agent write operations:

- `tracker.createTask`
- `tracker.createTicket`
- `tracker.updateTask`
- `tracker.updateTicket`
- `tracker.patch`
- `tracker.pick`
- `tracker.release`
- `tracker.linkRunPlan`

REST callers use the generic operation adapter:

```http
POST /api/v1/operations/tracker.get/call
POST /api/v1/operations/tracker.patch/call
```

CLI aliases exist for common calls but still use the same operation adapter:

```bash
stackos tracker status --project 1
stackos tracker next --project 1
stackos tracker brief workflow-7-review --project 1
stackos tracker pick --project 1 --assignee codex
stackos tracker create-task manual-comms "Manual communications" --project 1
stackos tracker create-ticket manual-comms send-ack "Send ack" --project 1
stackos tracker patch --project 1 --input tracker-patch.json
```

## Agent Flow

For workflow work:

```text
workflowTemplate.describe
-> runPlan.create
-> tracker.status or tracker.brief
-> runPlan.start
-> runPlan.claimStep
-> do the step
-> runPlan.recordStep
-> tracker.verify
```

For direct/manual work:

```text
tracker.createTask
-> tracker.createTicket
-> tracker.next
-> tracker.pick
-> tracker.brief
-> do the work
-> tracker.updateTicket or tracker.patch
-> tracker.verify
```

Use `tracker.brief` before working a ticket. Agent tracker reads such as
`tracker.status`, `tracker.next`, `tracker.blockers`, `tracker.brief`,
`tracker.why`, `tracker.execute`, `tracker.verify`, `tracker.history`,
`tracker.changed`, and `tracker.search` default to compact response mode: keys,
titles, statuses, dependency keys, run-plan refs, non-empty counts, links,
checks, compact history summaries, and suggested next actions. Use
`response_mode="standard"` or `"verbose"` only when diagnostics need the full
tracker rows with timestamps, metadata, definitions, and source payloads. Use
`tracker.changed` when you know a previous revision and only need new context.

`tracker.status` and `tracker.blockers` report active blockers for executable
work: non-terminal tickets with an explicit blocker reason or incomplete
dependencies. Historical blocker notes on `complete` or `deferred` tickets are
kept for context, but they do not make the project look actively blocked.

Use `tracker.get` only when the caller needs the full project tracker snapshot
or the UI graph projection. It can be intentionally large because it includes
all requested tasks, tickets, dependencies, links, and optional graph nodes.
Normal agents should prefer `tracker.status`, `tracker.next`, `tracker.brief`,
`tracker.verify`, `tracker.search`, and `tracker.changed` to keep context small.

## UI

The Tasks UI is a generic project work map. It renders:

- metrics for tasks, tickets, in-progress work, and blockers
- filters by workflow, status, assignee, and search text
- a task index where each task row shows status, source/workflow, priority,
  done/total ticket count, completion percent, and current detail
- one focused Vue Flow graph at a time so large imported tasks remain readable
- dependency-tree graph as the primary visualization, with ticket nodes laid out
  left-to-right by prerequisite/dependent relationships
- optional nested task-box view for compact containment inspection
- dependency edges between tickets, kept visually quiet at large scale
- graph-local status and block filters. Status filters select tickets by
  lifecycle status. Block filters use unresolved dependency state, with open
  `blocker_reason` treated as blocked; terminal deferred/complete notes are not
  counted as active blockers. The blocked view keeps the immediate blocking
  ticket visible so the dependency edge still explains why work is blocked. The
  graph header reports the visible ticket and edge counts when filters are
  active, not the full task totals.
- edge click highlighting for the selected dependency chain. Unrelated nodes
  and edges dim while upstream and downstream dependencies remain readable.
- a minimap and controls for navigating large task graphs
- ticket table for dense scanning
- detail panel for selected task/ticket context

The UI is for humans to navigate and inspect. Agents should use tracker
operations directly for writes.

## Graph Projection

Storage is normalized and not Vue Flow-specific. `tracker.get` returns an
optional graph projection so the UI can compose Vue Flow without rediscovering
relationships:

```json
{
  "graph": {
    "nodes": [],
    "edges": [],
    "warnings": [],
    "layout_hints": {
      "direction": "LR",
      "group_by": "task"
    }
  }
}
```

The mechanical mapping is:

- task -> task/group node
- ticket -> ticket node
- task/ticket relationship -> containment
- ticket dependency -> dependency edge
- StackOS/external links -> provenance metadata or link edges

## Boundaries

- Do not store secrets in tracker fields. Metadata, context, references, and
  patches are redacted.
- Do not add provider or workflow-specific tracker logic. Domain behavior
  belongs in plugins, templates, run plans, and agents.
- Do not add bespoke REST routes for tracker behavior. Register operations once
  and use the generated MCP/REST/CLI surfaces.
- Do not use the tracker as a replacement for run-plan grants. Workflow writes
  still require active run-plan step grants where applicable.
