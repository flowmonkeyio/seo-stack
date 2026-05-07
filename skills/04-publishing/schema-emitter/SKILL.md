---
name: schema-emitter
description: Compose JSON-LD per article from edited_md + brief + voice + author + assets + canonical URL, validate against the type's required-properties contract, persist via schema.set with the primary-row invariant, and freeze the version_published when called inside a publish flow.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: codex-seo @ 97c59bcdac3c9538bf0e3ae456c1e73aa387f85a (clean-room; no upstream files read during authoring)
license: clean-room (PLAN.md L858 + docs/upstream-stripping-map.md adapt notes)
allowed_tools:
  - meta.enums
  - project.get
  - voice.get
  - article.get
  - asset.list
  - author.get
  - schema.set
  - schema.get
  - schema.validate
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
  - table: schema_emits
    write: one row per emitted type via schema.set; the canonical Article-or-BlogPosting row carries is_primary=true and the others is_primary=false (the repository enforces exactly-one-primary).
  - table: runs
    write: per-type composition log + validation findings + which types were skipped (deprecated / restricted / inapplicable) in runs.metadata_json.schema_emitter.
---

## When to use

Procedure 4 dispatches this skill after the alt-text-auditor (#14) and before the interlinker (#15). At this point the article is `eeat_passed`, the image package is in place (the auditor's flags are written), and the canonical URL is known to the publish target (when one has been assigned via `articles.canonical_target_id`). The schema-emitter composes a JSON-LD blob per applicable schema type, validates each blob, and writes one `schema_emits` row per type. The publish skills (#17 / #18 / #19) consume the rows and emit the JSON-LD inline in the rendered HTML / frontmatter.

The skill also runs in two ad-hoc modes the procedure runner does not orchestrate. The first is operator-invoked re-emission when the article's body or image package changed mid-flight (the operator clicks "regenerate schema" on the Article Detail UI); the skill walks the existing rows, drops any that have become stale, and writes fresh ones. The second is procedure 7's monthly humanize pass, which re-emits schema after the body refresh so the `dateModified` reflects the new version.

The skill never emits HowTo (deprecated by Google as of 2023-09 — every emit is suppressed with a recorded reason). The skill never emits FAQPage on commercial / monetised sites (restricted as of 2023-08 — the project's voice profile or compliance rule indicates the site classification). BreadcrumbList is generated per-article inline in the publish-step frontmatter, not as a `schema_emits` row, because the breadcrumb shape depends on the publish target's URL scheme rather than the article body alone.

## Inputs

- `article.get(article_id)` — returns `edited_md` (the body the schema's `articleBody` references implicitly through the description), `brief_json` (the source of `schema_types[]`, `primary_kw`, `secondary_kws[]`, `intent`, `audience`), the `slug`, the `published_at` and the `last_refreshed_at` (used to render `datePublished` and `dateModified`), the `author_id`, and the `canonical_target_id` (used to look up the canonical URL once a publish target has been assigned). Confirm `status='eeat_passed'` (or `published` when running in refresh / re-emission mode).
- `voice.get(project_id)` — the active voice's `voice_md` plus the project-level brand metadata (`organization_name`, `organization_url`, `logo_url`, `same_as[]`) when the voice carries them. The Organization schema's required properties come from this row in conjunction with the project row; when neither carries them, the schema-emitter skips Organization rather than emitting a partial blob.
- `asset.list(article_id)` — every image attached to the article. The hero (`kind='hero'`) becomes the article's `image` field for the primary Article / BlogPosting row; the `og` and `twitter` rows are used only by the publish skill's frontmatter, not by the schema-emitter. Inline images contribute to a secondary `ImageObject` array when the brief's `schema_types[]` requested it (rare).
- `author.get(article.author_id)` — the article's author row. The author carries `name`, `url`, `description` (the byline), `same_as[]` (links to social profiles, ORCID, etc.), and `credentials[]` (the credentialed-author T04 input from the EEAT rubric). The author becomes the schema's `author` field for the primary Article / BlogPosting row; the same author is referenced as `creator` for any embedded `ImageObject`.
- `schema.get(schema_id)` (within step 6 only) — used to read the existing schema rows for the article when running in re-emission mode, so the skill can decide which existing rows to drop and which to update in place.
- `meta.enums` — surfaces the canonical `schema_emits.type` enumeration the repository accepts; the skill emits canonical type strings from this list and never invents new types.

## Steps

1. **Read context.** Resolve the article. Confirm status is `eeat_passed` (procedure-4 mode) or `published` (re-emission / refresh mode). Pull the brief, voice, hero asset, author, and canonical target id. Capture the live `step_etag` so the publish step can detect a mid-flight body change after schema emission.
2. **Determine the schema-type roster.** From `articles.brief_json.schema_types[]` (which the brief skill seeded based on the article's intent and content type), build the candidate type list. The brief never seeds HowTo (the brief skill is aware of the deprecation cliff). When the brief seeded FAQPage and the project's voice profile or a compliance rule indicates a commercial / monetised site, demote FAQPage to a `runs.metadata_json.schema_emitter.skipped[]` entry with reason `'restricted-commercial'` and continue. Apply this precedence to fill in any types the brief did not seed:
   - **Article** — the universal default for editorial / informational content.
   - **BlogPosting** — when the project's content type is `blog` (declared on the project row's `content_type` field) and the article's intent is `informational` or `transactional` with a personal-voice byline.
   - **Product** — when the article reviews a single product and the brief seeded the product metadata (sku, brand, offers).
   - **Review** — when the article is structured as a review and the brief carries `review.itemReviewed`.
   - **Organization** — when the project's voice / project row carries the load-bearing org metadata (`organization_name`, `url`, `logo_url`).
   - **FAQPage** — when the brief seeded a `faq[]` block AND the project is not commercial.
   - **NewsArticle** — when the project's content type is `news` and the article carries a `dateline`.
   The principal type is the type whose JSON-LD will carry `is_primary=true` in the `schema_emits` table; the principal is normally Article (or BlogPosting for blog projects). All other emitted types are written with `is_primary=false`. The repository's `set` method enforces exactly-one-primary by transitioning others' `is_primary` to false on a primary write — the skill writes the primary first, then the secondaries, to avoid an intermediate two-primary state.
3. **Resolve the canonical URL.** When `article.canonical_target_id` is populated, the canonical URL is rendered from the target's `config_json.public_url_pattern` (e.g., `https://example.com/blog/{slug}`) interpolated with the article's `slug`. When `canonical_target_id` is null (the article has not been published anywhere yet — the schema-emitter is running before the publish step within procedure 4), the canonical URL is computed against the project's primary publish target (the `is_primary=true` row in `publish_targets`); the publish step's preview later replaces this provisional value if the operator chose a non-primary target as canonical. Persist the resolved URL in the per-type metadata so any audit can trace which target produced it.
4. **Compose Article / BlogPosting (the principal blob).** For the principal type, build the JSON-LD object with these fields:
   - `@context: 'https://schema.org'`
   - `@type: 'Article'` (or 'BlogPosting' / 'NewsArticle' depending on roster)
   - `headline`: the article's `title` from the brief, trimmed to ≤ 110 characters (Google's headline ceiling).
   - `description`: the brief's meta-description when present; otherwise the first paragraph of `edited_md` after the H1, trimmed to 160 characters.
   - `image`: the hero asset's URL when present, rendered as a single string for backward compatibility; the publish step renders an array variant in the `<picture>` block but the schema's `image` is a single string.
   - `datePublished`: ISO-8601 from the article's `published_at` (procedure-4 mode infers from the run's start; re-emission mode uses the existing `published_at`).
   - `dateModified`: ISO-8601 from the article's `last_refreshed_at` when it differs from `published_at`; otherwise equal to `datePublished`.
   - `author`: a nested Person object — `{@type: 'Person', name, url, description, sameAs}` from the author row.
   - `publisher`: a nested Organization object — `{@type: 'Organization', name, logo: {@type: 'ImageObject', url}, sameAs}` from the project / voice metadata. When the org metadata is incomplete, the schema-emitter abstains from emitting the Article row — `publisher` is required and a partial blob would fail validation in step 8.
   - `mainEntityOfPage`: a `WebPage` object with `@id` set to the canonical URL.
   - `inLanguage`: the project's `locale` (e.g., `en-GB`, `de-DE`).
   - `keywords`: the brief's `primary_kw` plus `secondary_kws[]`, joined by commas.
   - `articleBody`: omitted from the JSON-LD blob (publish targets render the body inline; duplicating it in JSON-LD bloats the page weight without measurable benefit). The decision is conscious; do not silently add `articleBody` even if a future spec change would permit it.
5. **Compose secondary blobs.** For each secondary type in the roster, compose the type's blob with the same source-of-truth pattern: brief and voice for content metadata, asset list for image references, author / publisher per the principal blob's nested objects. Per-type field rules:
   - **Product** — required `name`, `image`, `description`, `sku`, `brand`, `offers`. Brand is a nested Organization; offers is `{@type: 'Offer', price, priceCurrency, availability, url}` interpolated from the brief's `product.offer` block. When the brief did not seed offers, abstain.
   - **Review** — required `itemReviewed`, `reviewRating`, `author`. The reviewRating is `{@type: 'Rating', ratingValue, bestRating, worstRating}` interpolated from the brief's `review` block.
   - **Organization** — required `name`, `url`, `logo`. Optional `sameAs`, `contactPoint`. Emitted independently of any single article (the row is per-article but the content is project-wide); writing one per article keeps the schema_emits row uniform but a future migration could dedupe at the project level.
   - **FAQPage** — required `mainEntity` (an array of `Question` nodes, each with a `name` and a nested `acceptedAnswer` carrying `Text`). Source from the brief's `faq[]` block. Skipped when the project is commercial (step 2's restricted-commercial demotion).
   - **NewsArticle** — same shape as Article plus `dateline` (location string from the brief) and optional `printSection` / `printColumn` for projects whose `voice` requires print-edition fields.
