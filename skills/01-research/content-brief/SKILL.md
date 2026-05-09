---
name: content-brief
description: Compose a complete content brief — title, thesis, intent, audience, sources, target word count — and persist via article.setBrief.
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
  - article.create
  - article.setBrief
  - source.add
  - source.list
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
  topic_id:
    source: env
    var: CONTENT_STACK_TOPIC_ID
    required: true
  article_id:
    source: env
    var: CONTENT_STACK_ARTICLE_ID
    required: false
    description: When omitted the skill calls article.create to mint a fresh row from the topic; when present (resume after a partial run) the skill writes against the existing row.
  depth:
    source: args
    type: str
    required: false
    default: medium
    description: One of light | medium | heavy — drives source-count and research effort.
outputs:
  - table: articles
    write: article.setBrief persists brief_json + advances articles.status from briefing → outlined.
  - table: research_sources
    write: source.add persists each citable source with title, url, snippet, used flags.
  - table: runs
    write: brief composition trail; per-source rationale captured under runs.metadata_json.content_brief.
---

## When to use

This is the first authoring step inside procedure 4 (`topic-to-published`). After topic approval but before outline drafting, the brief locks the title, the thesis, the intended audience, the primary keyword's intent, the citable sources, and the per-jurisdiction compliance requirements. Every later draft skill (#7 intro, #8 body, #9 conclusion) reads from `articles.brief_json` so the brief is the single source of truth for the article's identity.

Skip this skill when the operator hand-authored a brief in the UI — that flow writes through `PATCH /articles/{id}` directly.

## Inputs

