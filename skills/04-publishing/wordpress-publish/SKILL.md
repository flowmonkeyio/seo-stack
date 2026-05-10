---
name: wordpress-publish
description: Render edited_md to HTML, upload article assets to /wp-json/wp/v2/media, POST the post to /wp-json/wp/v2/posts with title / slug / content / excerpt / categories / tags / featured_media / yoast-or-rank-math meta, and record the result via publish.recordPublish; advance to published on the primary target.
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
  target_id:
    source: args
    type: int
    required: true
    description: The publish_targets.id whose kind='wordpress' the procedure controller selected for this run. Procedure 4 publishes to the primary target first, then queues secondary targets.
outputs:
  - table: article_publishes
    write: one row per (article_id, target_id, version_published) via publish.recordPublish — published_url + frontmatter_json + status='published' on success, status='failed' + error on failure.
  - table: articles
    write: article.markPublished on the primary target advances eeat_passed → published; the slug becomes immutable from this point.
  - table: runs
    write: per-step diagnostics (HTML conversion log, media upload IDs, REST response, post ID, post URL) + cost (zero — REST API calls are free) in runs.metadata_json.wordpress_publish.
---

## When to use

Procedure 4 calls this skill after the interlinker (#15) and the schema-emitter (#16). At that point the article is `eeat_passed`, the canonical URL is resolvable from the primary target, and the publish target is a `kind='wordpress'` row whose `config_json` carries the WordPress site's REST URL, auth method, default status, category / tag id mappings, and the per-target frontmatter / meta template. The skill renders the markdown body to HTML, uploads each asset to the WordPress Media Library, POSTs the composed post payload to the REST API, records the publish row, and — when the run is for the project's primary target — advances `articles.status` to `published`.

Procedure 4's publish phase publishes to the primary target first; secondary `wordpress` targets (e.g., a multisite mirror, a sibling locale, or a staging-then-production flow) are handled by the operator agent as explicit follow-up publish steps. Each invocation receives the target_id through args. The skill is idempotent on `(article_id, target_id, version_published)` because the publish.recordPublish call upserts; re-running the same target with the same version produces the same row state. The actual WordPress post is identified by an external post id stored in the publish row's `frontmatter_json.wp_post_id` so re-runs PUT to the existing post rather than creating a duplicate.

The skill also runs in two non-procedure-driven modes the operator can invoke from the UI. The first is a manual republish triggered after the operator edited the article in the editor UI; the contract is identical, with a fresh `run_id`. The second is a content-refresh republish from procedure 7, where the article carries a new `version_published` and the skill PUTs the refreshed body to the existing WordPress post.

## Inputs

- `target.list(project_id, kind='wordpress')` — every WordPress target the project has. The skill reads the specific target by id (the args carry the chosen target). The target's `config_json` is the source of truth for:
  - `wp_url` — the WordPress site's base URL (e.g., `https://example.com`); the REST endpoint is `<wp_url>/wp-json/wp/v2/`.
  - `auth_method` — one of `application_password` (the default modern auth), `jwt` (when the site uses the JWT plugin), or `oauth1` (legacy; not commonly used).
  - `default_status` — one of `publish` (immediate live), `draft` (publishes invisibly), `pending` (awaits editorial review), `future` (requires a `date` field). The skill defaults to `draft` when the target does not declare a status; the operator's UI lets them flip to `publish` after a final review.
  - `category_ids[]` — a map from the project's tag / cluster id to the WordPress category id. The skill maps the article's cluster to a category id at publish time.
  - `tag_ids[]` — a map from the brief's tag list to WordPress tag ids; tags not present in the map are auto-created when `auto_create_tags=true` on the target config, otherwise dropped with a log entry.
  - `seo_plugin` — one of `yoast`, `rank_math`, or `none`. When set, the skill emits `yoast_meta` or `rank_math_meta` meta fields on the post payload so the SEO plugin's per-post settings (focus keyword, meta description, og image) get populated.
  - `integration_credential_id` — the foreign key into `integration_credentials WHERE kind='wordpress'`. The credential row carries the auth payload (the application password, the JWT secret, etc.). The daemon's HTTP helper is the only consumer; the skill does not read the encrypted blob directly.
  - `public_url_pattern` — used to compute `published_url` (e.g., `https://example.com/{slug}` or `https://example.com/blog/{slug}`).
  - `is_primary` — whether this target is the project's primary publish target.
- `article.get(article_id)` — returns `edited_md` (the body to render to HTML), `brief_json` (used for the meta description, focus keyword, intent, audience), `slug`, `title`, the live `step_etag`, the `version`, `author_id`, and `canonical_target_id`. Confirm `status='eeat_passed'` (procedure-4 first publish) or `status='published'` (refresh / republish).
- `voice.get(project_id)` — the active voice's metadata for the WordPress-specific HTML rules (some voices declare HTML purity preferences — e.g., Gutenberg block markup vs. classic HTML; the skill respects the preference when rendering markdown to HTML).
- `compliance.list(project_id, position='hidden-meta')` — compliance rules whose position is `hidden-meta` render as WordPress custom fields (post meta) so the site's theme can read them server-side. Visible compliance rules are already inlined in `edited_md`.
- `schema.get(schema_id)` (the principal `schema_emits.is_primary=true` row's id, plus secondaries) — read each schema row's `schema_json` and emit it under a custom field the SEO plugin renders as `<script type="application/ld+json">`. Yoast and Rank Math both expose this seam; the field name is `_yoast_wpseo_schema` or `_rank_math_schema` respectively.
- `asset.list(article_id)` — every asset row. The skill uploads each asset to the Media Library via `POST /wp-json/wp/v2/media`, captures the returned WP media id and source URL, and rewrites the body's image references to the WP-hosted URLs.
- `source.list(article_id, used=true)` — feeds the references custom field when the target's frontmatter template renders a sources block.
- `integration.test` — pre-flight credential probe. The wrapper's test call (typically `GET /wp-json/wp/v2/users/me`) verifies the credential is live and has post-creating privileges before any media uploads happen.
- `meta.enums` — the `publish_targets.kind` and `article_publishes.status` enums.

## Steps

1. **Read context.** Resolve the article. Confirm the status is one of `eeat_passed` or `published`. Pull the target row, confirm `kind='wordpress'` and `is_active=true`. Compute `version_published` per the same rule as the Nuxt skill (article.version + 1 on first publish; article.version + 1 on republish where procedure 7 has already created a new version).
2. **Pre-flight credential check.** Call `integration.test` against the target's `integration_credential_id`. The probe goes through the daemon's HTTP helper which mints the auth header (Basic for application_password, Bearer for JWT) and calls `GET /wp-json/wp/v2/users/me`. The response carries the user's roles; the skill confirms the user has `editor` or `author` role at minimum. Refuse to proceed when the role is `administrator` (the operator should never publish with an admin credential — the blast radius of a leaked admin token is too large). Refuse to proceed when the user has none of `editor` / `author` (insufficient privileges). Surface the role check in `runs.metadata_json.wordpress_publish.role_check`.
3. **Render markdown to HTML.** Convert `edited_md` to HTML via `markdown-it` (or the equivalent) configured for the WordPress dialect:
   - Tables → `<table>` with WordPress-friendly classes the theme styles.
   - Code blocks → `<pre><code>` with no language hint inline (WordPress's default code highlighter consumes a separate `class="language-…"` attribute).
   - Footnote markers `[^N]` and definitions render as inline anchors and a `## References` section, identical to the source markdown.
   - Compliance footer renders verbatim as the body's tail.
   - Image references are placeholder for now (the actual `<img>` tags are rewritten in step 5 after media upload).
   - Citations with `[^N]` markers render as `<sup>` tags pointing at the references section anchor.
   When the voice declares Gutenberg blocks (`voice.publishing.gutenberg=true`), wrap each section in the appropriate block comment markers (`<!-- wp:paragraph -->`, `<!-- wp:heading -->`, etc.); when not, render classic HTML.
4. **Upload assets.** For each asset row in `asset.list`:
   - Resolve the source bytes from the daemon's local filesystem path (per skill #13's documented layout).
   - Compose the multipart form-data body: the file bytes, plus a JSON metadata object with `title`, `alt_text` (from the asset row), `caption`, and `description`. The alt_text is what the alt-text-auditor refined.
   - POST to `<wp_url>/wp-json/wp/v2/media` via the daemon's HTTP helper. Capture the returned media id and `source_url`.
   - When the upload returns a 4xx for a permission reason, capture the error and continue without that asset's media id; the body's image reference remains pointing at the daemon's URL (the WordPress site renders it as a remote image, which is suboptimal but not a hard failure).
   - When the upload returns a 5xx, retry once. Two consecutive 5xx aborts that asset's upload but not the run.
   Capture the media id list as `runs.metadata_json.wordpress_publish.media_ids[]` so a failure-mode rollback can delete the uploaded media on a failed post creation.
5. **Rewrite image references.** Walk the rendered HTML body and replace every `<img src="<daemon-url>" …>` with `<img src="<wp-source-url>" data-wp-id="<media-id>" …>` matching the asset's media id. The hero asset's media id is captured separately for the post payload's `featured_media` field.
6. **Compose the post payload.** Build the JSON object the REST API expects:
   - `title`: the article's title.
   - `slug`: the article's slug (WordPress will warn-and-not-conflict on duplicate slugs by appending `-2`; the skill reads the response slug rather than asserting equality).
   - `content`: the rendered HTML body from step 5.
   - `excerpt`: the brief's `meta_description` when set; otherwise the first 160 chars of the first body paragraph.
   - `status`: from the target's `default_status` config; the skill never overrides except in the variants below.
   - `categories`: the mapped category ids from `target.config_json.category_ids`.
   - `tags`: the mapped tag ids; auto-create tags via `POST /wp-json/wp/v2/tags` when `auto_create_tags=true` and capture the returned ids.
   - `featured_media`: the hero asset's WP media id (when an `og` asset exists, it is uploaded as a separate media row but `featured_media` always points at the hero — the og asset is referenced via the SEO plugin's meta).
   - `meta`: a JSON object carrying:
     - `_yoast_wpseo_metadesc` / `rank_math_description` — the meta description.
     - `_yoast_wpseo_focuskw` / `rank_math_focus_keyword` — the brief's `primary_kw`.
     - `_yoast_wpseo_canonical` / `rank_math_canonical_url` — the article's canonical URL.
     - `_yoast_wpseo_opengraph-image` / `rank_math_facebook_image` — the og asset's WP source URL when present.
     - `_yoast_wpseo_schema` / `rank_math_schema` — the schema_emits rows' `schema_json`, JSON-encoded.
     - One key per compliance.list(position='hidden-meta') entry, prefixed with `cs_compliance_`.
   - `author`: the WP user id from the target's `author_id_map[<article.author_id>]` config. When the project's author has no WP-side mapping, default to the credentialed user (the same user the credential identifies); surface the fallback in the audit row.
   - `date`: the article's `published_at` ISO-8601 (used for backdating refreshed articles).
   The composed payload's serializable form persists to `article_publishes.frontmatter_json` as the snapshot.
7. **POST or PUT the post.** When the publish row for `(article_id, target_id, version_published)` already carries a `frontmatter_json.wp_post_id` (a prior publish wrote it), the skill PUTs to `<wp_url>/wp-json/wp/v2/posts/<post-id>` to update the existing post. When no prior post id exists, the skill POSTs to `<wp_url>/wp-json/wp/v2/posts/`. Capture the response: `id`, `link`, `slug`, `modified`, `status`. The response's `link` is the canonical published URL.
8. **Compute the published URL.** Use the response's `link` field — WordPress is authoritative for the URL because permalinks may differ from the target's `public_url_pattern` (WordPress sometimes appends a duplicate-slug counter or the operator chose a non-default permalink structure). The pattern is a fallback for record-keeping when the response link is missing.
9. **Record the publish row.** Call `publish.recordPublish(article_id, target_id, version_published, published_url=<response.link>, frontmatter_json=<step 6 payload + wp_post_id>, status=<published|failed>, error=<error or null>)`. The repository upserts on `(article_id, target_id, version_published)`. The `wp_post_id` is what makes future refreshes PUT instead of POST.
10. **Set canonical when this is the canonical target.** Same logic as the Nuxt skill: when the article's `canonical_target_id` is null AND this run is for the primary target AND the post wrote `published`, call `publish.setCanonical(article_id, target_id)`.
11. **Advance article status (primary target only).** Same logic as the Nuxt skill: on the primary target, on first-publish path, on a successful publish, call `article.markPublished(article_id, expected_etag)`.
12. **Persist the audit row.** Write `runs.metadata_json.wordpress_publish = {target_id, target_kind: 'wordpress', target_is_primary, version_published, slug, wp_post_id, post_url, post_status, role_check, media_ids: [...], categories_resolved: [...], tags_resolved: [...], tags_auto_created: [...], seo_meta_keys: [...], rollback_applied?, error?}`.
13. **Finish.** Call `run.finish` with `{article_id, target_id, status, version_published, published_url, wp_post_id?, post_status}`. Heartbeats fire after the HTML render (step 3), after each media upload batch (step 4), and after the POST/PUT (step 7).

## Outputs

- `article_publishes` — one row per (article_id, target_id, version_published) with the snapshot payload, the WP post id (in frontmatter_json), the published URL, and the success / failure status.
- `articles.status` — advanced to `published` on the primary target's first successful publish; unchanged on secondary targets and republishes.
- `articles.canonical_target_id` — set to this target on primary first publish via `publish.setCanonical`.
- `runs.metadata_json.wordpress_publish` — the structured publish-step audit row.

## Failure handling

- **Status not `eeat_passed` or `published`.** Abort. Sequencing bug; the procedure runner should have advanced the status.
- **Target row not found / `kind` mismatch.** Abort. The procedure runner's per-target replication should have filtered to `kind='wordpress'`.
- **Credential probe fails (step 2 — auth).** Abort. The operator fixes the integration_credentials row via the Settings UI and re-runs.
- **Credential role is `administrator`.** Abort with a clear message asking the operator to switch to a role-restricted account. Document in `docs/api-keys.md`.
- **Credential role insufficient (no editor / author).** Abort with the role check surfaced; the operator escalates the WP user's role.
- **Media upload returns 4xx for a single asset (step 4).** Capture the error, mark the asset failed in the audit row, continue. The body's image reference falls back to the daemon URL; the publish proceeds in degraded mode. Hero failure is hard fail (the post would have no `featured_media`).
- **Media upload returns 5xx for a single asset.** Retry once. Two consecutive 5xx aborts that asset; same hero-vs-non-hero rule applies.
- **POST returns 4xx (step 7).** Capture the error in the publish row's `error` field, mark `status='failed'`, surface, do not retry. Common 4xx reasons: permission denied (covered by the role check), invalid slug (auto-collide; WordPress should append `-2` rather than reject), invalid meta keys (some SEO plugins lock down meta updates).
- **POST returns 5xx.** Capture, mark `status='failed'`, surface, and let the procedure agent decide whether to retry.
- **Rollback uploaded media on failed POST.** When the POST failed AND `media_ids[]` is non-empty, attempt to delete each uploaded media row via `DELETE /wp-json/wp/v2/media/<id>?force=true`. Best-effort; failures are logged but do not propagate. The audit row reflects whether the rollback succeeded so the operator can clean up orphan media manually if needed.
- **`publish.recordPublish` rejects.** Hard failure; the skill must always record its outcome. Surface and abort.
- **`article.markPublished` etag mismatch.** Refresh, retry once. The publish row is in place either way; only the status advancement is at risk.

## Variants

- **`fast`** — skips the role check (step 2 still calls test but the role-restriction enforcement is downgraded to a warning) and uploads media in parallel rather than serial. Useful in `bulk-content-launch` against a trusted credential. The role-check downgrade requires the operator's explicit opt-in via the target config (`role_check_strict=false`).
- **`standard`** — the default flow above.
- **`pillar`** — adds an extra step between media upload and post composition: the skill uploads a sitemap-friendly redirect entry to the WordPress redirection plugin (when installed) so the article's previous slug — if any — redirects to the new one. Useful for pillar articles that may have lived under a placeholder slug during draft.
- **`refresh`** — invoked by procedure 7. Identical to `standard` except the article's status is already `published`, the skill PUTs to the existing post id, and the `meta._yoast_wpseo_canonical` / `rank_math_canonical_url` is re-asserted in case the operator changed it externally between refreshes. The post's `date` is preserved (a refresh updates `modified` automatically; backdating the original post would suppress in feeds).