6. **Re-emission housekeeping.** When the skill is running in re-emission mode (the article already has `schema_emits` rows from a prior run), walk the existing rows and decide for each:
   - **Update in place** — the type still applies and the new blob differs from the existing `schema_json`. Call `schema.set` with the same `article_id` + `type`; the repository upserts.
   - **Drop** — the type no longer applies (e.g., FAQPage was emitted at first publish but the article was demoted to commercial since). The skill does not delete schema_emits rows directly (no `schema.remove` MCP exists); instead it surfaces the stale row in `runs.metadata_json.schema_emitter.stale[]` and the operator's UI offers a manual cleanup. The publish step's preview also flags stale rows so they do not silently render.
   - **No change** — the new blob equals the existing `schema_json`. Skip the write; surface in the audit row as `unchanged`.
7. **Persist each blob.** For each type in roster order (principal first, then secondaries):
   - Compose the JSON-LD object per steps 4 / 5.
   - Call `schema.set(article_id, type=<canonical type>, schema_json=<object>, is_primary=<true for principal else false>, position=<order index>, version_published=<integer when in publish flow>)`.
   - The `version_published` field is required when the schema-emitter is running as part of a publish flow (procedure 4 first publish or procedure 7 republish). In procedure 4 the value is `articles.version` after `mark_published` would assign it (the schema-emitter runs before mark_published, so the value is `articles.version + 0` for first publish or `articles.version + 1` for republish — the procedure runner passes the explicit number). In re-emission mode without a publish flow, the value is null and the row carries the previously-frozen version.
   - Capture the response envelope so the per-type log can record the schema row id.
