---
name: draft-conclusion
description: Write the article conclusion per the chosen closing archetype, render the compliance footer, append references, and close the draft phase via article.markDrafted.
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
  - article.markDrafted
  - source.list
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
  - table: articles
    write: article.setDraft (append=true) appends conclusion + footnotes; article.markDrafted advances outlined → drafted.
  - table: runs
    write: closing archetype, footer rules rendered, footnote count in runs.metadata_json.draft_conclusion.
---

## When to use

Procedure 4 calls this skill after `draft-body` (#8). The conclusion seals the article: it closes whichever rhetorical loop the intro opened, surfaces the compliance footer, materialises the footnote definitions for every `[^N]` marker the intro and body planted, and explicitly advances `articles.status` from `outlined` to `drafted` via `markDrafted`. After this skill returns, the editor (#10) takes over.

Re-running this skill replaces the conclusion (overwrites whatever follows the last body H2) and re-renders the footnote block. The procedure runner controls when to re-run via etag rotation.

## Inputs

- `article.get(article_id)` — returns `outline_md` (with archetype HTML comments), `brief_json` (closing archetype hint, target word count, references-section directive for `heavy` depth), the live `step_etag`, and `draft_md` (the H1 + intro + body sections from the prior skills). Confirm `status='outlined'` (the body did not advance status).
- `voice.get(project_id)` — the active voice's `voice_md`. The conclusion inherits the voice the intro and body set; no last-minute drift. Surface the voice's `closing_preference` if set (some voices default to `summary` regardless of archetype).
- `compliance.list(project_id, position='footer')` — the rules that render in the conclusion's footer block (responsible-gambling notices, age-gate notices, affiliate disclosures, jurisdiction-specific YMYL disclaimers).
- `eeat.list(project_id)` — the active criteria. The conclusion's primary EEAT job is C01 (compliance disclosure rendered correctly per active jurisdictions) and one half of T04 (credentialed-author byline if the voice profile prefers it in the footer instead of the byline).
- `source.list(article_id, used=true)` — the research sources cited in the intro and body. The conclusion renders their footnote definitions in a `## References` section so the citation markers resolve. Sources with `used=false` are not rendered (the brief seeded them but the article never cited them).
- `meta.enums` — surfaces enum values for compliance positions and EEAT categories.

## Steps

1. **Read context.** Resolve the article and parse `outline_md` for the archetype HTML comment at the bottom (`<!-- opening: ...; closing: ... -->`). Pull the live `step_etag`. Read `runs.metadata_json.outline.archetypes` and `runs.metadata_json.draft_intro` so the conclusion knows what hook the intro used (essential for the `callback` archetype).
2. **Confirm the closing archetype.** From the outline metadata and the brief, the closing archetype is one of six:
   - **Summary** — recap the load-bearing claims. Rendered as a tight 80–150 word paragraph or, for longer articles, a numbered list of 3–5 takeaways. Default for informational and how-to content.
   - **Call_to_action** — name a specific next step. Two to three sentences naming the action (sign up, download, compare, subscribe, contact) plus a link or button affordance the publish step renders. Default for commercial and transactional intent.
   - **Open_question** — leave a deliberately unresolved question to keep the reader thinking. One paragraph, ending on the question. Useful when the article opened a debate; less useful when the article was a how-to.
   - **Callback** — return to the intro's hook (anecdote, scene, contradiction) and close the loop. Two paragraphs: the first revisits the hook with new context, the second names the lesson. Default when the intro used a `narrative` opening.
   - **Provocation** — sharpen the thesis into a memorable claim. One paragraph, ending on a single declarative sentence. Useful when the brief's voice profile prefers strong opinions.
   - **Key_takeaways** — bulleted "if you remember nothing else" list. Five to seven bullets, each one short sentence. Tuned for skim readers and SEO featured-snippet eligibility.
3. **Write the closing.** Aim for ~120–250 words for `standard` and `short` variants, ~250–400 for `pillar`. The closing inherits the voice of the body; do not introduce new tone or formality. Cite at most one fresh research source `[^N]` here — the conclusion is for synthesis, not new evidence; if the source list is short on used sources, surface in `runs.metadata_json.draft_conclusion.unmet_signals[]` rather than fabricate.
4. **Render the compliance footer.** For each rule in `compliance.list(project_id, position='footer')`:
   - Render the rule's `body` verbatim (markdown blockquote, bold callout, or plain paragraph depending on the rule's shape).
   - When multiple jurisdictions apply, render the rules in the order returned by the repository (the repository sorts by jurisdiction code for stability).
   - When a rule is jurisdiction-specific and the article's `brief_json.compliance_jurisdictions[]` does not include the rule's jurisdiction, skip the rule and log in `runs.metadata_json.draft_conclusion.compliance_skipped[]`.
   - The compliance footer renders under a `## ` heading: typically `## Disclosures` for affiliate / financial / responsible-gambling rules, `## Notice` for age-gate, `## Health Information` for medical YMYL. The voice profile may override the heading text via `voice.compliance_heading`; honour the override when present.
