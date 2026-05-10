# Authoring procedures

A procedure is an ordered, named playbook the current operator agent
walks step-by-step. Each step is either a skill prompt the current
agent follows (optionally with caller-owned subagents) or a
`_programmatic/<name>` handler (pure Python). The daemon persists
every step's input + output to the audit trail, exposes grants and
state transitions, and supports five failure modes plus three
operator-driven control flows (resume / fork / abort).

This guide is the canonical authoring contract for
`PROCEDURE.md` files. The implementation lives at
[`content_stack/procedures/parser.py`](../content_stack/procedures/parser.py)
and [`content_stack/procedures/runner.py`](../content_stack/procedures/runner.py);
when this document and the parser disagree, the parser wins.

For the broader "how do I add a procedure" workflow, see
[`./extending.md#2-adding-a-procedure`](./extending.md). This guide
focuses on the frontmatter schema, the failure-mode semantics, and
worked examples.

---

## 1. Frontmatter spec

`PROCEDURE.md` opens with a YAML frontmatter block delimited by
`---` lines. The body below the second `---` is markdown
documentation; the runner ignores it.

```yaml
---
name: topic-to-published                  # human-readable label
slug: 04-topic-to-published               # MUST equal directory name
version: 0.1.0                            # semver
description: |
  One-paragraph summary; surfaces in MCP procedure.list + UI.
triggers:                                 # natural-language; informational
  - "Manual: operator runs via UI"
  - "Procedure 5 (bulk-content-launch) — fans out one per topic"
prerequisites:                            # natural-language predicates
  - "topic.status = 'approved'"
  - "project has voice_profiles with is_default=true"
produces:                                 # tables this procedure writes
  - articles
  - article_versions
  - runs
inputs:                                   # arg names → descriptions
  topic_id: "An approved topic id (int; required)."
  budget_cap_usd: "Optional float USD ceiling."
steps:
  - id: brief
    skill: 01-research/content-brief
    on_failure: abort
  - id: outline
    skill: 02-content/outline
    on_failure: abort
  - id: draft-intro
    skill: 02-content/draft-intro
    on_failure: retry
    max_retries: 1
  - id: editor
    skill: 02-content/editor
    on_failure: abort
  - id: eeat-gate
    skill: 02-content/eeat-gate
    on_failure: loop_back
    loop_back_to: editor
variants:
  - name: short-form
    description: "Skip the asset chain for short articles."
    steps_omit:
      - image-generator
      - alt-text-auditor
  - name: pillar
    description: "Long-form pillar; deeper research."
    args_overrides:
      brief:
        depth_tier: heavy
        target_word_count: 4000
concurrency_limit: 4                      # per (slug, project_id)
resumable: true                           # procedure.resume allowed
schedule:                                 # OPTIONAL — only for cron-triggered
  cron: "0 9 * * 1"                       # 09:00 every Monday
  timezone_field: projects.schedule_json.timezone
---
```

### 1.1 Required vs. optional fields

| Field                | Required | Default                                  | Notes                                                       |
| -------------------- | -------- | ---------------------------------------- | ----------------------------------------------------------- |
| `name`               | yes      | —                                        | Human-readable label.                                       |
| `slug`               | yes      | —                                        | MUST equal `procedures/<slug>/` directory name.             |
| `version`            | yes      | —                                        | Semver; bumps on schema or step changes.                    |
| `description`        | yes      | —                                        | Multi-line YAML block for the UI body.                      |
| `steps[]`            | yes      | —                                        | At least one step; duplicate ids rejected at parse.         |
| `triggers[]`         | no       | `[]`                                     | Natural-language; informational only.                       |
| `prerequisites[]`    | no       | `[]`                                     | First step's skill enforces.                                |
| `produces[]`         | no       | `[]`                                     | Surfaced in UI; documentation.                              |
| `inputs{}`           | no       | `{}`                                     | Arg names → descriptions.                                   |
| `variants[]`         | no       | `[]`                                     | Named overrides; resolved at `runner.start`.                |
| `concurrency_limit`  | no       | `1`                                      | Must be `>= 1`. Applied per `(slug, project_id)`.            |
| `resumable`          | no       | `true`                                   | Whether `procedure.resume(run_id)` is allowed after abort.   |
| `schedule`           | no       | `None`                                   | Only required for cron-triggered procedures (6, 7).         |

### 1.2 Step shape

Each step is a YAML map with the following fields:

