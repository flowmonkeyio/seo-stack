# content-stack — PLAN.md Audit

Three parallel reviews: an architect (Plan agent), an adversarial second-pass (general-purpose with ruthless framing), and a verifier (general-purpose checking factual claims). Raw agent outputs preserved under `docs/_audit-raw/{plan,adversarial}.md`; the verifier's report is reproduced in §6 of this doc.

Sources flagged per finding: **(P)** Plan-agent, **(A)** adversarial, **(V)** verifier. Findings agreed by both design agents have both flags.

---

## 1. Executive summary

| | Count |
|---|---|
| BLOCKERs (must resolve before M0 sign-off) | 28 |
| MAJORs (must resolve before M2 — DB+repos) | 25 |
| MINORs (deferrable) | 19 |
| Strip-map citations checked | 63 |
| Strip-map citations VERIFIED | 33 |
| Strip-map citations OFF_BY_N | 16 |
| Strip-map citations PARTIAL | 8 |
| Strip-map citations UNGROUNDED | 6 |

Headline: **PLAN.md is structurally sound; vision and phasing are coherent; locked decisions are good.** But the foundation cannot be built from this doc alone. Eight architectural calls need the user's input before any code lands; the remainder are schema/contract additions that follow from those calls.

After the recommended amendments PLAN.md grows from 651 lines to roughly 900 lines (six new tables, three new contract sections, two ops subsections, originals coverage in strip map). Implementation estimate revises **25d → 28d**.

---

## 2. Top 5 risks if shipped as-is

**(verbatim from adversarial agent — these are the failure modes a real user hits in week 1)**

1. **Cody's license blows up the editor pass.** Seven of our 24 skills source from a repo whose license forbids "different or competing frameworks." The strip-map's "we'll re-author and call it fair use" posture is exactly the kind of legal hand-wave that gets a project DMCA'd in week three — *and* it's an easy fix (clean-room reauthor, or pivot the editor source) if we decide pre-M0 instead of post-M7. Worse, codex-seo's own license is internally inconsistent, and our installer literally clones it. Both must be resolved before any skill author touches a `cody` or `codex-seo` file.

2. **Concurrency on a SQLite WAL with a fat `articles` row + parallel procedure-4 runs is going to corrupt content silently.** The plan acknowledges WAL contention but mitigates with "short transactions" — that doesn't address the actual failure mode, which is two skills writing different columns of the same `articles.id` and the second clobbering the first because there's no etag. At concurrency=8 in bulk launch, this happens within hours. Drafts disappear, status moves forward, the user finds a published article that's not what they reviewed.

3. **The EEAT gate can be silently disabled by a project owner.** The schema lets a project deactivate every EEAT criterion including the three veto items. The plan calls EEAT a "gate" but doesn't enforce a floor. The whole product value proposition turns into a configurable rubber stamp.

4. **The procedure runner is unspecified for context-window pressure and crash recovery.** Procedure 4 is 9–10 sequential skills with mutually-dependent state. PLAN.md never says whether the LLM client orchestrates or the daemon does. It never says how `runs.status='running'` gets reaped after a crash or sleep. A user who runs procedure 5 against 50 topics and lets their laptop sleep returns to 50 forever-`running` rows, no resume button, and a DB that procedure-replay misinterprets.

5. **Cost runaway and rate-limit blowups are post-hoc, not preventative.** Bulk-launch with no per-integration budget cap, no rate-limit token bucket, and no cascade-abort means the first user to type `/procedure bulk-content-launch 100` sets fire to their DataForSEO/Firecrawl/OpenAI bills before the daemon can track it. The plan logs spend in `runs.metadata_json` *after* the call. Pre-emptive `integration_budgets` table + per-integration token bucket + `run.abort` cascade are required day-one features, not v1.1.

---

## 3. User decisions needed (the calls only you can make)

These are architectural calls; the rest of the audit's amendments follow once these are locked. Recommendation in **bold** for each.

**D1. Cody license posture.** The editor pass + 6 other skills derive from `cody-article-writer` whose license forbids "different or competing frameworks" or any derivative work. Three options:
- **(Recommended) Clean-room re-author from first principles.** Skill authors for #4, #6, #7, #8, #9, #10, #24 do NOT read any cody file; only PLAN.md + general editorial knowledge. Document the clean-room procedure in `docs/attribution.md`. CI fingerprint check rejects substrings from cody verbatim text.
- Email Red Pill Blue Pill Studios for a written exception. Slow + likely silence.
- Drop cody as a source; pivot editor pass to seo-geo-claude-skills (Apache-2.0, weaker patterns).

