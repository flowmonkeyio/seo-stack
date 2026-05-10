---
name: humanizer
description: Vary sentence rhythm, strip second-order AI tells the editor missed, inject voice-appropriate asides, and rewrite edited_md back through article.setEdited.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: original
license: project-internal
allowed_tools:
  - meta.enums
  - project.get
  - voice.get
  - article.get
  - article.setEdited
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
    write: article.setEdited rewrites edited_md (status remains edited).
  - table: runs
    write: per-paragraph rhythm deltas, second-order tell removals, asides injected in runs.metadata_json.humanizer.
---

## When to use

Procedure 4 calls this skill once per article version, between the editor (#10) and the EEAT gate (#11). The editor scrubs the surface tells (filler stems, transition overuse, weak structures) and calibrates against the voice profile; the humanizer is the second pass that handles what survives — rhythm uniformity (the most reliable AI-tell signal), second-order phrase patterns the editor's blacklist did not catch, and the absence of voice-appropriate asides where the brief permits them. The output is rewritten in place: `articles.edited_md` is replaced (not appended), `articles.status` does not change, and the article remains in the `edited` state for the gate to score.

The humanizer also runs inside procedure 7 (`monthly-humanize-pass`): for each article whose `articles.status='refresh_due'`, the procedure creates a new version via `article.createVersion`, runs the humanizer against the new version's `edited_md`, then re-runs the editor + gate against the updated content. Per audit P-I1, the humanizer runs **once per article version** — re-running on the same version is forbidden because successive humanizer passes drift away from voice.

## Inputs

- `article.get(article_id)` — returns `edited_md` (the artifact under rewrite), `outline_md` (structural reference), `brief_json` (the contract — especially the voice and the EEAT plan), the live `step_etag`. Confirm `status='edited'`.
- `voice.get(project_id)` — the active voice profile's `voice_md`. The humanizer leans hard on voice for two decisions: which sentence-rhythm fingerprint to target (clipped staccato vs. flowing periodic vs. mixed), and whether asides are permitted (some voices forbid first-person; some encourage personal anecdote; many sit in between). Surface the voice's `humanizer_preferences` block when present (a free-form key the operator can use to give the humanizer specific guidance, e.g., "prefer two-clause sentences over three-clause").
- `meta.enums` — surfaces enum values referenced when the humanizer logs its rewrites.

## Steps

1. **Read context.** Resolve the article. Confirm `status='edited'`. Pull `edited_md`, the voice profile, and the live `step_etag`. Read `runs.metadata_json.editor.ai_tell_log[]` (when present) so the humanizer doesn't re-flag the same tells the editor already addressed — second-order work only.
2. **Idempotency check.** Per audit P-I1, the humanizer runs once per article version. Detect whether this version already had a humanizer pass by querying recent runs of this article: if any prior `runs` row has `kind='humanize-pass'`, `status='success'`, `article_id=<this article>`, AND that run's completion timestamp is later than `articles.updated_at` of the most recent edit (i.e., no editor pass intervened), abort with a clear message. The procedure agent is responsible for sequencing humanizer once per version; this check is a defence-in-depth invariant rather than a primary control.
3. **Initialise the change log.** The humanizer writes `runs.metadata_json.humanizer` with a structured shape: `{rhythm_deltas: [...], second_order_tells_removed: [...], asides_injected: [...], voice_drift_score, citation_invariant_held}`. Each rewrite gets logged so the EEAT gate's tone-consistency dimension and any future audit can trace what changed.
4. **Pass 1 — Sentence rhythm analysis.** Walk the article paragraph by paragraph. For each paragraph, compute the sentence-length distribution (word counts per sentence; mean and standard deviation across the paragraph). The fingerprint of LLM-uniform prose is low standard deviation: when most sentences in a paragraph land in a tight band (e.g., 14–18 words), the rhythm reads as machine-shaped even when the words are correct. Flag every paragraph whose standard deviation falls below a per-voice threshold (default: 5 words; voice profiles can override via `voice.humanizer.rhythm_floor`). Compute the same metric across the full article — uniform article-level rhythm is the strongest single AI tell.
5. **Pass 2 — Sentence rhythm rewrite.** For each flagged paragraph, vary the sentence lengths:
   - Pick the longest sentence and consider fragmenting it into two shorter sentences at the most natural conjunction. The fragment that comes second often wants to be a sharp short sentence (5–10 words) that lands a point.
   - Pick the shortest sentence and consider absorbing it into the prior sentence as a clause when the meaning flows. Short sentences that start with a conjunction ("And X.", "But Y.") are usually candidates.
   - Where neither move applies, rewrite one sentence to a different length (e.g., a 16-word sentence becomes a 9-word sentence + a 7-word follow-up) so the rhythm gains variety.
   - Cap the rewrites: do not rewrite every paragraph; pick the 30–50% of flagged paragraphs whose rewrites carry the highest rhythm delta. Over-rewriting breaks the voice's pacing.
   For every rewrite, log a `{paragraph_id, rhythm_delta, before, after}` entry in `rhythm_deltas[]`.
6. **Pass 3 — Second-order AI-tell removal.** Beyond the editor's blacklist (filler stems, transition overuse, weak structures), scan for the higher-order phrase patterns that mark LLM prose:
   - **Article-as-tour-guide phrases** — "let's dive into...", "let's explore...", "we'll take a look at...", "in this comprehensive guide we will...". The article should not announce its own structure; structure is the headings' job.
   - **Empty-evidence phrases** — "studies show...", "research suggests...", "experts agree...", "many people say..." without a citation marker. Either replace with a specific citation `[^N]` (when a research source supports the claim) or with a sentence that names the actual evidence ("the 2024 industry report from <name>..."). When neither path is available, drop the empty claim — a hedged claim with no evidence weakens the article.
   - **Reader-flattering openers** — "as you may know...", "as we all know...", "you've probably heard...", "as a savvy reader you...". Strip; the reader doesn't need to be told what they know.
   - **Wikipedia-voice constructions** — "X is the term used to describe Y", "X refers to Y", "Y is often defined as X". Replace with a fresh definition in the article's voice ("X handles Y by..." or "Y is when..." depending on tone slider).
   - **Paragraph-level repetition** — three consecutive paragraphs that all start with the same noun, same connective, or same sentence shape. Vary at least one.
   For every removal, log a `{tell_pattern, paragraph_id, before, after}` entry in `second_order_tells_removed[]`. Cap the log at 50 entries; beyond that, count without storing.
7. **Pass 4 — Voice-appropriate asides.** When the voice profile permits (`voice.structure.permit_personal_asides=true` or equivalent), inject one anecdote-style aside per ~700 words at natural section boundaries. The aside is grounded in the brief's `voice.author_voice` description; if the brief did not seed a voice persona, do not invent one. The aside lands as a one-paragraph parenthetical or as a one-sentence in-line note that breaks the paragraph rhythm naturally:
   - In-section asides land at the end of a paragraph as a fresh sentence: "I've watched this play out three times now in client engagements; the pattern holds."
   - Section-boundary asides land between two H2 sections as a one-paragraph italicised block when the voice permits italics for asides; otherwise as a plain paragraph.
   - Each aside cites no research source and makes no testable claim — asides are voice texture, not evidence. The EEAT gate's R10 check ignores them.
   When the voice profile forbids first-person or any personal aside, this pass is skipped entirely. Surface the skip in `runs.metadata_json.humanizer.asides_skipped='voice-prohibits'`.
   For every injected aside, log a `{paragraph_anchor, aside_text, voice_persona_used}` entry in `asides_injected[]`.
8. **Citation invariant check.** Throughout every pass, the humanizer MUST NOT modify the `[^N]` markers. The marker syntax is load-bearing for the EEAT gate's R10 check and the conclusion skill's footnote definitions. Count markers in `edited_md` before and after the humanizer's rewrites; the counts must match exactly. Where they do not, the rewrite that broke the invariant gets rolled back and re-attempted without affecting the marker. Log `citation_invariant_held=true` when the final count matches; on mismatch the humanizer aborts with a recoverable error and the procedure agent may retry once.
9. **Voice drift detection.** Compute a coarse voice-drift score: tokenise the rewritten article and compare its tone fingerprint (formality words, hedge words, first-person count, rhetorical-question count) against the voice profile's expected fingerprint. The drift score is normalised to 0–100 where 0 means perfect alignment and 100 means a fully disjoint tone. Surface in `runs.metadata_json.humanizer.voice_drift_score`. Drift scores above 30 trigger a warning but do not abort; the EEAT gate's tone-consistency dimension reads the rewritten article and decides FIX vs. SHIP independently. Drift scores above 60 abort the humanizer and roll back to the pre-humanizer `edited_md` — the editor's output is the safer baseline to ship to the gate.
10. **Persist.** Call `article.setEdited(article_id, edited_md=<rewritten markdown>, expected_etag=<live etag>)`. The repository writes `edited_md` (replacing whatever was there from the editor's pass), rotates `step_etag`, and does NOT change status (status was already `edited`; setEdited's documented behaviour is `drafted → edited`, which is a no-op when called from `edited`). The procedure agent passes the new etag to skill #11 (eeat-gate).
11. **Finish.** Call `run.finish` with `{article_id, paragraphs_analyzed, paragraphs_rewritten, second_order_tells_removed_count, asides_injected_count, voice_drift_score, citation_invariant_held}`. Heartbeats fire after each pass so a slow rewrite stays visible.

## Outputs

- `articles.edited_md` — humanized markdown with varied rhythm, second-order tells stripped, voice-appropriate asides injected.
- `articles.step_etag` — rotated; the procedure agent passes the new value to skill #11.
- `runs.metadata_json.humanizer` — structured change log per pass.

## Failure handling

- **Status not `edited`.** Abort. The editor advances `drafted → edited`; if status is `drafted`, the editor never ran; if `eeat_passed`, the gate already approved and the humanizer is too late. The procedure agent sequences correctly; the check is defence-in-depth.
- **Idempotency check trips (already humanized).** Abort with the clear message; the procedure agent is responsible for not running humanizer again on the same version. This is the audit P-I1 safety net.
- **Citation marker count diverges.** Roll back the offending rewrite, retry without affecting the marker. Two consecutive rollbacks on the same paragraph aborts the humanizer and persists the editor's pre-humanizer output.
- **Voice drift score exceeds 60.** Abort and roll back to the editor's `edited_md`. The EEAT gate scores the editor-only output; the operator audits the humanizer's run metadata to decide whether the voice profile needs adjustment or whether the humanizer over-applied.
- **Aside injection fails because the voice persona is empty.** Skip the aside pass; log `asides_skipped='voice-persona-empty'`; continue. The other passes still run.
- **Etag mismatch on `setEdited`.** Refresh via `article.get`; retry once with the new etag. Two conflicts abort and the procedure agent decides whether to retry or fork.
- **`runs` query for prior humanize-pass returns ambiguous results.** Default to the conservative path: assume the version was already humanized; abort. The operator can override by manually setting `articles.updated_at` (procedure 7's `article.createVersion` step bumps it correctly).

## Variants

- **`fast`** — passes 1, 2, and 8 only (rhythm + citation invariant); skips the second-order tell pass and the asides pass. Useful inside `bulk-content-launch` where the editor's pass is sufficient and the humanizer is a polish.
- **`standard`** — the default flow above, all four passes.
- **`refresh`** — invoked from procedure 7 (`monthly-humanize-pass`) against a freshly-versioned article. Identical to `standard` except the idempotency check reads `article_versions.created_at` instead of `articles.updated_at` because procedure 7 created the new version moments earlier and the timestamp comparison shape differs.