| Field                | Required | Default          | Notes                                                              |
| -------------------- | -------- | ---------------- | ------------------------------------------------------------------ |
| `id`                 | yes      | —                | Lowercase alpha+dash, 1..80 chars, starts with a letter.            |
| `skill`              | yes      | —                | `<phase>/<name>` for LLM steps, `_programmatic/<name>` for handlers. |
| `args`               | no       | `{}`             | Merged into the agent-facing step package.                          |
| `on_failure`         | no       | `"abort"`        | One of `abort`, `retry`, `loop_back`, `skip`, `human_review`.       |
| `loop_back_to`       | no       | `None`           | REQUIRED iff `on_failure == "loop_back"`. Names a prior step id.   |
| `max_retries`        | no       | `0`              | REQUIRED `>= 1` iff `on_failure == "retry"`.                       |
| `concurrency_group`  | no       | `None`           | Reserved for future cross-step rate limiting.                      |

### 1.3 Variant shape

```yaml
variants:
  - name: <variant-name>                  # required; unique per procedure
    description: "<one-line>"             # optional
    args_overrides:                       # optional; keyed by step id
      <step_id>:
        <arg_key>: <arg_value>
    steps_omit:                           # optional; list of step ids to skip
      - <step_id>
```

The parser rejects:

- Variant names that collide.
- `args_overrides` referencing unknown step ids.
- `steps_omit` referencing unknown step ids.

### 1.4 Schedule shape (cron-triggered)

```yaml
schedule:
  cron: "0 9 * * 1"                       # five-field cron expression
  timezone_field: projects.schedule_json.timezone
```

- `cron` — five whitespace-separated tokens (minute hour
  day-of-month month day-of-week). The parser does a shallow check
  (token count); APScheduler's `CronTrigger.from_crontab` does the
  deep validation when M8 wires it up.
- `timezone_field` — dotted path into the project row that names
  the IANA timezone for the schedule. Default
  `projects.schedule_json.timezone`. Operators can override per-procedure
  (e.g., a procedure that always runs in UTC regardless of project
  timezone).

The runner ignores `schedule:`. M8's `cron_procedures.py` reads it
at job-registration time and creates one job per active project per
scheduled procedure with `job_id=procedure-{slug}-{project_id}`.

---

## 2. DSL primitives

The procedure DSL is intentionally small. Two step types, five
failure modes, two override shapes for variants.

### 2.1 Step types

#### Skill steps

```yaml
- id: outline
  skill: 02-content/outline
  args:
    target_word_count: 1800
  on_failure: abort
```

The agent-led flow:

1. `procedure.run` pre-writes a `runs` row and the
   `procedure_run_steps` skeleton with `status='pending'`.
2. The current agent calls `procedure.currentStep` or
   `procedure.claimStep`.
3. `procedure.claimStep` marks the step `running`, loads
   `skills/02-content/outline/SKILL.md`, returns the skill body,
   merged args, previous outputs, and allowed tools, and binds the run
   token to that step's skill grant in `permissions.py`.
4. The current agent performs the work directly through MCP tools
   (or delegates bounded subtasks to caller-owned subagents).
5. The current agent calls `procedure.recordStep` with the output JSON,
   which persists to `procedure_run_steps.output_json` and advances the
   durable cursor.

#### Programmatic steps

```yaml
- id: project-create
  skill: _programmatic/project-create
  on_failure: abort
```

Programmatic steps are deterministic daemon work. The current agent
calls `procedure.executeProgrammaticStep`, which invokes the registered
handler once and records its output; no LLM session is involved. See
[`./extending.md#3-adding-a-_programmatic-step-handler`](./extending.md)
for the registry contract.

Programmatic handlers cover non-LLM work like project creation,
GSC pulls, child-run spawning, and operator-pause checkpoints.

### 2.2 Failure modes

See section 5 below for the per-mode behaviour.

### 2.3 Variants

See section 4 below for walked examples.

---

## 3. Walked example: procedure 4 (`topic-to-published`)

The workhorse procedure. Thirteen steps, three-verdict EEAT gate with
loop-back to the editor, three failure-mode classes (`abort`,
`retry`, `skip`).

Frontmatter excerpt (full file at
[`procedures/04-topic-to-published/PROCEDURE.md`](../procedures/04-topic-to-published/PROCEDURE.md)):