**D2. codex-seo `--with-codex-seo` installer flag.** PLAN.md L498–499 recommends `scripts/install-codex.sh --with-codex-seo` that clones the upstream into the user's home. The upstream LICENSE is Avalon Reset proprietary (forbids derivative works for distribution; requires "active membership"). Inducing the install via our scripts is contributory.
- **(Recommended) Drop the flag entirely.** Users who want codex-seo install it themselves; documented in `docs/extending.md`.
- Keep, with prominent license-notice on first run.

**D3. Multi-locale.** `projects.locales` is plural but no skill, procedure, or article has locale awareness. PLAN.md L620 says translation is out of scope. Pick one:
- **(Recommended) Singular.** Change `projects.locales` → `projects.locale TEXT NOT NULL`. Drop the multi-locale claim. Multi-locale = separate project per locale.
- Multi-locale for real. Adds locale columns to articles/topics, locale-aware interlinker, hreflang in schema-emitter, per-locale publish targets, optional translator skill #25. Significant scope.

**D4. Procedure orchestration model.**
- **(Recommended) Daemon-orchestrated.** `procedure.run(slug, args)` enqueues a server-side runner (APScheduler) which calls back into MCP via fresh per-skill LLM sessions. The user's LLM only kicks off and polls. Tight context window per skill. Requires the daemon to hold its own LLM credentials (one of OpenAI/Anthropic, separate from the runtime's).
- LLM-orchestrated. The calling LLM walks the playbook, fetches state via MCP, calls each skill itself. Subject to context-window pressure on long procedures.

**D5. Daemon authentication.** "Localhost only, no auth" doesn't survive contact with browser CSRF, cross-process drive-bys from any local Claude Code/Codex instance, or local malware.
- **(Recommended) Per-install bearer token.** `~/.local/state/content-stack/auth.token` (32 bytes, 0600). Every REST + MCP request requires `Authorization: Bearer <token>`. Install scripts inject it into Codex's MCP config and `.mcp.json`. Rotation on `make install` re-run. Refuse non-local `Host:` headers. CORS same-origin. Doctor verifies token mode 0600.
- Stay open. Accept the CSRF + cross-process risk.

**D6. Articles versioning.**
- **(Recommended) Separate `article_versions` table.** `articles` keeps current; `article_versions` carries history. `article.createVersion` MCP copies live → versions before mutating.
- Self-FK on `articles` with `parent_article_id` and `archived` status. Fragile — requires partial unique index on slug.

**D7. EEAT floor.** Pick one:
- **(Recommended) `eeat_criteria.tier` enum (`core`/`recommended`/`project`).** 3 veto items (T04/C01/R10) seeded as `tier='core'`; cannot be deactivated, `required` cannot be toggled off. Procedure 4 EEAT gate refuses to score if coverage < 100% (all 8 dimensions active).
- Soft-only: warning in UI when criteria deactivated. Lets projects rubber-stamp.

**D8. UI dist artifacts.** PLAN.md is contradictory: L170 says `ui_dist/` is gitignored; L574–575 says "built once and committed for installs without pnpm."
- **(Recommended) Commit the bundle.** Drop `ui_dist/` from `.gitignore`. CI verifies the committed bundle matches `ui/src/`. Lowers the install floor — no pnpm required.
- Pnpm at install. Higher install floor, smaller repo.

Once you call these eight, I patch PLAN.md to reflect the locks and apply the cascade of schema/contract amendments. No code changes until PLAN.md is sealed.

---

## 4. BLOCKERs (must resolve before M0 sign-off)

Numbering aligns with the consolidated audit, not the source agents.

### Architecture / contract

**B-01 (V).** PLAN.md L278 still says "14 tables"; actual is 16, growing to ~22 with this audit's additions.
*Fix:* Update L278 to "22 tables" (or final count).

**B-02 (P-A1).** `make install` and `make build-ui` referenced (L574, L642–643) but no Makefile section enumerates targets.
*Fix:* Insert "Makefile targets" subsection after L119 listing 14 targets with semantics, idempotency, daemon dependence.

**B-03 (P-A2).** `cli.py # serve | init | migrate | install | doctor` (L133) — no spec for any subcommand, flags, or exit codes.
*Fix:* Add "CLI reference" section after L537. Per subcommand: name, args/flags, side effects, exit codes (0/1/2/3/4 for success/misuse/dep-missing/db-locked/migration-failed).

**B-04 (P-A3).** PROCEDURE.md frontmatter unspecified. PLAN.md L432–435 alludes to fields but never declares which are YAML frontmatter vs. markdown body.
*Fix:* Insert canonical YAML frontmatter spec after L437: `name, version, triggers, prerequisites, produces, steps[{id, skill, mcp_calls, on_failure}], variants, concurrency_limit, resumable`.

