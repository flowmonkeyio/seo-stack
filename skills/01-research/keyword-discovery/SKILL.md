---
name: keyword-discovery
description: Expand seed keywords into a deduplicated topic queue using DataForSEO, Reddit, and Google "People Also Ask".
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: codex-seo @ 97c59bcdac3c9538bf0e3ae456c1e73aa387f85a (clean-room; no upstream files read during authoring)
license: clean-room (PLAN.md L843 + docs/upstream-stripping-map.md adapt notes)
allowed_tools:
  - meta.enums
  - project.get
  - cluster.list
  - topic.bulkCreate
  - topic.list
  - integration.test
  - integration.testGsc
  - cost.queryProject
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
  seed_keywords:
    source: args
    type: list[str]
    required: true
    description: Caller supplies one or more seed keywords; the skill expands each into 30-50 long-tail variants.
  max_topics_per_seed:
    source: args
    type: int
    required: false
    default: 50
outputs:
  - table: topics
    write: bulk insert via topic.bulkCreate; rows tagged with source=dataforseo|reddit|paa
  - table: runs
    write: heartbeat + finish on the existing skill-run row; cost rolled up under runs.metadata_json.cost.by_integration
---

## When to use

Run this skill when a project needs a fresh queue of topic candidates and the operator has at least one seed keyword in mind. Procedure 3 (`keyword-to-topic-queue`) drives this skill as its first step. The procedure runner sets `CONTENT_STACK_PROJECT_ID` + `CONTENT_STACK_RUN_ID` and forwards `seed_keywords` as a structured argument.

