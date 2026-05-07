---
name: nuxt-content-publish
description: Compose Nuxt Content frontmatter from edited_md + brief + voice + schema + canonical URL, write the .md file into the target's repo, copy referenced assets, commit, push, and record the result via publish.recordPublish; advance to published on the primary target.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: original
license: original (clean-room; no upstream — PLAN.md L859 + docs/upstream-stripping-map.md "Original skills" section)
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
    description: The publish_targets.id whose kind='nuxt-content' the procedure runner has selected for this dispatch. Procedure 4 publishes to the primary target first, then queues secondary targets via publish_target.replicate.
outputs:
  - table: article_publishes
    write: one row per (article_id, target_id, version_published) via publish.recordPublish — published_url + frontmatter_json + status='published' on success, status='failed' + error on failure.
  - table: articles
    write: article.markPublished on the primary target advances eeat_passed → published; the slug becomes immutable from this point.
  - table: runs
    write: per-step diagnostics (frontmatter composition, asset copy paths, git commit SHA, push response) + cost (zero — git push is free) in runs.metadata_json.nuxt_content_publish.
---

## When to use

Procedure 4 dispatches this skill after the interlinker (#15) has emitted suggestions and the schema-emitter (#16) has written the JSON-LD rows. The article is `eeat_passed`, the canonical URL is resolvable, and the publish target is a `kind='nuxt-content'` row whose `config_json` carries the Nuxt site's repo path / branch / public URL pattern. The skill writes a `.md` file with frontmatter into the target's content directory, copies any referenced assets into the target's `public/` tree, commits the change, pushes to the configured remote, records the publish row, and — if this dispatch is for the project's primary target — advances `articles.status` from `eeat_passed` to `published`.

Procedure 4's publish phase publishes to the project's primary target first; secondary `nuxt-content` targets (e.g., a staging mirror, a sibling locale, or a multi-domain mirror) are dispatched in turn via the procedure runner's per-target replication. Each dispatch is a fresh skill invocation; the procedure runner walks the active targets in primary-first order and passes the appropriate `target_id` through args. The skill is idempotent on `(article_id, target_id, version_published)` because `publish.recordPublish` is upsert — re-running the same dispatch produces the same row state.

The skill also runs in two non-procedure-driven modes the operator can invoke from the UI. The first is a manual republish triggered after the operator edited the article in the editor UI; the procedure runner is not in the loop, but the contract is identical — a fresh `run_id` is minted and the skill walks every step. The second is a content-refresh republish from procedure 7, where the article carries a new `version_published` (incremented by `article.createVersion` earlier in the procedure) and the skill writes the refreshed body to the same target.

## Inputs

- `target.list(project_id, kind='nuxt-content')` — every Nuxt Content target the project has. The skill reads the specific target by id (the args carry the chosen target). The target's `config_json` is the source of truth for:
  - `repo_path` — absolute path to the local clone of the target's content repo (the daemon's installer ensures the clone exists; the skill does not clone on first run).
  - `content_subdir` — the directory under `repo_path` where the `.md` files live (typically `content/blog`, `content/articles`, `content/posts`).
  - `public_subdir` — the directory under `repo_path` where image assets are copied (typically `public/images`).
  - `branch` — the git branch to push to (typically `main` for production, `staging` for staging).
  - `git_remote` — the remote name (typically `origin`).
  - `commit_template` — a templated commit message; defaults to `content-stack: publish <slug>` when absent. Templates may include `{slug}`, `{title}`, `{version}`, `{kind}` placeholders. The template is passed as a `-m` argument, never shell-interpolated.
  - `public_url_pattern` — used to compute `published_url` (e.g., `https://example.com/blog/{slug}`).
  - `frontmatter_template` — an optional dictionary the operator can override per target; the skill merges the project defaults with this override.
  - `is_primary` — whether this target is the project's primary publish target (used to decide whether to call `article.markPublished`).