```yaml
---
name: topic-to-published
slug: 04-topic-to-published
version: 0.1.0
description: |
  The workhorse procedure — full pipeline from approved topic to
  published article.
prerequisites:
  - "topic.status = 'approved'"
  - "project has voice_profiles with is_default=true"
  - "project has eeat_criteria with tier='core' for all 3 vetoes (T04 / C01 / R10)"
  - "project has at least one publish_targets row with is_active=true (and a primary)"
inputs:
  topic_id: "The approved topic to draft + publish (int; required)."
steps:
  - id: brief
    skill: 01-research/content-brief
    on_failure: abort
  - id: outline
    skill: 02-content/outline
    on_failure: abort
  - id: draft-intro
    skill: 02-content/draft-intro
    on_failure: retry
    max_retries: 1
  - id: draft-body
    skill: 02-content/draft-body
    on_failure: retry
    max_retries: 1
  - id: draft-conclusion
    skill: 02-content/draft-conclusion
    on_failure: retry
    max_retries: 1
  - id: editor
    skill: 02-content/editor
    on_failure: abort
  - id: humanizer
    skill: 02-content/humanizer
    on_failure: retry
    max_retries: 1
  - id: eeat-gate
    skill: 02-content/eeat-gate
    on_failure: loop_back
    loop_back_to: editor
  - id: image-generator
    skill: 03-assets/image-generator
    on_failure: skip
  - id: alt-text-auditor
    skill: 03-assets/alt-text-auditor
    on_failure: skip
  - id: schema-emitter
    skill: 04-publishing/schema-emitter
    on_failure: abort
  - id: interlinker
    skill: 04-publishing/interlinker
    on_failure: skip
  - id: publish
    skill: 04-publishing/nuxt-content-publish
    on_failure: abort
concurrency_limit: 4
resumable: true
---
```

### 3.1 Step-by-step annotated

| # | Step                | Skill                         | Purpose                                                          | MCP verbs                                          | `articles.status` after  |
| - | ------------------- | ----------------------------- | ---------------------------------------------------------------- | -------------------------------------------------- | ------------------------ |
| 1 | `brief`             | `01-research/content-brief`   | Resolve voice + compliance + EEAT + sources; persist brief_json. | `voice.get`, `compliance.list`, `eeat.list`, `article.setBrief`, `source.list` | `outlined`               |
| 2 | `outline`           | `02-content/outline`          | Generate H1/H2/H3 from the brief.                                | `article.get`, `voice.get`, `article.setOutline`   | `outlined`               |
| 3 | `draft-intro`       | `02-content/draft-intro`      | First drafting pass — hook + thesis.                              | `article.get`, `voice.get`, `article.setDraft`     | (still `outlined`)       |
| 4 | `draft-body`        | `02-content/draft-body`       | Second drafting pass — section expansion, evidence injection.    | `article.get`, `source.list`, `article.setDraft`   | (still `outlined`)       |
| 5 | `draft-conclusion`  | `02-content/draft-conclusion` | Third drafting pass — summary + CTA + compliance footer.         | `article.get`, `compliance.list`, `article.setDraft`, `article.markDrafted` | `drafted`               |
| 6 | `editor`            | `02-content/editor`           | Polish the stitched draft against voice + criteria.              | `article.get`, `voice.get`, `article.setEdited`    | `edited`                 |
| 7 | `humanizer`         | `02-content/humanizer`        | One pass of rhythm/AI-tell cleanup for the current article version. | `article.get`, `voice.get`, `article.setEdited`    | `edited`                 |
| 8 | `eeat-gate`         | `02-content/eeat-gate`        | Score against project's active criteria.                          | `eeat.score`, `eeat.bulkRecord`, `article.markEeatPassed` | `eeat_passed` (on SHIP)  |
| 9 | `image-generator`   | `03-assets/image-generator`   | Generate hero image.                                              | `article.get`, `asset.create`                      | (unchanged)              |
| 10| `alt-text-auditor`  | `03-assets/alt-text-auditor`  | Audit + complete alt text on any assets.                          | `asset.list`, `asset.update`                       | (unchanged)              |
| 11| `schema-emitter`    | `04-publishing/schema-emitter`| Build JSON-LD payload (Article + Author + Image refs).           | `article.get`, `schema.list`, `schema.set`, `schema.validate` | (unchanged)              |
| 12| `interlinker`       | `04-publishing/interlinker`   | Suggest internal links from existing articles.                    | `interlink.suggest`, `interlink.list`              | (unchanged)              |
| 13| `publish`           | `04-publishing/nuxt-content-publish` (or wordpress / ghost) | Push to primary publish target. | `article.get`, `schema.get`, `target.list`, `publish.preview`, `article.markPublished`, `publish.recordPublish` | `published` |

