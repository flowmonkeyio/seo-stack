# Extending content-stack

How to add skills, procedures, programmatic step handlers, integrations,
MCP tools, and REST routes to content-stack. Read
[`./architecture.md`](./architecture.md) first for the system overview;
this document focuses on the day-to-day "I want to add X" workflows.

Cross-references use relative paths; file:line references use the
format `path/to/file.py:42`.

---

## 1. Adding a skill

A skill is a single-purpose markdown file that an LLM session reads to
perform one phase of the pipeline (e.g. "generate the outline",
"audit the alt text"). The skill calls MCP tools to read + write the
DB; it never touches the engine directly.

### 1.1 Pick the phase + name

The five phases align with the canonical SEO content flow:

1. `01-research/` — keyword discovery, SERP analysis, clustering,
   briefs, sitemap shortcuts.
2. `02-content/` — outline, drafting, editor, EEAT gate, humanizer.
3. `03-assets/` — image generation, alt-text audit.
4. `04-publishing/` — interlinker, schema emitter, per-target publish.
5. `05-ongoing/` — GSC opportunities, drift watch, refresh detector.

Pick the phase that matches the skill's role; pick a kebab-case name
that describes the skill in 2–4 words.

### 1.2 Scaffold the skill directory

```bash
mkdir -p skills/<phase>/<skill-name>
cp skills/02-content/editor/SKILL.md skills/<phase>/<skill-name>/SKILL.md
```

Edit the new `SKILL.md` (do NOT keep the editor body — we copy editor
because its frontmatter is well-formed; everything else gets
rewritten).

### 1.3 Frontmatter contract

Every `SKILL.md` opens with a YAML frontmatter block:

```yaml
---
name: my-new-skill
description: One-line summary of what the skill does, surfaced in MCP tool listings.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: original
license: project-internal
allowed_tools:
  - meta.enums
  - project.get
  - article.get
  - article.setOutline
  - run.start
  - run.heartbeat
  - run.finish
  - run.recordStepCall
inputs:
  project_id:
    source: env
    var: CONTENT_STACK_PROJECT_ID
    required: true
  run_id:
    source: env
    var: CONTENT_STACK_RUN_ID
    required: true
  article_id:
    source: env
    var: CONTENT_STACK_ARTICLE_ID
    required: true
outputs:
  - table: articles
    write: article.setOutline (current row)
  - table: runs
    write: heartbeat + finish on the existing skill-run row
---
```

Fields:

- `name` — kebab-case; matches the directory name.
- `description` — one-line summary; surfaces in `procedure.list` MCP
  output and the UI's procedures detail view.
- `version` — semver; bumps when the prompt or the I/O contract
  changes.
- `runtime_compat` — `["codex", "claude-code"]` for both runtimes.
- `derived_from` — set to `original` for in-house skills.
- `license` — set to `project-internal` for in-house skills.
- `allowed_tools` — full tool-grant list for this skill. Must mirror
  `content_stack/mcp/permissions.py:SKILL_TOOL_GRANTS[<phase>/<name>]`
  verbatim. The startup smoke check + the unit test
  `tests/integration/test_skills_frontmatter.py::test_allowed_tools_matches_permissions_matrix`
  enforces parity.
- `inputs` — context keys the agent-led procedure step package
  supplies; the skill body reads them.
- `outputs` — tables the skill writes; surfaces in the UI for
  blast-radius prediction.

### 1.4 Body sections

Standard body shape (no frontmatter, just markdown):

```markdown
## When to use

One paragraph describing the scenario the skill handles. Surfaces in
the UI's skill picker; should help an operator decide whether the
skill is the right one.

## Inputs

What the skill reads before any external call. Referenced by frontmatter
`inputs` for env vars + `args` for procedure-step arguments.

## Steps

Numbered list of what the LLM does, step-by-step. Mention every MCP
tool call by name (e.g., `article.get(article_id)`, `voice.get`,
`compliance.list`). Each step is one or two paragraphs of prose; the
LLM reads them sequentially.

## Outputs

What the skill produces — DB writes, log lines, structured summaries
in `runs.metadata_json`.

## Failure handling

How the skill behaves when an external call fails or a precondition
isn't met. Mirrors the `on_failure` modes available to the procedure
runner.

## Variants

Named alternative flows the skill supports (e.g., `shallow` /
`standard` / `deep` for keyword-discovery). Selected via the procedure
step's `args.variant` field.
```

