---
name: eeat-gate
description: Score the edited article against the project's active EEAT criteria, compute SHIP / FIX / BLOCK verdict, and persist via article.markEeatPassed when the verdict is SHIP.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: original
license: project-internal
allowed_tools:
  - meta.enums
  - project.get
  - voice.get
  - eeat.list
  - eeat.score
  - eeat.bulkRecord
  - article.get
  - article.markEeatPassed
  - compliance.list
  - run.start
  - run.heartbeat
  - run.finish
  - run.recordStepCall
  - procedure.currentStep
  - procedure.recordStep
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
  - table: eeat_evaluations
    write: eeat.bulkRecord persists one row per active criterion with verdict pass / partial / fail and rationale notes.
  - table: articles
    write: article.markEeatPassed advances edited → eeat_passed when the verdict is SHIP.
  - table: runs
    write: per-criterion verdicts, dimension scores, system scores, vetoes_failed, top_issues, final verdict in runs.metadata_json.eeat.
---

## When to use

This is the gate between LLM-authored content and the published article. Procedure 4 calls it after the editor (#10) and humanizer (#12) have polished the draft. The gate audits `articles.edited_md` against the project's active `eeat_criteria` rows (not the hardcoded 80-item rubric — every project customises), produces three artifacts (per-criterion verdicts, aggregate scores, a final SHIP / FIX / BLOCK verdict), and either advances the article toward publication or routes it back for repair.

The skill is the FIX loop boundary: when the verdict is FIX, the current operator agent loops back to the editor (#10) with the gate's fix list. When the verdict is BLOCK, the procedure aborts with `articles.status='aborted-publish'` per audit BLOCKER-09. When the verdict is SHIP, the article advances and the next skill (image-generator #13) runs.

Re-runs are common during the FIX loop — each EEAT-gate run is a fresh `run_id` and writes a fresh batch of `eeat_evaluations` rows; old evaluations from prior runs remain for audit. The repository's `score()` query filters by `(article_id, run_id)` so the current run's verdict is computed against only the current run's evaluations.

## Inputs

- `article.get(article_id)` — returns `edited_md` (the artifact under review), `outline_md` (structural context), `brief_json` (the contract the article was written against), `voice_md`-related metadata, and the live `step_etag`. Confirm `status='edited'`.
- `voice.get(project_id)` — the active voice profile. The gate uses voice for two things: dimension weight overrides (some voices specify per-content-type weight tables; see step 5) and tone-consistency evaluation (the gate scores Trust dimension partly on whether the article's voice matches the voice profile).
- `eeat.list(project_id, active_only=true)` — the project's currently active EEAT criteria. The gate audits against these rows, not against a hardcoded rubric. Each row carries: `id`, `code` (e.g., `T04`, `C01`, `R10`, `E03`), `category` (one of `C / O / R / E / Exp / Ept / A / T`), `tier` (`core` / `recommended` / `project`), `text` (the human-readable standard), `required` (bool), `weight` (per-criterion override; defaults to 1.0).
- `compliance.list(project_id, active_only=true)` — the active rules. The gate confirms `position='footer'` rules surfaced in the article (a Trust dimension input for C01) and `position='after-intro'` rules surfaced where the brief flagged them.
- `meta.enums` — the EEAT category / tier / verdict enums plus the canonical 8-dimension code list, so the gate can render a consistent report shape regardless of which subset the project activated.

## Steps

1. **Read context.** Resolve the article. Confirm `status='edited'`. Pull `edited_md`, the active criteria, the active compliance rules, the voice profile, and the live `step_etag`. Read `runs.metadata_json.editor.fix_addressed[]` from the prior editor run (when this is a FIX-loop re-entry) so the gate can prioritise re-checking the criteria the editor claimed to address.
2. **Coverage floor check (D7 invariant — load-bearing).** Compute coverage as the percentage of the 8 canonical dimensions (`C / O / R / E / Exp / Ept / A / T`) that have at least one active criterion. If any dimension has 0 active criteria, the gate aborts the run with a `EeatCoverageError` and surfaces a `BLOCK` verdict to the API. Per PLAN.md L1028–1031 and audit D7, this is non-negotiable: the gate refuses to score a project whose rubric has been deactivated below the coverage floor. Surface the empty dimension(s) in `runs.metadata_json.eeat.coverage_failure_dimensions[]` and recommend `procedure bootstrap-fix` to repair the seed.
3. **Critical trust pre-check.** Before running the full pass, scan three load-bearing trust signals quickly:
   - **Affiliate disclosure (T04 input)** — confirm the after-intro and footer positions both render the active affiliate rule when the article carries any monetised link patterns. Missing disclosure with monetised links is the primary T04 fail mode.
   - **Title-content match (C01 input)** — confirm the title (H1) makes a promise the body delivers. If the H1 names a specific claim and the body never substantiates it, C01 fires.
   - **Self-consistent data (R10 input)** — scan numeric claims for internal contradictions ("23% drop" in one section, "40% drop" in another for the same metric). Self-contradicting data is the primary R10 fail mode.
   The pre-check is fast (regex + simple semantic compares) and lets the gate surface a likely BLOCK verdict early so the operator agent can abort without paying for the full 80-item evaluation.
4. **Per-criterion evaluation (the LLM-reasoning pass).** Walk every active criterion. For each:
   - Read the criterion's `text` (the human-readable standard, e.g., "Article cites at least one primary source per load-bearing claim" for R10).
   - Read the criterion's `category` and `tier` to know which slice of the article to focus on.
   - Apply the standard to `edited_md`. Produce a verdict (`pass` / `partial` / `fail`) and a short note (1–3 sentences) explaining the evidence behind the verdict. The note is the audit trail — the EEAT-FIX loop reads it to know what the editor needs to fix.
   - For `tier='core'` rows, be conservative: the verdict gates publishing. A `fail` here is a BLOCK; never assign `partial` to a core criterion when the evidence is ambiguous — escalate to `fail`.
   - For dimensions outside the article's scope (e.g., a B2B SaaS landing-page article evaluating an `Exp` row about first-person sensory detail), record `partial` with a note explaining the inapplicability rather than `fail`. The project should have deactivated the inapplicable criterion at bootstrap; if it didn't, surface for the next bootstrap-fix.
5. **Content-type-specific dimension weights (advisory).** When the project's voice profile carries a weight table keyed by article content type (e.g., `voice.eeat.weights['product-review'] = {C: 1.2, O: 1.0, R: 0.9, E: 1.5, Exp: 1.4, Ept: 1.0, A: 1.1, T: 1.3}`), apply the weights to the dimension scores before final aggregation. Common content types: Product Review, How-to Guide, Comparison, Landing Page, Blog Post, FAQ Page, Alternative, Best-of, Testimonial. The weights are advisory — the gate runs without them when the voice doesn't carry a table. Persist the chosen weight set in `runs.metadata_json.eeat.weights_applied`.
6. **Persist the per-criterion verdicts.** Call `eeat.bulkRecord(article_id, run_id, evaluations=[...])`. The repository inserts one row per criterion in a single transaction. Each evaluation is `{criterion_id, verdict, notes}`. The bulk insert is atomic; a per-row failure rolls back the whole batch.
7. **Aggregate scores.** Call `eeat.score(article_id, run_id)`. The repository returns:
   - `dimension_scores: {C, O, R, E, Exp, Ept, A, T → 0–100}` — each dimension's score is the average of its criteria's verdict scores (`pass=100`, `partial=50`, `fail=0`).
   - `system_scores: {GEO, SEO}` — `GEO = mean(C, O, R, E)`, `SEO = mean(Exp, Ept, A, T)`.
   - `coverage: {C, O, R, E, Exp, Ept, A, T → bool}` — confirms each dimension actually evaluated. Should already be all true after step 2, but the score query is the canonical confirmation.
   - `vetoes_failed: list[code]` — every `tier='core'` criterion with `verdict='fail'`.
   - `total_evaluations: int` — the row count for the run.
8. **Compute the verdict (PLAN.md L1018–1027 and audit BLOCKER-09 — load-bearing logic).**
   - **BLOCK** when `vetoes_failed` is non-empty. Any core veto failure aborts publishing regardless of overall score. Surface every failed code in the run metadata so the operator knows which veto fired.
   - **FIX** when `vetoes_failed` is empty AND any of these holds:
     - `min(dimension_scores.values()) < 60` — at least one dimension scored below the per-dimension floor.
     - `min(system_scores.values()) < 70` — either GEO or SEO scored below the per-system floor.
     - At least one `required=true` (non-core) criterion has `verdict='fail'`.
   - **SHIP** when `vetoes_failed` is empty AND every dimension is ≥ 60 AND both system scores are ≥ 70 AND no `required=true` criterion is `fail`.
9. **Identify top issues.** Select the top 3–5 criteria with the worst contribution to the verdict, sorted by impact:
   - Veto failures first (highest impact).
   - `required=true` failures next.
   - Failures in dimensions below the per-dimension floor next.
   - Partials in dimensions near the threshold last.
   For each top issue, capture `{criterion_code, category, tier, severity, finding}` where severity is `critical | high | medium | low`. The editor's FIX-loop pass reads `top_issues` to target its rewriting.
10. **Persist the audit row to the run.** Write `runs.metadata_json.eeat = {dimension_scores, system_scores, coverage, vetoes_failed, top_issues[], verdict, weights_applied?, fix_required?}`. The shape matches the `eeat-audit` discriminated-union row in PLAN.md L444 (`eeat-audit` kind), with the addition of `fix_required` when verdict is FIX so the editor's FIX-loop knows what to fix. `fix_required[]` is the same shape as `top_issues[]` filtered to `verdict='fail'` rows.
11. **Verdict-specific persistence.**
    - **SHIP** → call `article.markEeatPassed(article_id, expected_etag=<live etag>, run_id, eeat_criteria_version=<current rubric version>)`. The repository advances `articles.status` from `edited` to `eeat_passed`, freezes the rubric version (so future rubric edits don't retroactively invalidate the audit), and rotates `step_etag`. The next claimed step uses the fresh etag.
    - **FIX** → do NOT advance status. Persist `runs.metadata_json.eeat.fix_required[]` so the operator agent can loop back to skill #10 with focused repair instructions. The fix-loop counter is procedure state; if it exceeds the cap (default 3), the operator agent aborts the procedure rather than repeating the loop.
    - **BLOCK** → do NOT advance via `markEeatPassed`. Mark the article `aborted-publish` through the allowed article state transition, persist the BLOCK verdict to `runs.metadata_json.eeat`, and record the step as failed/aborted for the procedure.
12. **Finish.** Call `procedure.recordStep` with `{article_id, verdict, dimension_scores, system_scores, vetoes_failed, top_issues_count, fix_required_count?, fix_loop_iteration}`. A heartbeat fires after the per-criterion evaluation pass (step 4).

## Outputs

- `eeat_evaluations` — one row per active criterion for this run; verdict + notes.
- `articles.status` — advanced to `eeat_passed` on SHIP; unchanged on FIX; the operator agent moves it to `aborted-publish` on BLOCK.
- `articles.eeat_criteria_version_used` — frozen on SHIP for audit reproducibility.
- `articles.step_etag` — rotated on SHIP; the next claimed step uses the new value.
- `runs.metadata_json.eeat` — full audit shape per PLAN.md L444.

## Failure handling

- **Coverage floor breached.** Abort the run; do not write evaluations. Surface the empty dimension(s) and recommend `bootstrap-fix`. Status remains `edited`; the operator agent aborts the procedure with a clear operator-facing message.
- **`eeat.list` returns zero rows.** Equivalent to coverage failure; same handling.
- **`eeat.bulkRecord` rolls back.** Means a per-evaluation validation failed (e.g., a criterion_id no longer exists because the operator deactivated it mid-run). Refresh the criterion list, recompute evaluations against the fresh list, retry the bulk record once. Two consecutive rollbacks aborts the run.
- **`markEeatPassed` etag conflict on SHIP.** Means another writer touched the article between the gate's read and the markEeatPassed call. Refresh via `article.get`, retry once with the new etag. Two conflicts aborts and the operator agent restarts the gate.
- **A criterion's evidence is genuinely ambiguous.** Default to the more conservative verdict (partial vs. pass; fail vs. partial). The notes field records the ambiguity so the FIX-loop editor can decide whether to clarify or whether to flag the criterion as inapplicable.
- **Voice profile carries malformed weight table.** Ignore the weights and proceed with the unweighted aggregation. Surface in `runs.metadata_json.eeat.weights_skipped=true` with the parse error.

## Variants

- **`standard`** — the default flow above.
- **`strict`** — raises the per-dimension floor from 60 to 70 and the per-system floor from 70 to 80; useful for pillar articles or for projects with a stricter quality bar set in `voice.eeat.thresholds`. The strict thresholds are advisory; the operator agent reads them from voice and passes via skill args.
- **`audit-only`** — performs the full evaluation and persists `eeat_evaluations` but does NOT call `markEeatPassed` regardless of verdict. Used for periodic content-quality re-audits of already-published articles (procedure 6's GSC-driven cadence) where the gate is informational rather than gating.
