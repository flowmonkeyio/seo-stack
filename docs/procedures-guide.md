# Authoring procedures

A procedure is an ordered, named playbook the daemon's runner walks
step-by-step. Each step is either a skill (LLM session) or a
`_programmatic/<name>` handler (pure Python). The runner persists
every step's input + output to the audit trail and supports five
failure modes plus three operator-driven control flows
(resume / fork / abort).

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
| `args`               | no       | `{}`             | Merged into the step's `args` payload at dispatch.                  |
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

The runner:

1. Pre-writes a `procedure_run_steps` row with `status='pending'`.
2. Loads `skills/02-content/outline/SKILL.md`.
3. Spawns an LLM session via the bound `LLMDispatcher`
   (`AnthropicSession` in production, `StubDispatcher` in tests).
4. Sets `CONTENT_STACK_PROJECT_ID`, `CONTENT_STACK_RUN_ID`,
   `CONTENT_STACK_ARTICLE_ID?`, `CONTENT_STACK_TOPIC_ID?` env vars.
5. Provisions the bearer token + the run_token (signed; resolves to
   the skill name via `permissions.py`).
6. Tells the LLM to call MCP at `http://127.0.0.1:5180/mcp`.
7. Persists the dispatcher's output verbatim to
   `procedure_run_steps.output_json`.

#### Programmatic steps

```yaml
- id: project-create
  skill: _programmatic/project-create
  on_failure: abort
```

The runner dispatches via
`ProgrammaticStepRegistry.dispatch(name, ctx)`. The handler is pure
Python; no LLM session is involved. See
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

The workhorse procedure. Twelve steps, three-verdict EEAT gate with
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
| 1 | `brief`             | `01-research/content-brief`   | Resolve voice + compliance + EEAT + sources; persist brief_json. | `voice.get`, `compliance.list`, `eeat.list`, `article.setBrief`, `source.list` | `briefing`               |
| 2 | `outline`           | `02-content/outline`          | Generate H1/H2/H3 from the brief.                                | `article.get`, `voice.get`, `article.setOutline`   | `outlined`               |
| 3 | `draft-intro`       | `02-content/draft-intro`      | First drafting pass — hook + thesis.                              | `article.get`, `voice.get`, `article.setDraft`     | (still `outlined`)       |
| 4 | `draft-body`        | `02-content/draft-body`       | Second drafting pass — section expansion, evidence injection.    | `article.get`, `source.list`, `article.setDraft`   | (still `outlined`)       |
| 5 | `draft-conclusion`  | `02-content/draft-conclusion` | Third drafting pass — summary + CTA + compliance footer.         | `article.get`, `compliance.list`, `article.setDraft`, `article.markDrafted` | `drafted`               |
| 6 | `editor`            | `02-content/editor`           | Polish the stitched draft against voice + criteria.              | `article.get`, `voice.get`, `article.setEdited`    | `edited`                 |
| 7 | `eeat-gate`         | `02-content/eeat-gate`        | Score against project's active criteria.                          | `eeat.score`, `eeat.bulkRecord`, `article.markEeatPassed` | `eeat_passed` (on SHIP)  |
| 8 | `image-generator`   | `03-assets/image-generator`   | Generate hero image.                                              | `article.get`, `asset.create`                      | (unchanged)              |
| 9 | `alt-text-auditor`  | `03-assets/alt-text-auditor`  | Audit + complete alt text on any assets.                          | `asset.list`, `asset.update`                       | (unchanged)              |
| 10| `schema-emitter`    | `04-publishing/schema-emitter`| Build JSON-LD payload (Article + Author + Image refs).           | `article.get`, `schema.set`, `schema.validate`     | (unchanged)              |
| 11| `interlinker`       | `04-publishing/interlinker`   | Suggest internal links from existing articles.                    | `interlink.suggest`, `interlink.list`              | (unchanged)              |
| 12| `publish`           | `04-publishing/nuxt-content-publish` (or wordpress / ghost) | Push to primary publish target. | `article.get`, `schema.get`, `target.list`, `publish.preview`, `article.markPublished`, `publish.recordPublish` | `published` |

### 3.2 EEAT three-verdict logic (step 7)

The eeat-gate step is the only step the runner branches on a verdict
for. Per audit BLOCKER-09:

- **`SHIP`** — all `tier='core'` criteria pass + no required criterion
  fails + all 8 dimensions ≥ 70. Runner advances to step 8
  (`image-generator`).
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

The runner catches `HumanReviewPause`, marks the step paused, and
emits the event for the UI. `procedure.resume(run_id, args={"approved": [...]})`
re-dispatches the step with the operator's input merged into `args`.

### 4.2 Estimate-then-spawn (procedure 5)

Procedure 5 (`bulk-content-launch`) spawns N child procedure-4 runs.
Before spawning, an estimate-cost guard refuses if the estimated
spend would exceed `--budget-cap-usd`:

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

The bulk-cost-estimator handler refuses with `BudgetExceededError`
(-32012) when the estimate exceeds the cap; the procedure aborts
without spawning anything. Per audit M-25.

### 4.3 Compose other procedures (procedure 8)

Procedure 8 (`add-new-site`) composes procedures 1, 2, 5 by
spawning each as a child run:

