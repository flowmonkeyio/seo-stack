---
name: draft-intro
description: Write the article intro per the chosen opening archetype, restate the thesis, and persist via article.setDraft.
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
  - article.setDraft
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
    write: article.setDraft (append=false) seeds draft_md with the intro; status remains outlined.
  - table: runs
    write: chosen archetype, hook excerpt, citation insertions in runs.metadata_json.draft_intro.
---

## When to use

Procedure 4 dispatches this skill immediately after `outline` (#6). The intro is written first because it locks the voice the body and conclusion will match: the opening archetype, the reading level, the implied reader, the level of formality. Skills #8 (body) and #9 (conclusion) read the intro back to maintain continuity.

The intro is `article.setDraft(append=false)`: it overwrites whatever `draft_md` previously held. Re-running this skill replaces the intro and rotates the step_etag; the procedure runner picks up the fresh etag for the body phase.

## Inputs

- `article.get(article_id)` — returns `outline_md` (with the archetype HTML comments at the bottom), `brief_json`, the live `step_etag`, and the article's project metadata. Confirm `status='outlined'` before writing.
- `voice.get(project_id)` — the active `voice_md`. The intro inherits the voice's tone, person (first / second / third), formality slider, and any explicit prohibitions (e.g., "no exclamation points", "no rhetorical questions"). When the voice clashes with the chosen archetype, voice wins; the outline skill should have flagged the mismatch but enforce here too.
- `compliance.list(project_id, position='header')` and `compliance.list(project_id, position='after-intro')` — the rules that surface near the top of the article. Header rules render before the H1 (rare; mostly hidden-meta); after-intro rules render as a one-line callout immediately after the intro paragraph (e.g., affiliate disclosure for review content, age-gate notice for regulated jurisdictions).
- `eeat.list(project_id)` — surface the `tier='core'` and `required=true` rows so the intro can plant the right signals (a credentialed-author byline; a primary-source citation in the thesis statement; a compliance disclosure right after the hook).
- `source.list(article_id, used=false)` — the research-source rows the brief seeded. The intro typically cites one to three sources to anchor the thesis; mark each cited source `used=true` (via the source repository) by passing the new used flag through `source.add` semantics — the daemon handles the upsert.
- `meta.enums` — surfaces `intent`, `compliance_position`, and other enum values that intro composition references.

## Steps

1. **Read the outline + brief + run metadata.** Resolve the article and parse `outline_md` for the archetype HTML comment at the bottom (`<!-- opening: ...; closing: ... -->`). Pull the brief's title, thesis, audience, intent, and target word count. Capture the live `step_etag`. Read `runs.metadata_json.outline.archetypes` and `eeat_placement` from the previous run step so the intro inherits the outline's plan.
2. **Choose the hook concretely.** The outline named the archetype; the intro names the specific hook. Each archetype has a fingerprint:
   - **Direct** — first sentence states the thesis. Second sentence names the reader's stake. Third sentence sets the article's promise. No throat-clearing.
   - **Contextual** — first paragraph (3–5 sentences) frames why this matters now: a recent shift, a stat that names the problem, a concrete scenario the reader is in. Second paragraph states the thesis and the article's promise.
   - **Narrative** — first paragraph (3–6 sentences) sketches a scene, anecdote, or short case. The protagonist is either the reader-projection ("you walk into...") or a third party ("Sara opened the report..."). Voice profile decides which. Second paragraph zooms out to name the thesis.
   - **Tension** — first sentence names a contradiction or a contested claim. Next 2–4 sentences sketch the two sides. Final sentence names the thesis as the resolution the article will defend.
3. **Write the hook.** Aim for ~80–150 words, longer for `pillar` variants and shorter for `short` variants. The hook ends with a sentence that earns the thesis — not "in this article we will explore..." but a sentence that makes the reader want the next paragraph.
4. **Restate the thesis.** Convert the brief's `thesis` into one sentence in the article's voice. The thesis sentence is the contract: a reader who reads only the intro should walk away knowing what the article argues. Place it as the final sentence of the second paragraph (contextual / narrative archetypes) or the second sentence of the first paragraph (direct archetype) or the closer of the first paragraph (tension archetype).
5. **Set the reader's expectation.** A short third paragraph (or the closer of the second, depending on archetype) names what the reader will be able to do or know after reading. Avoid the outline-as-promise smell ("we'll cover X, Y, Z") — instead, frame the takeaway. Three to five sentences max.
6. **Plant load-bearing EEAT signals.** The brief's `eeat_plan` and the outline's `eeat_placement` told us which signals belong here. Common intro-resident signals:
   - **T04 (credentialed author)** — surface the byline naturally if the voice profile permits ("After ten years auditing accounts in this niche..."); otherwise the publish step renders a structured byline block elsewhere.
   - **R10 (primary-source citation)** — cite at least one research source `[^N]` in the thesis paragraph to anchor the central claim.
   - **C01 (compliance disclosure)** — render the after-intro footer rule one line beneath the intro using the rule's `body` field.
   Do not invent credentials or citations the brief did not seed; if the brief is short on signals, surface the gap in `runs.metadata_json.draft_intro.unmet_signals[]` rather than fabricate.
7. **Insert citations.** Use `[^N]` markers where N is the stable source index from `source.list`. The footnote definitions are NOT written by the intro skill; they accumulate at the end of the draft after `draft-conclusion` finishes and the editor pass tightens. The marker reference is enough — the body and conclusion skills coordinate so each marker gets a definition exactly once.
8. **Render the after-intro compliance line.** For each rule in `compliance.list(project_id, position='after-intro')`, append a one-line callout immediately below the intro paragraphs. The exact rendering depends on the rule's `body` (typically a markdown blockquote or a bold callout). Do not modify the rule body; render it verbatim. The conclusion skill handles `position='footer'` rules separately.
9. **Compose the markdown.** The intro markdown is the H1 line from the outline followed by the intro paragraphs and the after-intro compliance callout. Do not include any H2 sections; the body skill writes those. Keep the H1 line exactly as the outline rendered it — the editor pass may tighten the H1 later, but the intro skill does not.
10. **Persist.** Call `article.setDraft(article_id, draft_md=<intro markdown>, append=false, expected_etag=<live etag>)`. The repository writes `draft_md` (replacing whatever was there), rotates `step_etag`, and does NOT advance status — the body skill will append, and `mark_drafted` (from the conclusion skill) will close the draft phase. Capture the new etag.
11. **Finish.** Call `run.finish` with `{article_id, archetype, hook_words, thesis_sentence, citations_inserted, compliance_lines_rendered, unmet_signals}`. Heartbeats fire after the hook is drafted (step 3) and after the EEAT signal pass (step 6) so a slow LLM call stays visible.

## Outputs

- `articles.draft_md` — H1 + intro paragraphs + after-intro compliance callout.
- `articles.step_etag` — rotated; the procedure runner hands the new value to skill #8.
- `runs.metadata_json.draft_intro` — `{archetype, hook_words, citations_inserted[], compliance_lines_rendered[], unmet_signals[]}`.

## Failure handling

- **Status not `outlined`.** Abort. `set_draft` accepts `outlined` or `drafted`, but a fresh intro on `drafted` would clobber the body — refuse and let the procedure runner reset by calling `mark_drafted` reversal (M7's responsibility).
- **Outline missing archetype comment.** Abort with a message asking the runner to re-run skill #6. The intro cannot pick a hook without knowing the archetype the outline planned.
- **Voice / archetype clash unresolvable.** Surface in `runs.metadata_json.draft_intro.voice_archetype_conflict` with both values; pick voice (it's higher authority); proceed.
- **Source `used=true` flip fails (concurrent writer).** The intro itself succeeded; record the failure in metadata and continue. The body skill will refresh the source list and re-mark.
- **Etag mismatch.** Refuse to write. Procedure runner refreshes by reading the article again.

## Variants

- **`fast`** — direct archetype only, single iteration; useful in `bulk-content-launch` where speed matters and the bulk template already vetted the voice.
- **`standard`** — the default flow with archetype-from-outline and one revision pass.
- **`pillar`** — longer hook (up to 250 words), permits a sub-thesis paragraph between the hook and the main thesis when the article spans multiple stakes.
