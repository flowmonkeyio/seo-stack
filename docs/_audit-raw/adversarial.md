I have enough to deliver a thorough adversarial audit. The big things confirmed:

- `articles` is a single fat row with multi-stage columns (brief_json, outline_md, draft_md, edited_md, frontmatter_json, published_url) — concurrent writes will collide.
- `publish_targets` is a 1-many table per project, but `articles.published_url` is a SINGLE column — multi-target publishes have no place to land.
- "Bulk launch in parallel" is described, but the locking model is hand-waved via "short transactions" — without a per-article ownership token nothing prevents a runaway agent from clobbering another's draft.
- `compliance_rules.kind` enum is fixed but `kind: 'custom'` is in the list — so a project can name an arbitrary "custom" rule but the schema doesn't enforce a body shape.
- `runs.status` has no "pending" / "queued" / "paused" / "needs-input" — once started, a run is `running` until terminal.
- The Cody license forbids "create a different or competing framework, tool, or product" — content-stack literally is a competing framework. The strip-map's mitigations (re-author from first principles) are aspirational and the temptation is overwhelming.
- `eeat_criteria` allows projects to deactivate items and re-weight — including the three veto items (T04, C01, R10) — which means an end user can rubber-stamp anything by deactivating all required rows.
- No idempotency keys on any MCP tool. "Idempotent where it makes sense" is a non-spec.
- No request/response logging trail — `runs.metadata_json` is one bag-of-bytes per RUN, not per STEP.
- `integration_credentials.encrypted_payload` — the per-machine seed has no rotation story, no recovery if the machine is wiped.
- GSC OAuth tokens expire — refresh path is unspecified.
- Transcript / context window management is unspecified — Procedure 4 has 9 sequential skills and the LLM has to remember everything via MCP fetches.

Now I'll deliver the full audit.

---

# Adversarial Audit — content-stack PLAN.md

Tone: every issue below is something I think you discover the day a real user hits it, not something a static review catches. I have grouped by severity. Line references are to `/Users/sergeyrura/Bin/content-stack/PLAN.md` unless otherwise noted.

## BLOCKER (must fix before M0 — these break the architecture)

### BLOCKER-01 — The "single fat row" + parallel procedure-4 model is broken in two different ways

**Location:** PLAN.md L288 (`articles` columns), L631 (WAL risk row), L447 (procedure 5 "spawn procedure 4 in parallel batch").

**Problem:** SQLite in WAL mode allows many concurrent readers but exactly **one** writer at a time. The PLAN's mitigation ("short transactions; per-procedure runs are queued") is a hand-wave. There are two failure modes that nobody has reasoned about:

1. **Cross-article contention is the easy case** — different `articles.id` rows being mutated in parallel only contend on the writer-mutex for the few-millisecond `UPDATE` itself. Fine.
2. **Same-article contention is the actual blocker.** Procedure 4 has *nine* skills writing back to the *same* `articles.id` (`brief_json`, `outline_md`, `draft_md` partial, `draft_md` partial, `draft_md` partial, `edited_md`, `eeat_passed` flag, `frontmatter_json`, `published_url`). The schema gives every skill license to write any column at any time, and there is no per-row ownership token. Two scenarios:
   - **Bulk launch crash recovery.** Daemon restarts mid-procedure. Two skills with retries-from-disk both target `articles.id=42`. They each call `article.setDraft`. Last writer wins; the earlier (possibly correct) version vanishes silently because there is no version column on the *partial* artifacts (only on whole-article versions, L288).
   - **User intervenes from UI while skill runs.** The UI's `MarkdownEditor` (L199) is described as round-tripping `articles.edited_md` over PATCH. If the user fixes a typo in the editor while the editor skill is mid-pass, one of the two will silently overwrite the other.
3. **Bulk-launch parallelism is undefined.** "Configurable concurrency" (L447) — at concurrency=8, you have 8 procedure-4 runs each calling 9 sequential skills, each potentially calling 5–20 MCP tools. That is up to ~1,440 short transactions per minute through one writer mutex. Plus the APScheduler writers. Plus the UI. It will work, but it will have surprising 503/timeout behavior at the FastAPI layer that will look like "the daemon hangs". And nothing in the plan defines an overload signal back to the bulk launcher.

**Fix:**
- Add to L288 `articles`: `current_step VARCHAR`, `owner_run_id INTEGER NULL`, `step_started_at`, `step_etag VARCHAR` (a UUID regenerated each step transition).
- Add a hard rule: every `article.set*` MCP tool requires `expected_etag`; mismatch → 409 with current state. This is the only safe way to do optimistic concurrency on a fat row.
- Add a `publish_targets` ownership rule too: each procedure-4 run takes a row-level advisory lock (a `lock_token` column on `articles`) for its duration; concurrent attempts fail-fast.
- Add to risk table (L631): explicit limit of 4 concurrent procedure-4 runs by default, with a `MAX_CONCURRENCY` env var. The number must be small enough to keep the writer mutex healthy for the daemon's own jobs and the UI.
- Add a serial-write benchmark to M2 acceptance: 100 sequential `article.setDraft` calls of 200 KB markdown each must complete < 2 s on a 2020 MBP. Without the benchmark, the WAL story is faith-based.

---

### BLOCKER-02 — `articles.published_url` is single-valued; `publish_targets` is many-per-project. They cannot both be right.

**Location:** L288 (`articles.published_url`), L296 (`publish_targets`), L308 enum mentions `nuxt-content | wordpress | ghost | hugo | astro | custom-webhook`.

**Problem:** A project can register multiple `publish_targets` (Nuxt + WP for the same site, or staging + production, or syndication to Medium/Substack, or a `custom-webhook` for a CDN purge). Procedure 4 says "publish skill (17/18/19 per `publish_targets`)" (L446) — i.e., it iterates targets — but the article schema can record exactly one URL. There are several real consequences:

- The first target overwrites the second's URL. The audit trail shows only the last publish.
- "Drift detection" (L294 `drift_baselines`) needs *which* live page to diff against. With multi-target, the baseline-vs-live concept becomes ambiguous.
- The interlinker's "to_article_id" (L290) implies a single canonical URL. If the same article lives at `site.com/post` and `wp.site.com/post`, which gets the inbound link?
- Republish on humanize pass (procedure 7, L449) increments `articles.version` but has nowhere to record per-target republish status.

**Fix:**
- New table `article_publishes`: `id, article_id, target_id, published_url, published_at, version_published, status, error`. PK (`article_id`, `target_id`, `version_published`).
- Drop `articles.published_url`, `articles.published_at`. Keep `articles.last_refreshed_at` and `articles.version` (those are about content, not a target).
- Add a `articles.canonical_target_id` FK so `internal_links` and `drift_baselines` know the authoritative URL.
- Update procedure 4 publish step (L446) to fan out across `publish_targets WHERE is_active=true AND project_id=:p`.

---

### BLOCKER-03 — The eeat_criteria customization model lets a project nuke the EEAT gate