- `project.get(project_id)` — niche, locale, domain.
- `voice.get(project_id)` — the active voice profile's free-form `voice_md`. The brief composes title and thesis with the voice in mind; the editor skill (#10) leans on this same voice during polish.
- `compliance.list(project_id)` — every active rule. The brief stores the applicable jurisdictions in `brief_json.compliance_jurisdictions[]` so the conclusion skill (#9) knows which footers to render.
- `eeat.list(project_id)` — the active EEAT criteria. The brief notes which expertise/authority/trust signals the article must surface (e.g., a credentialed author bio, primary-source citations, original data) so the EEAT gate (#11) doesn't fail later for missing signals the brief could have flagged.
- `article.get` — when the procedure runner is resuming a brief on an existing article row, read the prior state.
- `source.list(article_id)` — when resuming, deduplicate against sources already collected.

## Steps

1. **Resolve the article.** When `article_id` is unset, call `article.create(project_id, topic_id, status='briefing')` to mint a fresh row that inherits `topic.title` and `topic.primary_kw`. The article row is the durable container; `brief_json` is the column we populate.
2. **Read the project context.** Fetch voice, compliance, EEAT criteria, and the topic's cluster row (`cluster.get(topic.cluster_id)` if non-null). The cluster carries the pillar/spoke distinction and the implied word-count target; respect it unless the procedure variant overrides.
3. **Title + thesis.** Compose a title that obeys the voice's tone slider and the topic's primary keyword. The title is concise (50–60 chars when possible to fit a SERP listing), specific, and free of clickbait fluff. The thesis is the article's argument in one sentence — what the reader will know after reading. Capture both in `brief_json.title` and `brief_json.thesis`. Iterate internally if the first pass reads as generic; the brief is the contract that the rest of the pipeline executes against.
4. **Audience and intent.** Capture `brief_json.audience` (one paragraph describing the reader: their role, their existing knowledge, their goal in landing on this article) and `brief_json.intent` (informational / commercial / transactional / navigational / mixed — the topic.intent is a starting point but the brief refines it based on how the title is phrased).
5. **Word-count target.** Pull from the cluster row's metadata when present; default to 1800 words for spokes, 4000 for pillars, 800 for short variants. The procedure can override via `args.target_word_count`.
6. **Research depth and sources.** The depth tier governs source count and research effort:
   - **Light depth** — target one to five citable sources; suitable for opinion pieces, listicles, or content where authority lives in the author's voice rather than external evidence.
   - **Medium depth** — target six to eleven sources; the default for most informational and commercial articles where the EEAT gate will check for evidence-backed claims.
   - **Heavy depth** — target twelve to twenty sources; required for YMYL topics (medical, financial, legal) where the EEAT gate's `tier='core'` veto criteria expect dense citation.
   For each source the skill captures a structured row: `url`, `title`, `domain`, `snippet`, `relevance` (a one-sentence rationale), `required` (true/false — did the EEAT or compliance pass demand this exact source?), `accessed_at`. The skill collects these by reading the prior `serp-analyzer` run's audited URLs (`runs.metadata_json.serp_analyzer.audits[]` keyed under the same article's `primary_kw`) and adding fresh sources via Firecrawl scrapes when the SERP set is too thin or stale. Use `source.add` to persist; mark `used=false` because outline + draft skills choose which sources actually show up in the article.
7. **Outline hint.** A markdown skeleton with H1 + 4–8 H2 candidates and a one-line description per H2. Persist as `brief_json.outline_hint_md`. The outline skill (#6) refines this; the brief simply seeds it so the outline skill doesn't start from a blank page. Each H2 maps to a section that satisfies one of the brief's load-bearing claims.
8. **Compliance jurisdictions.** Filter `compliance.list` results by the project's active locale set; the brief carries the resulting jurisdiction list in `brief_json.compliance_jurisdictions[]`. The conclusion skill renders footers per the rules at `position='footer'` for each jurisdiction.
9. **Schema hint.** Suggest the JSON-LD types this article should emit, based on intent: Article + FAQPage for informational; Article + Review/AggregateRating for review content; Article + HowTo (deprecated — avoid) replaced by step-marker H3s. Capture under `brief_json.schema_types[]`.
10. **EEAT signal plan.** Walk the active EEAT criteria. For each criterion in the four core dimensions (Experience / Expertise / Authority / Trust), note in `brief_json.eeat_plan` how this article will satisfy it: which source citations carry the authority signal, how the author bio should be surfaced (passing the credentialed-author T04 veto), how primary-source claims will be flagged (passing the citation R10 veto), how compliance footers map to jurisdictions (passing the disclosure C01 veto).
11. **Image directives.** Capture `brief_json.image_directives = {count, style?, alt_text_hints?, allow_real_persons?}`. The image-generator skill (#13) reads this; the brief leaves `style` unset when the project's voice already specifies it.
12. **Persist.** Call `article.setBrief(article_id, brief_json=...)`. The repository call advances `articles.status` from `briefing` → `outlined` per audit clarification (skill #4 owns this transition). The mutating tool returns a `WriteEnvelope` with the updated article row; capture the new `etag` for the next skill in the chain.
13. **Finish.** `run.finish` with `{article_id, sources_added, depth, target_word_count, intent}`. Heartbeats fire after each source.add to keep the runs UI responsive.

## Outputs

- `articles.brief_json` — fully populated; the contract the rest of procedure 4 executes.
- `articles.status` — advanced from `briefing` to `outlined`.
- `research_sources` — one row per citable source with `used=false`.
- `runs.metadata_json.content_brief` — composition trail.

## Failure handling

- **Voice missing.** Refuse to compose. The procedure-1 bootstrap should have written a default voice; if it didn't, abort with a structured message asking the operator to run procedure 1.
- **EEAT criteria below floor.** Per audit D7 the eeat-gate refuses to score when any dimension has zero active criteria. The brief skill checks this at composition time and aborts early so the procedure doesn't run all the way through draft + editor only to fail at the gate. Surface the dimension that's empty.
- **Source.add returns conflict.** A duplicate `(article_id, url)` is benign — skip and continue. Repeated conflicts on every source means the brief is being re-run on a complete row; check `articles.status` first.
- **DataForSEO/Firecrawl unavailable.** Best-effort fallback: cite from `serp-analyzer`'s prior run only. If no prior SERP audit exists, abort with a clear message that asks the procedure runner to run skill #2 first.

## Variants

- **`light`** — one to five sources; smallest target word count; intended for short opinion or list articles.
- **`medium`** — six to eleven sources; default depth for the standard article shape (1500–2000 words).
- **`heavy`** — twelve to twenty sources; required for YMYL or pillar articles; pulls in the deeper EEAT signal plan and a `references_section` directive that the conclusion skill renders.
