---
name: editor
description: Apply the ten-section editorial pass to the assembled draft, scrub AI tells, calibrate emphasis and visual breaks against the voice profile, and persist via article.setEdited.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: original
license: project-internal
allowed_tools:
  - meta.enums
  - project.get
  - voice.get
  - compliance.list
  - eeat.list
  - article.get
  - article.setEdited
  - source.list
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
    write: article.setEdited writes edited_md and advances drafted → edited.
  - table: runs
    write: per-pass change counts, AI-tell removal log, voice-calibration deltas in runs.metadata_json.editor.
---

## When to use

Procedure 4 dispatches this skill once per draft cycle, after `draft-conclusion` (#9) closes the draft phase. The editor is the single most important quality gate before the EEAT pass: it scrubs the surface tells that mark LLM-authored prose, calibrates emphasis and visual breaks against the project's voice profile, and tightens clauses that the section-by-section drafting necessarily left baggy. The EEAT gate (#11) reads `articles.edited_md` directly — it does not see the raw `draft_md`.

The editor also handles the EEAT-FIX loop. When the EEAT gate returns FIX, the procedure runner re-runs this skill with `runs.metadata_json.fix_required=[{criterion_id, finding, severity}]` so the editor can target specific deficiencies the gate detected. The runner increments a fix-loop counter; once the counter reaches its cap (default 3), the run aborts to avoid infinite ping-pong between editor and gate.

## Inputs

- `article.get(article_id)` — returns `draft_md` (the assembled output of skills #7/8/9), `outline_md` (preserved as a structural reference), `brief_json`, the live `step_etag`. Confirm `status='drafted'` (the conclusion advanced it). On a FIX-loop re-run, `runs.metadata_json.fix_required[]` from the prior gate run is read by the procedure runner and surfaced via the run's args.
- `voice.get(project_id)` — the load-bearing input. The editor calibrates against the voice's `tone` slider, `formality` slider, `structure.examples`, `structure.example_density`, `structure.visual_breaks`, `formatting.em_dashes`, `formatting.emojis`, and any explicit prohibitions captured in `voice_md`. Skip voice and the editor renders generic LLM prose; the EEAT gate's tone-consistency dimension penalises that hard.
- `compliance.list(project_id)` — every active rule. The editor confirms each rendered rule (header / after-intro / every-section / footer) survived the draft phase intact. Compliance bodies are immutable; the editor must not paraphrase them.
- `eeat.list(project_id)` — the active criteria. The editor pre-checks the FIX-class signals (citation density, header presence, claim specificity) so the EEAT gate's first look is on a polished article.
- `source.list(article_id, used=true)` — the cited research sources. The editor confirms every `[^N]` marker in the draft has a corresponding footnote definition and vice versa; mismatches are FIX-class.
- `meta.enums` — surfaces enum values the editor references (compliance positions, EEAT categories, voice tone keys).

## Steps

1. **Read context.** Resolve the article. Confirm `status='drafted'`. Pull `draft_md`, `voice_md`, the active compliance rules, the EEAT criteria, and the used-source list. Capture the live `step_etag`. On a FIX-loop re-run, parse the fix list and prioritise those criteria during the appropriate passes below.
2. **Initialise the change log.** The editor writes `runs.metadata_json.editor` with a structured change log per pass. Each entry is `{pass, count, examples}` where examples are 2–5 representative before/after snippets. The log lets the EEAT gate (and a follow-up FIX loop, if any) audit what the editor changed.
3. **Pass 1 — Content enhancement.** Walk every H2 / H3 section. Calibrate examples (lists, tables, diagrams, code blocks, blockquotes, case-study snippets) against `voice.structure.examples` and `voice.structure.example_density`. The body skill (#8) seeded the example types; the editor:
   - Adds a missing example in a section that needs it (a reader-facing comparison without a comparison table; a numerical claim without a chart-shaped block).
   - Removes a gratuitous example that doesn't serve the section's claim.
   - Tightens a list that's too long (above 7 items in `low` density, above 12 in `generous`).
   - Converts a paragraph-shaped enumeration into a list when the voice density permits.
   Do not invent data; if a comparison would need numbers the brief did not seed, surface a `runs.metadata_json.editor.example_gap` entry and leave the prose alone.
4. **Pass 2 — Text emphasis.** Apply emphasis discipline:
   - **Bold** for key terms on first appearance, takeaway sentences, and warnings the reader must not miss.
   - **Italic** for subtle emphasis, technical terms in their own definition, the titles of works being referenced, and the spoken stress of a phrase the voice profile prefers to surface.
   Cap density: at most one bold per paragraph for `low` voice density, two for `moderate`, three for `generous`. The same cap applies to italics. Strip emphasis the draft over-applied (entire sentences in bold, multiple bold runs in a single sentence).
5. **Pass 3 — Visual breaks.** Calibrate by `voice.structure.visual_breaks`:
   - **Minimal** — paragraphs of 3–6 sentences, two visual breaks per article max (a horizontal rule between major sections only).
   - **Moderate** — paragraphs of 2–4 sentences, visual breaks at every other H2.
   - **Generous** — paragraphs of 1–3 sentences, visual breaks at every H2, optional pull-quote blocks in body sections.
   The body skill drafted at moderate density by default; rebalance to match the voice. Avoid wall-of-text paragraphs (more than 6 sentences) regardless of voice.
6. **Pass 4 — Em dashes.** Calibrate by `voice.formatting.em_dashes`:
   - **0–2 per article** — sparse use; replace excess with commas or sentence breaks.
   - **3–5 per article** — moderate; preserve the most rhetorically effective uses.
   - **6–10 per article** — generous; permit em-dashes for asides and dramatic pauses.
   Em-dash overuse is a strong AI tell. Default-strip below the voice's range; rewrite with commas, parentheses, or new sentences. Never replace an em-dash with a hyphen.
7. **Pass 5 — Emoji.** Calibrate by `voice.formatting.emojis`:
   - **None** — strip every emoji from the prose. The compliance footer's renderer is exempt (some compliance bodies carry warning glyphs verbatim).
   - **Sparing** — one to two per article, only at section closes or in lists where they aid scanning.
   - **Generous** — voice-permitting; cap at one per paragraph regardless.
   Strip every emoji from headings unconditionally — headings are SEO surface and emojis hurt rendering on some publish targets.
8. **Pass 6 — AI-tell removal (the load-bearing pass).** This is where the editor earns its keep. Scan the entire draft for the surface signals that mark LLM-authored prose. The procedure runner reads the count of removals as a quality KPI; the EEAT gate's tone-consistency dimension reads the residual count. Three categories of tell to scrub:
   - **Filler stems** — phrases that announce a thought without adding to it. The editor strips every instance of stems that follow this shape: "It is important to note that...", "It is worth mentioning that...", "Interestingly enough...", "In today's world...", "In this article, we will...", "It is no surprise that...", "It cannot be overstated that...", "Without a doubt...", "Needless to say...". Replacement is usually nothing — the sentence reads better with the stem deleted entirely. When the stem signalled an actual transition the prose needed, replace with a one-word transition that pulls weight ("Also", "Still", "Today", "Because of this") or with a sentence-level pivot the editor writes fresh.
   - **Transition overuse** — connector words that the LLM drafts every other paragraph. Reduce drastically: at most one per page of body for words like "Additionally", "Furthermore", "Moreover", "However", "Therefore", "Consequently", "In addition", "On the other hand". Replace surplus instances with sentence-level pivots (a new sentence that names the contrast or addition without the connector word) or with shorter connectors ("And", "But", "So", "Yet"). The voice profile may permit higher density when its `formality` slider is set high.
   - **Overused structures** — the LLM defaults that flatten prose. Three patterns to break:
     - Multiple paragraphs starting with "This" — the deictic-this-as-paragraph-opener is so common it reads as machine-shaped. Vary: lead with the noun the "this" pointed at, with a sentence subject other than "this", or with a fresh transition.
     - "When it comes to X..." — almost always replaceable with a direct "X is..." or "In X...".
     - "X is a Y that Z" — the weak-verb definition. Rewrite with the strongest verb that fits ("X handles Y", "X surfaces Y", "X breaks Y") and move the modifier next to its noun.
   For every removal, log a `{tell, before, after, paragraph_id}` row in `runs.metadata_json.editor.ai_tell_log[]`. Cap the log at 50 entries; beyond that, count without storing.
9. **Pass 7 — Tone consistency.** Calibrate against `voice.tone`. The voice's tone slider is a continuum (e.g., authoritative ↔ conversational; clinical ↔ warm; understated ↔ punchy). Walk the draft section by section and flag sentences whose tone diverges from the voice's set point. Rewrite the divergent sentences to match. The body skill (#8) sometimes drifts mid-article when a section pulls heavily from one source whose original tone leaks through; the editor catches it.
10. **Pass 8 — Prose tightening.** Apply the universal tightening rules:
    - **Remove redundant words** — "very", "really", "quite", "extremely", "completely", "totally" rarely add meaning. Strip on sight unless the voice profile explicitly permits intensifiers.
    - **Remove weasel words** — "some", "many", "experts say", "studies show" — replace with the specific number, source, or quoted expert if the brief seeded one; otherwise drop the unsupported claim.
    - **Remove unnecessary qualifiers** — "in some cases", "more or less", "to a certain extent" — the qualifier weakens the claim without protecting it. Strip.
    - **Passive → active** — convert passive constructions where active reads cleaner. Preserve passive when the actor is genuinely unknown or unimportant.
    - **Long → short** — sentences above 30 words usually want a break. Find the most natural conjunction and split.
    - **Weak → strong verbs** — "make use of" → "use"; "give consideration to" → "consider"; "reach a conclusion" → "conclude". Strip the noun-of-verb pattern wherever it appears.
11. **Pass 9 — Spelling and grammar.** Run a fresh pass for typos, agreement errors, comma splices, and mis-capitalised proper nouns. The voice profile may carry locale-specific spelling (en-GB vs. en-US); honour the locale per the project row. Compliance-rule bodies are immutable: do not "fix" spelling in a rule's `body`; surface in `runs.metadata_json.editor.compliance_grammar_warnings[]` for the operator to flag upstream if needed.
12. **Pass 10 — Flow and transitions.** Read the article straight through. Where a section transition jolts the reader, add a one-sentence bridge at the end of the prior section or the start of the next. Where a paragraph repeats the prior paragraph's content, merge or cut. The voice profile carries an implicit flow signature (some voices favour abrupt cuts, some favour smooth bridges); honour the signature.
13. **Citation marker invariant.** Throughout every pass, the editor MUST NOT modify the `[^N]` markers. The marker syntax is load-bearing for the EEAT gate's R10 check (every load-bearing claim cites a source) and the conclusion skill's footnote definitions. Removing or reordering markers breaks the article. The editor may add new markers when a fresh sentence cites a previously-uncited source; never remove. Any change to citation density gets logged in `runs.metadata_json.editor.citation_changes[]`.
14. **FIX-loop targeted edits.** When `runs.metadata_json.fix_required[]` was passed in (re-run from the EEAT gate), prioritise the relevant passes:
    - FIX with `criterion_code` in `{R01..R10}` (Referenceability) → re-run pass 6 (citation pre-check) plus pass 8 (tone consistency for citation prose).
    - FIX with `criterion_code` in `{T01..T10}` (Trust) → confirm the compliance footer rendered, the citations resolve, the byline is accurate; if a `tier='core'` Trust criterion fired, the gate returned BLOCK not FIX so this branch should not see core-Trust fixes.
    - FIX with `criterion_code` in `{C01..C10}` (Contextual Clarity) → re-run pass 1 (content enhancement, structural examples) plus pass 10 (flow).
    - FIX with `criterion_code` in `{O01..O10}` (Organization) → re-run pass 1 + pass 10.
    - FIX with `criterion_code` in `{E01..E10}` (Exclusivity) → flag in `runs.metadata_json.editor.exclusivity_gap[]`; the editor cannot manufacture exclusivity (original data, first-hand experience) — surface for operator review.
    - FIX with `criterion_code` in `{Exp01..Exp10}` (Experience) → re-run pass 7 (tone consistency for first-person voice).
    - FIX with `criterion_code` in `{Ept01..Ept10}` (Expertise) → flag for operator; the editor cannot manufacture expert credentials.
    - FIX with `criterion_code` in `{A01..A10}` (Authority) → confirm citations to authoritative domains; flag missing.
    For every FIX item, mark `{fix_id, addressed: bool, addressed_in_pass}` in `runs.metadata_json.editor.fix_addressed[]` so the next EEAT gate run can audit.
15. **Compose `edited_md`.** The structural shape mirrors `draft_md`: H1 + intro + body H2/H3 + conclusion + compliance footer + (optional) about-author + references. The differences are at the prose level — every change traced to a pass entry in the change log.
16. **Persist.** Call `article.setEdited(article_id, edited_md=..., expected_etag=<live etag>)`. The repository writes `edited_md`, advances `articles.status` from `drafted` to `edited`, and rotates `step_etag`. The procedure runner hands the new etag to skill #12 (humanizer) — humanizer runs after editor and writes back to `edited_md` without changing status.
17. **Finish.** Call `run.finish` with `{article_id, passes_run: [1..10], total_changes, ai_tell_count, citation_changes, fix_addressed_count, fix_loop_iteration}`. Heartbeats fire after each of the 10 passes so a long edit run stays visible.

## Outputs

- `articles.edited_md` — fully edited markdown with the full structural shape preserved.
- `articles.status` — advanced from `drafted` to `edited`.
- `articles.step_etag` — rotated; the procedure runner hands the new value to skill #12.
- `runs.metadata_json.editor` — structured change log per pass, AI-tell removal log, citation changes, fix-addressed map.

## Failure handling

- **Status not `drafted`.** Abort. The conclusion skill should have advanced via `markDrafted`. If status is `outlined`, the conclusion never ran; the procedure runner restarts from #9. If status is `edited`, the editor already ran; the FIX-loop re-run path uses the same skill but the procedure runner manages the etag rotation and increments the fix-loop counter.
- **Voice profile missing.** Abort. The editor without voice produces generic prose; the EEAT gate's tone-consistency dimension flags it. Procedure 1 should have seeded a default voice; if it didn't, the bootstrap is broken — surface and stop.
- **Citation marker count changes unexpectedly.** When `[^N]` count in `edited_md` differs from `draft_md` and the editor did not log the change in `runs.metadata_json.editor.citation_changes[]`, refuse to persist; the change log is the audit trail and an unrecorded change is a bug. Re-run the relevant pass.
- **AI-tell removal stripped a citation.** Means a stem like "Studies show that X[^4]" got over-aggressively trimmed. Detected via citation invariant; restore the citation marker, persist a `runs.metadata_json.editor.citation_restored[]` entry, continue.
- **FIX-loop iteration cap reached.** Default cap is 3 (per audit M-29). Procedure runner aborts the run before re-dispatching the editor when the counter hits the cap; the editor itself does not enforce the cap because it has no state for it.
- **Etag mismatch.** Refuse to persist; refresh via `article.get`; retry once.
- **Compliance rule body modified inadvertently.** Detect via byte-for-byte comparison against the rule's `body` field; restore the original; log in `runs.metadata_json.editor.compliance_restored[]`.

## Variants

- **`fast`** — passes 1–6 + 8 + 13 only; skip flow / spelling-grammar / final-tone passes for `bulk-content-launch` runs where the EEAT gate's FIX loop will catch quality misses anyway.
- **`standard`** — the default flow above, all 10 passes.
- **`pillar`** — adds an extra structural pass at the start (verify the H2 roster matches the outline), runs the AI-tell pass twice, and runs flow + transitions twice. Cost is roughly 30% more LLM tokens; quality lift is meaningful for pillar articles where the EEAT gate's standards are tighter.
- **`fix-loop`** — invoked when `runs.metadata_json.fix_required[]` is non-empty. Skips passes that don't intersect the fix list and emphasises the targeted passes from step 14.