### 3.2 EEAT three-verdict logic (step 8)

The eeat-gate step is the only step the runner branches on a verdict
for. Per audit BLOCKER-09:

- **`SHIP`** — all `tier='core'` criteria pass + no required criterion
  fails + all 8 dimensions ≥ 70. Runner advances to step 9
  (`image-generator`) after the humanizer has completed.
- **`FIX`** — ≥1 required criterion fails OR a dimension score < 70.
  Runner stamps `runs.metadata_json.eeat.fix_required[]` with the
  failure list, then `loop_back_to: editor` (step 6). Editor reads
  the fix list and re-edits; eeat-gate re-runs. Capped at
  `settings.procedure_runner_max_loop_iterations` (default 3); on
  exhaustion the procedure aborts with `runs.error` describing the
  loop-cap breach.
- **`BLOCK`** — any criterion with `tier='core'` (T04 / C01 / R10)
  fails. Runner aborts the procedure with `runs.status='aborted'`
  and flips `articles.status='aborted-publish'`. The article does
  not advance to `eeat_passed`; the operator has to start fresh
  after fixing the veto cause.

### 3.3 State-machine transitions

The runner walks `articles.status` through a strict state machine:

```
briefing → outlined → drafted → edited → eeat_passed → published
                                   ↑          │
                                   │          ↓
                              (FIX loop)  (BLOCK / fail)
                                          → aborted-publish
```

Forward transitions are only allowed by the matching MCP verb
(`article.setOutline` advances to `outlined`,
`article.markEeatPassed` advances to `eeat_passed`, etc.). The
permissive REST `PATCH /articles/{id}` bypasses the state machine
but writes a `runs.kind='manual-edit'` row for the audit trail.

---

## 4. Common patterns

### 4.1 Approve-and-resume (procedures 2 + 3)

When a procedure needs operator approval mid-flight, use a
`_programmatic/<name>` handler that raises `HumanReviewPause`:

```yaml
- id: approve-topics
  skill: _programmatic/approve-topics
  on_failure: human_review
```

The handler:

```python
@ProgrammaticStepRegistry.register("approve-topics")
async def _approve_topics(ctx: StepContext) -> StepResult:
    if not ctx.args.get("approved"):
        raise HumanReviewPause(
            reason="Topics need operator approval",
            hint="Open the Topics view; approve the queued rows; resume.",
        )
    return {"approved_count": ctx.args["approved"]}
```

The controller catches `HumanReviewPause`, records
`output_json.human_review=true`, and leaves the same step current. The
agent waits for the operator to approve the queue, then retries the
step or records the operator's decision explicitly.

### 4.2 Estimate-then-spawn (procedure 5)

Procedure 5 (`bulk-content-launch`) opens N child procedure-4 runs.
Before opening children, an estimate-cost guard refuses if the
estimated spend would exceed `--budget-cap-usd`:

```yaml
- id: estimate-cost
  skill: _programmatic/bulk-cost-estimator
  on_failure: abort
- id: spawn-batch
  skill: _programmatic/spawn-procedure-4-batch
  on_failure: abort
- id: wait-for-children
  skill: _programmatic/wait-for-children
  on_failure: abort
```

The bulk-cost-estimator handler fails the step when the estimate
exceeds the cap; because the step declares `on_failure: abort`, the run
ends without opening child runs. Per audit M-25.

### 4.3 Compose other procedures (procedure 8)

Procedure 8 (`add-new-site`) composes procedures 1, 2/3, and optional
5 by opening each as a child run:

```yaml
- id: bootstrap
  skill: _programmatic/run-child-procedure
  args:
    child_procedure: 01-bootstrap-project
  on_failure: human_review
- id: topic-discovery-shortcut
  skill: _programmatic/run-child-procedure
  args:
    child_procedure: 02-one-site-shortcut
  on_failure: human_review
- id: bulk-launch
  skill: _programmatic/run-child-procedure
  args:
    child_procedure: 05-bulk-content-launch
  on_failure: human_review
```

Each handler calls `ctx.runner.start(slug=..., parent_run_id=ctx.run_id, ...)`.
The handler records the child run id and returns a human-review pause
until the current agent has completed that child run.

### 4.4 Cron-triggered (procedures 6 + 7)

Procedures 6 and 7 declare a `schedule:` block:

```yaml
schedule:
  cron: "0 9 * * 1"                       # weekly: Monday 09:00
  timezone_field: projects.schedule_json.timezone
```

