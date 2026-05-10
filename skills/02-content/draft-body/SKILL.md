---
name: draft-body
description: Write each H2 / H3 body section against its bound sources, insert citation markers, and append via article.setDraft.
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
  - article.setDraft
  - source.list
  - source.update
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
  - table: articles
    write: article.setDraft (append=true) appends body sections to draft_md; status remains outlined.
  - table: runs
    write: per-section status, source-utilisation, citation-insertion log in runs.metadata_json.draft_body.
---

## Shared operating contract

Before executing, read `../../references/skill-operating-contract.md` and
`../../references/seo-quality-baseline.md`. Apply the shared status, validation,
evidence, handoff, people-first, anti-spam, and tool-discipline rules before the
skill-specific steps below.

## When to use

Procedure 4 calls this skill after `draft-intro` (#7). The body fills the H2 / H3 frame the outline drew, citing the research sources the brief seeded. The body is the largest single chunk of word count in any article — typically 70–80% of the target — so this skill iterates section-by-section with heartbeats so the procedure controller can show progress and the operator can intervene if a section drifts.

The body uses `article.setDraft(append=true)`: each section appends to the existing `draft_md`. A re-run replaces only the sections affected when the procedure runner reframes the article via `expected_etag` rotation.

## Inputs

- `article.get(article_id)` — returns `outline_md` (with HTML-comment metadata per section), `brief_json`, the live `step_etag`, the existing `draft_md` (which contains the intro from skill #7). Confirm `status='outlined'` (the body must run before `mark_drafted`).
- `voice.get(project_id)` — the active voice's `voice_md`. The body inherits the same tone and formality the intro set; do not drift mid-article. Surface the voice's `structure.examples` slider (lists / tables / diagrams / code / quotes / case_studies) and `structure.example_density` setting because the body is where examples mostly land.
- `compliance.list(project_id)` — every active rule. The body skill renders `position='every-section'` rules at the head of each H2 section; the conclusion skill (#9) handles `position='footer'` rules.
- `eeat.list(project_id)` — the active criteria. The body's primary EEAT job is R10 (primary-source citation): every load-bearing claim should carry a `[^N]` marker tied to a research source. Surface `tier='core'` and `required=true` rows so the body skill knows what gates the EEAT pass will check.
- `source.list(article_id)` — the research-source rows. The brief and outline bound required sources to specific sections; the body resolves those bindings and consumes additional voluntary sources where claims need backing. Track per-section source utilisation in `runs.metadata_json.draft_body.section_sources[]` so a follow-on EEAT-FIX loop can see which claims in which sections went uncited.
- `meta.enums` — surfaces enum values referenced in the body (e.g., `compliance_position` keys, `eeat_category` codes when surfacing the EEAT plan inline).

## Steps

1. **Read context.** Resolve the article and parse `outline_md` for the H2 / H3 roster. Each H2 carries an HTML-comment line of the form `<!-- claim: <one line>; sources: [^a,^b]; eeat: <codes> -->`; parse it. Pull the live `step_etag`. Read `runs.metadata_json.outline.source_bindings` and `eeat_placement` so the body inherits the outline's plan instead of redoing it.
2. **Initialise per-section trackers.** For each H2 in the roster, mint a tracker with status `pending`. The trackers persist in `runs.metadata_json.draft_body.section_status[]` so the procedure runner's heartbeat surface shows real-time progress. Heartbeats fire after each section's status transitions `pending → in_progress → complete` (or `failed`).
3. **Iterate per H2.** For every H2 in outline order:
   1. Mark the tracker `in_progress` and emit a heartbeat.
   2. Render the section heading exactly as the outline did (`## ` line). Strip the HTML-comment line — the rendered draft does not surface the planning metadata to readers.
   3. **Render `position='every-section'` compliance** at the top of the section if any active rule applies (typically gambling-affiliate disclosures or supplement-claim disclaimers).
   4. **Write the section prose.** Give each section enough room to satisfy its claim and source obligations, using the brief's depth/target length hint only as a scope guard. Do not pad thin sections to hit a number; expand only when the reader needs evidence, examples, comparisons, or caveats. Open with a sentence that names the section's load-bearing claim from the HTML-comment metadata. Develop the claim with evidence drawn from the bound sources. Close with a transition sentence that points the reader at the next section without explicitly naming it.
   5. **Insert citation markers** at the end of every load-bearing sentence. The marker syntax is `[^N]` where N is the stable index from `source.list`. A sentence may carry multiple markers when multiple sources support the claim: `... a 23% drop in retention.[^4][^11]`. The body never writes the footnote definitions; those land at the end of the draft once the conclusion skill closes out, and the editor pass tightens.
   6. **Render H3 subsections** when the outline declared them. Each H3 follows the same pattern: render heading, write prose, cite. H3 word weight is roughly H2 weight divided by the number of H3 children; sum to the H2's total.
   7. **Choose `voice.structure.example_density` examples.** Pick a list, table, diagram (rendered as ASCII or referenced as an image directive), code block, blockquote, or case-study sketch. Use no more than one example block per H2 in `low` density, two in `moderate`, three in `generous`. Examples must serve the section's claim, not decorate.
   8. **Mark the tracker `complete`.** Persist the section's source-utilisation list (`{section_index, sources_used: [4, 11], sources_required: [4], sources_voluntary: [11]}`).
4. **Render unbound-source warnings.** Walk `runs.metadata_json.outline.unbound_sources[]` (if any) and check whether the body drafting absorbed them into a section. Sources the body never cited get logged in `runs.metadata_json.draft_body.unused_sources[]` so a downstream EEAT-FIX loop can decide whether to add a section or relax the requirement.
5. **Plant deeper EEAT signals.** Beyond R10 (citation density), the body is where Expertise (Ept) and Authority (A) get their best evidence: original analysis, comparison tables, named experts quoted by source. Surface in `runs.metadata_json.draft_body.eeat_signals[]` which sections planted which signals so skill #11 can audit. Do not invent expertise the brief did not declare; `unmet_signals` propagates from skill #7.
6. **Compose the section markdown and append.** After each section completes, call `article.setDraft(article_id, draft_md=<section markdown only>, append=true, expected_etag=<live etag>)`. Each call rotates the etag — capture the new value before the next section's setDraft. Appending per section instead of writing the entire body in one call keeps the procedure runner's progress surface accurate and lets a section-level failure recover at the section boundary instead of the whole body.
7. **Mark `used=true` on cited sources.** For every source whose `[^N]` marker landed in the draft, call `source.update(source_id=<id>, used=true)` so the conclusion skill's references section knows which to render and the EEAT gate (#11) can detect the "required source went uncited" failure mode.
8. **Final consistency pass.** Walk the appended sections and check:
   - Every required source bound to the body in the outline has at least one citation marker.
   - No section opened with a filler stem (the editor pass will catch most of these but flagging them now reduces editor work).
   - Heading levels match the outline exactly (no surprise H4s; no skipped H2s).
   - Voice consistency holds — first-person remains first-person, formality slider remains stable.
   Surface any drift in `runs.metadata_json.draft_body.consistency_warnings[]`.
9. **Finish.** Call `run.finish` with `{article_id, sections_drafted, h3_count, citations_inserted, sources_used, sources_unused, consistency_warnings}`. Heartbeats already fired per section in step 3.

## Outputs

- `articles.draft_md` — H1 + intro + body H2/H3 sections in outline order. The conclusion (#9) appends afterward.
- `articles.step_etag` — rotated per section; the procedure runner hands the most recent value to skill #9.
- `research_sources.used` — flipped to `true` for every cited source.
- `runs.metadata_json.draft_body` — per-section trackers, source utilisation, EEAT signal placement, consistency warnings.

## Failure handling

- **Status not `outlined` or `drafted`.** Abort; refuse to clobber. `set_draft` accepts both, but the body should never run before the intro or after the conclusion.
- **Required source missing from `source.list`.** Surface the missing source in `runs.metadata_json.draft_body.missing_required_sources[]` and continue with voluntary sources only; the EEAT gate (#11) will flag the FIX-class failure if it matters. Do not silently drop the requirement.
- **Per-section `set_draft` returns conflict.** Means another writer touched `draft_md` between sections (rare in headless procedure runs; possible during an interactive override). Refresh the article via `article.get`, capture the new etag, retry the failed section once. Two consecutive conflicts on the same section means the procedure runner restarts the body skill from the intro boundary.
- **Voice drift detected.** Log in `consistency_warnings`; do not abort. The editor pass cleans most drift; the EEAT gate's tone-consistency check can downgrade if drift is severe.
- **Compliance rule body missing.** Persist a `runs.metadata_json.draft_body.compliance_render_failures[]` entry and continue rendering remaining rules; the EEAT gate flags the section.
- **Cited source's `used=true` flip fails.** Continue; the conclusion skill re-flips with `source.update` during its own pass.

## Variants

- **`fast`** — single-pass body without the consistency check in step 8; useful inside `bulk-content-launch`.
- **`standard`** — the default flow above.
- **`pillar`** — relaxes the H2 word weight cap, permits longer evidence blocks (tables up to 8 rows, code blocks up to 30 lines, multi-paragraph case studies), and runs the consistency pass twice.
