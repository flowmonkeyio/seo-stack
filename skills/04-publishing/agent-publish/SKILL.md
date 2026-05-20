---
name: agent-publish
description: Hand the final publish to the current operator agent when no daemon-managed target is required; publish through the available external repo/API/DB/tooling, then record the targetless result via publish.recordExternal and advance the article.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: original
license: project-internal
allowed_tools:
  - meta.enums
  - project.get
  - article.get
  - asset.list
  - source.list
  - schema.get
  - schema.list
  - publish.recordExternal
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
  - table: article_publishes
    write: one targetless row per (article_id, version_published) via publish.recordExternal, with target_id=null, published_url, frontmatter_json, and status.
  - table: articles
    write: publish.recordExternal advances eeat_passed → published when mark_article_published=true and the external publish succeeded.
  - table: runs
    write: per-step diagnostics describing which external path was used and the final published URL.
---

## Shared operating contract

Before executing, read `../../references/skill-operating-contract.md` and
`../../references/seo-quality-baseline.md`. Apply the shared status, validation,
evidence, handoff, people-first, anti-spam, and tool-discipline rules before the
skill-specific steps below.

## When to use

Procedure 4 authors this skill as the default publish step. Use it when the
project has no daemon-managed publish target, when the primary target kind is
not wired to a production publisher, or when the operator intentionally wants
the main agent to publish through an external capability that content-stack does
not own directly.

This skill does not create a `publish_targets` row and does not require one.
The current operator agent does the actual publish using the tools available in
the main thread: a website repo, a first-party admin/API tool, a direct DB MCP,
or a manual operator handoff. Content-stack remains the durable source of the
article, assets, schema rows, and publish audit trail.

When a project does have a primary active `kind='nuxt-content'` target, the
procedure controller swaps the step package to `nuxt-content-publish` before
the agent sees it. Other target kinds fall back here until their real hidden
publisher operations exist and are granted.

## Inputs

- `article.get(article_id)` — fetch the final article body, title, slug, brief,
  version, status, and live `step_etag`. Confirm status is `eeat_passed` for a
  first publish, or `published` for an external republish.
- `asset.list(article_id)` — fetch hero, OG, thumbnail, and inline assets so the
  external publisher can upload or reference them.
- `schema.list(article_id)` / `schema.get(schema_id)` — fetch the JSON-LD rows
  the external publisher should embed or store.
- `source.list(article_id, used=true)` — fetch the source ledger when the
  external publisher needs a structured references block.
- `project.get(project_id)` and `meta.enums` — read project metadata and the
  canonical publish status enums.
- `publish.recordExternal` — the only content-stack write for this skill. Call
  it through `toolbox.call` after the external publish succeeds or after a
  failed external attempt needs an audit row.

## Steps

1. **Read context.** Resolve the article, project, assets, used sources, and
   schema rows. Capture `article.step_etag`, `article.version`, `article.slug`,
   and the final `edited_md`. Do not rewrite the body at publish time; the EEAT
   gate approved this exact content.
2. **Choose the external path.** Use the main thread's available tools and
   current workspace context. Examples: write directly to the current site's DB
   through its MCP, call an internal website publish tool, edit and commit the
   website repo, call WordPress/Ghost/admin APIs when those are available to the
   main agent, or pause for a manual operator publish. Do not pretend the
   content-stack daemon has a hidden target-specific operation unless the step's
   `allowed_tools` grants that exact tool.
3. **Publish externally.** Send the article body, title, slug, schema package,
   asset references, and source ledger to the selected external publisher. If
   assets must be uploaded first, keep the resulting public asset URLs in the
   audit metadata. If the external system returns a draft/preview first, inspect
   the final rendered URL before marking the publish successful.
4. **Compute the publish record.** Set `version_published` to the article's
   current `version` for the first targetless publish unless the calling
   procedure supplied an explicit version. Set `published_url` to the live URL
   returned by the external system or confirmed by the operator. Put structured
   diagnostics in `frontmatter_json`, including `publisher: agent`,
   `external_path`, public asset URLs, schema row ids, and any external post id
   or commit SHA.
5. **Record success.** Call `publish.recordExternal` with `article_id`,
   `version_published`, `published_url`, `frontmatter_json`, `status='published'`,
   `expected_etag=<article.step_etag>`, and `run_id=<current run_id>`. Leave
   `mark_article_published=true` so the tool writes the targetless publish row
   and advances the article from `eeat_passed` to `published`.
6. **Record failure when needed.** If the external publish attempt failed after
   it touched the destination system, call `publish.recordExternal` with
   `status='failed'`, `error=<clear reason>`, and `mark_article_published=false`.
   If no external publish was attempted, abort without a publish row and make
   the procedure error explain the blocker.
7. **Finish.** Call `run.finish` with `{article_id, status, version_published,
   published_url?, external_path, external_ref?}`. Heartbeat after reading the
   article and after any long external publish/upload operation.

## Outputs

- `article_publishes` — one targetless row with `target_id=null`, the published
  URL, status, error when any, and metadata about the external path.
- `articles.status` — advanced to `published` on successful first publish.
- `runs.metadata_json.agent_publish` — the operator-facing audit payload for
  what external path was used.

## Failure handling

- **Article status is not `eeat_passed` or `published`.** Abort. The procedure
  reached publish out of order.
- **No publish path is available.** Abort with a clear handoff note. Do not add
  a target row just to satisfy the flow.
- **External publish returns a draft-only URL.** Do not mark success until a
  public URL is confirmed. Record a failed row only if the external system was
  actually mutated.
- **`publish.recordExternal` rejects because of an etag mismatch.** Refresh
  via `article.get` and retry once with the new etag only if the article body
  and version still match the content that was published. If the body changed,
  abort and surface the mismatch for human review.
- **Target-specific tool is tempting but not granted.** Do not call it through
  content-stack. Use the main thread's independent tool access if available,
  or abort with the missing capability named plainly.

## Variants

- **`standard`** — default external publish and record flow.
- **`manual-confirm`** — pause after composing the publish payload and wait for
  the operator to confirm the live URL before calling `publish.recordExternal`.
- **`db-direct`** — publish through an internal website/database tool exposed
  to the main thread, then record the DB primary key as `external_ref`.