M8's `cron_procedures.py` reads the schedule at job-registration
time; one APScheduler job per active project per scheduled
procedure (`job_id=procedure-{slug}-{project_id}`). The runner
ignores the `schedule:` block in flight; the cron block only
influences the registration step.

When a project is deactivated, the corresponding cron jobs are
unregistered. When a project's `scheduled_jobs.enabled` is toggled
off in the UI, the cron job is paused without unregistering.

---

## 5. Failure Handling

The controller does not hide retries or loop-backs inside the daemon.
It returns the declared `on_failure` policy in each step package, and
the current agent applies that policy when it records the step.

### 5.1 `abort`

If a step with `on_failure: abort` is recorded as `failed`, the run is
marked `failed` and no current step is returned.

Use for structural failures that retrying will not fix: missing voice,
missing primary publish target, invalid schema output.

### 5.2 `retry`

The agent retries the same step, respecting `max_retries` from the step
package and the global safety cap. The daemon records each attempt in
the run audit trail; it does not spawn another model session.

```yaml
- id: draft-body
  skill: 02-content/draft-body
  on_failure: retry
  max_retries: 1
```

### 5.3 `loop_back`

The agent returns to the named prior step and records the repair path in
the run output. The parser still enforces that `loop_back_to` references
a prior step and only appears on `on_failure: loop_back`.

```yaml
- id: editor
  skill: 02-content/editor
  on_failure: abort
- id: eeat-gate
  skill: 02-content/eeat-gate
  on_failure: loop_back
  loop_back_to: editor
```

Use for `eeat-gate FIX -> editor`: the current agent gives the editor
the gate's `fix_required[]` list, reruns the gate, and stops when the
loop cap is reached.

### 5.4 `skip`

The agent may record `status='skipped'` and continue. Use for
quality-enhancing steps the article can ship without, such as
`image-generator`, `alt-text-auditor`, and `interlinker`.

### 5.5 `human_review`

Programmatic handlers raise `HumanReviewPause` when operator or child
run work is required. The controller records a failed step with
`output_json.human_review=true` and keeps the run in `running` state.
The current agent completes the requested work, then retries the same
step.

---

## 6. Resume And Fork

`procedure.resume(run_id)` (REST + MCP) reopens an aborted or paused
procedure run for caller-owned execution. It does not execute work.
The next call to `procedure.currentStep` returns the current pending,
running, or failed step for the agent to handle.

`procedure.fork(run_id, from_step_index)` creates a new child run for
"redo from step N onward". The child copies prior successful outputs as
skipped step rows and leaves step N and beyond pending. This is the
preferred way to redo a later chain without mutating the original audit
trail.

---

## 7. Concurrency

The durable state model is multi-run, but execution concurrency is owned
by the caller. Bulk and umbrella procedures open child runs with
`parent_run_id`; the current agent decides whether to handle those child
runs sequentially, delegate them to caller-owned subagents, or pause
until the operator chooses.

Cron-triggered procedures still use APScheduler only as a trigger
source: each job opens an agent-led run. APScheduler does not execute
the procedure steps or spawn writer sessions.

---

## 8. Budget pre-emption

Per audit M-25, the integration layer refuses calls that would
exceed `monthly_budget_usd` *before* hitting the vendor:

```python
# content_stack/integrations/_base.py
class BaseIntegration:
    async def _http_call(self, op: str, ...):
        estimated = self._estimate_cost_usd(op, ...)
        # IntegrationBudgetRepository.record_call raises BudgetExceededError
        # if current_month_spend + estimated > monthly_budget_usd
        budget_repo.record_call(self.kind, project_id, estimated)
        # ... then dispatch the actual httpx call ...
```

For procedures that fan out (procedure 5), a dedicated
`_programmatic/bulk-cost-estimator` step pre-flights the cap before
spawning children. The estimator reads
`integration_budgets.current_month_spend` and the procedure's
declared `inputs.budget_cap_usd`; mismatch returns -32012 and the
procedure aborts without spawning anything.

The UI's BudgetsView surfaces per-integration spend + remaining
quota. `cost.queryProject(project_id, month=YYYY-MM)` MCP returns
the current month's spend by integration.

---

## 9. Worked example: a custom procedure

Suppose you want a "promotional-bonus-page" procedure for a gambling
project: pull the latest bonus terms, draft a comparison page,
publish via the WordPress target.

### 9.1 Scaffold

```bash
cp -R procedures/_template procedures/09-promotional-bonus-page
# edit procedures/09-promotional-bonus-page/PROCEDURE.md
```