**B-05 (P-A6, A7).** JSON column shapes for `articles.frontmatter_json` and `runs.metadata_json` are undefined. Both are referenced 5+ times each.
*Fix:* Add "JSON column shapes" subsection after L309. `articles.frontmatter_json` is per-publish-target flat map (depends on D6+D8 publishing model). `runs.metadata_json` is a discriminated union by `runs.kind` — list 12 kinds and required keys for each.

**B-06 (P-A10).** `db/seed.py` referenced (L140, 590, 591) but content unspecified. Strip map implies it seeds 80-item EEAT, schema templates, default voice, default compliance — none in PLAN.md.
*Fix:* Add "Seed data" subsection after L309. Seeds: 0 rows in project-scoped tables; default `eeat_criteria` rows seeded *at project creation* (with 3 `tier='core'` rows from D7); default `schema_emits` templates. Spec: idempotent via `INSERT OR IGNORE`.

**B-07 (A-01).** Fat-row + parallel procedure-4 corruption. Two skills writing different columns of the same `articles.id` clobber each other; no etag/ownership.
*Fix:* Add `articles.owner_run_id`, `articles.step_etag` (UUID, regenerates each step), `articles.current_step`, `articles.step_started_at`. Every `article.set*` MCP tool requires `expected_etag`; mismatch → 409. Add `MAX_CONCURRENCY` env var, default 4. Add benchmark to M2 acceptance: 100 sequential `article.setDraft` of 200KB each <2s.

**B-08 (A-02).** `articles.published_url` is single-valued; `publish_targets` is many-per-project. Multi-target publishes have nowhere to land URLs; drift baselines + interlinker assume one canonical URL.
*Fix:* New table `article_publishes(id, article_id, target_id, published_url, published_at, version_published, status, error)`, PK `(article_id, target_id, version_published)`. Drop `articles.published_url`/`published_at`. Add `articles.canonical_target_id` FK so interlinks/drift know the authoritative URL. Procedure 4 publish step fans out across `publish_targets WHERE is_active=true`.

**B-09 (A-03).** EEAT gate rubber-stamp risk. `eeat_criteria.required` and `eeat_criteria.active` can both be toggled off for every row, including the 3 veto items.
*Fix (D7):* Add `eeat_criteria.tier ENUM('core','recommended','project')`. T04/C01/R10 seeded `tier='core'`; rules with `tier='core'` cannot have `required=false` or `active=false` (repository invariant + 422). Procedure 4 EEAT gate computes coverage; refuse to score if any dimension has 0 active items. Add `eeat_criteria.text` so the row is self-describing if upstream renumbers.

**B-10 (A-04).** No per-skill MCP-tool whitelist; any skill can call any tool, including `article.markPublished` (skip EEAT) or `project.delete`.
*Fix:* Define a tool-grant matrix in `docs/extending.md`. `run.start` returns a `run_token`; every subsequent tool call carries it. Server enforces `tool ∉ whitelist[skill] → 403`. State-machine invariant on `articles.status`: `published` requires prior `eeat_passed` AND a corresponding `runs.kind='eeat-gate', status='success'` row. Add `run.abort(run_id, cascade=true)` MCP tool.

**B-11 (A-05).** Cody license. **See D1.** Until decided, M7 skill-authoring track is blocked for skills #4, #6, #7, #8, #9, #10, #24.

**B-12 (A-06).** codex-seo Avalon Reset license. **See D2.** Drop `--with-codex-seo` from PLAN.md L498–499. Apply same clean-room rule for skills #1, #2, #3, #14, #16, #20, #21, #22 — no verbatim prompts/scripts.

**B-13 (P-B5+F2, A-07).** Daemon crash recovery. `runs.status='running'` orphans on crash/sleep; no resume points; no heartbeat.
*Fix:* New table `procedure_run_steps(id, run_id, step_index, step_id, status, started_at, ended_at, output_json, error)`. Add `runs.heartbeat_at`, `runs.last_step`, `runs.last_step_at`, `runs.parent_run_id`, `runs.client_session_id`. APScheduler heartbeats every 30s. On startup, daemon scans `running AND heartbeat_at < now()-5min` → mark `aborted` with `error='daemon-restart-orphan'`. New MCP `run.heartbeat`, `run.resume`, `run.fork`. PROCEDURE.md frontmatter declares `resumable: true|false`.

**B-14 (A-08).** Daemon auth. **See D5.** Per-install bearer token + CORS same-origin + Host header check.