### 1.5 Tool-grant matrix entry

Add the skill's grant list to
`content_stack/mcp/permissions.py:SKILL_TOOL_GRANTS`. The grant must
mirror `SKILL.md`'s `allowed_tools` verbatim:

```python
_SKILL_MY_NEW_SKILL: frozenset[str] = _RUN_LIFECYCLE | {
    "meta.enums",
    "project.get",
    "article.get",
    "article.setOutline",
    # ... any other tools the skill calls
}

SKILL_TOOL_GRANTS: dict[str, frozenset[str]] = {
    # ... existing entries ...
    "<phase>/<my-new-skill>": _SKILL_MY_NEW_SKILL,
}
```

The `_RUN_LIFECYCLE` shared frozenset (`run.start`, `run.heartbeat`,
`run.finish`, `run.recordStepCall`) is union'd in for every real
skill so a future author doesn't accidentally drop one.

### 1.6 Tests

`tests/unit/test_skills_frontmatter.py` validates every `SKILL.md`
automatically:

- Frontmatter parses as YAML.
- Required keys present.
- `allowed_tools` is a subset of the MCP tool registry.
- `allowed_tools` matches `SKILL_TOOL_GRANTS[<phase>/<name>]`.
- `runtime_compat` is non-empty.
- `derived_from` follows the format `<repo> @ <SHA>` or `original (n/a)`.

No fixture changes needed — the test discovers new skills by
walking `skills/`.

### 1.7 Cross-runtime support

`SKILL.md` works with both Codex CLI and Claude Code unmodified. No
code generation, no per-runtime variants. The runner sets the same
env vars + provides the same MCP server in both runtimes; the skill
body is plain markdown that any LLM session can follow.

---

## 2. Adding a procedure

A procedure is an ordered playbook the runner walks step-by-step.
Each step is either a skill or a `_programmatic/<name>` handler.

### 2.1 Scaffold the procedure directory

```bash
mkdir -p procedures/<NN-slug>
cp procedures/_template/PROCEDURE.md procedures/<NN-slug>/PROCEDURE.md
```

The leading `NN-` prefix orders procedures consistently with the
existing eight (01 through 08). Pick the next two-digit prefix.

### 2.2 Frontmatter contract

`content_stack/procedures/parser.py:ProcedureSpec` is the canonical
shape. Required keys:

```yaml
---
name: my-procedure
slug: 09-my-procedure                     # MUST equal the directory name
version: 0.1.0
description: |
  One-paragraph summary of what the procedure does and when to use it.

triggers:
  - "Manual: operator runs via UI / `/procedure my-procedure <args>`"
  - "Parent procedure: invoked from procedure-N as a child"

prerequisites:
  - "topic.status = 'approved'"
  - "project has voice_profiles with is_default=true"

produces:
  - articles
  - runs
  - run_steps
  - procedure_run_steps

inputs:
  topic_id: "An approved topic id (int; required)."
  budget_cap_usd: "Optional float USD ceiling (default 0 = no cap)."

steps:
  - id: brief
    skill: 01-research/content-brief
    on_failure: abort
  - id: outline
    skill: 02-content/outline
    on_failure: abort
  - id: editor
    skill: 02-content/editor
    on_failure: retry
    max_retries: 1
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

concurrency_limit: 4
resumable: true
---
```

Optional cron block (only for procedures 6 + 7 currently):

```yaml
schedule:
  cron: "0 9 * * 1"                       # 09:00 every Monday
  timezone_field: projects.schedule_json.timezone
```

The runner ignores `schedule:`; M8's APScheduler bootstrap
(`content_stack/jobs/cron_procedures.py`) reads it at job-registration
time so each active project's cron-triggered procedures land as
`job_id=procedure-{slug}-{project_id}`.

### 2.3 Step types

Two kinds of steps:

- **Skill steps** — `skill: <phase>/<name>` (e.g., `02-content/editor`).
  The current agent claims the step via `procedure.claimStep`, receives
  `skills/<phase>/<name>/SKILL.md`, executes the work through MCP, and
  records output with `procedure.recordStep`.
