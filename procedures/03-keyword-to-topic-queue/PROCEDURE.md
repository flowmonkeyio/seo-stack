---
name: keyword-to-topic-queue
slug: 03-keyword-to-topic-queue
version: 0.1.0
description: |
  Deeper-path topic discovery — DataForSEO + Reddit + PAA seed
  expansion, optional SERP analysis on the high-value subset,
  hierarchical clustering, then operator approval. Slower than the
  one-site shortcut (procedure 2) but produces a much richer queue
  with verified search-volume + per-URL competitor audits.

triggers:
  - "Manual: operator runs `/procedure keyword-to-topic-queue <project-id> --seed-keywords \"...\"`"
  - "Programmatic: invoked from procedure 8 (add-new-site) when the operator does NOT pick `--use-shortcut`"

prerequisites:
  - "projects.id exists AND projects.is_active=true"
  - "voice_profiles WHERE project_id=:project_id AND is_default=true exists"
  - "integration_credentials.kind='dataforseo' set (the variant `light` does NOT relax this — DataForSEO is core to the discovery step)"

produces:
  - topics
  - clusters
  - research_sources
  - runs
  - run_steps
  - procedure_run_steps

inputs:
  seed_keywords: "Comma-separated seed keywords or a single phrase (str; required). Drives keyword-discovery + downstream expansion."
  topic_cap: "Optional cap on topics surfaced for approval (int; default 100)."
  serp_top_n: "How many top SERP results to audit per high-value keyword (int; default 10). Only used by the deep variant."

steps:
  - id: keyword-discovery
    skill: 01-research/keyword-discovery
    on_failure: retry
    max_retries: 1
  - id: serp-analyzer
    skill: 01-research/serp-analyzer
    on_failure: skip
  - id: topical-cluster
    skill: 01-research/topical-cluster
    on_failure: abort
  - id: human-review-queue
    skill: _programmatic/topic-approval-pause
    on_failure: human_review

variants:
  - name: light
    description: "Skip the SERP analyzer step (faster, less per-URL signal but DataForSEO + Reddit + PAA still drive the queue)."
    steps_omit:
      - serp-analyzer
  - name: deep
    description: "Full pipeline — DataForSEO + Reddit + PAA + per-URL SERP audit + cluster + approval."

concurrency_limit: 2
resumable: true
---

# 03 — Keyword to Topic Queue

The canonical deep-path topic discovery procedure. Combines
DataForSEO keyword-volume data, Reddit thread mining, Google's
People-Also-Ask scraper, and (in the deep variant) per-URL SERP
audits before clustering and operator approval.

## When to use

The operator wants a thoroughly-researched topic queue (not just
"what the competitor ranks for") and is willing to wait minutes-
to-an-hour for the discovery + analysis runs. Procedure 2 is the
shortcut for "start writing today"; procedure 3 is for "build the
quarter's content plan".

## Step-by-step

1. **keyword-discovery** (#1) — DataForSEO seed expansion + Reddit
   thread mining + PAA scraping. Persists rows into
   ``research_sources`` keyed off the seed keyword. Drafts a
   first-cut topic list keyed on volume / competition. The skill
   reads the variant's ``serp_top_n`` arg into the topic-importance
   ranking. ``on_failure=retry(max_retries=1)``: a transient
   DataForSEO 5xx gets one re-shot.
2. **serp-analyzer** (#2) — For the top-N keywords from step 1
   (default 10): fetch each SERP's top-10 result URLs, scrape the
   pages via Firecrawl (or Jina fallback), audit each URL's word
   count, header structure, EEAT signal density. Persists per-URL
   audit blobs in ``research_sources``.
   ``on_failure=skip``: a missing SERP audit is a quality-degradation,
   not a deal-breaker; the cluster step still works on the
   first-cut topics from step 1.
3. **topical-cluster** (#3) — Cluster the discovered topics into a
   pillar/spoke hierarchy. Persists rows to ``clusters`` and
   ``topics`` with ``source='keyword-discovery'`` and
   ``status='proposed'``. ``on_failure=abort``: a structural cluster
   failure means we have no coherent map to surface for approval.
4. **human-review-queue** — Operator reviews the proposed queue +
   cluster suggestions in the UI. Step intentionally pauses
   (``on_failure=human_review``): same pattern as procedure 2 — the
   programmatic handler records ``output_json.human_review=true``; the
   operator flips ``topics.status='approved'`` on their picks; the
   current agent retries or continues once the queue is ready.

## Variants

- ``light`` — Skip the SERP analyzer. Faster, lower API cost
  (no Firecrawl per-URL audits), but the cluster doesn't see
  competitor structure. Useful when the operator just wants a
  first-cut volume-weighted queue.
- ``deep`` — Full pipeline including per-URL SERP audits. Standard
  path for new project content planning.

## Failure handling commentary

- **keyword-discovery** → ``retry(max_retries=1)``. DataForSEO is
  generally reliable; one retry covers transient 5xx, then we abort.
- **serp-analyzer** → ``skip``. The per-URL audits are advisory;
  the topic queue can still be built without them.
- **topical-cluster** → ``abort``. A failed cluster post-discovery
  means the LLM couldn't form a coherent map; the operator needs to
  revisit (likely re-tuning the seed keywords).
- **human-review-queue** → ``human_review``. Operator can take days
  to walk the queue; pausing the run with `status='running'` keeps
  heartbeats firing without burning a runner slot.

## Relationship to other procedures

- Procedure 4 (`topic-to-published`) consumes one approved topic per
  invocation; procedure 3 is its upstream feeder.
- Procedure 5 (`bulk-content-launch`) batches procedure 4 across the
  approved queue.
- Procedure 8 (`add-new-site`) calls procedure 3 instead of procedure
  2 when the operator wants the deep path on a new site.
- Procedure 6 (`weekly-gsc-review`) appends to the same topic queue
  via ``source='gsc-opportunity'``; procedure 3's queue and
  procedure 6's queue interleave naturally.