```yaml
- id: bootstrap
  skill: _programmatic/spawn-bootstrap-project
  on_failure: abort
- id: optional-sitemap
  skill: _programmatic/spawn-one-site-shortcut
  args:
    skip_if_no_sitemap: true
  on_failure: skip
- id: bulk-launch
  skill: _programmatic/spawn-bulk-content-launch
  on_failure: abort
```

Each handler calls `ctx.runner.start(slug=..., parent_run_id=ctx.run_id, ...)`.
The parent's `concurrency_limit` queues additional children when
capacity is full.

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

## 5. Failure handling

The runner branches per `ProcedureStep.on_failure` after each step's
dispatcher returns or raises:

### 5.1 `abort`

Mark `runs.status='failed'` (or `'aborted'` for EEAT BLOCK + manual
abort); raise; no resume by default. The step row gets
`status='failed'` with the dispatcher's error in `error`.

Use for: structural failures that retrying won't fix (missing voice,
missing primary publish target, schema-emitter producing invalid
JSON-LD).

### 5.2 `retry`

Re-dispatch the same step. Capped at `max_retries` (must be `>= 1`;
the runner caps at 3 even if a higher value is declared).

Use for: transient LLM hiccups (`draft-*` skills) that succeed on a
retry. The drafter's malformed-JSON case is the canonical example.

```yaml
- id: draft-body
  skill: 02-content/draft-body
  on_failure: retry
  max_retries: 1
```

### 5.3 `loop_back`

Set the cursor back to a *prior* step. Capped at
`settings.procedure_runner_max_loop_iterations` (default 3); on
exhaustion the procedure aborts with `runs.error` describing the
loop-cap breach.

Use for: `eeat-gate FIX → editor`. The runner stamps the gate's
`fix_required[]` list onto `runs.metadata_json.eeat`; the editor
reads the list and targets fixes; eeat-gate re-runs.

```yaml
- id: editor
  skill: 02-content/editor
  on_failure: abort
- id: eeat-gate
  skill: 02-content/eeat-gate
  on_failure: loop_back
  loop_back_to: editor
```

The parser rejects forward jumps (`loop_back_to` referencing a
later step) and `loop_back_to` on non-`loop_back` steps.

### 5.4 `skip`

Mark `procedure_run_steps.status='skipped'`; advance to the next
step. The dispatcher's failure is logged but does not propagate.

Use for: quality-enhancing steps that the article can ship without
(`image-generator`, `alt-text-auditor`, `interlinker`). A failure
to generate an image doesn't block publishing — the schema-emitter
handles the missing `image:` JSON-LD field accordingly.

### 5.5 `human_review`

Mark `procedure_run_steps.status='paused'`; emit an event for the
UI; runner stops dispatching this run. The run row stays
`status='running'` so heartbeats keep firing (and the reaper does
NOT mark it orphaned).

Use for: operator-approval checkpoints (procedures 2 + 3 use this
for topic-queue approval).

`procedure.resume(run_id, args={...})` re-dispatches the paused
step with the operator's args merged in.

---

## 6. Resume semantics

`procedure.resume(run_id, args?)` (REST + MCP) re-dispatches the
last paused / failed step:

1. Runner reads `procedure_run_steps` for the run's last clean
   state.
2. The next step (`status='pending'` or `'running'` or `'paused'`)
   is the resume point.
3. If the procedure declares `resumable: false`, resume returns
   -32008 (state-machine violation).
4. If `args` is supplied, it merges into the step's `args` payload
   at dispatch time (used by `human_review` resumes to carry the
   operator's decision).

By default, the runner re-runs the failed step from scratch
(idempotent skills are the contract). A per-skill opt-out flag is
reserved for future use.

`procedure.fork(run_id, from_step)` creates a new child run for
"redo from step N onward". The child copies prior step outputs as
inputs but executes step N and beyond fresh. Used by humanizer
chains where the operator wants to redo step 7 (eeat-gate) without
re-running steps 1-6.

---

## 7. Concurrency

Two layers of concurrency control:

### 7.1 In-process semaphore

`ProcedureRunner` keeps an `asyncio.Semaphore` per `(slug, project_id)`
sized to `concurrency_limit`. When N child runs of the same procedure
target the same project, the (N − concurrency_limit) extras queue
on the semaphore. Within-process serialisation is fine-grained.

### 7.2 APScheduler `max_instances`

Cross-process serialisation comes from APScheduler's `max_instances=1`
on each `job_id=procedure-{slug}-{project_id}`. Even if the daemon
restarts mid-flight and a stale job tries to re-fire, APScheduler
queues it behind the in-flight one.

### 7.3 Project-wide ceiling

`MAX_CONCURRENCY` env var (default 4) caps simultaneous procedure
runs system-wide. Beyond the per-procedure semaphore, this protects
the writer mutex on the SQLite WAL.

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
- Runs the runner end-to-end with a stub LLM dispatcher; asserts
  the article advances through each state and lands at `published`.

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
  — the dispatch loop + failure-mode implementation.
- [`../content_stack/procedures/programmatic.py`](../content_stack/procedures/programmatic.py)
  — the programmatic step registry.
- [`../PLAN.md`](../PLAN.md) — the canonical spec.