- **Programmatic steps** — `skill: _programmatic/<name>` (e.g.,
  `_programmatic/project-create`,
  `_programmatic/spawn-procedure-4-batch`). The current agent calls
  `procedure.executeProgrammaticStep`; the daemon runs the registered
  Python handler for that one deterministic step. No LLM session is
  spawned.

See section 3 below for adding new programmatic handlers.

### 2.4 on_failure modes

| Mode           | Required keys                      | Effect                                                                          |
| -------------- | ---------------------------------- | ------------------------------------------------------------------------------- |
| `abort`        | —                                  | A failed record marks `runs.status='failed'`.                                   |
| `retry`        | `max_retries >= 1`                 | The agent retries the same step, respecting the cap in the step context.        |
| `loop_back`    | `loop_back_to: <prior step.id>`    | The agent returns to a prior step, respecting the loop cap.                     |
| `skip`         | —                                  | The agent may record the step as `skipped` and continue.                        |
| `human_review` | —                                  | The agent records a review pause, waits for operator input, then retries.       |

The parser validates these at load time:

- `loop_back_to` must reference a *prior* step id (forward jumps
  rejected).
- `retry` requires `max_retries >= 1`.
- `loop_back_to` is only valid with `on_failure='loop_back'`.

A malformed PROCEDURE.md aborts daemon startup with the parse error
in the lifespan log — operators see the error immediately, not as a
mysterious 500 on the first `procedure.run`.

### 2.5 Variants

Two override shapes:

- `args_overrides` — dict keyed by step id; merges into that step's
  `args` in the step package. Useful for "deeper research" or "longer
  word count" without authoring a separate procedure.
- `steps_omit` — list of step ids to skip entirely (status='skipped').
  Useful for "short-form" variants that drop the asset chain.

Variants are applied at `ProcedureRunner.start` time when the caller
passes `variant=<name>`. The runner deep-copies the spec and applies
the overrides; the original spec stays untouched so concurrent runs
of different variants don't cross-contaminate.

### 2.6 Tests

`tests/integration/test_procedure_runner/test_procedures_catalog.py`
validates every `PROCEDURE.md` automatically:

- Frontmatter parses as YAML.
- `slug == directory.name`.
- Every step's `skill` resolves to a real `skills/<phase>/<name>/`
  directory or a registered `_programmatic/<name>` handler.
- Every `loop_back_to` references a prior step.
- Variants reference real step ids.

No fixture changes needed — the test discovers new procedures by
walking `procedures/`.

---

## 3. Adding a `_programmatic/` step handler

Programmatic steps run pure Python code instead of an LLM session.
They cover non-LLM work like project creation, GSC pulls, and child-run
spawning.

### 3.1 Implement the handler

Add the handler to
`content_stack/procedures/programmatic.py`:

```python
from content_stack.procedures.programmatic import (
    ProgrammaticStepRegistry,
    StepContext,
    StepResult,
)


@ProgrammaticStepRegistry.register("my-handler-name")
async def _my_handler(ctx: StepContext) -> StepResult:
    """One-line docstring describing what the handler does."""
    # ctx.engine        — SQLAlchemy engine (read-write).
    # ctx.run_id        — parent run's id.
    # ctx.project_id    — project context.
    # ctx.args          — merged step.args + procedure-level args.
    # ctx.previous_outputs — dict of prior step outputs (keyed by step.id).
    # ctx.parent_run_id — parent run id when this run was spawned by
    #                     another procedure (e.g. procedure 5 spawns
    #                     procedure 4 children).
    # ctx.runner        — live ProcedureRunner; call runner.start(...) to
    #                     spawn child runs.
    return {"my_output_key": "value"}     # JSON-serialisable dict
```

### 3.2 Reference it from a PROCEDURE.md

```yaml
steps:
  - id: my-step
    skill: _programmatic/my-handler-name
    args:
      foo: bar
    on_failure: abort
```

Programmatic resolution: if `skill` starts with `_programmatic/`, the
step package returns `next_action='execute_programmatic_step'` and the
current agent calls `procedure.executeProgrammaticStep`. Otherwise the
step is a normal skill step and the current external agent follows the
referenced skill.

### 3.3 Pause for operator review

A handler that needs the operator to make a decision (e.g.,
"approve these N topics before continuing") raises `HumanReviewPause`:

