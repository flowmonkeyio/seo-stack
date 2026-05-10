---
name: one-site-shortcut
slug: 02-one-site-shortcut
version: 0.1.0
description: |
  Topical-map-fast playbook: pull competitor sitemaps (+ optional
  Ahrefs export) → cluster into pillar/spoke → present queue for
  operator approval → re-cluster the approved subset into the final
  hierarchy. Two-clustering passes ensure the LLM doesn't lock in a
  shape the operator would have to undo by hand.

triggers:
  - "Manual: operator runs `/procedure one-site-shortcut <project-id> --competitors a.com,b.com`"
  - "Parent procedure: invoked from procedure 8 (add-new-site) when the operator picks `--use-shortcut`"

prerequisites:
  - "projects.id exists AND projects.is_active=true"
  - "voice_profiles WHERE project_id=:project_id AND is_default=true exists (procedure 1 / bootstrap-project ensures this)"
  - "procedure 4 prerequisites are NOT required — the shortcut feeds the topic queue, doesn't draft"

produces:
  - clusters
  - topics
  - research_sources
  - runs
  - run_steps
  - procedure_run_steps

inputs:
  competitors: "Comma-separated list of competitor domains (str; required). Each gets its sitemap.xml fetched + optional Ahrefs ranking export pulled."
  topic_cap: "Optional cap on the number of topics surfaced for approval (int; default 50)."

steps:
  - id: competitor-sitemap-shortcut
    skill: 01-research/competitor-sitemap-shortcut
    on_failure: abort
  - id: pre-approval-cluster
    skill: 01-research/topical-cluster
    on_failure: retry
    max_retries: 1
  - id: human-approval
    skill: _programmatic/topic-approval-pause
    on_failure: human_review
  - id: topical-cluster
    skill: 01-research/topical-cluster
    on_failure: abort

variants:
  - name: competitors-only
    description: "Skip the Ahrefs export inside competitor-sitemap-shortcut (faster, sitemap-only signal)."
    args_overrides:
      competitor-sitemap-shortcut:
        use_ahrefs: false
  - name: with-ahrefs
    description: "Require the Ahrefs credential; pulls per-competitor ranking exports for richer cluster signal."
    args_overrides:
      competitor-sitemap-shortcut:
        use_ahrefs: true

concurrency_limit: 2
resumable: true
---

# 02 — One-Site Shortcut

A fast, manual-input-light path to a topical map for operators with a
single site and one or two competitors they want to mirror. The
shortcut trades the rigour of full keyword discovery (procedure 3)
for a sitemap-driven first pass that ships an approved topic queue in
hours rather than days.

## When to use

The operator wants topics live now, not after a multi-day keyword
expansion. Sitemap + (optional) Ahrefs is a strong-enough signal for
"start writing in week one" outputs; procedure 3 covers the deeper
keyword-discovery path when the operator has time.

## Step-by-step

1. **competitor-sitemap-shortcut** (#5) — Fetch each competitor's
   `sitemap.xml`, deduplicate URLs, optionally pull an Ahrefs export
   (kw + traffic data) per the variant. Persists raw rows to
   `research_sources` with `source='competitor-sitemap'`.
   ``on_failure=abort``: a sitemap fetch failure means we have no
   signal to cluster; better surface the error than ship a thin map.
2. **pre-approval-cluster** (#3) — First-pass cluster of the gathered
   URLs into pillar/spoke topics, persisted to ``clusters`` +
   ``topics`` with ``source='competitor-sitemap'`` and
   ``status='proposed'``. ``on_failure=retry(max_retries=1)``: a
   transient LLM hiccup gets one re-shot before we abort.
3. **human-approval** — The operator reviews the proposed topic queue
   in the UI's Topics view, approves / rejects / edits each row. The
   step intentionally pauses (``on_failure=human_review``): in
   practice ``_programmatic/topic-approval-pause`` records
   ``output_json.human_review=true`` and leaves this step current. The
   agent retries once the operator flips ``topics.status='approved'`` on
   their picks.
4. **topical-cluster** (#3) — Second-pass cluster, now over the
   operator-approved subset, builds the final pillar/spoke hierarchy
   the topic queue carries forward. ``on_failure=abort``: a structural
   cluster failure post-approval means the chosen topics don't form a
   coherent map; the operator needs to revisit.

## Variants

- ``competitors-only`` — Skip the Ahrefs export. Faster, no Ahrefs
  credential required, but the cluster signal is sitemap-only.
- ``with-ahrefs`` — Require the Ahrefs credential. Richer signal
  (kw + traffic) drives a more accurate pre-approval cluster.

## Failure handling commentary

- **competitor-sitemap-shortcut / topical-cluster** → ``abort``.
  These are structural; a missing sitemap or a cluster blow-up after
  approval should surface, not paper over.
- **pre-approval-cluster** → ``retry(max_retries=1)``. The first-pass
  cluster is the most LLM-flaky step; one retry covers a transient
  bad output, then we abort.
- **human-approval** → ``human_review``. The operator's review can
  take hours or days; the run's heartbeat keeps it alive while
  waiting. Resume picks up on ``procedure.resume``.

## Relationship to procedure 3 (keyword-to-topic-queue)

Procedure 3 is the deeper, slower path that goes through DataForSEO +
Reddit + PAA + SERP analysis before clustering. Procedure 2 is the
shortcut: trades depth for speed when the operator has competitor
domains they trust. Procedure 8 (`add-new-site`) chooses between the
two via the ``--use-shortcut`` flag.
