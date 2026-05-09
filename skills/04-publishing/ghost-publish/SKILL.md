---
name: ghost-publish
description: Render edited_md to HTML, upload article assets via PUT /ghost/api/admin/images/upload, POST or PUT the post via /ghost/api/admin/posts/?source=html with feature_image / tags / authors / codeinjection_head, and record the result via publish.recordPublish; advance to published on the primary target.
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
  - article.markPublished
  - asset.list
  - source.list
  - schema.get
  - target.list
  - publish.preview
  - publish.recordPublish
  - publish.setCanonical
  - integration.test
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
  target_id:
    source: args
    type: int
    required: true
    description: The publish_targets.id whose kind='ghost' the procedure runner has selected for this dispatch. Procedure 4 publishes to the primary target first, then queues secondary targets.
outputs:
  - table: article_publishes
    write: one row per (article_id, target_id, version_published) via publish.recordPublish — published_url + frontmatter_json + status='published' on success, status='failed' + error on failure.
  - table: articles
    write: article.markPublished on the primary target advances eeat_passed → published; the slug becomes immutable from this point.
  - table: runs
    write: per-step diagnostics (HTML conversion log, image upload URLs, Admin API response, post id and URL, JWT lifecycle notes) + cost (zero — REST API calls are free) in runs.metadata_json.ghost_publish.
---

## When to use