```python
from content_stack.procedures.programmatic import HumanReviewPause


@ProgrammaticStepRegistry.register("approve-topics")
async def _approve_topics(ctx: StepContext) -> StepResult:
    if not ctx.args.get("approved"):
        raise HumanReviewPause(
            reason="Topics need operator approval",
            hint="Open the Topics view; approve the queued rows; resume the run.",
        )
    return {"approved_count": ctx.args["approved"]}
```

The controller catches `HumanReviewPause`, records a failed step with
`human_review=true`, and keeps the run in agent-led mode. After the
operator completes the requested action, the current agent retries the
same step.

### 3.4 Spawning child runs

A handler that fans out child procedures (e.g., procedure 5 spawns
procedure 4 once per approved topic) calls `ctx.runner.start(...)`:

```python
@ProgrammaticStepRegistry.register("spawn-procedure-4-batch")
async def _spawn_batch(ctx: StepContext) -> StepResult:
    children = []
    for topic_id in ctx.args["topic_ids"]:
        result = await ctx.runner.start(
            slug="04-topic-to-published",
            project_id=ctx.project_id,
            args={"topic_id": topic_id},
            parent_run_id=ctx.run_id,        # parent-child relationship
        )
        children.append(result["run_id"])
    return {"child_run_ids": children}
```

The child runs are opened with `parent_run_id` so the current agent can
manage them as a visible tree. A later `_programmatic/wait-for-children`
step summarizes terminal child runs or returns a review pause while any
child is still running.

### 3.5 Tests

`tests/integration/test_procedure_runner/test_programmatic_*.py`
covers each handler. Conventions:

- One test file per handler (`test_programmatic_<name>.py`).
- Use the `runner` + `engine` fixtures from `conftest.py`.
- Verify the handler's `StepResult` shape, the DB rows it writes, and
  the heartbeat / audit-trail behaviour.

---

## 4. Adding an integration

An integration is a vendor wrapper — DataForSEO, Firecrawl, GSC,
OpenAI Images, Reddit, PAA, Jina, Ahrefs. Adding a new one means
three things: implement the wrapper, register it, document the
credential.

### 4.1 Implement the wrapper

Create `content_stack/integrations/<vendor>.py`:

```python
from typing import Any

from content_stack.integrations._base import BaseIntegration


class MyVendorIntegration(BaseIntegration):
    """Wrapper for the My Vendor REST API."""

    kind = "myvendor"                  # matches integration_credentials.kind
    default_qps = 2.0                  # token-bucket rate (calls/sec)
    vendor = "myvendor"                # short id for cost logs

    async def call(self, op: str, **kwargs: Any) -> Any:
        # Resolve the credential, build the httpx request, dispatch
        # via self._http_call(...) for retry + audit-trail handling.
        ...

    async def test_credentials(self) -> None:
        # Probe a cheap endpoint to verify the credential.
        ...

    def _estimate_cost_usd(self, op: str, **kwargs: Any) -> float:
        # Pre-call estimate for the budget pre-emption check.
        return 0.001

    def _extract_actual_cost_usd(self, response: Any) -> float | None:
        # Post-call reconciliation — return None if vendor doesn't
        # report cost; the estimate stands.
        return response.get("cost")
```

The base class handles:

- Token-bucket QPS pacing (`_rate_limit.py`).
- Pre-call `IntegrationBudgetRepository.record_call` — refuses with
  `BudgetExceededError` (-32012) if `current_month_spend +
  estimated_cost > monthly_budget_usd`.
- Retry / backoff on 429 / 5xx (3 retries, 0.5 s → 1 s → 2 s).
- Per-call `RunStepCallRepository.record_call` — every vendor hit
  lands in `run_step_calls` with cost_cents + duration_ms.
- Sanitised request / response logging.

### 4.2 Register the wrapper

Add to `content_stack/integrations/__init__.py`:

```python
from content_stack.integrations.myvendor import MyVendorIntegration

REGISTRY: dict[str, type[BaseIntegration]] = {
    # ... existing entries ...
    "myvendor": MyVendorIntegration,
}
```

The MCP tool `integration.test` and the REST endpoint
`POST /api/v1/projects/{id}/integrations/{iid}/test` both look up via
`REGISTRY[kind]` so the new wrapper is callable immediately.