**Location:** L284 (`eeat_criteria.required, active`), L409 (skill #11 "Use project-specific criteria from `eeat_criteria`"), L448 (procedure 4 EEAT gate), `docs/upstream-stripping-map.md` §5 around L591 "veto items become rows with `required=true`".

**Problem:** The plan says the 80-item rubric is project-customizable, and the strip-map notes this generalization explicitly: "ANY required-item Fail blocks publishing. This generalizes beyond exactly-three-vetoes." Combined with `active=false`, a project owner can:
1. Toggle every `eeat_criteria.required` to `false`.
2. Toggle every `eeat_criteria.active` to `false`.
3. Pass the EEAT gate trivially. Or rather: nothing fails because nothing is checked.

The plan calls EEAT a **gate** (procedure 4 explicitly says "fail loops back to draft"), implying it cannot be bypassed in the canonical flow. But there is no floor — no "core" required items, no minimum dimension count, no minimum item count. The Cody license, the user's commercial pipeline, and the EEAT framework all assume a real gate. We are shipping a feature whose contract says "blocks bad content" and whose schema says "blocks whatever the operator says, including nothing".

This is BLOCKER-grade because:
- The whole reason this product exists is "humans can't operate the SEO pipeline; LLMs can't EEAT-grade themselves; we are the system that gates". Without an unkillable floor we are a checkbox.
- The veto-item IDs (T04, C01, R10) are referenced through the strip-map as load-bearing — if they're optional in the schema, downstream skill prompts must conditionally check them, which means the prompt becomes branchy and hallucination-prone.

**Fix:**
- Add a new column `eeat_criteria.tier` ENUM('core', 'recommended', 'project'). The 80 seed items get `tier='recommended'` except T04/C01/R10 which get `tier='core'`.
- Hard rule in `repositories/eeat.py` and the `eeat.toggle` MCP tool: rows with `tier='core'` cannot be deactivated, cannot have `required` toggled off. Return 422.
- Procedure 4 EEAT gate must compute `coverage` (% of dimensions with ≥1 active item) and refuse to score if coverage < 100% (all 8 dimensions must be active). Not a hint, a hard floor.
- The 80-item seed must persist `eeat_criteria.text` (the human-readable standard) per row so we are self-describing if the upstream renumbers.
- Add to "Out of scope" L613 a clarifying line: "Rubber-stamp mode: not provided. Every project must run with all 8 dimensions and 3 core veto items active."

---

### BLOCKER-04 — There is no per-skill MCP-tool whitelist; every skill can call every tool

**Location:** L364–388 (~70 MCP tools), L207–233 (skills), L388 ("Every tool: pydantic-validated, idempotent where it makes sense").

**Problem:** PLAN.md does not specify which tools a skill is permitted to call. In practice:
- The `draft-body` skill could call `article.markPublished`, `interlink.apply`, `gsc.bulkIngest`, `project.delete`. That is the contract today.
- The strip-map briefly notes (line ~620) that Claude Skills support an `allowed-tools` frontmatter field — but PLAN.md doesn't normatively require it, and the field is Claude-specific (Codex skills don't honor it).
- An LLM that hits a token-budget squeeze, summarizes the prompt, and tries to "save time" can absolutely jump to `article.markPublished` and skip the EEAT gate. There is no schema-level enforcement that publishing requires `articles.status='eeat_passed'`.
- A run-amok or jailbroken skill can call `project.delete` on the wrong project; the `runs` audit log is post-hoc.

**Fix:**
- L388 must become normative: define a **tool-grant matrix** in `docs/extending.md` (a new section), and back it with a server-side check. Every skill name maps to a set of allowed tool names. The MCP server reads the calling skill's name from a dedicated header or from a `runs.id` join (the `run.start` MCP tool returns a `run_token` and every subsequent tool call must include it). The server enforces: tool ∉ whitelist[skill] → 403.
- In `articles` table: add a CHECK that `status='published'` requires `status` was previously `eeat_passed` AND a corresponding `runs.kind='eeat-gate', status='success'` row exists. Implement as a trigger or repository invariant — never trust the LLM to honor enums.
- Status transitions are a state machine, not a free string. Document the legal transitions in PLAN.md L304 inline and enforce in `repositories/articles.py.set_status()`.
- Add an "emergency stop" tool: `run.abort(run_id)` that the UI can call to terminate a procedure. PLAN.md has `run.start | finish | list | get` (L385) but no abort. Without it, a bulk launch that goes wrong cannot be stopped without `kill -9` on the daemon.

---

### BLOCKER-05 — Cody Article Writer's license forbids exactly what content-stack does

**Location:** PLAN.md L500 ("No copy-paste of upstream prompts. We rewrite them in our voice + against our DB schema. The upstream is a reference, not a parent."), strip-map §`cody-article-writer` §2.

**Problem:** Cody's license (`/Users/sergeyrura/Bin/content-stack/.upstream/cody-article-writer/LICENSE.md` L18–25) reads:

> "**No Adaptation or Derivative Works:** You may not adapt, translate, extend, or otherwise use the codebase to create a different or competing framework, tool, or product. Using any part of Cody Article Writer in other software or projects is disallowed."

> "**No Modification (Except for Contribution):** You may not modify Cody Article Writer or create derivative works."