Procedure 4 dispatches this skill after the interlinker (#15) and the schema-emitter (#16). At that point the article is `eeat_passed`, the canonical URL is resolvable, and the publish target is a `kind='ghost'` row whose `config_json` carries the Ghost site's URL, the default post status, the format preference (HTML / Lexical / mobiledoc), tag and author mappings, and the per-target frontmatter / meta template. The skill renders the markdown body to HTML, uploads each asset to Ghost's image endpoint, POSTs (or PUTs) the post to the Admin API with `?source=html`, records the publish row, and — when the dispatch is for the primary target — advances `articles.status` to `published`.

Procedure 4 publishes to the primary target first; secondary `ghost` targets (e.g., a multi-publication setup, or a Ghost-side mirror of a Nuxt primary) are dispatched in turn. Each dispatch is a fresh skill invocation with the `target_id` passed through args. The skill is idempotent on `(article_id, target_id, version_published)` because publish.recordPublish upserts. The Ghost post is identified externally by a `ghost_post_id` stored in the publish row's `frontmatter_json` so re-dispatches PUT to the existing post.

The skill also runs in two non-procedure-driven modes the operator can invoke from the UI: a manual republish after a UI edit, and a content-refresh republish from procedure 7 against a humanized version. The contract is identical in both modes; only the status sequencing differs.

A note on JWTs and email send: Ghost's Admin API uses short-lived JWTs (5-minute expiration) signed with the secret half of an Admin API key. The daemon's HTTP helper handles minting and refreshing tokens; the skill never reads the secret directly. The skill defaults `email_only=true` (or `status='draft'` when the operator's UI confirmation is part of the publish flow) so an automated publish never accidentally blasts an email to the publication's subscribers — that decision belongs to the human, not the procedure runner.

## Inputs

- `target.list(project_id, kind='ghost')` — every Ghost target the project has. The skill reads the specific target by id. The target's `config_json` is the source of truth for:
  - `ghost_url` — the Ghost site's base URL (e.g., `https://example.com`); the Admin API endpoint is `<ghost_url>/ghost/api/admin/`.
  - `default_status` — one of `published` (live), `draft` (saved invisibly), `scheduled` (requires `published_at` in the future). The skill defaults to `draft` so the operator confirms via the Ghost UI before going live; the operator can override per target.
  - `format` — one of `html` (the default; the skill emits HTML and Ghost converts to its internal format), `lexical` (Ghost v5+ native; emit Lexical JSON), or `mobiledoc` (legacy v4; emit mobiledoc JSON). HTML is the recommended setting because the skill's markdown renderer is well-tested for it; Lexical / mobiledoc paths are supported but require additional composition work in step 5.
  - `tag_map[]` — a map from the brief's tag list to Ghost tag slugs; tags not in the map are auto-created when `auto_create_tags=true`, otherwise dropped with a log entry.
  - `author_map[]` — a map from the project's `author_id` to Ghost author slugs.
  - `email_only` — boolean defaulting to `true`. When the publish status is `published` AND `email_only=false`, Ghost sends the post as an email to the publication's subscribers; the skill defaults to `true` to suppress the email blast, and never sets it to `false` without an explicit operator override in the target config.
  - `integration_credential_id` — the FK into `integration_credentials WHERE kind='ghost'`. The credential row stores the Admin API key in `<key_id>:<secret>` form.
  - `public_url_pattern` — used to compute `published_url` (e.g., `https://example.com/{slug}/`); the Ghost API also returns the canonical URL in the response payload, which is authoritative.
  - `is_primary` — whether this target is the project's primary publish target.
- `article.get(article_id)` — returns `edited_md`, `brief_json`, `slug`, `title`, the live `step_etag`, `version`, `author_id`, `canonical_target_id`. Confirm `status='eeat_passed'` (procedure-4 first publish) or `status='published'` (refresh / republish).
- `voice.get(project_id)` — the active voice's metadata for any Ghost-specific render preferences (some voices declare a preference for Ghost's native cards — e.g., `<!--kg-card-begin: callout-->` — when a section's tone matches; the skill respects the preference).
- `compliance.list(project_id, position='hidden-meta')` — compliance rules whose position is `hidden-meta` render as Ghost's `codeinjection_head` (a snippet injected into the `<head>` of the rendered post). Visible rules are already inlined in `edited_md`.
- `schema.get(schema_id)` (the principal `schema_emits.is_primary=true` row's id, plus secondaries) — read each schema row's `schema_json` and emit them inside a `<script type="application/ld+json">` block in the post's `codeinjection_head`. Ghost does not have a first-class JSON-LD field; the head injection is the canonical seam.
- `asset.list(article_id)` — every asset row. The skill uploads each asset to the Admin API's `images/upload/` endpoint and rewrites the body's image references to the Ghost-hosted URLs.
- `source.list(article_id, used=true)` — feeds the references block in the body when the target's frontmatter template renders one.
- `integration.test` — pre-flight credential probe. The wrapper's test call (typically `GET /ghost/api/admin/users/me/`) verifies the Admin API key is valid and the JWT lifecycle works before any image uploads happen.
- `meta.enums` — the `publish_targets.kind` and `article_publishes.status` enums.

## Steps

1. **Read context.** Resolve the article. Confirm the status is `eeat_passed` or `published`. Pull the target row, confirm `kind='ghost'` and `is_active=true`. Compute `version_published` per the same rule as the Nuxt and WordPress skills.
2. **Pre-flight credential check.** Call `integration.test` against the target's `integration_credential_id`. The probe confirms the daemon's HTTP helper can mint a JWT from the Admin API key and reach `GET /ghost/api/admin/users/me/`. Surface the response (the user's role and slug) in `runs.metadata_json.ghost_publish.role_check`. Refuse to proceed when the response is 401 (invalid key) or when the user's role is `Owner` (publishing with the owner credential is over-privileged for automation; the operator should provision an `Editor` or `Author` integration). Default `Editor` role is the recommended setting.
3. **Render markdown to HTML.** Convert `edited_md` to HTML via `markdown-it` configured for Ghost's HTML dialect:
   - Tables → `<table class="kg-card-no-border">` (or the project's preferred table card class).
   - Code blocks → `<pre><code class="language-…">` (Ghost's themes consume the `language-…` class for syntax highlighting).
   - Footnote markers `[^N]` and definitions render as inline anchors and a `## References` section.
   - Compliance footer renders verbatim as the body's tail.
   - Image references are placeholder for now (rewritten in step 5 after upload).
   - Citations with `[^N]` markers render as `<sup>` tags.
   - When the voice declares Ghost cards (`voice.publishing.ghost_cards=true`), wrap matching sections in card markers (callouts, bookmarks, dividers).
   When the target's `format='lexical'` or `format='mobiledoc'` was chosen, perform the additional conversion through Ghost's published converter library; the HTML render is still the canonical source-of-truth and the format-specific render is derived from it.
4. **Upload assets.** For each asset row in `asset.list`:
   - Resolve the source bytes from the daemon's local filesystem.
   - PUT the bytes to `<ghost_url>/ghost/api/admin/images/upload/` as multipart form-data with the `file` part carrying the bytes and a `purpose` field (`image` for hero / inline / og, `profile_image` for author avatars — the skill only uploads article assets, not avatars). Capture the response's `url` field as the Ghost-hosted URL.
   - On 4xx capture the error and continue without that asset (the body's image reference remains pointing at the daemon URL — the live site renders it as a remote image). Hero upload failure is hard fail because the post's `feature_image` would be invalid.
   - On 5xx retry once. Two consecutive 5xx aborts that asset's upload but not the run.
   The JWT minted in step 2 may have expired between assets when an upload pass takes longer than 5 minutes; the daemon's HTTP helper auto-mints a fresh JWT mid-flow. The skill does not handle the lifecycle.
5. **Rewrite image references.** Walk the rendered HTML body and replace every `<img src="<daemon-url>" …>` with `<img src="<ghost-source-url>" …>` matching the asset. The hero asset's Ghost URL is captured separately for the `feature_image` field. When the target format is `lexical` or `mobiledoc`, the rewrite happens in the converted format's image-node fields rather than in HTML strings.
6. **Compose the post payload.** Build the JSON object the Admin API expects:
   - `title`: the article's title.
   - `slug`: the article's slug.
   - `html` (when format=html): the rendered HTML body from step 5. The `?source=html` query parameter on the POST tells Ghost to consume the `html` field rather than expecting Lexical / mobiledoc.
   - `lexical` / `mobiledoc` (when format!=html): the converted body in the chosen native format.
   - `status`: from the target's `default_status` config; the skill never overrides except in the variants below.
   - `feature_image`: the hero asset's Ghost URL when present.
   - `feature_image_alt`: the hero's audited alt text.
   - `feature_image_caption`: an optional caption (when the brief seeded one).
   - `custom_excerpt`: the brief's `meta_description` when set; otherwise the first 160 chars of the first paragraph.
   - `tags`: an array of `{slug, name}` objects mapped from the brief's tag list. Tags not in `tag_map[]` are auto-created (Ghost does this server-side via the same array — tags missing the `id` key are created).
   - `authors`: an array of `{slug, name}` objects mapped via `author_map[]`. When the author has no Ghost-side mapping, default to the credentialed user.
   - `published_at`: the article's `published_at` ISO-8601 (used for backdating refreshed articles when the target's config permits).
   - `meta_title`: the brief's `seo_title` when distinct from `title`.
   - `meta_description`: the brief's `meta_description`.
   - `og_image`: the og asset's Ghost URL when present (otherwise Ghost falls back to feature_image).
   - `og_title` / `og_description`: when distinct from the standard meta.
   - `twitter_image` / `twitter_title` / `twitter_description`: same shape for Twitter cards.
   - `canonical_url`: the article's resolved canonical URL.
   - `codeinjection_head`: a `<script type="application/ld+json">` block carrying every emitted schema_emits row's `schema_json` joined with newlines, plus any `compliance.list(position='hidden-meta')` entries rendered as `<meta>` tags.
   - `email_only`: from the target's config; defaults to `true`.
   - `email_recipients`: typically `none` for `email_only=true` posts; the skill never sets `all` automatically.
   The composed payload's serializable form persists to `article_publishes.frontmatter_json` as the snapshot.
7. **POST or PUT the post.** When the publish row for `(article_id, target_id, version_published)` already carries a `frontmatter_json.ghost_post_id` (a prior publish wrote it), the skill PUTs to `<ghost_url>/ghost/api/admin/posts/<post-id>/?source=html` to update the existing post. The PUT body must include `updated_at` (Ghost's optimistic concurrency seam — without it Ghost rejects the update); the skill reads the current `updated_at` via a preceding GET when the cached value is stale. When no prior post id exists, the skill POSTs to `<ghost_url>/ghost/api/admin/posts/?source=html`. Capture the response: `id`, `url`, `slug`, `updated_at`, `published_at`, `status`. The response's `url` is the canonical published URL.
8. **Compute the published URL.** Use the response's `url` field — Ghost is authoritative for the URL.
9. **Record the publish row.** Call `publish.recordPublish(article_id, target_id, version_published, published_url=<response.url>, frontmatter_json=<step 6 payload + ghost_post_id>, status=<published|failed>, error=<error or null>)`.
10. **Set canonical when this is the canonical target.** Same logic as the other publish skills.
11. **Advance article status (primary target only).** Same logic as the other publish skills.
12. **Persist the audit row.** Write `runs.metadata_json.ghost_publish = {target_id, target_kind: 'ghost', target_is_primary, version_published, slug, ghost_post_id, post_url, post_status, role_check, image_urls: [...], tags_resolved: [...], tags_auto_created: [...], authors_resolved: [...], format_used, email_only, codeinjection_keys: [...], jwt_refreshed_count, error?}`.
13. **Finish.** Call `run.finish` with `{article_id, target_id, status, version_published, published_url, ghost_post_id?, post_status, format_used, email_only}`. Heartbeats fire after the HTML render (step 3), after each image upload batch (step 4), and after the POST/PUT (step 7).

## Outputs

- `article_publishes` — one row per (article_id, target_id, version_published) with the snapshot payload, the Ghost post id (in frontmatter_json), the published URL, and the success / failure status.
- `articles.status` — advanced to `published` on the primary target's first successful publish; unchanged on secondary targets and republishes.
- `articles.canonical_target_id` — set to this target on primary first publish via `publish.setCanonical`.
- `runs.metadata_json.ghost_publish` — the structured publish-step audit row.

## Failure handling

- **Status not `eeat_passed` or `published`.** Abort. Sequencing bug.
- **Target row not found / `kind` mismatch.** Abort. Procedure runner's per-target replication should have filtered.
- **Credential probe fails (step 2 — auth).** Abort. The operator fixes the integration_credentials row and re-runs.
- **Credential role is `Owner`.** Abort with a clear message asking the operator to provision an `Editor` integration.
- **Image upload returns 4xx for a single asset.** Capture, mark failed in audit, continue. Body image reference falls back to the daemon URL. Hero failure is hard fail.
- **Image upload returns 5xx.** Retry once. Two consecutive 5xx aborts that asset; same hero rule applies.
- **JWT expires mid-upload (step 4).** The daemon's HTTP helper auto-mints a fresh JWT and retries the upload transparently. When the helper itself fails to mint (e.g., the credential has been rotated server-side and our copy is stale), the skill aborts with `runs.metadata_json.ghost_publish.jwt_refresh_failed=true`.
- **POST returns 4xx (step 7).** Capture, mark `status='failed'`, surface, do not retry. Common 4xx reasons: invalid slug (Ghost returns the canonicalised version), permission denied (covered by role check), invalid `published_at` (when scheduling and the time is in the past), invalid `tags` shape (when auto-create is off and a tag slug is missing).
- **POST returns 5xx.** Capture, mark `status='failed'`, raise so the procedure runner's `retry(3, backoff=exponential)` shape decides whether to re-dispatch.
- **PUT returns 409 (Ghost's optimistic concurrency).** Means the post was edited externally between our last read and our update. Refresh the post via GET, capture the new `updated_at`, retry the PUT once. Two consecutive 409s abort the publish so the operator can decide whether to overwrite or merge.
- **`email_only=false` slipped through unintentionally.** Defence-in-depth: when the composed payload would set `email_only=false` AND the operator did not explicitly opt in via the target config, downgrade to `email_only=true` and surface the override in `runs.metadata_json.ghost_publish.email_blast_prevented=true`. The skill must never blast an email to subscribers without an explicit opt-in.
- **`publish.recordPublish` rejects.** Hard failure; the skill must always record its outcome. Surface and abort.
- **`article.markPublished` etag mismatch.** Refresh, retry once. The publish row is in place either way.

## Variants

- **`fast`** — uploads images in parallel rather than serial; skips the optional `feature_image_caption` field; uses Ghost's auto-create-on-empty-slug for tags rather than pre-validating against `tag_map[]`. Useful in `bulk-content-launch`.
- **`standard`** — the default flow above.
- **`pillar`** — adds a step between asset upload and post composition: the skill uploads the principal schema's `Article` blob to Ghost's `pages` endpoint as well, creating a structured-data sibling page (some Ghost themes consume this for pillar overviews). Useful for projects whose theme treats pillar pages distinctly from blog posts.
- **`refresh`** — invoked by procedure 7. Identical to `standard` except the article's status is already `published`, the skill PUTs to the existing post id (after a fresh GET to capture `updated_at`), and `email_only` is unconditionally `true` (a refresh must never email subscribers a duplicate of the original post; refreshes are not new content from the reader's perspective).