### 4.3 Default budget

Add a default `integration_budgets` row to `db/seed.py` so a new
project gets a sensible cap when the integration is enabled:

```python
DEFAULT_BUDGETS = [
    # ... existing entries ...
    {"kind": "myvendor", "monthly_budget_usd": 50.0,
     "alert_threshold_pct": 80, "qps": 2.0},
]
```

### 4.4 Encryption

Credentials get AES-256-GCM at-rest via the M4 crypto layer. The UI
posts the plaintext credential; the repository encrypts before
writing the row. No code change needed — the encryption seam is
generic.

### 4.5 Add per-vendor docs

Append a section to [`./api-keys.md`](./api-keys.md) covering:

- What skills consume the integration.
- Where to obtain the credential (URL + sign-up flow).
- The credential shape (which keys land in the encrypted payload,
  which in `config_json`).
- Cost ballpark + example projects.
- Env var equivalents for tests.

### 4.6 Tests

Per-vendor cassette test under
`tests/integration/test_integrations/test_<vendor>_call.py`. Use
`pytest-httpx` to record the wrapper's HTTP traffic; assert the
contract (URL, headers, body shape) and the audit-trail writes
(`run_step_calls.cost_cents`, `integration_budgets.current_month_spend`).

---

## 5. Tool-grant matrix discipline

The matrix is the load-bearing security seam. Every MCP request
resolves to a calling skill name (via the run_token ↔ runs.client_session_id
lookup); `check_grant(tool_name, skill_name)` raises -32007 if the
tool is not in `SKILL_TOOL_GRANTS[skill_name]`.

### 5.1 Sentinel skills

Two reserved names define bootstrap/test behaviour:

- `__system__` — direct REST/UI calls (no run_token present); this gets
  a deliberately narrow bootstrap allow-list.
- `__test__` — test fixtures; `is_full_grant` short-circuits the
  matrix lookup. Naming convention:
  test-only skills use the `_test_` prefix so production names cannot
  collide.

Production callers always present a provisioned token; the system
surface (REST/UI) carries `None` and resolves to `__system__`.

### 5.2 Parity enforcement

Two checks:

- **Boot-time smoke** — server startup walks `SKILL_TOOL_GRANTS`,
  cross-references each entry against `skills/<phase>/<name>/SKILL.md`'s
  `allowed_tools`, refuses to boot on mismatch.
- **Unit test** —
  `tests/integration/test_skills_frontmatter.py::test_allowed_tools_matches_permissions_matrix`
  asserts the same parity in local release checks.

### 5.3 Adding a new tool to a skill

1. Add the tool to `SKILL.md`'s `allowed_tools` list.
2. Add the tool to `_SKILL_<NAME>` in
   `content_stack/mcp/permissions.py`.
3. Run `make test` — the parity test confirms the change.

Removing a tool is the inverse; both lists shrink atomically in the
same commit.

---

## 6. Adding an MCP tool

When a new repository operation needs MCP exposure:

### 6.1 Add the tool definition

Pick the resource's tools file:
`content_stack/mcp/tools/<resource>.py` (e.g., `articles.py`,
`projects.py`). Add the Input + Output models and the handler:

```python
from content_stack.mcp.contract import MCPInput, WriteEnvelope


class FooSetBarInput(MCPInput):
    """Input for `foo.setBar`."""

    project_id: int
    foo_id: int
    bar: str
    expected_etag: str | None = None
    idempotency_key: str | None = None


class FooSetBarOutput(WriteEnvelope[Foo]):
    """Mutating tools return WriteEnvelope[Inner]."""


async def _foo_set_bar(
    inp: FooSetBarInput,
    ctx: MCPContext,
    emitter: ProgressEmitter,
) -> FooSetBarOutput:
    """One-line docstring becomes the MCP description."""
    repo = FooRepository(ctx.session)
    foo = repo.set_bar(
        project_id=inp.project_id,
        foo_id=inp.foo_id,
        bar=inp.bar,
        expected_etag=inp.expected_etag,
    )
    return FooSetBarOutput(
        data=foo,
        run_id=ctx.run_id,
        project_id=inp.project_id,
    )
```

### 6.2 Register the tool

