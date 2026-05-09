---
name: topical-cluster
description: Group keywords into pillar/spoke clusters using SERP-overlap evidence; persist the resulting topical map.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: original
license: project-internal
allowed_tools:
  - meta.enums
  - project.get
  - cluster.create
  - cluster.list
  - cluster.get
  - topic.list
  - topic.bulkUpdateStatus
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
  topic_status:
    source: args
    type: str
    required: false
    default: queued
    description: Filters which topics enter the clustering pass — typically queued (right after keyword-discovery).
outputs:
  - table: clusters
    write: one row per pillar plus one per spoke; parent_id wires spokes to their pillar.
  - table: topics
    write: cluster_id assigned via the topic repository (a clustering update path that does not require status transitions).
  - table: runs
    write: cluster scorecard in runs.metadata_json.topical_cluster.scorecard.
---

## When to use

After `keyword-discovery` (skill #1) populates the topic queue. The cluster step turns a flat list of keywords into a hub-and-spoke topical map: each cluster has one pillar topic (broad, high-volume) and 2–4 spoke topics (narrower, related). The cluster IDs feed the brief and outline skills (#4, #6) so a draft can declare its place in the map.

Skip this skill when the operator is doing a one-off article and has already chosen its place in an existing cluster — the brief skill can take a `cluster_id` argument directly.

## Inputs

- `project.get` resolves locale and existing cluster topology.
- `cluster.list` returns the existing clusters so we don't double-create.
- `topic.list(project_id, status='queued')` returns the unclustered candidates that arrived from skill #1. The default filter is `queued`; pass `status='approved'` to recluster the human-approved set after a queue review.
- The skill expects each topic row to carry the SERP top-10 URLs for its `primary_kw` in `topic.metadata_json.serp_urls` — `keyword-discovery` populates that field as part of step 3. If a topic is missing SERP data, the skill skips it with a heartbeat warning; rerun `serp-analyzer` against the missing rows first.

## Steps

1. **Pre-group by intent.** Pure pairwise comparison of N topics costs O(N²); for 40 topics that's 780 comparisons. Reduce the load by partitioning topics into intent buckets first (informational, commercial, transactional). Within each bucket the comparison count is roughly N/4 squared, then add a small cross-bucket sweep on the bucket-edge topics. The optimisation rests on the observation that informational and transactional keywords almost never share a top-10 SERP. Document the bucket sizes in the run's heartbeat for reproducibility.
2. **Compute pairwise SERP overlap.** For every candidate pair within a bucket, count how many of the top-10 organic URLs are shared. The shared-URL count drives the relationship taxonomy:
   - **7 to 10 shared** — the keywords target the same page. Merge them: pick the higher-volume keyword as `primary_kw`, fold the other into `secondary_kws[]`. Mark the lower-volume row for status transition to `rejected` via `topic.bulkUpdateStatus` with a metadata note explaining the merge.
   - **4 to 6 shared** — same cluster, different post. Both topics live in the queue; cluster step assigns them the same `cluster_id`.
   - **2 to 3 shared** — adjacent clusters, interlink candidates. Different `cluster_id` rows; the interlinker (#15) will recommend cross-links.
   - **0 to 1 shared** — separate territories. Different clusters; no relationship signal.
   The bucket-edge sweep handles the rare cross-intent overlap (a "best beginner X" query that ranks both informational guides and commercial reviews).
3. **Pick the pillar per cluster.** Within each cluster (set of keywords with mutual 4-to-6 overlap), the pillar is the keyword with the highest search volume AND the broadest intent (informational beats commercial beats transactional for pillar duty). Tie-break by SERP-overlap centrality: the keyword whose SERP overlaps with the most other cluster members. Persist the pillar via `cluster.create(name=<pillar primary_kw>, type='pillar')`. Set the pillar topic's `cluster_id` to the new cluster's id.
4. **Add spokes.** Each remaining cluster member becomes a spoke. Create a child cluster row via `cluster.create(name=<spoke primary_kw>, type='spoke', parent_id=<pillar cluster id>)` and assign the topic to it. Cap each pillar at 4 spokes; a fifth candidate either folds into an existing spoke (if SERP-overlap merits) or gets promoted to its own pillar.
5. **Word-count targets.** The cluster row carries an implicit content-length expectation that the brief skill reads from `meta.enums` defaults: pillar pages target 2500–4000 words, spoke pages target 1200–1800. The procedure-4 brief variant (`pillar` vs `spoke`) overrides this when the operator wants a different shape. Document the targets in the cluster's metadata so the brief skill doesn't have to re-derive them.
6. **Cannibalisation guard.** A topical map is only valuable if no two posts target the same `primary_kw`. After cluster assignment, run a pass over the project's `topics WHERE status IN ('queued','approved','drafting','published')` and reject any newly-clustered row whose `primary_kw` matches an existing approved-or-drafted topic. Use `topic.bulkUpdateStatus` to flip those to `rejected` with a metadata note pointing to the conflicting topic.
7. **Internal-link plan.** The cluster topology implies a mandatory link matrix: every spoke must link up to its pillar; every pillar must link down to every direct spoke; spokes within a cluster should cross-link 2–3 times each; cross-cluster links are rare (0–1 per spoke). The skill does not call the interlinker — it persists the topology, and the interlinker (#15) reads it later.
8. **Cluster scorecard.** Compute a small scorecard per cluster: total search volume across pillar + spokes, average difficulty, intent split, expected CPC range when DataForSEO returned that field, and an "opportunity rating" (low/medium/high) based on volume vs difficulty. Persist into `runs.metadata_json.topical_cluster.scorecard[<cluster_id>]` so the UI can sort the queue.
9. **Finish.** Call `run.finish` with `{clusters_created, spokes_created, topics_merged, topics_rejected_cannibalisation}`. Heartbeats fire after each cluster's spoke assignment so the runs UI is responsive on big batches.

## Outputs

- `clusters` — one pillar row per cluster, plus one spoke row per spoke topic, with `parent_id` wiring spokes to their pillar.
- `topics` — `cluster_id` populated; rejected duplicates flipped to `status='rejected'`.
- `runs.metadata_json.topical_cluster` — the scorecard, the merge log, and the cannibalisation rejections.

## Failure handling

- **Topic missing SERP data.** Skip with a heartbeat warning. The remaining topics still cluster; the missing row stays in `status='queued'` and will re-enter on the next clustering pass after `serp-analyzer` populates its SERP urls.
- **All topics in one bucket fail to overlap.** Treat each as its own cluster (a pillar with no spokes). The interlinker can't help much, but the brief skill can still proceed; the operator may want to expand seed keywords.
- **Conflict on `cluster.create`.** A name collision means the cluster already exists. Read the existing row via `cluster.get`, attach the new spokes to it, and continue.
- **Cannibalisation pass would reject every new topic.** Don't silently empty the queue. Persist the result, finish with `partial=true` and a clear summary message; the operator decides whether to widen the seed or accept the verdict.

## Variants

- **`tight`** — only count clusters with mutual 4-to-6 overlap; everything else stays unclustered. Highest signal, smallest map.
- **`standard`** — the default flow above; produces a working hub-and-spoke map suitable for procedure 4.
- **`exploratory`** — lower threshold (3-to-5) to surface weak associations; tag those clusters `confidence='low'` and let the operator review before approval.
