---
name: content-refresher
description: Snapshot a refresh_due article into article_versions via article.createVersion, run a material-change refresh plan, delegate editor/humanizer/EEAT/schema/publish as child skill runs, repair stale links, and republish through the primary target.
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
  - article.list
  - article.createVersion
  - article.listVersions
  - interlink.repair
  - schema.list
  - schema.set
  - target.list
  - publish.preview
  - publish.recordPublish
  - redirect.create
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
  - table: article_versions
    write: one row per refresh via article.createVersion — the prior live row snapshots into article_versions; the live articles row becomes the basis for the new version (version+=1).
  - table: articles
    write: the live row's edited_md, status, last_refreshed_at, version, and step_etag are mutated by delegated child skill runs (editor, humanizer, eeat-gate, schema-emitter, publisher); the refresher itself does not rewrite content.
  - table: schema_emits
    write: the delegated schema-emitter (#16) re-emits per-type rows with the new version_published; the refresher reads / lists / sets via schema.list and schema.set when the chain calls require version coordination.
  - table: article_publishes
    write: the delegated publish skill (#17/18/19) writes one row per refresh with the new version_published and the canonical published_url.
  - table: runs
    write: the chained-skill run ids (each child skill writes its own run row), the version snapshot id, the refresh reason, the broken-link repair count, and the schema re-emit count in runs.metadata_json.content_refresher.
---

## Shared operating contract

Before executing, read `../../references/skill-operating-contract.md` and
`../../references/seo-quality-baseline.md`. Apply the shared status, validation,
evidence, handoff, people-first, anti-spam, and tool-discipline rules before the
skill-specific steps below.

## When to use

Procedure 7 (`monthly-humanize-pass`) calls this skill once per article whose `articles.status='refresh_due'`. The refresh-detector (#23) populated the queue; the content-refresher consumes it. The skill is the orchestrator that runs the production chain against an existing article, snapshotting the prior version into `article_versions` first so the history is preserved.

The refresher does NOT re-author the editor / humanizer / EEAT gate / schema-emitter / publisher. The current operator agent delegates those skills as caller-owned child runs by calling `run.start(kind='skill-run', parent_run_id=<refresher_run_id>, skill_name=<child skill>)`, switching to the returned child `run_token` for that skill's MCP calls, finishing that child run, then returning to the refresher token to record the handoff. The daemon does not spawn hidden writer sessions.

The skill also runs in operator-invoked one-off mode when the operator clicks "refresh now" on `ArticleDetailView.vue` for an article they manually flagged for refresh. The contract is identical; the difference is procedure-7-driven runs come with a fresh `run_id` per article and the per-skill child runs are linked via `runs.parent_run_id` to procedure 7's parent run, while operator-driven one-offs link to a parent run created by the operator's UI request handler.

## Inputs

- `project.get(project_id)` — returns `domain`, `locale`, the `schedule_json` (refresh tuning knobs the chain reads), the `voice_id` mapping, and the project's primary publish-target id (used to drive the re-publish step).
- `voice.get(project_id)` — the active voice profile. The editor and humanizer steps read voice via the same `voice.get` call; the refresher pre-reads it so a credential failure is caught before the chain spins up.
- `compliance.list(project_id)` — the active compliance rules. The editor needs them when validating that compliance-rendered prose survived the refresh untouched (compliance bodies are immutable across versions).
- `eeat.list(project_id)` — the active EEAT criteria. The eeat-gate (which procedure 7 wraps around the refresher per the procedure's wider chain — note the gate is a procedure-level step, not a refresher-level delegation) reads the criteria to score the refreshed body.
- `article.get(article_id)` — the live article row. The skill reads the existing `edited_md` (the body to refresh), `brief_json` (the immutable contract — the refresh does not change the brief, only the rendered prose), `slug`, `title`, `published_url`, `last_refreshed_at`, `version`, `author_id`, `canonical_target_id`, and the live `step_etag`. Confirm `status='refresh_due'`.
- `article.list(project_id, status='refresh_due', limit=1, after_id=:focal_article_id-1)` — only used in the rare audit-mode where the skill confirms the focal article is still in the refresh queue between delegation and the first write.
- `article.createVersion(article_id, refresh_reason=…)` — the snapshot writer. Repository copies the live row's `brief_json`, `outline_md`, `draft_md`, `edited_md`, `frontmatter_json`, `published_url`, `published_at`, `voice_id_used`, and `eeat_criteria_version_used` into a new `article_versions` row; bumps `articles.version`; returns the version row's id. The refresh_reason carries the score breakdown from refresh-detector's audit row so the version's history is self-explanatory.
- `article.listVersions(article_id)` — used post-snapshot to confirm the prior version is durable before the chain mutates the live row.
- `interlink.repair` — repairs broken applied internal links on the article. Repository walks every `internal_links WHERE from_article_id=:focal AND status='applied'` row and re-validates the destination article's slug + canonical URL; rewrites anchors when the destination's slug changed since the link was applied; marks rows as `broken` and queues a replacement suggestion when the destination was unpublished. The refresher invokes `interlink.repair` after the body is refreshed but before the publish step.
- `schema.list(article_id)` and `schema.set(article_id, type=…, schema_json=…, is_primary=…, version_published=…)` — used by the schema-emitter's `refresh` variant. The refresher reads the existing rows to confirm the version_published handoff and the delegated emitter rewrites them with the new version.
- `target.list(project_id)` — the publish target roster. The refresher reads `is_primary` and `kind` to decide which publish skill to delegate (#17 nuxt / #18 wordpress / #19 ghost).
- `publish.preview(article_id, target_id)` — used pre-publish to dry-run the payload and capture any preview-time validation failures (slug collision in the target repo, broken canonical URL, asset-rewrite gap).
- `publish.preview(article_id, target_id)` — blocks republish when rendered output would introduce indexability, canonical, robots/noindex, structured-data, public-image, paid-link, or sitemap/lastmod regressions.
- `publish.recordPublish(article_id, target_id, version_published, published_url, frontmatter_json, status, error?)` — written by the delegated publish skill, not by the refresher directly. The refresher reads the resulting `article_publishes` row id for the audit.
- `redirect.create` — writes a 301 only when an operator-approved pre-publish slug change is unavoidable. Never publish a changed slug without this redirect succeeding first.
- `meta.enums` — surfaces `articles.status` transitions, `article_versions.refresh_reason`, and the `runs.kind` enum strings.

## Steps

The skill is a thin coordinator. When a numbered step needs another skill, the current operator agent owns that delegation: run the referenced skill in the current thread or a caller-owned subagent, but bind all child MCP calls to a child `run_token` whose `skill_name` matches the delegated skill. Record each child run id and status before continuing. Do not call a child skill's write tools while still bound to the refresher grant.

1. **Read context.** Resolve the article. Confirm `status='refresh_due'`. Pull the brief, voice, compliance, EEAT criteria, and the live `step_etag`. Compute the refresh reason from refresh-detector's audit row (`refresh_detector_run_id` may arrive via procedure args; the refresher reads `runs.metadata_json.refresh_detector.per_article[article_id]` to extract the score breakdown). Capture the prior `articles.version` for the audit.
2. **Build the material-change plan.** Refresh only when something meaningful changed: user intent, SERP competitors, GSC query mix, source freshness, product/pricing/legal facts, screenshots/assets, schema eligibility, compliance requirements, or internal-link/canonical state. Pure rhythm polish does not update `last_refreshed_at` or `dateModified`; it can produce a humanizer audit only. Persist `{material_change: bool, change_reasons[], evidence[]}` before snapshotting.
3. **Pre-flight target resolution.** Call `target.list(project_id)` and find the `is_primary=true` row. The refresh re-publishes through the primary target only; secondary targets are queued via `publish_target.replicate` after the primary refresh succeeds (the replicate path is procedure-7's responsibility, not the refresher's). Confirm the primary target is `is_active=true`. When the primary is inactive (the operator deactivated the target since the prior publish), abort with `runs.metadata_json.content_refresher.no_active_primary=true`; the operator either re-activates the target or aborts the refresh queue.
4. **Snapshot via `article.createVersion`.** Call `article.createVersion(article_id, refresh_reason=<reason_string>)`. The repository copies the live row into a fresh `article_versions` row (the prior version is preserved in full), bumps `articles.version`, and returns the version id. Capture the version id in the audit row. The snapshot is the load-bearing safety net: every subsequent step mutates the live row but the prior version is durable on disk; a chain failure can roll back by overwriting `articles` from the snapshot row's columns.
5. **Verify the snapshot.** Call `article.listVersions(article_id)` and confirm the just-snapshotted row is present at the top of the list. The verification catches the rare race where `createVersion` returned success but the row is not yet visible (transactional isolation gap on a concurrent reader). When the snapshot is not visible after a 1-second backoff and one retry, abort the run before any chained step runs — the snapshot must be durable before the live row mutates.
6. **Re-edit via skill #10 (editor).** Delegate the editor against the live article row using a child skill run. The editor reads `edited_md` from the live row (which still holds the prior version's body until the editor writes), runs the ten-section editorial pass, and persists the rewritten body via `article.setEdited`. The editor's `refresh` variant scopes the work to material changes and documented AI-tell repairs. Record the child run id, status, and handoff summary.
7. **Optionally chain humanizer (skill #12) per audit P-I1.** When the project's voice profile permits humanizing and the material-change plan warrants prose rewriting, delegate the humanizer against the just-edited body using a child skill run. The "once per article version" invariant is preserved because the version was just bumped. When the voice forbids humanizing or the plan is cosmetic-only, skip this step and surface the reason.
8. **Run EEAT gate as a child skill.** Delegate skill #11 against the refreshed body. SHIP is required before republish. FIX loops back to the editor child run within the procedure loop cap. BLOCK marks this candidate aborted-publish and skips to the next refresh candidate; do not publish.
9. **Repair broken interlinks via `interlink.repair`.** Call `interlink.repair(from_article_id=<focal>)`. The repository walks every applied outbound link from the article, re-validates each destination's slug + canonical URL, and either repairs in place (when the destination's slug or URL drifted but the destination is still published) or marks the link as `broken` and queues a fresh suggestion (when the destination was unpublished or hard-deleted). Capture the repair count and the broken-link count in the audit row.
10. **Re-emit schema via skill #16 (schema-emitter).** Delegate the schema-emitter's `refresh` variant against the live article row. The emitter reads the existing `schema_emits` rows for the article, recomputes each blob with the new `dateModified` only when `material_change=true`, the new `version_published`, and any updated metadata, then writes back via `schema.set`.
11. **Re-publish via the appropriate publish skill.** Read the primary target's `kind`, call `publish.preview`, and delegate the matching publish skill:
   - `kind='nuxt-content'` → skill #17 (nuxt-content-publish).
   - `kind='wordpress'` → skill #18 (wordpress-publish).
   - `kind='ghost'` → skill #19 (ghost-publish).
   The publish skill's `refresh` variant (documented in each skill) PUTs the refreshed body to the existing remote post (not POST a new one) using the post id stored in `article_publishes.frontmatter_json.<target>_post_id`. The publish skill writes the new `article_publishes` row with the new `version_published` and the canonical `published_url`. Capture the publish row id in the audit.
12. **Pre-publish slug-change handling.** When the editor or the brief-renderer changed the article's slug pre-publish, require explicit operator approval and call `redirect.create` before publishing. The redirect is `kind='301'`. When the redirect write fails, abort before publish. When the slug is unchanged, no redirect row is written.
13. **Status / timestamp handoff.** The publish skill's success path advances `articles.status` from `eeat_passed` to `published`. Update `last_refreshed_at` and `dateModified` only when `material_change=true`; cosmetic polish is recorded in run metadata without pretending the facts changed.
14. **Persist the audit row.** Write `runs.metadata_json.content_refresher = {prior_version, new_version, snapshot_version_id, refresh_reason, material_change, change_reasons, delegated_skills: [{skill, child_run_id?, status, duration_ms}], slug_changed, redirect_id?, interlink_repair_count, interlink_broken_count, schema_reemit_count, primary_target_id, publish_row_id, published_url, last_refreshed_at_iso?}`. Heartbeats fire after every delegated-skill completion so the run timeline stays inspectable.
15. **Finish.** Call `procedure.recordStep` with `{article_id, prior_version, new_version, snapshot_version_id, delegated_skill_count, interlink_repair_count, schema_reemit_count, publish_row_id, published_url, material_change}`. The current operator agent then advances to the next refresh-due article or queues secondary-target replication per the project configuration.

## Outputs

- `article_versions` — one row per refresh via `article.createVersion`; the prior live row is preserved in full.
- `articles` — `version` bumped, `edited_md` rewritten by the editor / humanizer chain, `last_refreshed_at` set only when `material_change=true`, `status` advanced through `edited → eeat_passed → published` by delegated child skill runs, `step_etag` rotated.
- `schema_emits` — re-emitted per-type rows with the new `version_published` and the updated `dateModified`.
- `article_publishes` — one row per refresh via the delegated publish skill, carrying the new `version_published` and the canonical URL.
- `internal_links` — repaired in place via `interlink.repair`; broken links marked and queued.
- `redirects` — a `kind='301'` row when the slug changed pre-publish.
- `runs.metadata_json.content_refresher` — the chained-skill log + the snapshot id + the per-step counts + the EEAT-pending flag.

## Failure handling

- **Article status is not `refresh_due`.** Abort. Procedure 7 is the legitimate caller and it filters by status; an off-status call is a coordination bug. Surface `runs.metadata_json.content_refresher.unexpected_status=<actual_status>`.
- **Snapshot via `article.createVersion` fails.** Abort BEFORE any chained step runs. The snapshot is the rollback safety net; without it, a chain failure mid-step leaves the live row in an inconsistent state with no recovery path. Surface `runs.metadata_json.content_refresher.snapshot_failed=true` and let the operator triage. The refresh queue retains the article in `refresh_due`; the next procedure-7 run picks it up after the operator addresses the underlying cause.
- **Editor delegation fails (FIX-loop reaches the cap, or a transient error).** The snapshot is durable; the live row's `edited_md` is the editor's last-attempted output. The refresher does NOT roll back to the snapshot — the operator may want to inspect the partial edit. Surface `runs.metadata_json.content_refresher.editor_failed=true` with the child run id; the procedure agent stops the refresh chain for this article and the operator decides next steps.
- **Humanizer delegation aborts on voice-drift score above 60.** The humanizer's documented behaviour rolls back to the editor's `edited_md`; the refresher inherits that rollback before interlink repair by reading the live row after the child run. Surface `runs.metadata_json.content_refresher.humanizer_voice_drift=true`. The chain continues with the editor-only body; the EEAT gate reads that body downstream.
- **Interlink repair encounters a destination article that no longer exists.** The repair tool marks the broken link and surfaces the count. The refresher captures the count and continues; the publish chain still runs because the broken link is a soft signal, not a hard publish blocker. The operator's UI surfaces the broken-link list for human triage.
- **Schema re-emission fails for a single type (e.g., FAQ schema rejected by the validator).** The delegated emitter's `refresh` variant treats this as block-this-type, not block-the-run. The refresher continues; the failed type is in the audit row and the publish step still emits the principal Article / BlogPosting blob.
- **Publish returns a 4xx from the publish target's API (auth revoked, post deleted remotely).** The publish skill writes a `failed` `article_publishes` row with the error. The refresher captures the row id and surfaces `runs.metadata_json.content_refresher.publish_failed=true`. The article remains in the chain's last successful status (`eeat_passed`); the operator re-authorises the target or addresses the remote-side issue and the procedure agent retries or forks.
- **Slug change but the redirect write fails.** Abort before the publish step. Surface `runs.metadata_json.content_refresher.redirect_write_failed=true`. The publish without a redirect would orphan the prior URL; the refresher refuses to publish in that state. The operator addresses the underlying redirect-write issue (likely a permissions or schema regression).
- **Two consecutive refreshes on the same article without procedure 7 advancing the status.** Means the eeat-gate is rejecting the refresh repeatedly. Refresh-detector won't re-mark because the article is already `refresh_due`. Surface `runs.metadata_json.content_refresher.eeat_block_recurrence_count` (read from prior runs) so the operator can decide whether the EEAT criteria are too tight or the editor is regressing on a specific dimension.
- **Etag mismatch on `article.createVersion`.** Refresh via `article.get`, retry once. Two consecutive mismatches abort.
- **Procedure 7 budget cap exceeded mid-chain.** The delegated skill's `cost.queryProject` pre-flight check should catch this; when it slips through (concurrent runs racing on the budget), the delegated skill aborts. The refresher captures the abort and surfaces `runs.metadata_json.content_refresher.budget_capped=true`. The chain stops; the procedure agent skips the remaining refresh-due articles.

## Variants

- **`fast`** — runs only the editor + interlink repair + publish delegation; skips humanizer + schema re-emit. Useful when the project's voice forbids humanizing on refresh AND the schema package is known-stable (e.g., the project has only the principal Article blob and no rich-result optional types). The publish skill's `refresh` variant still updates `dateModified` regardless because the publish step rewrites the frontmatter from the brief at every call.
- **`standard`** — the default flow above, full chain.
- **`schema-only`** — runs only the schema re-emit + a publish delegation that updates the JSON-LD inline in the rendered HTML / frontmatter, without touching the body. Useful when refresh-detector flagged the article on schema-drift signal alone (the editor pass would not change anything substantive).
- **`audit-only`** — composes the per-step plan, persists the audit row carrying the delegation sequence + estimated costs, but does NOT actually run any of the chained skills. Used for refresh-cost forecasting where the operator wants to know what the chain would burn before committing to a project-wide refresh sweep.