content-stack is, on its face, "a different or competing framework". The strip-map openly cites cody for *seven* skills (#4, #6, #7, #8, #9, #10, #24) including the editor's 244-line `editor-style-guide.md`, where it says we re-author "all 244 lines re-authored as a content-stack-voice equivalent" (strip-map L397). "Re-authoring all 244 lines of a copyrighted style guide" is — under almost any reading of this license — exactly what the license prohibits. The strip-map's mitigation is "fair use", which is:
1. Not a license-grant (it is an affirmative defense to infringement claims).
2. Risky for a *commercial pipeline* that resells these skills' outputs at scale.
3. Not how "reference, don't vendor" was framed in PLAN.md (which assumes all upstreams have permissive licenses).

The plan's posture (L494, "`docs/attribution.md` lists every upstream source") does not satisfy a license that says "you cannot create a competing framework". Attribution does not cure the prohibition.

This is BLOCKER-grade because it sits under M7 (skills), not M0, but if it isn't resolved before M0 the team builds 7 skills' worth of work that may have to be re-authored from a clean room.

**Fix:**
- Before any skill author looks at a Cody file, decide between three positions:
  1. **Clean-room re-author from first principles** — explicitly do not read cody-article-writer at all when authoring skills #4, #6, #7, #8, #9, #10, #24. Use only PLAN.md's data model + author's general knowledge of editorial workflow. Document the clean-room procedure in `docs/attribution.md`.
  2. **Written exception from Red Pill Blue Pill Studios** — email `marcelo@redpillbluepillstudios.com` with a description of content-stack and request a written license addendum that permits content-stack. Decision needed before M7. *Probability of yes: low. Probability of silence: high.*
  3. **Drop cody as a source.** Source the editor-pass skill from `aaron-he-zhu/seo-geo-claude-skills` (Apache-2.0) instead, even if the patterns are weaker. The strip-map explicitly notes those phases are out of seo-geo's scope, but seo-geo's `geo-content-optimizer` and `seo-content-writer` plus public domain editorial guides cover most of the editor pass.
- Until the decision is made, **block the M7 skill-authoring track**. PLAN.md's "implementation sequencing" (L580) currently lets M7 start as soon as M2 is done; that's wrong for these 7 skills.
- Add a CI check in `tests/`: a script that fails the build if any `skills/02-content/*/SKILL.md` contains substrings from cody's verbatim text (a small list of fingerprint phrases stored in `tests/fixtures/upstream-fingerprints.json`).

---

### BLOCKER-06 — The codex-seo "Avalon Reset" license is being wished away

**Location:** PLAN.md L508 (`codex-seo` referenced for 8 skills), strip-map §`codex-seo` §2.

**Problem:** codex-seo's repo claims MIT in 6 metadata files but the actual `LICENSE` is "Avalon Reset" proprietary, which forbids derivative works for distribution and requires "active membership in the copyright holder's community program" (`/Users/sergeyrura/Bin/content-stack/.upstream/codex-seo/LICENSE` L9–13, 27–32). The strip-map says "we are within fair use (reading + re-authoring)" — that is again a defense not a grant. PLAN.md L499 makes things worse by recommending a `--with-codex-seo` install option that **clones the upstream into the user's home directory**. The plan claims that's safe because "the user is cloning directly". That is two separate problems:

1. **Our `scripts/install-codex.sh --with-codex-seo` is running `git clone` programmatically.** That is no different in copyright terms from us redistributing a tarball. We are inducing the install. If Avalon Reset's license is enforceable, our installer is a contributory cause.
2. **The "active membership" clause** is a use restriction, not a redistribution restriction. End users running `--with-codex-seo` who don't know about the membership requirement are placed in license violation by our installer.

**Fix:**
- Drop `--with-codex-seo` entirely. PLAN.md L498–499 must be deleted; mention codex-seo as "see this URL, install it yourself if you want it" in `docs/extending.md`.
- For the eight skills derived from codex-seo (#1, #2, #3, #14, #16, #20, #21, #22), the same clean-room rule as BLOCKER-05 applies: skill authors must not paraphrase codex-seo's prompt text. The strip-map's own warning ("we should not copy *prompt text or scripts verbatim*") is correct but understated.
- Add to `docs/attribution.md` a section "Upstream license inconsistency: codex-seo" that documents the LICENSE-vs-metadata mismatch, and email the upstream maintainer asking them to fix the LICENSE file. If they relicense to MIT, our risk evaporates.
- The strip-map's "Approximate volume kept: ~150 LOC in two reference docs + ~80 LOC adapted" (e.g., L101) language is irresponsibly permissive. Replace those with "ideas, not lines" — the plan must commit to zero verbatim lines.

---

### BLOCKER-07 — Daemon crash recovery is unspecified; orphaned `runs.status='running'` rows are inevitable

**Location:** PLAN.md L295 (`runs` table), L530 (PID file), L631 (WAL contention mitigation).

**Problem:** PLAN.md describes `runs.status` as `running | success | failed | aborted` (L304). It does not specify:

- How a `running` row gets reaped after a daemon crash. If the user `kill -9`s the daemon (or it OOMs, or launchd restarts it), every run that was in flight stays `running` forever. The UI's RunsView will accumulate "running" rows that never finish.
- Resume semantics. If a procedure-4 run was on step 7 (eeat-gate) when the daemon died, what does the user do? Re-trigger procedure 4 from the start? Then steps 1–6 run again, possibly clobbering valid state.
- The Codex/Claude-Code session being interrupted. The MCP transport is stateless (Streamable HTTP) — if the LLM session disconnects mid-`article.setDraft`, the daemon doesn't know. From the daemon's view the partial draft is a complete draft. Status moves forward. The half-written content gets edited.

This is a real-world blocker because the user *will* hit it on day 1. They will run procedure 5 against 50 topics; their laptop will sleep; they will come back and see "20 running runs"; nothing will progress.

**Fix:**
- Add to `runs`: `heartbeat_at TIMESTAMP`, `last_step VARCHAR`, `last_step_at TIMESTAMP`, `parent_run_id INTEGER NULL`, `client_session_id VARCHAR`. APScheduler updates `heartbeat_at` every 30 s for any running row owned by the daemon process. On startup, the daemon scans for rows where `status='running' AND heartbeat_at < now() - 5 min` and transitions them to `aborted` with `error='daemon-restart-orphan'`.
- Add `articles.last_completed_step` so a re-trigger of procedure 4 can resume from the last clean step (skip brief if `articles.brief_json IS NOT NULL`, etc.). The procedure runner reads this, the LLM doesn't have to know.
- New MCP tool `run.heartbeat(run_id)` for the LLM client to call on every step transition. Plus a `run.resume(run_id)` and `run.fork(run_id)` (the latter for "redo this from step N onward as a new versioned run"). Without these, "long-running procedures" is a marketing claim, not a feature.
- Document the recovery semantics in `docs/architecture.md` (which is in the layout L259 but undefined) — "what happens if the daemon dies mid-procedure" must be a top-level doc section.

---

### BLOCKER-08 — The daemon has zero authentication and assumes 127.0.0.1 isolation that doesn't hold

**Location:** PLAN.md L94 ("Bound to `127.0.0.1`"), L614 (out of scope: "Multi-user authentication. Localhost only.").

**Problem:** "127.0.0.1 only" is a security claim that breaks in three real scenarios:

1. **Anything on the local machine can read your DB and your API keys.** Every browser tab the user opens. Every VS Code extension. Every npm package's postinstall script. Every Docker container with `host.docker.internal` networking. The daemon has the AES-256-GCM seed-derived key in memory and the same machine has access to it. Any local malware reads everything.
2. **`localhost` MCP exposed to every LLM client running on the machine** — that includes any `claude code` started in any directory, plus future agentic tools. If the user runs an unrelated Claude Code instance for some other task, that instance can call `project.delete` on the active project because there is no project-binding in the MCP request.
3. **CSRF from the browser.** The UI is at `http://localhost:5180` with no CORS posture documented. Any random website the user visits can fire `fetch('http://localhost:5180/api/v1/projects/1', { method: 'DELETE' })`. PLAN.md does not specify the CORS policy. Same-origin? Allow `*`? Reject everything? Without a spec, the framework default kicks in, which for FastAPI is "allow nothing", which means the UI itself stops working — the developer flips to `allow_origins=['*']` and ships CSRF.

**Fix:**
- Add to PLAN.md L94 a normative line: "The daemon refuses any HTTP request whose `Host:` header is not `localhost` or `127.0.0.1`. CORS is `same-origin only`; the UI is served from the same origin so it works."
- Generate a per-install random token (`uuid4`, written to `~/.local/state/content-stack/auth.token`, mode 0600). Every REST and MCP request must carry `Authorization: Bearer <token>`. Install scripts inject the token into Codex's MCP config and Claude's `.mcp.json` automatically. This is *not* "user auth" — it's a single shared token that proves "you can read this file, so you have local-machine access". It blocks browser CSRF and cross-process drive-bys.
- The token rotates on `make install` re-run (and the install script overwrites the MCP configs to match).
- Add a doctor.sh check: "auth token file exists and is mode 0600".
- Update L614 "out of scope" to clarify: "multi-user is out of scope; per-install token enforces single-user binding".

---

## MAJOR (must fix before M2 — DB + repos)

### MAJOR-09 — `integration_credentials.encrypted_payload` has no key rotation, no recovery, no scope

**Location:** L297 (`integration_credentials` table), L474 ("AES-256-GCM using a key derived from a per-machine seed at first run").

**Problem:**
- The "per-machine seed" is presumably a file on disk. Where? PLAN.md doesn't say. If `~/.local/state/content-stack/seed.bin` and the user `rm -rf`s state by mistake, every credential is unrecoverable garbage in the DB and the daemon doesn't know — it just decrypts to garbage and the integration calls fail with cryptic errors.
- No key-rotation story. After an OS reinstall or laptop swap, the user copies the DB over, the seed is gone, every credential is lost. PLAN.md L617 says "Back up via your normal mechanism" — but if the user backs up the DB without the seed, they have ciphertext nobody can decrypt.
- No per-credential nonce documented. AES-256-GCM with a static seed and reused nonce is catastrophic. Need to spec a per-row random nonce stored alongside the ciphertext.
- No "test integration" path that doesn't decrypt — i.e., the doctor script can't tell "key works" from "credentials are wrong".
- GSC OAuth tokens specifically: refresh tokens are long-lived but access tokens expire in 1 h. The encrypted blob must hold both, plus a refresh-time hook that re-encrypts the new pair. PLAN.md doesn't say.

**Fix:**
- Specify (PLAN.md L474) the seed location: `~/.local/state/content-stack/seed.bin`, mode 0600, generated at first run if missing. The seed is *also* derived from `os.uname()[1]` (machine hostname) so a copy-attack across machines fails by default.
- Add a column to `integration_credentials`: `nonce BLOB NOT NULL` (12 bytes per row, random). `encrypted_payload` becomes ciphertext + auth tag.
- Add to `integration_credentials`: `kind`, `expires_at`, `last_refreshed_at` so the OAuth refresh logic can find expiring rows.
- Add a doctor.sh check: "all `integration_credentials` rows decrypt cleanly". Failure surfaces a specific error: "seed corrupted, re-add credentials".
- Add a `make export-credentials` command that emits a passphrase-encrypted backup of the credentials table (using a passphrase the user supplies, not the seed). For machine migration.
- Specify how to reset: `make reset-integrations` clears the credentials table and the seed, forcing the user to re-add. This must be in the troubleshooting docs, not just the code.

---

### MAJOR-10 — GSC OAuth flow is mentioned but never specified end-to-end

**Location:** L466 ("OAuth flow → token in `integration_credentials`").

**Problem:** OAuth on a localhost daemon is non-trivial. None of the following are specified:
- Where the redirect URI lives. Google requires a registered redirect URI; localhost ports are allowed but `http://localhost:5180/api/v1/integrations/gsc/callback` must be registered with Google Cloud Console by the *user*. Who tells them?
- The flow: user clicks "Connect GSC" in UI → daemon opens browser to Google's consent screen → Google redirects back to `localhost:5180/...?code=...` → daemon swaps for tokens → encrypts → stores. PLAN.md doesn't enumerate.
- The user must create their own Google Cloud project and OAuth client (Google has not allowed shared OAuth clients for years). PLAN.md `docs/api-keys.md` (mentioned at L264) doesn't exist yet, but its existence is not enough — the OAuth-client setup is 12 manual steps in Google Cloud Console.
- Refresh: `google-auth` library handles it but where? In `integrations/gsc.py` per call? In a background job? PLAN.md doesn't say. If per-call, every call costs a refresh check. If background, it must run every <55 min.

**Fix:**
- New section in PLAN.md after L477: "Integration first-run flows". Per integration, document:
  - DataForSEO: just an API key, no flow.
  - Firecrawl: API key.
  - Reddit (PRAW): create app at `reddit.com/prefs/apps`; "script" type; persist client_id + secret.
  - GSC: full 12-step OAuth client setup with screenshots in `docs/api-keys.md`.
  - OpenAI: shared with the runtime, not stored separately. (BUT — see MAJOR-11.)
- Add to `integration_credentials`: `oauth_redirect_uri` and on first add, the daemon prints "register this URI in Google Cloud Console: ..." in the UI.
- New MCP tool `integration.testGsc` that does a `searchanalytics.query` with `rowLimit=1`. If 401, surfaces "re-auth needed" to the UI. The UI then triggers re-auth.
- Background job `jobs/oauth_refresh.py` runs every 50 min, refreshes any GSC token whose `expires_at < now() + 10 min`.

---

### MAJOR-11 — "OpenAI / Anthropic LLM calls reused from runtime config" is wrong

**Location:** L468 ("OpenAI / Anthropic (LLM calls)... reused from runtime config (Codex/Claude already authenticated)").

**Problem:** The daemon's *integrations* (image-generator, possibly content-brief if it does its own embeddings) need OpenAI keys. The plan says "reused from runtime config". This is a category error:

- Codex CLI authenticates against the user's ChatGPT subscription or API key — but those credentials are inside the Codex process, not exposed to MCP servers. The daemon cannot read them.
- Claude Code's API key is held by Anthropic's runtime. Same problem.
- The image-generator skill (#13) calls the OpenAI Images API. That's a daemon-side HTTP call, and it needs an OpenAI API key the daemon has access to.
- The strip-map (around line 251) acknowledges OpenAI Images is "authored fresh", which means the daemon needs the key directly.

So in fact:
- Daemon-side image-gen → needs `OPENAI_API_KEY` in `integration_credentials`.
- Skill-side LLM calls (the actual content-generation reasoning) → those happen in the LLM runtime (Codex/Claude), and those calls don't go through our daemon at all. They go through whatever runtime the user is in.

The plan conflates the two and ends up describing neither correctly.

**Fix:**
- L467 (OpenAI Images) — change to `integration_credentials.kind='openai-images'`, separate row, separate key. Document in `docs/api-keys.md`.
- Delete L468 entirely. Replace with: "Skill-level LLM reasoning is performed by the calling LLM runtime (Codex CLI, Claude Code, etc.) using its own model and credentials. content-stack does not call any LLM directly except for image generation."
- This also clarifies BLOCKER-04: skills call MCP tools, they don't call OpenAI/Anthropic directly. So the cost-runaway risk from L636 is bounded by whatever the user's runtime budget is, not by the daemon.

---

### MAJOR-12 — Bulk-launch concurrency has no cost cap, no rate-limit enforcement, and no abort

**Location:** L447 (procedure 5 "spawn procedure 4 in parallel batch (configurable concurrency)"), L636 (cost runaway risk).

**Problem:** 100 articles × procedure 4 means roughly:
- 100 × DataForSEO seed-expand calls (~$0.02 each in the cost-tier table)
- 100 × Firecrawl crawl-of-top-10 (~$0.10 each)
- 100 × OpenAI Images (~$0.04 each at hd 1024×1024)
- 100 × runtime LLM calls (paid by the user's Codex subscription, but still a wall-clock cost)

That's ~$16 of integrations *plus* the runtime budget. At the user's first bulk run, if a Firecrawl call gets stuck retrying, the integration cost balloons. The plan's mitigation (L636 "Each integration tracks call count + cost in `runs.metadata_json`") is post-hoc — by the time the cost is logged, it has been spent.

DataForSEO and Firecrawl both have rate limits. PLAN.md says nothing about how the daemon enforces them. If procedure 5 with concurrency=10 fires 10 concurrent Firecrawl crawls and Firecrawl's plan caps at 5/sec, half will 429 and the procedure handles it… how?

**Fix:**
- New table `integration_budgets`: `id, project_id, kind, monthly_budget_usd, alert_threshold_pct, current_month_spend, current_month_calls, last_reset`. UI surfaces it; integrations check it before each call.
- Each integration wrapper enforces a token-bucket rate limit (read from `integration_budgets.qps`). Defaults: DataForSEO 5 qps, Firecrawl 2 qps, GSC 1 qps (Search Analytics is brutally rate-limited in practice), OpenAI Images 10 qps.
- Procedure 5 must accept `--budget-cap-usd N` and refuse to start if estimated cost > cap. The estimator runs from per-skill cost templates (e.g., "this procedure uses ~$0.15 of integration calls per article").
- New MCP tool `run.abort(run_id, cascade=true)` — for bulk launches, cascade aborts all spawned procedure-4 sub-runs. Required for the UI's "stop the runaway".
- Add `runs.parent_run_id` (already proposed in BLOCKER-07) so the abort cascade is well-defined.
- Update L631 risk row text to be specific: "Each procedure-4 step has a per-step kill-switch via `run.abort`; bulk launches inherit cascade-abort. Default monthly cap per integration is configurable; default Firecrawl cap = $50/mo; the daemon refuses calls beyond the cap until the operator raises it."

---

### MAJOR-13 — `internal_links` graph has no delete/unpublish path

**Location:** L290 (`internal_links` table).

**Problem:** Suppose the user unpublishes article X (removes from CMS, sets `articles.status` back to `edited`). What happens to:
- Inbound links *to* X from other articles' `edited_md` (where the link is literally inlined as `[anchor](url)`)?
- Outbound links *from* X to other articles?
- The `internal_links` rows themselves — are they deleted? Marked as broken? Re-suggested?

PLAN.md doesn't say. The schema has `internal_links.status` as `suggested|applied|dismissed` — nothing for "stale" or "broken". And "applied" means "the link was inserted into the actual article markdown" — which is a destructive edit to `articles.edited_md`. Unpublishing X doesn't automatically reverse the edit; the link in Y's body now 404s.

This compounds into the refresh-detector and humanize procedures, which re-run the editor — which doesn't know about applied internal links and can mangle them.

**Fix:**
- Add a new state to `internal_links.status`: `broken`. Triggered when `to_article_id` transitions out of `published`.
- The interlinker skill (#15) on suggest must read only `articles WHERE status='published' AND project_id=:p`. It already does (via the strip-map's "applied to articles WHERE status='published'") but PLAN.md must say so.
- New MCP tool `interlink.repair` runs after any unpublish: scans for `status='applied'` rows pointing to the un-published article, transitions them to `broken`, and produces a `runs` row listing the affected articles for the editor to clean up.
- The editor skill (#10) must be aware of `internal_links` rows for the article being edited and preserve them in `articles.edited_md` — i.e., the AI-tell removal pass must not touch markdown link syntax. This is a skill-prompt invariant; document it in PLAN.md L408.
- Add `articles.last_link_audit_at` so the UI can surface "this article's outbound links haven't been verified since X".

---

### MAJOR-14 — `gsc_metrics` will explode for any moderately busy site

**Location:** L293 (`gsc_metrics` columns).

**Problem:** The schema is `(project_id, article_id, captured_at, query, impressions, clicks, ctr, avg_position)`. At "28 days, dimensions=query,page" (per the strip-map L160), a site with 100 published articles and 200 queries per article per pull = 20,000 rows per pull. Pulled nightly = 600,000 rows/month. Pulled for 12 months = 7.2M rows. With no index on `(project_id, captured_at, article_id)` the UI's GscView (L191) queries become slow. The PLAN.md doesn't mention indices at all.

A second issue: `query` is a free-text column with no normalization. Two queries differing only by capitalization (`"best slot machines"` vs `"Best Slot Machines"`) double the row count. GSC itself dedupes, but our schema can't.

A third: there is no aggregation table. Every "what's my CTR for article X this month" query reads ~600 rows. At 100 articles, the GscView does 60,000 row fetches.

**Fix:**
- Add unique index `gsc_metrics(project_id, article_id, captured_at, query)` to enforce dedup at the row level.
- Add aggregation table `gsc_metrics_daily(project_id, article_id, day, impressions_sum, clicks_sum, ctr_avg, avg_position_avg, queries_count)` populated by a nightly job (different from the raw pull). The GscView reads from this, not raw.
- Retention policy: raw `gsc_metrics` rolls off after 90 days into the aggregation table; documented in `jobs/gsc_pull.py` and PLAN.md.
- Add a `gsc_query_normalized` column (lowercase, NFC) and dedupe on it.
- Document in PLAN.md L293 the row-count estimate so future readers know the table is hot.

---

### MAJOR-15 — Make-install idempotency is unspecified and the install scripts can corrupt state

**Location:** L247–256 (scripts), L572 (`make install` brings up daemon, registers MCP, copies skills).

**Problem:** What happens on the *second* `make install` run?
- `cp -R skills/* ~/.codex/skills/` — overwrites the user's customizations.
- `register-mcp-codex.sh` does `codex mcp add content-stack ...` — what if it's already registered? Codex CLI's behavior is to error or duplicate.
- `register-mcp-claude.sh writes .mcp.json` — writes where? If the user has multiple Claude Code projects, only one gets the MCP. If it overwrites without merging, existing MCP servers get clobbered.
- `install-launchd.sh` — re-loading a plist that's already loaded errors out.
- DB migration on second install: `alembic upgrade head` is idempotent if the alembic state is healthy. If a previous migration half-applied and left the DB in a weird state (because the daemon was killed mid-migration), it isn't.
- `seed.py` — does it `INSERT OR IGNORE` (idempotent) or `INSERT` (duplicates)?

**Fix:**
- Each install script must be idempotent. Add to PLAN.md L573 a normative line: "All install scripts are idempotent: running `make install` twice produces the same result as running it once. Skills are merged not overwritten (existing user-customized skill files are preserved with `.bak` suffix on conflict)."
- `register-mcp-claude.sh` must read `.mcp.json`, parse JSON, merge `content-stack` server, write back. Never `>` overwrite.
- `seed.py` uses `INSERT OR IGNORE` for stable seed rows (eeat_criteria seed, schema_emits templates), with a stable identifier per row.
- Doctor.sh checks: MCP registered exactly once in each runtime; no duplicate seed rows; alembic at head.
- Add `make uninstall` symmetry. Without it, users who try to clean up will leave artifacts.

---

### MAJOR-16 — The procedure-runner has no transcript / context-window strategy

**Location:** L446 (procedure 4 lists 9–10 sequential skills), L437 ("Skills are atomic capabilities; procedures are how they compose").

**Problem:** Procedure 4 has the LLM calling content-brief → outline → 3 drafts → editor → eeat-gate → image-generator → alt-text-auditor → schema-emitter → interlinker → publish. That is a lot of MCP round-trips inside a single LLM session. By the time the LLM is on step 9, its context window contains:
- All the prior tool calls and their JSON responses (`articles.brief_json` is several KB; `articles.outline_md` is bigger; `articles.draft_md` is the biggest of all and gets fetched repeatedly).
- All the skill prompt blocks loaded.
- The user's original message.

Real Codex/Claude Code sessions hit context limits inside long agentic flows. PLAN.md never says how the procedure runner handles:
- Progressive summarization of completed steps.
- Dropping prior step output from context once the result is persisted.
- The "next step" orchestration: who is calling who? Is the user pasting `/procedure topic-to-published 42` and the LLM follows the playbook, calling MCP tools? Or is there a daemon-side procedure runner that the LLM only kicks off?

PLAN.md L646 ("I can run `/procedure topic-to-published <topic-id>`") implies LLM-side execution. That implies the LLM needs to "remember" the playbook over 9 steps, in the face of context pressure, while not getting confused. It will get confused.

**Fix:**
- Make procedures **daemon-orchestrated**. The MCP tool `procedure.run(slug, args)` enqueues a server-side runner (APScheduler) which calls back into MCP via *another* LLM session per skill step. Each skill step gets a fresh session with a tight prompt: "you are skill X; here is the article state; here are the tools you can call; produce output and return". The daemon coordinates the steps, persists between them.
- The LLM client's only job is "call `procedure.run` and poll `procedure.status(run_id)`". Context window stays tiny.
- This requires the daemon to be able to invoke an LLM directly — which means MAJOR-11 needs reversal: the daemon does need credentials for at least one LLM (likely OpenAI or Anthropic), separate from the user's runtime budget. PLAN.md must specify which.
- Alternative: keep client-side execution but require the LLM to call `procedure.advance(run_id, step_output)` after each step, where the daemon validates "is this the right next step", and the procedure prompt instructs the LLM to **fetch only the columns it needs** (e.g., outline skill reads `articles.brief_json` only, not the whole article row). PLAN.md must include this discipline in `docs/extending.md`.
- In PLAN.md L437, add: "Procedures are daemon-orchestrated. The LLM calls `procedure.run` and the daemon drives skill execution. Skills are stateless; their input is whatever the daemon passes."
- This change cascades into the API: `POST /api/v1/procedures/{slug}/run` (L362) becomes async-job-creating (returns 202 + run_id); `GET /api/v1/procedures/runs/{run_id}` returns status + step list + step outputs.

---

### MAJOR-17 — `compliance_rules.kind='custom'` makes the schema unstructured

**Location:** L284, L307 (`compliance_rules.kind` enum).

**Problem:** The enum is `responsible-gambling | affiliate-disclosure | jurisdiction | age-gate | privacy | terms | custom`. The first six imply a known shape (jurisdiction has a region list, age-gate has a min-age, etc.). `custom` is an escape hatch. But the schema (L284) is just `body_md, jurisdictions, position`. There's no `params_json` for a custom rule's structured fields, no `validator_kind`, nothing. So every custom rule is a markdown blob the LLM has to interpret. This will:
- Make humanize/refresh passes unable to validate compliance footers.
- Cause the LLM to hallucinate which rules apply (especially with `jurisdictions` overlapping).
- Make the upgrade path messy when "custom" rules need structured fields later.

**Fix:**
- Add `compliance_rules.params_json` (default `'{}'`).
- Add a `compliance_rules.validator` column (a Python callable name registered in the daemon, e.g., `validators.responsible_gambling`). Predefined kinds get a built-in validator; `custom` requires the user to specify a validator name (or "none").
- The draft-conclusion skill (#9) reads compliance rules via `compliance.list` MCP, applies validators where present, inserts the body_md footer literally otherwise.
- The EEAT gate (#11) checks "compliance footer present per active jurisdictions" as a separate gate, not as a CORE-EEAT item. Add this to procedure 4 between editor and eeat-gate.

---

### MAJOR-18 — The procedure trigger model is unspecified for "ongoing" jobs

**Location:** L165–168 (`jobs/`), L448 (procedure 6 "Weekly cron"), L449 (procedure 7 "Monthly cron").

**Problem:** APScheduler runs jobs in-process. PLAN.md says "weekly GSC review" and "monthly humanize" but never:
- The cron expression for each.
- What happens if the daemon is offline at the scheduled time (laptops sleep).
- Per-project schedules (does every project's GSC pull happen at the same nightly time, queueing them through one writer mutex?).
- User-configurable schedule per project.
- Whether the user can disable a recurring job.

A second issue: APScheduler with persistent jobs requires a job store. PLAN.md doesn't say where. If it's the SQLite DB itself, every scheduler-tick is another writer hitting the same DB. If it's in-memory, jobs vanish on restart and a daemon that was offline on Sunday at 2 AM never runs the weekly review.

**Fix:**
- Add `projects.schedule_json` with per-project schedule (nightly GSC pull at HH:MM in project's timezone, weekly GSC review on Mondays, monthly humanize on the 1st).
- New table `scheduled_jobs(id, project_id, kind, cron_expr, next_run_at, last_run_at, last_run_status, enabled)`.
- APScheduler uses `SQLAlchemyJobStore` against the same DB but in a separate jobstore — i.e., its own table prefix.
- "Catch-up on missed runs" semantics: if the daemon was offline for a week and missed Monday's GSC review, on next start it should run it once (not seven times). APScheduler supports `misfire_grace_time` and `coalesce=True` — set both.
- UI tab "Schedules" per project showing the next-run-at timestamps and an enable/disable toggle.

---

### MAJOR-19 — Translation pipeline is "out of scope" but `projects.locales` is plural and skills don't know what to do

**Location:** L282 (`projects.locales`), L620 ("Translation pipeline. Handle via skill prompt + locale on `projects`").

**Problem:** `projects.locales` is plural — a project can declare `['en-US', 'fr-CA']`. PLAN.md L620 says "handle via skill prompt + locale" but no skill in the catalogue has a locale parameter, no procedure mentions per-locale fan-out, no `articles` row has a locale, and `internal_links` doesn't account for cross-locale links being usually wrong. So either:
1. `projects.locales` is decorative and the system actually only supports one locale at a time. Then it should be `projects.locale TEXT` (singular) per BLOCKER-grade clarity.
2. Or the system supports multi-locale, and we need an `articles.locale` column, locale-aware interlinker, locale-aware schema (`hreflang`), per-locale publish targets.

PLAN.md is incoherent. The user will declare `locales: ['en-US', 'fr-CA']`, run procedure 4, and get one English article with no second-language counterpart. That's not "translation skill = prompt".

**Fix:**
- Either change L282 to `projects.locale TEXT NOT NULL` (singular) and remove the multi-locale claim from L620 — the user runs a separate project per locale.
- Or add `articles.locale TEXT NOT NULL` defaulting to `projects.locale`, plus a translation skill in the catalogue (skill #25 `02-content/translator`), plus per-locale publish_targets, plus hreflang in schema-emitter. This is a much bigger change and should not be done unless multi-locale is a real requirement.
- Recommend the singular path; locales as a list invites future-Sergey to "fix it later" and shipping the bug to a real user.

---

### MAJOR-20 — The codex-plugin-cc adversarial-review seam is wired without a circuit breaker

**Location:** L511 ("optional: enables Codex sub-agents inside Claude Code"), strip-map §codex-plugin-cc.

**Problem:** The strip-map describes the seam: when EEAT verdict is SHIP and the plugin is enabled, the eeat-gate skill issues a `Bash` invocation of `node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" adversarial-review ...`. Several things break in practice:
1. `${CLAUDE_PLUGIN_ROOT}` is only set when the calling LLM is **Claude Code**. If the user is running Codex CLI calling our MCP, `CLAUDE_PLUGIN_ROOT` is unset — but the seam fires regardless because it's controlled by `integration_credentials.codex-plugin-cc.enabled`. The `Bash` call fails with no clear path forward.
2. The seam is described as a *Bash call from inside our skill SKILL.md*. Our skills are runtime-portable (Claude Code + Codex CLI). Only Claude Code runs Bash inside a skill the way described.
3. Codex's adversarial-review can take minutes (it's an LLM call). PLAN.md doesn't budget the wall-clock time. Procedure 4 step "eeat-gate" suddenly grows from "score the article" to "score, then wait 3 min on Codex, then merge". Bulk launch with concurrency=10 means 10 simultaneous Codex sessions — and `codex` CLI doesn't necessarily support that without warming up server processes.
4. The plugin uses Apache-2.0 and we're pointing at `${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs` — fine for the user's runtime. But the *attribution* requirement: if we ship code or skills that hard-depend on this path, we must include a NOTICE crediting OpenAI's Apache-2.0 plugin in our distribution. PLAN.md L494 says `docs/attribution.md` covers it; that's not the same as a NOTICE file at the package root, which Apache-2.0 §4(d) requires for *redistributors*. We're not redistributing, but we are inducing the install via doctor.sh. Borderline.

**Fix:**
- Make the adversarial-review seam **runtime-conditional and async**:
  - The eeat-gate skill checks `runtime == claude-code AND plugin_enabled` before invoking; otherwise skips.
  - Invocation is via a daemon-side helper, not a Bash call from the skill prompt. Add `integrations/codex_plugin_cc.py` that POSTs to localhost:5180/api/v1/adversarial-review (a new endpoint) which spawns the codex-companion subprocess and returns a job_id. The eeat-gate polls.
  - Wall-clock budget per call: 90 s. After that, skip and log "adversarial-review timeout" in `runs.metadata_json.adversarial_review.skipped='timeout'`. The article is not blocked because of plugin slowness.
- Add a NOTICE file at content-stack root (text reproduced from `/Users/sergeyrura/Bin/content-stack/.upstream/codex-plugin-cc/NOTICE`) crediting OpenAI for the Apache-2.0 plugin if the optional install is recommended in our docs.
- The `integration_credentials.kind='codex-plugin-cc'` row should also gate via `is_active` so the user can flip it off when bulk-launching.

---

### MAJOR-21 — `runs.metadata_json` is a dumping ground; per-step trace is not a thing

**Location:** L295 (`runs` columns), L388 ("traceable via `runs` table").

**Problem:** `runs` has `metadata_json` (a single column per run) and `error` (single column). There is no:
- `run_steps` table for step-by-step audit.
- Per-step latency, per-step input/output snapshot.
- Cost tracking per step.
- Failure-recovery context (which step failed, what it had as input).

PLAN.md L636 ("Each integration tracks call count + cost in `runs.metadata_json`") implies the integration call log goes into one JSON blob. That blob will be 1+ MB on a single procedure-4 run with 50 integration calls. The UI's RunsView (L194) will be slow to load these. Worse: the audit trail is unreadable — the user's question is "show me what step 7 sent to GSC", not "give me a 1MB JSON blob".

**Fix:**
- New table `run_steps(id, run_id, step_index, skill_name, started_at, ended_at, status, input_snapshot_json, output_snapshot_json, error, cost_cents, integration_calls_json)`.
- Each MCP tool call inside a step creates a `run_step_calls(id, run_step_id, mcp_tool, request_json, response_json, duration_ms, error)` row.
- The cost tracking moves from `runs.metadata_json` to `run_steps.cost_cents` so the UI can sum across steps cleanly.
- The RunsView shows the step list with per-step status; clicking a step opens the input/output diff. This is what an "audit trail" actually means.

---

### MAJOR-22 — `articles.frontmatter_json` and `schema_emits` overlap; publish skills are going to fight

**Location:** L288 (`articles.frontmatter_json`), L292 (`schema_emits`).

**Problem:** A Nuxt Content article's frontmatter usually carries: title, description, canonical, og:image, schema (JSON-LD), related, taxonomy. WordPress posts use Yoast SEO meta or RankMath meta. Ghost uses its own frontmatter. The schema-emitter skill (#16) writes JSON-LD to `schema_emits`. The publish skill is supposed to combine `articles.frontmatter_json` + `schema_emits.schema_json` into the published artifact. PLAN.md doesn't say how. Two real consequences:

1. The frontmatter-vs-schema split is false: schema is part of the frontmatter for Nuxt Content (`schema:` key) but separate for WordPress (custom post-meta) and Ghost (separate codeinjection). The publish skills must each transform differently. PLAN.md just says "publish skill (17/18/19)".
2. Refresh: humanize-pass produces a new `articles.version` but `schema_emits` and `frontmatter_json` aren't versioned. So the live page's schema doesn't update, or it does and the audit trail doesn't show it.

**Fix:**
- `schema_emits` gets `version_published INTEGER NULL`. When set, it pins to a specific article version.
- `articles.frontmatter_json` becomes per-target: move the column to `article_publishes.frontmatter_json` (per BLOCKER-02). Different targets get different frontmatter.
- Each publish skill (17/18/19) is responsible for transforming `articles.edited_md + schema_emits.schema_json + article_publishes.frontmatter_json` into the target's expected payload. Document the contract per skill in PLAN.md L416–418.
- Add a "preview" MCP tool: `publish.preview(article_id, target_id)` returns the exact bytes that would be POSTed/written, without doing it. UI needs this for "show me what's about to publish".

---

### MAJOR-23 — The UI doesn't have an obvious way to handle EEAT failures or interlink reviews

**Location:** L184–202 (UI views), L599 (interlink "suggest before apply").

**Problem:** The plan lists views but never specifies:
- The EEAT failure UX. After eeat-gate fails, the procedure loops back to draft. What does the human see in the UI? A red "EEAT failed" badge with… what details? The 80-item rubric scores? Just the failed items? No PLAN.md text addresses this.
- The interlink review queue. `InterlinksView.vue` exists (L192) — but the workflow is "see suggested → review → apply or dismiss". For 100 articles × 5 suggested links per article = 500 suggestions to review one by one. Bulk-apply? Filter by score?
- Voice/compliance/EEAT edits: when a user changes the project's voice profile, what happens to in-flight articles whose drafts were generated against the old voice? PLAN.md doesn't say. Either: (a) editor pass re-runs automatically; (b) it doesn't; (c) the article keeps a `voice_profile_version_used` to reproduce the old voice.

**Fix:**
- ArticleDetailView (L189) needs explicit subviews: "EEAT report" (rubric scores per dimension, failed items with one-line standards highlighted), "Activity" (run_steps timeline), "Interlinks" (incoming + outgoing).
- InterlinksView (L192) needs filters (project, status, score) and bulk-apply / bulk-dismiss with confirmation.
- Add `articles.voice_profile_id_used` and `articles.eeat_criteria_version_used` so the UI can show "the EEAT this article passed isn't the one you're using now; want to re-run?". `eeat_criteria` should grow a `version` column to support this.
- The plan must, in PLAN.md L640 ("What done looks like"), include "the user can resolve an EEAT failure by clicking it in the UI and seeing exactly which item(s) failed".

---

## MINOR (post-launch — quality-of-life, not blockers)

### MINOR-24 — `topics.priority` is a bare INTEGER with no ordering convention
**L:** 287. Two projects might use 1=high vs 1=low. Spec a convention (lower = higher priority) and the UI sort default.

### MINOR-25 — `slug` collisions on `articles.slug` and `projects.slug` aren't constrained
**L:** 282, 288. Both should be UNIQUE per scope: `projects.slug` global, `articles.slug` per-project. Add CHECK + index.

### MINOR-26 — No telemetry / privacy posture
PLAN.md L613–622 doesn't address whether the daemon phones home, sends anonymous metrics, etc. Default should be "no", documented in `PRIVACY.md`. Skip silently is the bug; opting in to nothing is the fix.

### MINOR-27 — No backup story
L617 says "back up via your normal mechanism". For a SQLite-WAL database this is wrong: copying `content-stack.db` while the daemon is running gets a torn snapshot. Add `make backup` that runs `sqlite3 content-stack.db ".backup ~/...timestamp...db"`.

### MINOR-28 — `_template/PROCEDURE.md` is mentioned but not specified
L237, L452. Add a sample frontmatter spec to `docs/procedures-guide.md` so user-authored procedures are validated.

### MINOR-29 — `doctor.sh` is described but its checks aren't enumerated
L255, L534. Spec the check list in PLAN.md so the implementor doesn't ship a half-doctor: daemon up; auth token file mode 0600; MCP registered for each runtime exactly once; required API keys present per active project; alembic at head; all `integration_credentials` decrypt cleanly; seed rows present (eeat_criteria.tier='core' rows count = 3); skills count = 24 in both runtimes; procedures count = 8.

### MINOR-30 — `tests/` directory layout listed, but no test plan
L264–268, L596 ("VCR-style cassettes"). Spec the test layers: unit (repositories), integration (FastAPI + in-memory SQLite), MCP (vcrpy against fixture LLM), end-to-end procedure (a fake project + recorded LLM responses). Without a per-layer plan, the team will write ad-hoc tests that don't cover procedure-runner regression.

### MINOR-31 — `runs.kind` enum is not declared
L295 has `runs.kind` but L304 only lists `runs.status`. The `kind` column governs UI grouping; spec it: `procedure | scheduled-job | manual-skill | integration-call | maintenance`.

### MINOR-32 — No "readonly observer" mode
A power user wants a coworker to watch the bulk launch in real time. The UI is single-user (no auth, BLOCKER-08). Spec a read-only `Authorization: Bearer <readonly-token>` token that the auth middleware honors as GET-only. Two-line addition to `register-mcp-*.sh`.

### MINOR-33 — No handling for "article moved" — slug change post-publish
After a published article gets its slug changed, `internal_links.applied` rows still point at the old URL. CMS-side redirects are out of band. Spec: `articles.slug` is immutable post-publish (CHECK), or all interlinks invalidate on slug change.

### MINOR-34 — `humanizer` and `editor` interaction is undefined
Procedure 7 (L449) runs humanizer → editor. The strip-map L429 says "preserve `draft_md`; editor writes to `edited_md`". On a refresh: humanizer reads `edited_md`, writes back to where? `articles.edited_md` (overwriting the original)? Spec: refreshes use `articles.createVersion` first, then humanizer on the *new* version's `edited_md`.

### MINOR-35 — `firecrawl-py` + `playwright` fallback isn't implementation-ready
L111 says "primary + fallback". Spec the trigger: 5 s timeout? specific HTTP status? specific Firecrawl error shape? Without a spec, the integration silently degrades.

### MINOR-36 — `seed.py` is referenced (L141) but never specified
What seeds: 80-item EEAT default rows; schema_emits templates from codex-seo's templates.json (re-authored); compliance rules — none, since they are project-specific. Spec which.

### MINOR-37 — UI view ProjectSwitcher implies global state but URL routing isn't specified
A user with multiple projects clicks "switch" — does the URL change (`/projects/p1/articles` vs `/articles?project=p1`) or is it client-side state? Spec the routing pattern. Bookmarks and audit-trail links depend on it.

### MINOR-38 — `make build-ui` is referenced but UI-vs-Python release coupling isn't described
L575 says "UI is built once at make build-ui and committed in `content_stack/ui_dist/`". So the UI is committed to git? L171 says it's gitignored. Pick one. If gitignored, CI must build before publish — and there's no CI step in L271.

### MINOR-39 — `procedures/_template/PROCEDURE.md` is part of distribution but not in install-procedures-codex.sh
L240–245, L250–251. The template is for *authoring*, not running. Should be excluded from install. Easy slip.

### MINOR-40 — `Ahrefs` is "optional" but the plan never tells the user how to get an Ahrefs key
L464. Ahrefs API is enterprise-only and very expensive. Spec: `docs/api-keys.md` notes "Ahrefs API requires Enterprise plan; if you don't have one, the keyword-discovery skill works without it". Otherwise the user installs and gets stuck.

### MINOR-41 — No "delete project" cascade is specified
L326 (`DELETE /api/v1/projects/{id}`). What gets deleted? All articles, all topics, all gsc_metrics, all schemas, all interlinks, all credentials? Or is it a soft-delete (`is_active=false`)? Spec it. A user-driven `DELETE` that cascades 7M GSC rows in one transaction will lock the DB for minutes.

### MINOR-42 — Streamable HTTP MCP has known client compatibility gaps that aren't versioned
L630 risk row. Spec which client versions are tested: Codex CLI ≥ X, Claude Code ≥ Y. The doctor script must check the runtime version and fail loudly if too old.

---

## Top 5 risks if you ship as-is

1. **Cody's license blows up the editor pass.** Seven of our 24 skills are sourced from a repo whose license forbids "different or competing frameworks". The strip-map's "we'll re-author and call it fair use" posture is exactly the kind of legal hand-wave that gets a project DMCA'd in week three — *and* it's an easy fix (clean-room reauthor, or pivot the editor source) if we decide pre-M0 instead of post-M7. Worse, codex-seo's own license is internally inconsistent, and our installer literally clones it. Both must be resolved before any skill author touches a `cody` or `codex-seo` file.

2. **Concurrency on a SQLite WAL with a fat `articles` row + parallel procedure-4 runs is going to corrupt content silently.** The plan acknowledges WAL contention but mitigates with "short transactions" — that doesn't address the actual failure mode, which is two skills writing different columns of the same `articles.id` and the second clobbering the first because there's no etag. At concurrency=8 in the bulk-launch (procedure 5), this happens within hours. Drafts disappear, status moves forward, the user finds a published article that's not what they reviewed. Add etag-based optimistic concurrency before M2.

3. **The EEAT gate can be silently disabled by a project owner.** The schema lets a project deactivate every EEAT criterion including the three veto items. The plan calls EEAT a "gate" but doesn't enforce a floor. The whole product value proposition turns into a configurable rubber stamp. Add a `tier='core'` floor that cannot be deactivated.

4. **The procedure runner is unspecified for context-window pressure and crash recovery.** Procedure 4 is 9–10 sequential skills with mutually-dependent state in `articles`. PLAN.md never says whether the LLM client orchestrates or the daemon does. It never says how `runs.status='running'` gets reaped after a crash or sleep. It never says what "resume" means. A user who runs procedure 5 against 50 topics and lets their laptop sleep will return to 50 forever-`running` rows, no resume button, and a DB state that procedure-replay will misinterpret. The "daemon-orchestrated procedures + step-level audit + heartbeat reaping" stack must land in M2/M3, not "later".

5. **Cost runaway and rate-limit blowups are post-hoc, not preventative.** Bulk-launch with no per-integration budget cap, no rate-limit token bucket, and no cascade-abort means the first user to type `/procedure bulk-content-launch 100` sets fire to their DataForSEO/Firecrawl/OpenAI bills before the daemon can track it. The plan logs spend in `runs.metadata_json` *after* the call. Pre-emptive `integration_budgets` table + per-integration token bucket + `run.abort` cascade are required day-one features, not v1.1.agentId: a23a861b21439fb3d (use SendMessage with to: 'a23a861b21439fb3d' to continue this agent)
<usage>total_tokens: 108534
tool_uses: 15
duration_ms: 454878</usage>