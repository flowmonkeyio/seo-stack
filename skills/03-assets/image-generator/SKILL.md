---
name: image-generator
description: Compose voice-grounded prompts from the article brief, call OpenAI Images via the daemon-side wrapper, and persist each result as an article_assets row with hero / inline / og positioning.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: original
license: project-internal
allowed_tools:
  - meta.enums
  - project.get
  - voice.get
  - compliance.list
  - article.get
  - asset.create
  - asset.list
  - asset.update
  - cost.queryProject
  - integration.test
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
  - table: article_assets
    write: one asset.create per generated image with kind ∈ {hero, inline, og, twitter}, prompt, url, alt_text, width, height, position.
  - table: runs
    write: per-image cost rolled into runs.metadata_json.cost.by_integration.openai-images, prompt log + image_count + skip reasons in runs.metadata_json.image_generator.
---

## Shared operating contract

Before executing, read `../../references/skill-operating-contract.md` and
`../../references/seo-quality-baseline.md`. Apply the shared status, validation,
evidence, handoff, people-first, anti-spam, and tool-discipline rules before the
skill-specific steps below.

## When to use

Procedure 4 calls this skill after the EEAT gate (#11) returns SHIP and before alt-text-auditor (#14). The article body is final and frozen at this point — image prompts can ground in the actual headings and the actual paragraph the inline image sits next to. Running earlier is wasteful: a FIX loop that rewrites a section invalidates whatever inline image was generated against the previous text.

The skill also runs in two ad-hoc modes the procedure runner does not orchestrate. The first is a per-article re-generation when the operator deletes one or more `article_assets` rows via the UI and wants the gaps refilled. The second is procedure 7's monthly humanize pass, which can ask for a fresh hero on a refreshed article when the brief's `image_directives.regenerate_on_refresh` is true. In both modes the contract is the same: read what assets already exist via `asset.list`, generate only the missing slots, never duplicate hero or og positions.

## Inputs

- `article.get(article_id)` — returns `edited_md` (the final body — every inline image's prompt grounds in its surrounding paragraph), `brief_json` (the source of truth for `image_directives`), `outline_md` (the heading map — used to pick inline-image anchor points when the brief did not name them), the live `step_etag`, and the `slug` (used in the asset URL pattern). Confirm `status='eeat_passed'` so the body is frozen.
- `voice.get(project_id)` — the active voice's `voice_md`. The image-style cue is parsed out of the markdown via prompt instruction; there is no dedicated `image_style` column on the voice row. The voice's free-form text typically declares one of: `photorealistic`, `editorial photography`, `illustrated`, `flat-illustration`, `infographic`, `mixed-media`. When the voice does not name a style, the skill abstains and surfaces in `runs.metadata_json.image_generator.style_source='brief'` (only the brief's `image_directives.style` is then used) or `'none'` (the skill aborts; see failure handling).
- `compliance.list(project_id, kind='custom')` — the project's custom validators. The image-generator looks for a registered rule with `validator='validators.real_persons_in_images'`; when present and active, real-person prompts are forbidden by default. The brief's `image_directives.allow_real_persons` boolean is the per-article opt-in switch; when the rule is registered AND the brief does not opt in, the skill rewrites any prompt that names a real person into a generic substitute ("a software engineer at a desk" instead of "<named CEO> at a desk") and logs the rewrite.
- `cost.queryProject(project_id, kind='openai-images')` — pre-emptive budget query. The skill estimates the run's cost (per-image rate × `count`) and refuses to start when the estimate plus the project's month-to-date `current_month_spend` would exceed `monthly_budget_usd`. This is the daemon's pre-call gate (PLAN.md L1041); the wrapper enforces it again at call time, but checking up-front avoids burning a partial run.
- `asset.list(article_id)` — every asset already attached to this article. The skill uses this to dedupe (a hero already exists; do not generate another) and to pick the next free `position` integer for inline images (existing inlines occupy 1..N; the next one is N+1).
- `meta.enums` — surfaces the `ArticleAssetKind` enum (hero / inline / thumbnail / og / twitter / infographic / screenshot / gallery) so the skill emits canonical kind strings.
- `integration.test` — pre-flight credential probe. The wrapper's `test_credentials` shape returns `{ok: true, vendor: 'openai-images', models_count: N}` when the API key is live; the skill calls this once at start-up rather than discovering a 401 mid-run.

## Steps

1. **Read context.** Resolve the article. Confirm `status='eeat_passed'` (the gate advanced it). Pull `edited_md`, `brief_json`, `outline_md`, the active voice, the compliance list filtered to custom validators, the live `step_etag`, and the slug.
2. **Parse `image_directives`.** From `brief_json.image_directives` (per PLAN.md L425 — an optional sub-key on `brief_json`), extract:
   - `count` — total images to generate (default 1 hero only when the directive is absent; default 6 when the directive exists with no explicit count).
   - `style` — explicit override of the voice's style hint. When set, takes precedence over `voice_md`'s style cue.
   - `alt_text_hints[]` — caller-supplied phrasing hints, one per image. The hints are priming, not literal alt text; the auditor (#14) reviews the final alt text.
   - `allow_real_persons` — boolean opt-in for real-person prompts when the project's compliance rule otherwise forbids them.
   - `regenerate_on_refresh` — boolean (procedure 7 input only).
   - `inline_anchors[]` — optional list of H2 / H3 heading texts that mark inline-image anchor points; when omitted the skill picks anchors automatically from the outline.
3. **Resolve the style cue.** Apply this precedence: `image_directives.style` > voice_md style cue > none. When the result is `none`, abort with a clear operator message — image generation without a style cue produces inconsistent brand visuals and is forbidden. Persist the chosen style in `runs.metadata_json.image_generator.style_resolved` so the auditor and any human reviewer can see what guided the prompts.
4. **Plan the image slots.** For each requested image, decide its `kind` and `position`:
   - **Hero** (kind=`hero`, position=`0`) — exactly one per article. Generated first because the auditor's LCP / `fetchpriority='high'` rules apply to it. When `asset.list` already returns a hero row, skip — the operator is asking for inline-only refill.
   - **OG / social** (kind=`og`, position=`null`) — at most one per article. Generated when the directive's count requests social-share imagery; the publish skills (#17/18/19) consume it as the `og:image` frontmatter. Optional second variant kind=`twitter` for projects whose voice prefers a Twitter-card-shaped variant.
   - **Inline** (kind=`inline`, position=`1..N`) — one per inline anchor. Anchor selection: when `inline_anchors[]` was supplied, use those H2/H3 texts; otherwise pick anchors automatically by walking `outline_md` and picking every other H2 boundary up to the requested count.
   - **Thumbnail** (kind=`thumbnail`, position=`null`) — generated only when the brief explicitly requests it (rare; most publish targets derive thumbnails server-side from the hero).
   For each planned slot, capture the surrounding context: for hero, the H1 + first body paragraph; for og, the H1 + meta description; for inline, the section under whose H2/H3 the image will sit.
5. **Compose the prompt.** For each slot, the prompt is a structured paragraph the image API consumes:
   - **Subject sentence** — what the image shows. Grounded in the slot's surrounding context. For hero: the article's load-bearing claim rephrased as a visual concept. For inline: the section's own claim rephrased visually. For og: a tighter, social-card-friendly variant of the hero subject.
   - **Style sentence** — the resolved style cue, expanded into descriptors. `photorealistic` → "natural lighting, shallow depth of field, photographic detail"; `editorial photography` → "documentary style, neutral colour palette, candid composition"; `illustrated` → "flat vector illustration, brand colour palette, generous negative space"; `infographic` → "minimal labels, clear visual hierarchy, isometric perspective"; `mixed-media` → the voice's free-form description, used verbatim when present.
   - **Composition sentence** — aspect-ratio + framing + crop hints suited to the size: hero is `1792x1024` (landscape) by default; og is `1024x1024` (square); inline is `1024x1024` or `1792x1024` depending on the section's flow; thumbnail is `1024x1024`.
   - **Negative-prompt sentence** — what to avoid: "no embedded text, no watermarks, no logos, no real people unless explicitly directed." When the compliance rule forbids real persons and the brief did not opt in, this sentence becomes load-bearing.
   - **Brand sentence** (optional) — voice-specified palette / mood, when the voice supplies one.
6. **Real-person filter.** Before submitting any prompt, scan it for proper-noun patterns that name a person. When the project's compliance rule registers `validators.real_persons_in_images` AND `image_directives.allow_real_persons` is not true, rewrite the prompt to substitute a generic descriptor for the named person and log the rewrite under `runs.metadata_json.image_generator.real_person_rewrites[]`. When the brief did opt in, leave the prompt intact but log the opt-in for audit.
7. **Pre-call cost gate.** Estimate the run's USD cost as the sum of per-image rates per the wrapper's pricing table (`1024x1024 standard` ≈ $0.04, `1792x1024 hd` ≈ $0.12, etc.). Call `cost.queryProject(project_id, kind='openai-images')` to read `current_month_spend` and `monthly_budget_usd`. When `current_month_spend + estimate > monthly_budget_usd`, abort with a `BudgetExceededError` and surface the shortfall in `runs.metadata_json.image_generator.budget_failure`. The procedure runner catches the error and aborts the procedure cleanly rather than burning a partial generation.
8. **Generate the images.** For each slot in plan order (hero first, then og, then inlines):
   - Heartbeat with `{slot, kind, position, model, size, quality}` so the UI shows progress.
   - Call the daemon's `OpenAIImagesIntegration.generate(prompt, size, quality, n=1, model=...)`. The wrapper enforces the per-call rate limit (default 10 qps), records cost into `run_step_calls`, and returns the OpenAI response with the generated image URL or base64 data and the operative size/quality.
   - On 4xx (auth / quota / content-policy reject) — capture the error, mark the slot as failed in the metadata, continue. The skill is best-effort per slot; a single rejection should not fail the run.
   - On 5xx — retry once with the same prompt. Two consecutive 5xx aborts that slot.
   - On a content-policy reject specifically (the API rewrites or refuses the prompt), log `runs.metadata_json.image_generator.policy_rejects[]` with the slot id and the API's reason. The auditor's report flags missing inline images so the operator knows which sections need a manual replacement.
9. **Compose alt text.** For each successfully generated image, draft a candidate alt text:
   - Length 10–125 characters (the auditor enforces this floor + ceiling; the generator aims for the middle).
   - Describes the subject concretely (e.g., "Two laptop screens showing line-graph dashboards with Q3 revenue").
   - Naturally includes the article's `primary_kw` or one `secondary_kws` entry only when the subject permits — accessibility and accurate description come first.
   - Uses the brief's `image_directives.alt_text_hints[<slot>]` as priming when supplied; the hint biases vocabulary, not phrasing.
   - Avoids the word "image", "photo", "picture", "graphic" — screen readers already announce the role.
   The alt text is a candidate; the auditor (#14) is the final gate and may rewrite via `asset.update`.
10. **Persist the asset.** For each generated image call `asset.create(article_id, kind, prompt, url, alt_text, width, height, position)`:
    - `prompt` is the full composed prompt from step 5 (after any real-person rewrite). The repository keeps it for audit so a future re-generation can inspect what produced the image.
    - `url` is the URL the wrapper returned. When the OpenAI API returned base64 data instead of a URL, the daemon's helper writes the bytes under `~/.local/share/content-stack/assets/<project_slug>/<article_id>/<asset_id>.<ext>` and the URL points at the daemon's own `/api/v1/assets/<asset_id>` route — this keeps blobs out of SQLite.
    - `width` / `height` come from the operative size (e.g., `1792x1024` → `width=1792, height=1024`).
    - `position` is `0` for hero, `null` for og / twitter / thumbnail (those are not ordered with inlines), and `1..N` for inline (next free integer per `asset.list`).
    - The repository validates `kind` against the canonical enum and rejects unknown values; the skill always emits canonical strings from `meta.enums`.
11. **Persist the audit row.** Write `runs.metadata_json.image_generator = {style_resolved, count_planned, count_generated, count_failed, slots: [...], real_person_rewrites: [...], policy_rejects: [...], budget_estimate_usd, cost_actual_usd}`. The cost actual rolls up from the wrapper's `run_step_calls` rows into `runs.metadata_json.cost.by_integration['openai-images']` so the cost view is consistent across all integrations.
12. **Finish.** Call `run.finish` with `{article_id, count_generated, count_failed, hero_present, og_present, inline_count, total_cost_usd}`. Heartbeats fire after every slot generates so a slow image API stays visible.

## Outputs

- `article_assets` — one row per generated image with `kind`, `prompt`, `url`, `alt_text`, `width`, `height`, `position`.
- `runs.metadata_json.image_generator` — the structured slot map + real-person rewrites + policy rejects + budget reconciliation.
- `runs.metadata_json.cost.by_integration['openai-images']` — the wrapper's recorded cost across the run.

## Failure handling

- **Status not `eeat_passed`.** Abort. The gate advances to `eeat_passed` on SHIP; if status is `edited`, the gate has not run; if `published`, the procedure already published — image regeneration on a live article goes through procedure 7 and creates a new version first.
- **`integration.test` returns ok=false.** Abort with a clear message naming the missing or invalid OpenAI Images credential. The procedure runner halts; the operator fixes the credential via the Settings UI and re-runs.
- **Style cue resolution returns `none`.** Abort. Image generation without a style anchor produces inconsistent brand visuals; the operator must add a style hint either to the brief's `image_directives.style` or to the voice's `voice_md`.
- **Budget gate trips.** Surface the shortfall in `runs.metadata_json.image_generator.budget_failure` with `{estimate_usd, current_month_spend_usd, monthly_budget_usd}`. Abort the run; the operator either raises the budget or skips images for this article.
- **Per-slot 4xx (content policy / quota).** Mark the slot failed, capture the API's reason, continue. Total run failure only when zero slots succeeded.
- **Per-slot 5xx.** Retry once. Two consecutive 5xx aborts that slot but not the run.
- **OpenAI rewrites the prompt server-side.** The API sometimes returns the rewritten prompt in the response payload. Log the rewrite in `runs.metadata_json.image_generator.api_prompt_rewrites[]` so the operator can see the divergence between what we sent and what produced the image. The asset still persists with the as-sent prompt for audit consistency.
- **`asset.create` rejects an unknown kind.** Means the skill emitted a non-canonical kind string. Refuse to persist; refresh `meta.enums`; retry once with the canonical value. Repository invariant violations are bugs in the skill prompt, not data states the user can recover from.
- **Real-person rewrite would empty the subject.** Means the prompt named only a person and nothing else. Skip that slot, log the empty-subject reason, continue. The operator either supplies a richer subject in the brief or accepts the missing inline image.

## Variants

- **`fast`** — hero only, no og, no inlines. Useful in `bulk-content-launch` where downstream targets compute their own thumbnails. Default size `1024x1024`, quality `standard`.
- **`standard`** — the default flow above: hero + og + the inline count from the directive. Default size `1792x1024 hd` for hero, `1024x1024 standard` for og, `1024x1024 standard` for each inline.
- **`pillar`** — hero + og + twitter + every inline anchor in the outline (typically 4–8 inlines). Defaults to `hd` quality across the board because pillar articles carry the heaviest LCP signal load. Cost is meaningfully higher; the budget gate is more likely to trip — the operator should size the per-project image budget accordingly.
- **`refresh`** — invoked by procedure 7. Reads `image_directives.regenerate_on_refresh`; when true, regenerates the hero (only) and replaces the existing hero row's `url` via `asset.update` rather than creating a new row, so the publish step's frontmatter does not need a new asset id. When false, the variant is a no-op and the procedure proceeds without image work.