- `article.get(article_id)` — returns `edited_md` (the body to write), `brief_json` (used for the meta description, keywords, intent, audience, schema roster references), `slug`, `title`, the live `step_etag`, the `version` (for the upcoming `version_published`), the `author_id`, and `canonical_target_id`. Confirm `status='eeat_passed'` (procedure-4 first publish) or `status='published'` (refresh / republish).
- `voice.get(project_id)` — the active voice's metadata for the frontmatter's tone-related fields (e.g., the publish target's `voice_class` field maps article tone to a CSS hook the Nuxt site applies for editorial styling). Optional; the publish proceeds without voice metadata when the target's frontmatter template does not consume it.
- `compliance.list(project_id, position='hidden-meta')` — compliance rules whose position is `hidden-meta` render into frontmatter as JSON keys consumed by Nuxt's templating (e.g., a `hidden_meta.affiliate_disclosure_id` key the site theme reads to render a styled disclosure block). The visible compliance rules (`header`, `after-intro`, `footer`) are already inlined in `edited_md` by the draft skills; the skill does not re-render them.
- `schema.get(schema_id)` (the principal `schema_emits.is_primary=true` row's id, plus secondaries) — read each schema row's `schema_json` and emit it under the frontmatter's `schema` key (Nuxt Content's templating renders `<script type="application/ld+json">` blocks from this key). The publish step does not modify the schema blob; it copies it verbatim.
- `asset.list(article_id)` — every asset row. The skill copies each asset's bytes into the target's `public_subdir` and rewrites `edited_md`'s image references to point at the published path (typically `/images/<asset-filename>` relative to the Nuxt site root).
- `source.list(article_id, used=true)` — used to populate the frontmatter's `references[]` array when the target's frontmatter template includes a structured-references block (some Nuxt themes render a "Sources" section from this).
- `integration.test` — an optional pre-flight call against a `nuxt-content` integration row when the operator has wired one for git push credentials (typically the operator uses ssh-agent or git-credential-manager and no integration row is needed). When the row exists, the skill probes credentials before walking the rest of the steps.
- `meta.enums` — surfaces the `publish_targets.kind` and `article_publishes.status` enums.

## Steps

1. **Read context.** Resolve the article. Confirm the status is one of `eeat_passed` (first publish) or `published` (republish / refresh). Pull the target row, confirm `kind='nuxt-content'` and `is_active=true`. Compute `version_published`: for first publish (`status='eeat_passed'`), the value equals `articles.version` after `mark_published` would assign it (the procedure runner passes the explicit number through args, derived from `article.version + 1` because mark_published increments version on transition); for republish (`status='published'`), the value is `articles.version + 1` because the procedure runner has already invoked `article.createVersion` for the refresh and the new version's content is what we publish.
2. **Pre-flight integration check.** When the target's `config_json.integration_credential_id` is set, call `integration.test` against that row. The probe verifies the daemon's git push credentials are valid before the skill writes any files; failing fast saves a partial commit. When no integration row is wired (the daemon defers to system-level git credentials), skip the probe and proceed.
3. **Resolve the local repo.** Confirm the target's `repo_path` exists and is a git working tree. Run `git -C <repo_path> status --porcelain` (via `subprocess.run`); a non-empty result means the working tree is dirty. Refuse to publish on a dirty tree — the skill must not clobber the operator's uncommitted edits in the target repo. Surface `runs.metadata_json.nuxt_content_publish.dirty_tree=true` and abort. The operator either commits or stashes before retrying.
4. **Sync the target branch.** Run `git -C <repo_path> fetch <git_remote>` followed by `git -C <repo_path> checkout <branch>` and `git -C <repo_path> pull --ff-only <git_remote> <branch>`. The fast-forward-only constraint is intentional: the daemon never resolves merge conflicts in the target repo. When `pull --ff-only` fails (the remote has diverged from local — typical when another daemon instance pushed concurrently or the operator pushed by hand), the skill aborts with `runs.metadata_json.nuxt_content_publish.fetch_failed=true` and a clear message; the operator resolves the divergence and retries.
5. **Compose the frontmatter map.** Build the per-target frontmatter as a flat key→value map per PLAN.md L427-L433 (`article_publishes.frontmatter_json` shape):
   - `title` — from `articles.title` (and the brief's `title` when set there).
   - `slug` — from `articles.slug`. Also embedded in the file path; the value here is for theme-side use.
   - `description` — from `brief_json.meta_description` when set; otherwise the first 160 chars of the article's first body paragraph.
   - `canonical_url` — the resolved canonical URL from the principal target's `public_url_pattern` interpolated with `slug` (and the article's `canonical_target_id` when it differs from this target's id).
   - `og_image` — the `kind='og'` asset's published path; falls back to the hero's published path when no og asset exists.
   - `og_description` — the brief's `meta_description` (same value as `description` typically; the publish theme may diverge).
   - `published_at_iso` — the article's `published_at` ISO-8601.
   - `last_refreshed_at_iso` — the article's `last_refreshed_at` ISO-8601 when set; absent otherwise.
   - `author` — the author row's name + slug; the theme renders bylines from this.
   - `tags` — the brief's tags; the schema-emitter's `keywords` field also references these.
   - `categories` — the brief's categories or the topic's cluster-derived category.
   - `schema` — an array of every JSON-LD blob from `schema_emits` rows; Nuxt Content's templating renders `<script type="application/ld+json">` blocks for each entry.
   - `hidden_meta` — the merged compliance.list(position='hidden-meta') keys.
   - `voice_class` — the voice profile's CSS hook (when the target's frontmatter template consumes it).
   - `references[]` — the used-source rows when the target's frontmatter template renders a sources section.
   - `version` — the upcoming `version_published` integer.
   The composed map is the snapshot the publish.recordPublish row will carry as its `frontmatter_json` field.
6. **Compose the markdown body.** Take `edited_md` and rewrite every image reference from the daemon-side URL (`/api/v1/assets/<id>`) to the publish-side path (`/images/<asset-filename>`) where `asset-filename` is the file basename the skill copies in step 7. Other markdown content is unchanged: the compliance footer, the references block, the citation markers — all already rendered correctly by the draft / editor skills. Do NOT re-edit the body: any rewrite at publish time would invalidate the EEAT gate's audit on the same body.
7. **Copy assets into the target tree.** For each row in `asset.list`:
   - Resolve the source path. When the asset's `url` is an absolute external URL (e.g., a CDN URL the OpenAI Images response returned), download the bytes via `httpx.get` to a temp file. When the asset's `url` is the daemon's own `/api/v1/assets/<id>` route, read the file from `~/.local/share/content-stack/assets/<project_slug>/<article_id>/<asset_id>.<ext>` directly. The daemon's filesystem layout is the canonical source; the URL is just the addressing scheme.
   - Compose the destination path: `<repo_path>/<public_subdir>/<asset-filename>`. The `<asset-filename>` is `<slug>-<kind>-<position>.<ext>` for inlines (`acme-laptops-inline-1.webp`, `acme-laptops-inline-2.webp`) and `<slug>-<kind>.<ext>` for hero / og / twitter / thumbnail (`acme-laptops-hero.webp`).
   - Copy with `shutil.copy2` to preserve mtime (helps with downstream cache busting). Skip when the destination already exists with the same byte content (re-runs of the same version should be a no-op for unchanged assets).
8. **Compose the file path.** The full path is `<repo_path>/<content_subdir>/<slug>.md`. When a file already exists at this path AND the existing file's frontmatter `slug` differs from the article's slug, abort with `runs.metadata_json.nuxt_content_publish.slug_collision=true` — the slug collides with an unrelated article in the target repo and the operator must rename one.
9. **Write the file.** Render the YAML frontmatter (the map from step 5) followed by `---\n\n` and the rewritten markdown body from step 6. Use `pathlib.Path.write_text` with explicit utf-8 encoding. Capture the bytes-written count for the audit row.
10. **Stage the changes.** Run `git -C <repo_path> add <content_subdir>/<slug>.md` and `git -C <repo_path> add <public_subdir>` (the entire public subdir; the repository's `.gitignore` should exclude transient files). When `git status --porcelain` returns empty after staging, the publish is a no-op (the article + assets are byte-identical to what is already in the repo). Surface `runs.metadata_json.nuxt_content_publish.no_change=true`, skip the commit + push, jump to step 14, record the row with `status='published'` and the existing `published_url` so the audit reflects the operation completed.
11. **Commit.** Render the commit message from `commit_template` (or the default). Run `git -C <repo_path> commit -m "<rendered>"`. The `-m` argument is passed as a separate `subprocess.run` arg (never shell-interpolated). Capture the resulting commit SHA via `git rev-parse HEAD`.
12. **Push.** Run `git -C <repo_path> push <git_remote> <branch>`. When the push returns non-zero (auth failure, remote rejected, network), capture the stderr in `runs.metadata_json.nuxt_content_publish.push_error` and proceed to the rollback path: `git reset --hard HEAD~1` to undo the local commit (so the next publish attempt starts from a clean tree), then mark the publish as failed in step 14. Do not retry inside the skill — the procedure runner's `retry(3, backoff=exponential)` shape (PLAN.md procedure 4) handles 5xx-class retries; auth / 4xx errors should not be retried.
13. **Compute the published URL.** Interpolate the target's `public_url_pattern` with the article's slug (and any other placeholder the operator declared, e.g., `{locale}` for multi-locale projects). The URL is the `published_url` value the publish row will carry.
14. **Record the publish row.** Call `publish.recordPublish(article_id, target_id, version_published, published_url=<computed>, frontmatter_json=<map from step 5>, status=<published|failed>, error=<error message or null>)`. The repository upserts on `(article_id, target_id, version_published)`. When the push failed in step 12, status is `failed` with the error captured. When the push succeeded or the no-change branch fired in step 10, status is `published` and error is null.
15. **Set canonical when this is the canonical target.** When the article's `canonical_target_id` is null AND this dispatch is for the project's `is_primary=true` target, call `publish.setCanonical(article_id, target_id)` to make this target the canonical reference. When `canonical_target_id` is already set (a prior publish settled it), this step is a no-op.
16. **Advance article status (primary target only).** When the target's `is_primary=true` AND the article's status was `eeat_passed` AND step 14 wrote a `published` row, call `article.markPublished(article_id, expected_etag=<live etag>)`. The repository advances `articles.status` from `eeat_passed` to `published`, freezes the slug as immutable, and rotates `step_etag`. For secondary targets the step is a no-op (the article transitions only once, on the primary publish). For republish runs (status was already `published`), the step is also a no-op — the article is already published; the recordPublish row alone captures the new version.
17. **Persist the audit row.** Write `runs.metadata_json.nuxt_content_publish = {target_id, target_kind: 'nuxt-content', target_is_primary, version_published, slug, file_path, public_url, commit_sha?, push_succeeded, no_change?, dirty_tree?, slug_collision?, fetch_failed?, push_error?, asset_paths: [...], frontmatter_keys: [...], rollback_applied?}`. The audit row is what the operator's UI surfaces under the article's "Publishes" tab.
18. **Finish.** Call `run.finish` with `{article_id, target_id, status, version_published, published_url, commit_sha?, push_succeeded}`. Heartbeats fire after the body composition (step 6), after asset copy (step 7), after commit (step 11), and after push (step 12) so a slow git push or asset copy stays visible.

## Outputs

- `article_publishes` — one row per (article_id, target_id, version_published) with the frontmatter snapshot, the published URL, and the success / failure status.
- `articles.status` — advanced to `published` on the primary target's first successful publish; unchanged on secondary targets and republishes.
- `articles.canonical_target_id` — set to this target on primary first publish via `publish.setCanonical`.
- `runs.metadata_json.nuxt_content_publish` — the structured publish-step audit row.

## Failure handling

- **Status not `eeat_passed` or `published`.** Abort. The procedure runner's preceding skills should have advanced the status; re-entry without a valid status is a sequencing bug.
- **Target row not found / `kind` mismatch.** Means the procedure runner passed an invalid target_id. Abort with a clear message; the runner's per-target replication should have filtered to `kind='nuxt-content'` rows.
- **Working tree dirty (step 3).** Abort with the dirty-tree flag. The operator commits or stashes in the target repo and re-runs.
- **Branch fetch / fast-forward fails (step 4).** Abort with the fetch-failed flag. The operator resolves the remote divergence and re-runs. The skill does not auto-resolve.
- **Slug collision (step 8).** Abort with the slug-collision flag. The operator renames either the existing file in the target repo or the article's slug (which requires an `eeat_passed` retry — slug is immutable post-publish).
- **No change to commit (step 10).** Not a failure: the publish recorded a row with the existing URL and `no_change=true` for audit consistency. The operator's UI shows the row but flags it.
- **Commit failed (step 11).** Means the staged content is somehow invalid or git refuses for another reason. Capture the stderr, abort, surface in audit. Do not retry.
- **Push failed (step 12).** Roll back the local commit (`git reset --hard HEAD~1`), record the publish row with `status='failed'` and the error, surface in audit, raise so the procedure runner's `retry(3, backoff=exponential)` shape decides whether to re-dispatch. Auth-class errors (401 / 403) should be surfaced to the operator, not retried.
- **`publish.recordPublish` rejects.** Means a uniqueness constraint or input-validation error. Surface, abort, do not retry. The skill must always be able to record its own outcome; an inability to write the audit row is a hard failure.
- **`article.markPublished` etag mismatch.** Refresh via `article.get`, retry once. Two consecutive mismatches abort the markPublished call but leave the publish row in place — the publish itself succeeded; the status advancement is a separate concern the operator can complete manually via the UI.
- **Asset copy fails (step 7) for a single asset.** Capture the error, mark the asset as failed in the audit row, continue. A single missing inline image is a `partial` publish; the procedure runner's failure-handler decides whether to call this fail or continue. Hero copy failure is hard fail because the schema's `image` would be invalid.

## Variants

- **`fast`** — skips the integration probe (step 2) and the asset-existence dedupe (step 7's "skip when destination already exists with same bytes" branch). Useful in `bulk-content-launch` where dozens of articles publish in sequence and the asset tree is being populated wholesale.
- **`standard`** — the default flow above.
- **`pillar`** — adds an extra step between asset copy and frontmatter composition: it walks the body and validates every internal-link href against the project's `internal_links WHERE status='applied'` set, refusing to publish if a link references a not-yet-published article (avoids a 404 on the live site). Useful for pillar articles where every internal link must resolve at publish time.
- **`refresh`** — invoked by procedure 7 against a humanized-and-re-edited article. Identical to `standard` except the article's status is already `published` (procedure 7 does not run the EEAT gate when the refresh is a humanizer pass only), `version_published` is `articles.version + 1`, and the skill writes a redirect row when the slug changed pre-publish (procedure 7 disallows slug change post-publish so this branch only fires on operator overrides).