**B-15 (P-B1).** `refresh_detector`'s scheduling query has no expressible schema. `articles.last_evaluated_for_refresh_at` doesn't exist; `gsc_metrics(article_id, captured_at)` index missing.
*Fix:* Add `articles.last_evaluated_for_refresh_at TIMESTAMP NULL`. Add indexes `idx_gsc_metrics_article_time` and `idx_articles_status_project`. Document the canonical query.

**B-16 (P-B2).** `topics.priority` scale + tiebreaker undefined. Bulk-launch needs deterministic order.
*Fix:* `priority INTEGER 0–100; NULL=50; higher=sooner; tiebreaker (priority DESC, created_at ASC, id ASC)`.

**B-17 (P-B4).** `articles.version` is just a column; prior bodies are lossy. **See D6.** Add `article_versions` table.

**B-18 (P-B5).** `procedure_run_steps` table needed for resume. Subsumed in B-13.

**B-19 (P-B7).** `authors` table missing. EEAT rubric requires per-article author attribution; no `articles.author_id` exists.
*Fix:* New table `authors(id, project_id, name, slug, bio_md, headshot_url, role, credentials_md, social_links_json, schema_person_json, ...)`. Add `articles.author_id` and `articles.reviewer_author_id` FKs.

**B-20 (P-B10).** `eeat.score` MCP exists (L372) but no per-criterion result storage. `runs.metadata_json` holds dimension scores but per-item grain is unqueryable.
*Fix:* New table `eeat_evaluations(id, article_id, criterion_id, run_id, verdict, notes, evaluated_at)`, index `(article_id, run_id)`.

**B-21 (P-C7, A-MAJOR-16).** Procedure run sync vs. async unspecified. Procedures take minutes-hours; the LLM context window doesn't survive 9 sequential skill calls.
*Fix (D4):* Procedure runs are async, daemon-orchestrated. `POST /procedures/{slug}/run` returns 202 `{run_id, status_url, started_at}`. Daemon dispatches per-skill subprocess sessions; LLM client only polls.

**B-22 (P-D1, D5).** MCP contract undefined: pydantic schemas, idempotency keys, error model, result envelope.
*Fix:* Insert "MCP tool contract" subsection after L388: every tool has `tools/<name>.py` with Input/Output pydantic models; mutating tools take optional `idempotency_key`; return envelope `{data: T, run_id: int, project_id: int}`; read tools return bare. Error codes: validation -32602, not-found -32004, conflict -32008, integration-down -32010, rate-limited -32011, internal -32603. Add CI check.

**B-23 (P-E1).** Active-project resolution. MCP is stateless across calls; "active project" is racy across two clients.
*Fix:* Per-call `project_id` parameter on every project-scoped tool. `project.setActive`/`getActive` mutate UI state only. Skills read `project_id` from procedure context (env var `CONTENT_STACK_PROJECT_ID` set by procedure runner) and pass through every call.

**B-24 (P-G1).** Install scripts are not idempotent. `cp -R skills/*` overwrites; `register-mcp-claude.sh` clobbers existing `.mcp.json`; `seed.py` may duplicate rows.
*Fix:* Per-script semantics in PLAN.md "Install script semantics" subsection. `rsync -a --delete` for skills; `register-mcp-claude.sh` reads → upserts → atomic write with `.bak`; `install-launchd.sh` diffs before overwriting; `seed.py` `INSERT OR IGNORE` with stable IDs.

**B-25 (P-H1, H2).** Encryption seed location not specified. Cross-machine DB copy fails silently because seed is per-machine.
*Fix:* Specify `~/.local/state/content-stack/seed.bin`, 32 bytes from `os.urandom`, mode 0600, refuse to start if mode wrong. HKDF-SHA256 with seed as IKM and constant info string. Per-row 12-byte nonce stored alongside ciphertext. Add `nonce BLOB NOT NULL` column. AAD per row = `f'project_id={p}|kind={k}'`. `make backup` includes seed; restore without seed prompts user via doctor: "re-enter API keys".

**B-26 (P-B8, I3).** `compliance_rules.position` undefined.
*Fix:* Enum `header|after-intro|footer|every-section|sidebar|hidden-meta`. Within position, ordered by id ASC. Draft-conclusion renders `position='footer'`; draft-intro renders `position='header'` or `after-intro`.

**B-27 (P-I5).** `articles.slug` uniqueness scope unstated.
*Fix:* `UNIQUE(project_id, slug, COALESCE(locale, ''))`. Slug auto-generated kebab-case from title, max 80 chars, editable. UI/MCP refuse on conflict with 409 + suggestion.

