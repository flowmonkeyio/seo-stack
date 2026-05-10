# content-stack Skill Operating Contract

This contract applies to every content-stack skill. The skill-specific
`SKILL.md` remains the task plan; this file is the common execution layer.

## Agent Role

- The current operator agent is the planner and writer. The daemon provides
  state, MCP tools, audit trails, and permission checks; it does not spawn a
  hidden writer on the agent's behalf.
- Use caller-owned subagents only when the current agent explicitly chooses to
  delegate a bounded task and can review the result before recording the step.
- Treat the procedure step state as the source of truth. Start by reading the
  current step, the relevant project/article/topic state, and prior step
  outputs.

## Tool Discipline

- Call only tools in the active skill's `allowed_tools` list. If the step seems
  to need another tool, stop and report `BLOCKED` instead of improvising with a
  native browser, filesystem, or vendor call.
- Mutating writes must use the tool named in the skill outputs. Preserve
  optimistic concurrency inputs such as `expected_etag` whenever the tool
  requires them.
- External vendor operations must pass through content-stack integrations so
  rate limits, quota, and budget accounting remain auditable.
- Record long-running work with heartbeats and finish/record-step calls so the
  UI can show progress and resume safely.

## Delegated Skill Runs

- When a coordinator skill delegates to another skill, open a child run with
  `run.start(kind='skill-run', parent_run_id=<current run>, skill_name=<child
  skill key>)`.
- Execute child MCP calls with the child `run_token`, not the coordinator's
  token, so the child skill's own grant matrix and audit trail apply.
- Read the child skill's `SKILL.md`, follow its shared contracts, finish the
  child run, then return to the coordinator run and record the child handoff.
- Do not call another skill's write tools from the parent grant. If child-run
  binding is unavailable, report `BLOCKED`.

## Variant Selection

- Default to `standard` when no procedure step argument names a variant.
- Treat variants as procedure-step arguments, not free-form improvisation.
- When a variant changes cost, source depth, publish behavior, or validation
  strictness, record the selected variant and reason in the handoff summary.

## Validation Checkpoints

Before writing:

1. Confirm required inputs are present and match the expected article/topic
   status.
2. Confirm the project voice, compliance rules, EEAT criteria, publish target,
   or integration credential needed by the step is available.
3. Confirm the intended write is in scope for this skill and not owned by a
   later skill.

Before finishing:

1. Re-read or verify the write result returned by the MCP tool.
2. Check the step's SEO quality gates from `seo-quality-baseline.md`.
3. Capture exact blockers, partial data, and confidence levels in run metadata.

4. Persist the handoff status below under `runs.metadata_json.<skill>.handoff`
   or the nearest skill-specific metadata key.

## Completion Status

Every skill run should finish with one of these statuses in its step output:

- `DONE`: the skill completed the requested work and wrote the expected state.
- `DONE_WITH_CONCERNS`: the skill completed, but source, vendor, quota, or
  confidence gaps remain.
- `NEEDS_INPUT`: the skill cannot proceed without a concrete operator decision
  or missing project configuration.
- `BLOCKED`: the skill cannot safely complete with the current tools, state, or
  vendor availability.

## Handoff Summary

Emit or persist a compact handoff under the skill's run metadata:

```markdown
### Handoff Summary
- Status: DONE | DONE_WITH_CONCERNS | NEEDS_INPUT | BLOCKED
- Objective: one sentence describing the step
- Output: the durable rows or artifacts written
- Evidence: source URLs, tool result ids, or article sections used
- Open loops: missing data, risks, or operator decisions
- Recommended next step: one procedure step or skill
```

## Next-Step Rules

- Prefer the next step declared by the active procedure.
- If a skill recommends a different next step, include the reason and stop for
  the procedure controller to decide.
- Never auto-chain indefinitely. Stop after a single recommendation unless the
  procedure explicitly owns the chain.