Skip this skill when the operator already has a seed corpus of competitor URLs — that flow is `competitor-sitemap-shortcut` (skill #5) instead.

## Inputs

The skill reads the following before any external call:

- Project context via `project.get` — resolves `niche`, `domain`, and `locale`. The locale governs DataForSEO's `language_code` and `location_code` parameters; for the default `en-US` project the location code is `2840` and the language code is `en`. Other locales map per the daemon's enum table (`meta.enums`).
- Existing clusters via `cluster.list` — the skill reads the current topical map so it can dedupe newly-discovered keywords against topics already covered.
- Existing topics via `topic.list` — fetches the current queue so duplicates are skipped at insert time rather than rejected by the database's unique constraint.
- Project-month spend via `cost.queryProject` — the skill refuses to start a fresh DataForSEO sweep if the running spend is within 10% of the monthly budget cap, deferring instead with an explicit message to the procedure runner.

The seed keywords arrive as a JSON list on the procedure step argument (e.g., `["sportsbook bonuses", "live betting"]`).

## Steps

1. **Bootstrap.** Read project + locale + niche via `project.get(project_id)`. Pull the integration health table via `integration.test` (and `integration.testGsc` if a GSC credential is present so the cluster step can later cross-reference impressions). If DataForSEO's health probe fails, abort: this skill is a no-op without it. Reddit and PAA are nice-to-have; their failures degrade the run but do not abort.
2. **Seed expansion.** For each seed keyword, build 30–50 long-tail variants by combining four mining strategies:
   - **Modifier overlay.** Append a small modifier vocabulary to the seed: how-to, best, vs, comparison, guide, examples, mistakes, checklist, free, alternative, pricing, review, beginners, tools, template, pros and cons. The exact list is paraphrased and may be tuned per niche; document any niche-specific adds inline so the run is reproducible.
   - **Question mining.** Generate who/what/when/where/why/how variants of the seed.
   - **Intent overlay.** Layer commercial intent modifiers (review, alternative, pricing, comparison) and informational intent modifiers (guide, tutorial, learn).
   - **Related-search lift.** If the LLM client has a native search tool, pull "related searches" and "people also search for" rows and feed them back in as additional seeds for one more pass; otherwise lean on the DataForSEO `keyword_ideas` endpoint described below.
   Normalise variants to lower case, strip leading articles (a/an/the), and remove duplicates inside the seed's batch and against the project's existing `topics`.
3. **DataForSEO sweep.** For each de-duplicated variant batch:
   - Hit the SERP endpoint to capture the top organic results — the URL list will be reused by skills #2 (`serp-analyzer`) and #3 (`topical-cluster`).
   - Hit the keyword-volume endpoint to attach a monthly search-volume estimate.
   - Hit the keyword-difficulty endpoint to attach a difficulty score.
   - Hit the keyword-intent endpoint to attach an intent classification (informational, commercial, transactional, navigational).
   - Hit the trends endpoint when the operator wants to flag rising terms.
   - Hit the "keywords for site" endpoint with the project's own `domain` to surface keywords the site already ranks for; tag those rows so the procedure runner can prioritise low-effort wins.
   - Hit the "intersection" endpoint over a competitor list (when supplied) to find shared targets.
   Each call is preceded by a budget pre-emption check: the daemon's `integrations/dataforseo.py` wrapper consults `integration_budgets` and refuses if `current_month_spend + estimated_cost > monthly_budget_usd`. The daemon raises `BudgetExceededError` (-32012); the skill catches it, emits a heartbeat with the partial state, and surfaces a structured failure message that the procedure runner stores on the step row.
4. **Reddit mining (optional).** When the project's `integration_credentials` carries a Reddit row, expand the seed pool with community-sourced long-tails. For each seed, pick 1–3 niche-relevant subreddits (the project bootstrap procedure should have captured them; if not, prompt the operator). Issue `search_subreddit` and `top_questions` calls and extract candidate keywords from titles, especially titles ending in `?` (those are PAA-class questions). Tag rows `source='reddit'` so the cluster step weights them appropriately.
5. **People-Also-Ask harvest (optional).** Call the daemon's `google-paa` integration on each seed. The wrapper delegates to Firecrawl under the hood; cost is reckoned against the Firecrawl budget, not a separate PAA line. Each return shape is `{questions: [str, ...]}`. Convert each question into a topic candidate; tag rows `source='paa'`.
6. **Intent classification.** For every candidate keyword (DataForSEO + Reddit + PAA), assign one of five intents: informational, commercial, transactional, navigational, mixed. Where DataForSEO returned an explicit intent, trust it. For Reddit/PAA rows, infer from the keyword surface form: `how`/`what`/`why`/`guide`/`tutorial` patterns lean informational; `best`/`top`/`vs`/`review`/`alternative` lean commercial; `buy`/`price`/`coupon`/`sign up` lean transactional; brand/product names lean navigational. Drop pure-navigational rows from the queue — they are not topic candidates.
7. **Dedupe and persist.** Build the final candidate set: every row carries `title`, `primary_kw`, optional `secondary_kws[]`, `intent`, `source`, optional `priority`, and an optional `cluster_id` (left null at this stage; skill #3 fills it). Run a final dedupe pass against the project's existing topics by `(project_id, primary_kw)` so collisions are caught before the database's unique index rejects the batch. Persist via `topic.bulkCreate(project_id, items=[...])`. The streaming progress emitter fires every 50 inserts when N>50 so the procedure runner can render a progress bar.
8. **Roll up cost and finish.** Heartbeat after each external integration so the runs UI shows progress. On step exit, write the cost-of-truth into the existing `runs.metadata_json.cost.by_integration` map (`dataforseo`, `reddit`, `firecrawl` for PAA). Call `run.finish` with the summary `{topics_created, topics_skipped_duplicate, integrations_used}`.

## Outputs

- `topics` — one row per surviving candidate. The combined run typically produces 200–600 rows from 5–10 seeds. The runner's downstream step (`serp-analyzer`) will further narrow the SERP-overlap candidates.
- `runs` — heartbeats during the long DataForSEO sweep; final summary in `runs.metadata_json` keyed `keyword_discovery`. Cost lands under `runs.metadata_json.cost.by_integration`.
- No `clusters` writes — clustering is the next skill's job.

## Failure handling

- **DataForSEO health probe fails.** Abort the step with a structured message. The procedure step's `on_failure` is the procedure-level decision; this skill does not retry the credential test.
- **DataForSEO 429 from a single endpoint.** The wrapper's retry-with-backoff handles transient cases. Persistent rate-limiting bubbles up as `RateLimitedError` (-32011); the skill emits a partial-result heartbeat (any rows already collected for non-rate-limited variants), then aborts the step. The procedure step's `on_failure: retry(2, backoff=exponential)` covers replays.
- **Budget exceeded mid-sweep.** Catch `BudgetExceededError` (-32012); persist whatever has accumulated; finish with a `partial=true` summary; the procedure runner surfaces this to the operator as a "raise the cap or wait until next month" decision.
- **Reddit/PAA failures.** Non-blocking. Log a heartbeat with the failure reason and continue. The DataForSEO branch alone is enough to satisfy the step; community mining is additive.
- **Topic insert collision.** The repository raises `ConflictError` (-32008) on `(project_id, primary_kw)` collision. The skill should not see this in practice — the in-memory dedupe pass handles it — but if it surfaces, skip the offending rows and continue the batch.

## Variants

- **`shallow`** — single DataForSEO endpoint (volume) per variant; skip Reddit/PAA. Fastest and cheapest; useful for quick brainstorming runs.
- **`standard`** — the default flow described above; DataForSEO + optional Reddit + optional PAA.
- **`deep`** — adds the `intersection` endpoint over a competitor list (3–5 competitors), pulls trends per top-volume seed, and runs Reddit + PAA mandatorily. Costs ~3x; produces the richest queue and surfaces gaps in competitor coverage.

The variant is selected via the procedure step's `args.variant` field; the skill reads it from the step input and gates calls accordingly.