```python
def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="foo.setBar",
            description="Set the bar attribute on a Foo row.",
            input_model=FooSetBarInput,
            output_model=FooSetBarOutput,
            handler=_foo_set_bar,
            streaming=False,
        )
    )
    # ... other foo.* tools ...
```

### 6.3 Update the tool-grant matrix

Add `foo.setBar` to every skill's `allowed_tools` (in `SKILL.md`)
and the corresponding `_SKILL_<NAME>` set in
`content_stack/mcp/permissions.py` that needs it. Skills that don't
need the tool stay narrow.

### 6.4 Update generated UI types

`make gen-types` regenerates `ui/src/api.ts` from the daemon's
OpenAPI spec. The MCP tool itself doesn't change OpenAPI (MCP and
REST are separate transports); but if you also add a REST route
(see section 8 below) the types need to match.

### 6.5 Mutating-verb discipline

The envelope validation check (`assert_envelope_discipline` at
`content_stack/mcp/server.py`) verifies every mutating-verb tool
returns `WriteEnvelope[Inner]`. The verb list:
`create|update|set|mark|add|remove|toggle|approve|reject|apply|
dismiss|bulkCreate|bulkUpdate|bulkApply|run|snapshot|ingest|test|
validate|abort|resume|fork|activate|setPrimary|setActive`.

Read tools (whose name is not in that prefix list) return the bare
data. Mismatch refuses the daemon to boot.

---

## 7. Adding a REST route

Same flow as MCP but under `content_stack/api/<resource>.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from content_stack.api.deps import get_db
from content_stack.api.envelopes import WriteResponse
from content_stack.repositories.foo import FooRepository

router = APIRouter(prefix="/api/v1/projects/{project_id}/foos", tags=["foos"])


@router.patch("/{foo_id}/bar")
async def set_foo_bar(
    project_id: int,
    foo_id: int,
    body: SetBarRequest,
    if_match: str | None = Header(None),
    session: Session = Depends(get_db),
) -> WriteResponse[Foo]:
    """One-line docstring becomes the OpenAPI description."""
    repo = FooRepository(session)
    foo = repo.set_bar(
        project_id=project_id,
        foo_id=foo_id,
        bar=body.bar,
        expected_etag=if_match,
    )
    return WriteResponse(data=foo, run_id=None, project_id=project_id)
```

Register the router in `content_stack/api/__init__.py:register_routers`:

```python
from content_stack.api import foos

def register_routers(app: FastAPI) -> None:
    app.include_router(foos.router)
    # ... existing registrations ...
```

Run `make gen-types` after adding the route so the UI's `api.ts`
picks up the new shape. Release checks fail on diff if you forget.

### 7.1 Permissive vs. state-machine

REST patches accept arbitrary column updates and write a `runs` row
with `kind='manual-edit'`. This is the human escape hatch in the UI.
MCP equivalents enforce the state machine (e.g., `articles.status`
transitions) and the etag check. Both transports share the
repository layer; the differing strictness lives in the route /
tool wrapper, not the repository.

---

## 8. Common pitfalls

- **Forgetting the `_RUN_LIFECYCLE` union.** Every real skill needs
  `run.start`, `run.heartbeat`, `run.finish`, `run.recordStepCall`.
  Use the shared frozenset; don't enumerate them per skill.
- **Forward jumps in `loop_back_to`.** Parser rejects at load time;
  use a separate variant or `human_review` if you need to skip
  forward.
- **Mutating tool returning bare data.** `assert_envelope_discipline`
  refuses to boot. Wrap in `WriteEnvelope[Inner]`.
- **MCP tool name collision.** Tool names are global; the resource
  prefix (`foo.*`) keeps them distinct. If you need a new resource,
  add a new file under `content_stack/mcp/tools/`.
- **REST route bypasses the state machine.** Acceptable per design
  (UI escape hatch); but the route MUST write a
  `runs.kind='manual-edit'` row so the audit trail captures the
  edit. The `articles.py` patch route is the reference.

---

## See also

- [`./architecture.md`](./architecture.md) — system overview.
- [`./procedures-guide.md`](./procedures-guide.md) — PROCEDURE.md
  authoring contract.
- [`./api-keys.md`](./api-keys.md) — vendor credential setup.
- [`../PLAN.md`](../PLAN.md) — the canonical spec.