**B-28 (P-J1).** Strip-map omits 7 "original" skills (#5, #12, #13, #17, #18, #19, #23). Authors will search for non-existent upstream files.
*Fix:* Add "Original skills (no upstream)" section to `docs/upstream-stripping-map.md`. Per skill: 1-paragraph algorithm sketch, DB tables touched, MCP tools used, key risks. PLAN.md L423 forward-references this section.

---

## 5. MAJORs (must resolve before M2 — DB+repos)

Compact list. Detail in `_audit-raw/`.

| ID | Title | Source | Loc | Fix one-liner |
|---|---|---|---|---|
| M-01 | GSC schema explosion at scale | P-B3, A-MAJOR-14 | L293 | Add `gsc_metrics_daily` rollup, dedup hash, retention policy |
| M-02 | Multi-locale incoherence | P-B6, A-MAJOR-19 | L282, 620 | **See D3** |
| M-03 | `compliance_rules.kind='custom'` is unstructured | A-MAJOR-17 | L284 | Add `params_json`, `validator` columns |
| M-04 | `internal_links` no uniqueness constraint | P-B9 | L290 | Partial unique index excluding `dismissed` |
| M-05 | `internal_links` no broken/unpublished path | A-MAJOR-13 | L290 | Add `broken` status; `interlink.repair` MCP |
| M-06 | `runs.parent_run_id` + `procedure_slug` | P-B12 | L295 | Add cols; supports cascade abort |
| M-07 | `topics.intent` enum | P-B13 | L287 | `informational\|commercial\|transactional\|navigational\|mixed` |
| M-08 | `clusters.type` enum | P-B14 | L286 | `pillar\|spoke\|hub\|comparison\|resource` |
| M-09 | `article_assets.kind` enum | P-B15 | L289 | `hero\|inline\|thumbnail\|og\|twitter\|infographic\|screenshot\|gallery` |
| M-10 | `redirects` table for slug change | P-B16 | L288 | Refresh procedure writes 301/302 records |
| M-11 | Hot-path indexes missing | P-B17 | L309 | Composite indexes for 5 hot queries |
| M-12 | Monthly cost endpoint missing | P-C1 | L636 | `GET /projects/{id}/cost?month=` + `cost.queryProject` MCP |
| M-13 | Bulk operations missing | P-C2 | L374 | `article.bulkCreate`, `topic.bulkUpdateStatus`, `internal_link.bulkApply` |
| M-14 | Pagination convention | P-C3 | L313 | Cursor-based, `?limit=&after=` |
| M-15 | Filter/sort convention | P-C4 | L313 | Filter any enum; `?sort=col\|-col` |
| M-16 | Enum lookup endpoint | P-C5 | L301 | `GET /meta/enums` + `meta.enums` MCP |
| M-17 | REST/MCP coverage parity | P-C6 | L388 | Parity table + add `project.activate` MCP, `GET /articles/{id}/eeat` REST |
| M-18 | Article CRUD: PATCH vs. typed verbs | P-C8 | L343 | Document UI permissive vs. MCP state-machine |
| M-19 | `voice.setActive` missing | P-C9 | L283 | Add MCP + REST |
| M-20 | Idempotency keys absent | P-D2 | L388 | `idempotency_key` table; 24h dedup window |
| M-21 | Streaming model for long tools | P-D3 | L364 | Streaming tools declare `streaming:true`; emit `progress` events |
| M-22 | Cross-project credential leakage | P-E3 | L297 | Resolution order project→global, log `project_id` |
| M-23 | APScheduler concurrency model | P-F1 | L168 | Specify executors, max_instances, misfire policy, job store |
| M-24 | Backup story | P-F4, A-MINOR-27 | L616 | `make backup`/`restore`; weekly auto-backup with retention |
| M-25 | Cost cap + rate-limit pre-emption | A-MAJOR-12 | L447 | `integration_budgets` table; token bucket per integration; `--budget-cap-usd` flag |
| M-26 | LLM credentials confusion | A-MAJOR-11 | L468 | Daemon needs OpenAI key for image gen + (D4) procedure runner; skill LLM calls go through user runtime |
| M-27 | OAuth flow not specified | A-MAJOR-10 | L466 | Spec full GSC OAuth flow + refresh job |
| M-28 | Codex-plugin-cc seam not runtime-conditional | A-MAJOR-20 | L511 | Daemon-side helper; runtime-check; 90s timeout; NOTICE file |
| M-29 | Run-step audit trail missing | A-MAJOR-21 | L295 | New `run_steps` + `run_step_calls` tables |
| M-30 | `frontmatter_json` per-target | A-MAJOR-22 | L288, 292 | Move to `article_publishes.frontmatter_json`; add `publish.preview` MCP |
| M-31 | UI EEAT/interlink review UX | A-MAJOR-23 | L184–202 | Spec ArticleDetailView subviews; bulk-apply for interlinks |
| M-32 | Logging discipline | P-A8 | L531 | structlog JSON; run_id contextvar; rotating handler |
| M-33 | UI MarkdownEditor save semantics | P-A4 | L199 | Optimistic concurrency on `updated_at`; 409 on stale |
| M-34 | TS type generation tool unnamed | P-A5 | L183 | `openapi-typescript`; CI fails on regen diff |
| M-35 | README + PLAN install paths diverge | P-A11 | L642 | `make install` is canonical; README regenerated |
| M-36 | WAL PRAGMAs unspecified | P-F3 | L631 | Connect-time PRAGMAs declared in PLAN.md |
| M-37 | Localhost binding not enforced in code | P-H4 | L95 | CLI rejects `--host 0.0.0.0`; doctor verifies |
| M-38 | Adversarial-review prompt-injection hygiene | P-H5 | L511 | Pass via temp file 0600; XML-tag wrapper |
| M-39 | Schema_emits per-version | A-MAJOR-22 | L292 | Add `version_published` column |
| M-40 | Article-locked-by-run during procedure | A-01 | L288 | `articles.lock_token` + acquire/release |

---

## 6. Strip-map verification report

**Pass 1 — PLAN.md internal consistency** (verifier results):
- 16 tables exact (header L278 says "14"; acknowledged L299; **fix L278**)
- 72 MCP tools exact (PLAN.md says "~70" — tilde absorbs)
- 24 skills exact
- 8 procedures exact
- Implementation total: **25 days exact** (1+2+2+2+3+4+5+3+1+1+1)
- Status enums: **no drift** — every status string in narrative resolves to a declared enum
- All skill cross-references in procedures resolve to catalogue rows
- All integrations referenced in skills are in the integrations table
- REST↔MCP: minor naming nit (`/publish-targets` ↔ `target.*`); REST omits asset list/get (MCP has `asset.list|update|remove`) — asymmetric but acceptable

**Pass 2 — strip-map citations** (sampled 63 across 3 repos):

| Status | Count | Notes |
|---|---|---|
| VERIFIED | 33 | File + line range + content faithful |
| OFF_BY_N | 16 | Mostly off by 1; a few off by 2–4 |
| PARTIAL | 8 | Paraphrase mostly accurate but with notable drift |
| UNGROUNDED | 6 | File exists but cited line range is past EOF or content unrelated |
| MISCITED | 0 | No file-level errors |

**Top discrepancies to fix in `docs/upstream-stripping-map.md`:**

1. All four cody-article-writer file line counts off by +1 (SKILL.md=253→252, article-workflow=548→547, style-schema=128→127, editor-style-guide=244→243).
2. `editor-style-guide.md:200-204` cited for Section 9 → actual 194–198. `:206-210` cited for Section 10 → actual 200–204. ~6-line shift; load-bearing.
3. `content-quality-auditor/SKILL.md:113-115` cited as "three veto items (T04/C01/R10)" — actual content there is example invocation templates; vetoes live in the project's CLAUDE.md and `core-eeat-benchmark.md`.
4. `internal-linking-optimizer/SKILL.md:1-200+` overshoots EOF by ~50 lines (file is 151 lines).
5. "Min 3 incoming internal links per post" and "No more than 2 clicks from pillar to any spoke" attributed to `linking-templates.md` — neither is there. First is in codex-seo `seo-cluster/SKILL.md:158`; second in seo-geo-claude-skills `link-architecture-patterns.md:21`.
6. `article-workflow.md:154-173` paraphrased as "source approval flow" — actual content is a JSON state schema spec.
7. `research-workflow.md:115-121` for depth tiers off by 3 (actual 118–120).
8. `cody LICENSE.md` sub-line citations: "(line 25-28)" for No Public Forking → only line 25; "(line 30-34)" for No Sale → actual 27–31.
9. `seo-google/SKILL.md:142` for "striking distance" off by 1 (actual line 143).
10. `content-quality-auditor/SKILL.md` claimed "200+ lines" understates the actual **689 lines** materially.

LICENSE quotations checked: `codex-seo LICENSE:18-21` and `cody LICENSE.md:20` are both verbatim faithful.

---

## 7. MINORs (post-launch)

Compact bullets. Source agent in parens. Fixes in `_audit-raw/`.

- (P-A12) `procedures-guide.md` content unspecified
- (P-A9) i18n drift — see D3
- (P-B11) `schema_emits` ordering / `is_primary`
- (A-MINOR-24) `topics.priority` ordering convention (lower vs. higher)
- (A-MINOR-25) `projects.slug` global uniqueness; `articles.slug` per-project
- (A-MINOR-26) Telemetry / privacy posture (PRIVACY.md, default off)
- (A-MINOR-28) `_template/PROCEDURE.md` sample frontmatter
- (A-MINOR-29) `doctor.sh` enumerated check list
- (A-MINOR-30) `tests/` per-layer plan
- (A-MINOR-31) `runs.kind` enum declaration
- (A-MINOR-32) Read-only observer token
- (A-MINOR-33) `articles.slug` immutable post-publish (or invalidate links on change)
- (A-MINOR-34) Humanizer + editor interaction on refresh
- (A-MINOR-35) Firecrawl→playwright fallback trigger spec
- (A-MINOR-36) `seed.py` content (subsumed in B-06)
- (A-MINOR-37) `ProjectSwitcher` URL routing pattern
- (A-MINOR-38) `make build-ui` git policy (subsumed in D8)
- (A-MINOR-39) Procedure template excluded from `install-procedures-*.sh`
- (A-MINOR-40) Ahrefs Enterprise-only — note in `docs/api-keys.md`
- (A-MINOR-41) `DELETE /projects/{id}` cascade semantics (or soft-delete)
- (A-MINOR-42) MCP Streamable HTTP client version compat in doctor
- (P-F5) Graceful shutdown
- (P-F6) `/api/v1/health` endpoint
- (P-G2) Upgrade strategy v1→v2
- (P-G3) `doctor.sh` exit codes + `--json` flag
- (P-G4) pipx install path skills source
- (P-H3) Seed rotation command
- (P-H6) Per-tool rate limiting
- (P-I7) Voice variant pinning at brief time
- (P-I8) `publish_targets.is_primary` (subsumed in B-08)
- (P-I9) Codex-plugin-cc per-project opt-in default
- (P-I10) `niche` is freeform display only

---

## 8. Recommended PLAN.md amendment plan (line-level patch list)

Apply in this order. Each fix-ID maps to §4 / §5 above.

**Foundation (lines 86–119)**
1. After L86 (DB diagram): SQLite PRAGMAs subsection (M-36)
2. L95: append localhost-binding enforcement (M-37)
3. After L119 (Tech stack): "Makefile targets" subsection (B-02)

**Schema (lines 278–309)**
4. L278: update count "14" → final count after all additions (B-01)
5. L282: resolve `locales` per D3; add `niche` is-freeform note (P-I10)
6. L283: add voice snapshot pinning (P-I7)
7. L284: define `compliance_rules.position` enum (B-26); add `params_json`, `validator` (M-03)
8. L286: define `clusters.type` enum (M-08)
9. L287: lock `topics.priority` scale + tiebreaker (B-16); define `topics.intent` (M-07); add `topics.locale` per D3
10. L288: add `articles.author_id`, `reviewer_author_id` (B-19), `locale` per D3, `last_evaluated_for_refresh_at` (B-15), `owner_run_id`, `step_etag`, `current_step`, `step_started_at`, `lock_token` (B-07/M-40); slug uniqueness scope (B-27); drop `published_url`/`published_at` per B-08
11. L289: define `article_assets.kind` enum (M-09)
12. L290: add unique index on `internal_links` (M-04); add `broken` status (M-05)
13. L292: add `schema_emits.position`, `is_primary`, `version_published` (P-B11, M-39)
14. L293: add dedup hash + `gsc_metrics_daily` rollup + retention (M-01)
15. L295: add `runs.parent_run_id`, `procedure_slug`, `heartbeat_at`, `last_step`, `last_step_at`, `client_session_id` (B-13, M-06); declare `metadata_json` discriminated-union (B-05)
16. L296: drop `articles.published_url`; add `publish_targets.is_primary` per D6 (subsumed in B-08)
17. After L297: insert new tables — `authors` (B-19), `article_versions` (D6/B-17), `procedure_run_steps` (B-13/B-18), `eeat_evaluations` (B-20), `redirects` (M-10), `article_publishes` (B-08), `gsc_metrics_daily` (M-01), `run_steps` + `run_step_calls` (M-29), `integration_budgets` (M-25), `idempotency_keys` (M-20), `scheduled_jobs` (M-23). Final table count: **22+** depending on D3 choice.
18. L297 (`integration_credentials`): add `nonce`, `kind`, `expires_at`, `last_refreshed_at` (B-25, M-27)
19. After L309: insert subsections "JSON column shapes" (B-05), "Indexes" (M-11), "Seed data" (B-06)

**API (lines 313–388)**
20. L313: add "Pagination convention" + "Filtering / sorting" (M-14, M-15)
21. After L357 (Ongoing): `GET /api/v1/projects/{id}/cost` (M-12)
22. L360: append async semantics for procedure run (B-21/D4)
23. L366: clarify `setActive`/`getActive` are UI-state (B-23)
24. After L376: `article.bulkCreate`, `article.refreshDue`, `article.markRefreshDue` (M-13)
25. L384: `run.children`, `run.cost`, `run.heartbeat`, `run.resume`, `run.fork`, `run.abort(cascade)` (B-13, B-10, M-12)
26. After L388: insert "MCP tool contract", "Idempotency", "Streaming", "Error model", "Result envelope", "REST/MCP parity table", "Tool-grant matrix" subsections (B-22, B-10, M-17, M-20, M-21)

**Procedures (lines 392–453)**
27. L410: lock humanizer "once per article version" (P-I1)
28. L437: add procedure orchestration model + skill frontmatter spec (B-04, B-21, B-23)
29. L446: lock editor placement (P-I2); three-verdict eeat-gate (P-I4); publish-target primary (P-I8/B-08)
30. L421: lock entry points to `refresh_due` (P-I6)
31. After L423: forward reference to "Original skills" section in strip-map (B-28)

**Operations (lines 530–562)**
32. After L537: insert "CLI reference" (B-03), "Logging" (M-32), "Backup" (M-24), "Graceful shutdown" (P-F5), "Health endpoint" (P-F6), "Rate limits" (P-H6), "APScheduler config" (M-23), "Crash recovery" (B-13)
33. After L562: insert "Install script semantics" (B-24), "Upgrade strategy" (P-G2), "doctor.sh check list + exit codes" (P-G3, A-MINOR-29)

**Distribution (lines 568–576)**
34. L569: reconcile pipx vs. clone install paths (P-G4)
35. L170 + L574–575: reconcile per D8 (committed bundle vs. gitignored)

**Security (lines 472–476)**
36. After L476: insert seed file location + permissions + HKDF derivation + AAD spec; cross-machine restore semantics; rotation command (B-25, P-H3)
37. L511: per-project opt-in toggle (P-I9); temp-file passing for adversarial review (M-38); runtime-conditional + 90s timeout + NOTICE file (M-28)

**Risk + sequencing (lines 626–636, 580)**
38. L580: revise day estimates: M1 2d→3d, M3 2d→3d, M9 1d→2d. **Total 25d → 28d.**
39. L636: update cost-runaway mitigation to reference new endpoints + tables (M-25)
40. Add a row about cody/codex-seo license posture (D1, D2)

**Out of scope (lines 614–622)**
41. L614: clarify per-install token enforces single-user binding (D5)
42. L620: per D3, drop multi-locale claim or scope it for real

---

## 9. Recommended strip-map amendment plan

Apply to `docs/upstream-stripping-map.md`:

1. Fix all four cody line counts (item 1 in §6).
2. Re-cite `editor-style-guide.md` Sections 9 + 10 (item 2 in §6).
3. Fix `content-quality-auditor/SKILL.md:113-115` veto-item citation; redirect to `core-eeat-benchmark.md` and project CLAUDE.md (item 3).
4. Fix `internal-linking-optimizer/SKILL.md:1-200+` to actual line range (item 4).
5. Fix the two misattributed "hard targets" anchor citations (item 5).
6. Reframe `article-workflow.md:154-173` from "flow" to "JSON state schema" (item 6).
7. Fix `research-workflow.md:115-121` → 118–120 (item 7).
8. Fix `cody LICENSE.md` sub-line citations (item 8).
9. Fix `seo-google/SKILL.md:142` → 143 (item 9).
10. Update content-quality-auditor "200+ lines" → "689 lines" (item 10).
11. Add new top-level section "Original skills (no upstream)" covering #5, #12, #13, #17, #18, #19, #23 (B-28).
12. Replace any "approximate volume kept: ~N LOC" language with "ideas, not lines" — commit to zero verbatim text (B-11, B-12).

---

## 10. What I propose next

1. You make the eight calls in §3.
2. I patch PLAN.md per §8 (approximately 250 lines added, line numbers will shift but I'll commit each major section as a separate commit per your "incremental commits" preference).
3. I patch `docs/upstream-stripping-map.md` per §9.
4. We re-audit: one Plan agent does a delta check on the patched PLAN.md to confirm BLOCKERs are addressed; one verifier re-checks corrected strip-map citations.
5. Then M0 (Foundation).

If any of the eight recommendations in §3 are wrong for your situation, push back before I patch — those calls cascade through the rest.