8. **Validate each blob.** For each row written, call `schema.validate(schema_id)`. The repository's M3 implementation marks the row as validated; a future M5 wave will add the real JSON-LD shape check, but the skill's own pre-write composition already enforces required-property invariants for every type. The validate call is the canonical "row is publish-ready" stamp the publish step looks for. When `validate` rejects, the skill marks the type as failed in the audit row and continues with the next type — a single bad blob does not block the rest of the package.
9. **Persist the audit row.** Write `runs.metadata_json.schema_emitter = {types_emitted: [...], types_skipped: [...], types_failed: [...], stale: [...], canonical_url, principal_type, version_published?}`. Each `types_emitted` entry is `{type, schema_id, is_primary, validated, position}` so the publish step and the operator's UI can map every blob back to its row.
10. **Finish.** Call `run.finish` with `{article_id, principal_type, types_emitted_count, types_skipped_count, types_failed_count, validated_count, version_published?}`. Heartbeats fire after every type composes so a roster of six types stays visible.

## Outputs

- `schema_emits` — one row per emitted type, with `is_primary=true` on the principal row and the `schema_json` blob carrying the validated JSON-LD object. The row carries `version_published` when the run is part of a publish flow.
- `runs.metadata_json.schema_emitter` — the per-type composition log + skipped / failed / stale lists + the resolved canonical URL.