5. **Render the references block.** Walk `source.list(article_id, used=true)` in the order the sources appear in the draft (not in `id` order — citation order is what matters for the reader). For each used source, emit a footnote definition at the bottom of the draft:
   ```
   [^N]: <source.title> — <source.url> (accessed <source.accessed_at>).
   ```
   Render the references under a `## References` heading. The brief's `outline_hint_md` for `heavy`-depth articles requested a `references_section`; honour that with the heading rendered exactly as `## References`. For `light`-depth articles where the brief did not request a references section, the conclusion still emits the footnote definitions because the citation markers must resolve, but the heading is `## Sources` (more conversational) per voice convention. The voice profile may override either heading.
6. **Plant final EEAT signals.** Cross-walk the brief's `eeat_plan` against what the body produced:
   - **C01 (compliance disclosure)** — the footer render in step 4 satisfies this. Confirm at least one rule rendered for each jurisdiction in `compliance_jurisdictions[]`.
   - **T04 (credentialed author)** — when the voice prefers a footer-resident byline (rather than the byline rendered by the publish step), render an "About the author" block immediately above `## References`. Pull author content from the article's author row (the byline, credentials, link to author page).
   - **R10 (primary-source citation)** — confirmed by the references block; the EEAT gate (#11) cross-checks marker count vs. footnote count.
   Surface unmet signals in `runs.metadata_json.draft_conclusion.unmet_signals[]`.
7. **Compose the conclusion markdown.** Order:
   1. Closing paragraph(s) under the appropriate H2 heading. The H2 heading text depends on archetype: `## Conclusion` for summary, `## What Now` for call_to_action, `## The Open Question` for open_question, `## Coming Full Circle` for callback, `## The Real Question` for provocation, `## Key Takeaways` for key_takeaways. Voice profile may override.
   2. Compliance footer (step 4).
   3. About-the-author block (step 6 if voice prefers footer byline).
   4. References block (step 5).
8. **Persist the conclusion.** Call `article.setDraft(article_id, draft_md=<conclusion markdown>, append=true, expected_etag=<live etag>)`. The repository appends to whatever the body skill left in `draft_md` and rotates `step_etag`. Capture the new etag for the markDrafted call.
9. **Close the draft phase.** Call `article.markDrafted(article_id, expected_etag=<new etag>)`. The repository advances `articles.status` from `outlined` to `drafted`. The procedure runner reads the new etag from the response envelope and hands it to the editor skill (#10).
10. **Finish.** Call `run.finish` with `{article_id, archetype, closing_words, footer_rules_rendered, references_count, unmet_signals, status_advanced}`. Heartbeats fire after the closing is drafted (step 3) and after the references block renders (step 5).

## Outputs

- `articles.draft_md` — H1 + intro + body + conclusion + compliance footer + (optional) about-author + references.
- `articles.status` — advanced from `outlined` to `drafted`.
- `articles.step_etag` — rotated twice (once per setDraft, once per markDrafted); the editor (#10) receives the most recent value.
- `runs.metadata_json.draft_conclusion` — `{archetype, closing_words, footer_rules_rendered[], references_count, compliance_skipped[], unmet_signals[]}`.

## Failure handling

- **Status not `outlined`.** Abort; refuse to write. The body should have left the article in `outlined`. If status is `drafted`, the conclusion already ran; the procedure runner uses `expected_etag` rotation to decide whether to re-run.
- **`setDraft` succeeds but `markDrafted` fails.** Means another writer touched the article between calls. Capture the failure in `runs.metadata_json.draft_conclusion.markDrafted_conflict=true`, refresh via `article.get`, retry `markDrafted` once with the fresh etag. Two consecutive conflicts means the procedure runner aborts and restarts the conclusion skill.
- **Compliance rule body malformed.** Render what we can, log the malformed rule in `runs.metadata_json.draft_conclusion.compliance_render_failures[]`, continue. The EEAT gate flags the section.
- **Footnote definition order conflicts with citation order.** Renumber by first-appearance order in the draft. The body skill's index assignment is the canonical source of truth; do not silently re-index.
- **`source.list` returns no used sources.** The intro and body planted no citations. Render the references block as empty (just the `## References` heading with a placeholder note "No external sources cited"). The EEAT gate's R10 check will fail FIX-class; the editor + EEAT-FIX loop adds citations.
- **Etag mismatch on `setDraft`.** Standard etag conflict — refresh, capture the new etag, retry once.

## Variants

- **`fast`** — summary archetype only, no about-author block, references block rendered without `accessed_at`. Useful in `bulk-content-launch`.
- **`standard`** — the default flow above.
- **`pillar`** — extended closing (up to 400 words), supports a multi-section closing (e.g., `## Key Takeaways` followed by `## What Comes Next`), and renders a richer references block with optional source descriptions. The about-author block is rendered for pillar articles regardless of voice preference because pillars carry the heaviest authority signal load.