### 9.2 Frontmatter

```yaml
---
name: promotional-bonus-page
slug: 09-promotional-bonus-page
version: 0.1.0
description: |
  Pull current bonus terms via Firecrawl, draft a comparison page,
  publish to the WordPress primary target. Cron-triggerable weekly
  or operator-driven.
triggers:
  - "Manual: operator runs via UI / `/procedure 09-promotional-bonus-page <project_id>`"
  - "Cron weekly when schedule:.cron is set"
prerequisites:
  - "project has voice_profiles with is_default=true"
  - "project has at least one publish_targets row with kind='wordpress' and is_active=true"
  - "project has integration_credentials with kind='firecrawl'"
produces:
  - articles
  - article_versions
  - article_publishes
  - schema_emits
  - runs
inputs:
  bonus_urls: "List of vendor URLs to scrape (list[str]; required)."
  budget_cap_usd: "Optional float USD ceiling (default 0 = no cap)."
steps:
  - id: scrape
    skill: _programmatic/scrape-bonus-pages
    on_failure: abort
  - id: brief
    skill: 01-research/content-brief
    on_failure: abort
  - id: outline
    skill: 02-content/outline
    on_failure: abort
  - id: draft-intro
    skill: 02-content/draft-intro
    on_failure: retry
    max_retries: 1
  - id: draft-body
    skill: 02-content/draft-body
    on_failure: retry
    max_retries: 1
  - id: draft-conclusion
    skill: 02-content/draft-conclusion
    on_failure: retry
    max_retries: 1
  - id: editor
    skill: 02-content/editor
    on_failure: abort
  - id: eeat-gate
    skill: 02-content/eeat-gate
    on_failure: loop_back
    loop_back_to: editor
  - id: schema-emitter
    skill: 04-publishing/schema-emitter
    on_failure: abort
  - id: publish
    skill: 04-publishing/wordpress-publish
    on_failure: abort
concurrency_limit: 1
resumable: true
schedule:
  cron: "0 8 * * 5"                       # 08:00 every Friday
  timezone_field: projects.schedule_json.timezone
---
```

### 9.3 Programmatic handler

`scrape-bonus-pages` reads the `bonus_urls` arg, calls the Firecrawl
integration once per URL, persists the markdown to
`research_sources`, and returns the source ids in `previous_outputs`
for the brief step:

```python
@ProgrammaticStepRegistry.register("scrape-bonus-pages")
async def _scrape_bonus_pages(ctx: StepContext) -> StepResult:
    urls = ctx.args["bonus_urls"]
    source_ids: list[int] = []
    with Session(ctx.engine) as session:
        firecrawl = FirecrawlIntegration(session=session, project_id=ctx.project_id)
        for url in urls:
            result = await firecrawl.call("scrape", url=url)
            source_id = ResearchSourceRepository(session).create(
                project_id=ctx.project_id,
                url=url,
                markdown=result.data["markdown"],
            )
            source_ids.append(source_id)
        session.commit()
    return {"source_ids": source_ids}
```

### 9.4 Tests

`tests/integration/test_procedure_runner/test_promotional_bonus_page.py`:

- Validates the frontmatter parses cleanly (covered by the catalog
  test automatically).
- Mocks the Firecrawl integration; asserts the scrape handler
  writes the right `research_sources` rows.
- Opens an agent-led procedure run, asserts the step package exposes
  the scrape handler first, then records mocked outputs through the
  normal `procedure.claimStep` / `procedure.recordStep` flow.

---

## See also

- [`./extending.md`](./extending.md) — adding skills + integrations
  + REST routes + MCP tools.
- [`./architecture.md`](./architecture.md) — system overview and
  procedure-runner internals.
- [`../procedures/04-topic-to-published/PROCEDURE.md`](../procedures/04-topic-to-published/PROCEDURE.md)
  — the workhorse procedure as a reference.
- [`../procedures/_template/PROCEDURE.md`](../procedures/_template/PROCEDURE.md)
  — the scaffold for new procedures.
- [`../content_stack/procedures/parser.py`](../content_stack/procedures/parser.py)
  — the canonical frontmatter schema.
- [`../content_stack/procedures/runner.py`](../content_stack/procedures/runner.py)
  — the agent-led procedure controller.
- [`../content_stack/procedures/programmatic.py`](../content_stack/procedures/programmatic.py)
  — the programmatic step registry.
- [`../PLAN.md`](../PLAN.md) — the canonical spec.