## Failure handling

- **No schema types in the brief and no defaultable type derivable.** The brief skill should always seed at least Article. When it did not, abort with `runs.metadata_json.schema_emitter.no_roster=true` and a clear message to the operator. The publish step that runs after the schema-emitter would succeed without any JSON-LD but would lose all rich-result eligibility; the abort forces a brief-fix.
- **Hero asset missing.** Article / BlogPosting / NewsArticle / Product / Review all require `image`. Surface `runs.metadata_json.schema_emitter.image_missing=true` and abstain from emitting any image-required type. The publish step's preview surfaces the absence; the operator either regenerates the hero (back through skill #13) or accepts a thinner schema package.
- **Author row missing or incomplete.** Article / BlogPosting / NewsArticle / Product require `author` with at least `name` and `url`. When the row is incomplete, abstain from the type and surface `runs.metadata_json.schema_emitter.author_incomplete=true`. The author edit happens in the Author UI; the operator fixes and re-runs.
- **Organization metadata missing on the project.** Article requires `publisher`; when the project / voice does not carry the org metadata, abstain from emitting Article (and any other type that requires `publisher`). Surface `runs.metadata_json.schema_emitter.org_metadata_missing=true`. The bootstrap procedure should have seeded these; if it did not, the operator runs `bootstrap-fix`.
- **Canonical URL resolution fails.** Means neither `articles.canonical_target_id` nor a primary `publish_targets` row exists for the project. Without a canonical URL the `mainEntityOfPage` field cannot resolve; abstain from every type and surface `runs.metadata_json.schema_emitter.canonical_unresolved=true`. The procedure runner's publish step is the immediate next skill — the operator either creates a publish target or aborts the procedure.
- **`schema.set` rejects a duplicate-on-key conflict.** Means the article already has a row of this type with a conflicting `version_published`. Refresh via `schema.list`, decide whether to update or skip per step 6's housekeeping rules, retry once. Two consecutive rejections aborts that type but not the run.
- **`schema.validate` returns a known-bad shape.** The composition pass should not produce invalid blobs, but when it does (e.g., a future schema.org spec tightens a required property), capture the validator's reason in `runs.metadata_json.schema_emitter.types_failed[].reason` and continue. The publish step's preview surfaces the failure; the operator regenerates or accepts a thinner package.
- **HowTo or FAQPage-on-commercial silently slipped past the brief.** The skill's step 2 demotes them to skipped with the reason; never emit them. When the brief authors regress and re-introduce them, the demotion logs in `runs.metadata_json.schema_emitter.skipped[]` so the operator can patch the brief skill or the brief's `schema_types[]` entry.

## Variants

- **`fast`** — emits the principal type only (Article or BlogPosting). Skips secondary types regardless of the brief's roster. Useful in `bulk-content-launch` where rich-result eligibility is a phase-2 concern; the principal blob alone covers the canonical-URL + author + datePublished signals search engines need at first index.
- **`standard`** — the default flow above with the full roster from the brief.
- **`pillar`** — emits the principal plus every secondary the brief seeded plus a `BreadcrumbList` blob inline in the principal (rather than letting the publish step compose it from the URL pattern). The pillar mode also enforces that every nested `ImageObject` carries a `caption` derived from the asset's audited alt text — a richer rich-result signal at the cost of more composition work.
- **`refresh`** — invoked by procedure 7 against a humanized-and-re-edited article. Re-emits every existing row with the new `dateModified` and the new `version_published`. Drops any type that no longer applies (e.g., the project switched to commercial since the prior emit) and surfaces it in `stale`. Treats validation failures as block-this-type, not block-the-run, so a single regressed blob does not abort the refresh.
- **`audit-only`** — composes every blob, runs the validator, persists the audit row, but does NOT call `schema.set`. Used for periodic schema audits where the operator wants the report before deciding whether to overwrite live rows.
