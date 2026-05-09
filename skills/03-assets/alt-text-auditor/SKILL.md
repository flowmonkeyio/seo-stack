---
name: alt-text-auditor
description: Score every article asset against the alt-text rubric, file-size tier, format, and above-the-fold loading rules; rewrite weak alt text via asset.update and persist findings to runs.metadata_json.alt_text_audit.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: original
license: project-internal
allowed_tools:
  - meta.enums
  - project.get
  - article.get
  - asset.list
  - asset.update
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
  - table: article_assets
    write: asset.update writes refined alt_text and clears or sets the per-asset audit flags surfaced in the metadata.
  - table: runs
    write: per-asset score, per-rule pass/fail, refined alt-text deltas, and aggregate counts in runs.metadata_json.alt_text_audit.
---

## When to use

Procedure 4 dispatches this skill immediately after the image-generator (#13). The generator drafted candidate alt text per slot; this skill is the consistency gate that confirms each candidate meets the rubric, fits its file-size tier, uses a sensible format, and carries the right above-the-fold loading hints for the publish step. The auditor either accepts the generator's draft (no asset.update call needed) or rewrites it (one asset.update call per refined alt text), and always emits a structured rubric report under `runs.metadata_json.alt_text_audit` so the EEAT gate's rerun-after-images audit can read it.

The skill also runs in a standalone mode the operator can invoke from the UI on any already-published article whose alt-text quality the operator suspects has drifted (e.g., a publish-target migration changed image hosting and broke alt attributes). In standalone mode the audit is identical; the only difference is the procedure runner is not in the loop, and the runs row is the audit's own surface for the report.

## Inputs

- `article.get(article_id)` — returns `edited_md` (used to map each inline image's surrounding paragraph for keyword-relevance scoring), `brief_json` (specifically `primary_kw` and `secondary_kws[]` — the auditor's keyword-relevance check uses these), the article's `slug`, and the article's `status`. The auditor accepts any status from `eeat_passed` onward (including `published` for refresh runs).
- `asset.list(article_id)` — every asset attached to the article. Returns each row's `id`, `kind`, `prompt`, `url`, `alt_text`, `width`, `height`, and `position`. The auditor walks every row regardless of kind; the rubric applies differently per kind (the LCP rule fires only on `hero`; the file-size tier differs for `thumbnail` vs. `inline` vs. `hero`).
- `meta.enums` — surfaces the canonical `ArticleAssetKind` enum so the auditor can map kinds to their tier rules without hardcoding strings.

## Steps

1. **Read context.** Resolve the article, pull every asset row, and capture the brief's primary and secondary keywords. Confirm at least one asset row exists; an empty asset list is not a hard failure (the article may legitimately ship without imagery), but the auditor surfaces `runs.metadata_json.alt_text_audit.empty=true` so downstream consumers know to skip the report.
2. **Initialise the rubric report.** The audit's metadata shape is `{empty?, asset_count, per_asset: [{asset_id, kind, position, score, rule_findings, refined_alt_text?, refined_alt_text_reason?, flags: {...}}], aggregate: {pass_count, partial_count, fail_count, refined_count}}`. Each per-asset entry will be filled in step 4.
3. **Determine the article's keyword set.** From the brief, capture `primary_kw` and the `secondary_kws[]`. Normalise to lower-case and strip punctuation for the keyword-inclusion check. When the brief did not seed keywords (rare; the brief skill normally always does), surface in `runs.metadata_json.alt_text_audit.keyword_set_empty=true` and skip the keyword-inclusion sub-rule across every asset — the rest of the rubric still runs.
4. **Walk every asset.** For each row in `asset.list`, run the rubric below in order. Each sub-rule is a `pass` / `partial` / `fail` outcome, and the asset's overall score is the count of `pass` outcomes out of seven sub-rules (a 7-point scale). Capture every sub-rule's evidence (1–2 sentences) so the audit row is self-explanatory.

   **Sub-rule A — Present and meaningful.** The `alt_text` field is non-empty (`fail` if null or empty string), is not a placeholder (`fail` on values like "image", "alt", "alt text", "tbd", "TODO", "—"), and reads as a sentence-fragment that an audio screen reader could speak (`partial` on bare keyword spam without a verb or noun phrase).

   **Sub-rule B — Length 10–125 chars.** Strict ceiling at 125 chars (longer alt is verbose and screen-reader-hostile); strict floor at 10 chars (anything shorter cannot describe a real image). Outcomes: `pass` when in range, `partial` for 1–9 or 126–160, `fail` for 0 or > 160.

   **Sub-rule C — Subject + context.** The text names a concrete subject (a noun phrase) and at least one piece of relevant context (an action verb, a setting word, a comparison). "A laptop" is `partial`; "Two laptops on a desk showing dashboards" is `pass`; "image" is `fail`. The auditor judges by parsing for noun + (verb OR setting) tokens.

   **Sub-rule D — Keyword inclusion (natural).** The text includes the article's `primary_kw` OR at least one `secondary_kws[]` value as a natural phrase, not stuffed. `pass` when the keyword appears once and reads as part of the sentence; `partial` when the keyword appears but feels grafted on (e.g., "<primary_kw>" tagged at the end after a comma); `fail` when no keyword appears in any form. Stuffing (the same keyword more than once, or two unrelated keywords crammed in) downgrades to `partial` even when the inclusion is otherwise correct. Skipped entirely when the keyword set is empty (step 3).

   **Sub-rule E — File-size tier.** Inferred from the asset's `width × height` because the daemon does not store byte-size of remote URLs and refusing to score without a content-length probe would over-strict the audit. The tier rules are:
   - **Hero** (`kind='hero'`) — the asset's pixel area should be ≥ 1.4 megapixels (e.g., `1792x1024 ≈ 1.83 MP`); below that is `partial` with a recommendation to upscale; above 4 MP is `partial` with a recommendation to constrain. The publish step recompresses for the target's CDN; the audit's role is to flag dimension drift, not byte-size.
   - **Inline** (`kind='inline'`) — pixel area should sit between 0.6 and 2.0 MP. Outside that range is `partial`.
   - **Thumbnail** (`kind='thumbnail'`) — pixel area should be ≤ 0.5 MP. Larger thumbnails inflate listing pages and are `partial`.
   - **OG / Twitter** (`kind='og'` or `kind='twitter'`) — must be exactly the canonical social-card dimensions: og typically `1200x630` (square or 1.91:1) and twitter typically `1200x675`. Anything else is `partial`. (The publish step crops as a fallback but the audit flags the mismatch.)
   - **Other kinds** — `infographic`, `screenshot`, `gallery` — the audit tracks the dimensions but does not score; they are application-specific and the operator's call.

   **Sub-rule F — Format.** Inferred from the asset's URL extension. WebP and AVIF are `pass`; modern formats with native lossy-or-lossless compression and broad browser support. PNG is `partial` for hero / inline (file size penalty) but `pass` for screenshots and infographics where lossless matters. JPEG is `partial` for hero / inline (no transparency, dated compression) but acceptable for og / twitter (social cards strip transparency anyway). GIF is `fail` outside the explicit `gallery` kind. SVG is `pass` only for `infographic` / `gallery` and `fail` for hero / inline (rasters are expected there).

   **Sub-rule G — Above-the-fold loading.** For `hero` only, the asset's metadata must indicate the publish step will render `fetchpriority='high'` and will NOT add `loading='lazy'`. Because the auditor cannot read the publish target's render code, the check operates on a `loading_hint` flag the publish skills consult: when `runs.metadata_json.alt_text_audit.per_asset[<hero>].flags.lcp_ready=true`, the publish step renders eagerly with `fetchpriority='high'`; when absent or false, the publish step falls back to lazy loading (which is wrong for the hero). The auditor sets `lcp_ready=true` for the hero unconditionally — there is no scenario where lazy-loading the hero is correct. For non-hero assets the rule is inverted: `lcp_ready=false` (lazy-load is correct for below-the-fold imagery).

5. **Aggregate per-asset score.** Sum the seven `pass` outcomes (sub-rule G is binary so it counts as 0 or 1 toward the score). The asset's overall verdict is:
   - `pass` for score ≥ 6 (any single soft fail is acceptable on a per-asset basis).
   - `partial` for score 4–5 (re-write recommended; surface but do not block).
   - `fail` for score ≤ 3 (re-write is required; the auditor itself drafts the replacement).
6. **Refine alt text where required.** When an asset's verdict is `partial` or `fail`, draft a refined alt text that addresses the specific sub-rules that did not pass. The refinement is grounded in:
   - The asset's stored `prompt` (which described the image at generation time and is the most accurate source of subject + composition truth available to the auditor).
   - The article's section context: for inline images, the H2 / H3 immediately before the image's anchor point; for hero, the article's H1 + first-paragraph claim.
   - The keyword set: include the primary keyword unless the section is so off-topic that doing so reads as forced; in that case use a secondary keyword.
   - The character budget: aim for 60–110 chars; strict ceiling at 125.
   When the refined text differs from the existing `alt_text` by ≥ 1 character, call `asset.update(asset_id, alt_text=<refined>)` and capture both the original and the refined value in `runs.metadata_json.alt_text_audit.per_asset[<asset>].refined_alt_text`. When the refinement would be no-op, skip the update — the repository's optimistic-concurrency model treats unchanged updates as wasted writes.
7. **Persist per-asset flags.** For each asset, write the `flags` block on the metadata: `{lcp_ready, format_ok, dimension_tier, keyword_present, length_ok}` — booleans the publish skills consult before rendering. The auditor's job is to surface these flags; the publish step honours them. For example, when `format_ok=false` (e.g., a heavyweight PNG hero), the publish skill emits a `<picture>` block with a WebP source set even though the underlying asset URL is the original PNG, so the rendered HTML serves a modern format on capable browsers.
8. **Persist the aggregate.** Write `runs.metadata_json.alt_text_audit.aggregate = {pass_count, partial_count, fail_count, refined_count, asset_count}`. The aggregate row is what the EEAT gate's rerun-after-images audit reads to decide whether the article's image package is ready for publishing or whether a FIX-loop should regenerate weak assets.
9. **Persist top issues.** Write `runs.metadata_json.alt_text_audit.top_issues[]` with the lowest-scoring three to five assets, sorted by score ASC then by `kind` priority (hero first, then inline by position, then og / twitter / thumbnail). Each issue carries `{asset_id, kind, score, key_failures: [<sub-rule letters>], recommendation}`. The EEAT gate (#11) and the operator's UI both read this list.
10. **Finish.** Call `run.finish` with `{article_id, asset_count, pass_count, partial_count, fail_count, refined_count, top_issues_count, hero_lcp_ready}`. Heartbeats fire after every five assets so a long audit on an asset-heavy pillar article stays visible.

## Outputs

- `article_assets` — per-asset `alt_text` may be rewritten via `asset.update`; the rubric flags persist on the run, not on the asset row (the asset table stays minimal).
- `runs.metadata_json.alt_text_audit` — the per-asset rubric report + aggregate counts + top-issues list + per-asset flags the publish step consults.

## Failure handling

- **No assets to audit.** Surface `empty=true` and finish cleanly. The procedure runner advances to the next skill; the EEAT gate's rerun-after-images audit reads `empty=true` and treats the image package as "intentionally absent" rather than as a missed step.
- **Asset URL is unreachable / 404.** The auditor does not fetch URLs (it scores from metadata only) so URL liveness is not the auditor's surface. The publish step's preview catches dead URLs; the auditor flags `format_ok=false` only when the extension is unknown.
- **Brief is missing keywords.** The keyword-inclusion sub-rule is skipped; surface in metadata. Other sub-rules continue to apply.
- **Refined alt text would exceed the 125-char ceiling.** Trim to 120 chars at the nearest sentence boundary, log the trim in `runs.metadata_json.alt_text_audit.per_asset[<asset>].trim_applied=true`, and proceed with the trimmed value.
- **`asset.update` returns a NotFound (asset deleted between `asset.list` and the update).** Skip that asset, log `runs.metadata_json.alt_text_audit.per_asset[<asset>].update_skipped='asset-deleted'`, continue. The audit row reflects the as-listed snapshot, not a post-deletion view.
- **Hero is missing entirely.** Surface in `runs.metadata_json.alt_text_audit.hero_missing=true` and the top-issues list. The publish step's preview emits a warning; the operator decides whether to regenerate or accept the missing hero.
- **Multiple hero rows exist.** Means the image-generator wrote a duplicate hero (a bug; the generator's idempotency check should prevent this). The auditor scores all hero rows but writes `runs.metadata_json.alt_text_audit.hero_duplicates=true` so the operator can clean up via the UI before publishing.

## Variants

- **`fast`** — runs sub-rules A, B, and G only (presence + length + LCP). Useful in `bulk-content-launch` where the per-asset format / dimension audit is too slow at hundreds-of-articles scale and the EEAT gate's downstream reads do not consume the richer flags.
- **`standard`** — the default flow above with all seven sub-rules.
- **`strict`** — raises the per-asset pass threshold from score ≥ 6 to score ≥ 7 (every sub-rule must pass) and refines alt text on any sub-rule miss, not just on the partial / fail verdicts. Cost is meaningfully more `asset.update` writes; quality lift is meaningful for pillar articles.
- **`audit-only`** — performs every sub-rule and persists the report but does NOT call `asset.update` regardless of refinement. Used for periodic content-quality re-audits (procedure 6's GSC-driven cadence) and standalone operator-invoked audits where the operator wants the report before deciding whether to apply refinements.
