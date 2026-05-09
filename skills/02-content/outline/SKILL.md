---
name: outline
description: Compose a hierarchical H1 / H2 / H3 outline from the brief and persist via article.setOutline.
version: 0.1.0
runtime_compat: ["codex", "claude-code"]
derived_from: original
license: project-internal
allowed_tools:
  - meta.enums
  - project.get
  - voice.get
  - eeat.list
  - article.get
  - article.setOutline
  - source.list
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
  article_id:
    source: env
    var: CONTENT_STACK_ARTICLE_ID
    required: true
outputs:
  - table: articles
    write: article.setOutline persists outline_md (status remains outlined; set_brief already advanced briefing → outlined).
  - table: runs
    write: section roster + source-binding map in runs.metadata_json.outline.
---

## When to use

Procedure 4 (`topic-to-published`) runs this skill immediately after `content-brief` (#4). The brief locks the title, thesis, audience, and citable sources; the outline turns those into a section roster the three draft skills (#7 intro, #8 body, #9 conclusion) execute against. The outline is the contract between research and writing — every load-bearing claim in the brief should map to a section, and every required source should map to the section that will cite it.

Skip this skill only when the operator hand-authored an outline through `PATCH /articles/{id}` directly. Re-running this skill on the same article replaces `outline_md` and rotates the step_etag; the procedure runner picks up the fresh etag for the draft phase.

## Inputs

- `article.get(article_id)` — returns the current row including `brief_json` (the title, thesis, audience, intent, target word count, outline hint, EEAT plan, schema types, image directives, compliance jurisdictions) and the live `step_etag` the next call must echo back.
- `voice.get(project_id)` — the active voice profile's `voice_md`. The skill consults voice for two outline-level decisions: which `opening` archetype the intro should target (the brief usually nominates one but voice can override), and which `closing` archetype the conclusion should aim for. Both choices land in `runs.metadata_json.outline` so the draft skills don't have to re-derive them.
- `eeat.list(project_id)` — the active criteria. Surface during outlining the criteria with `tier='core'` (T04 / C01 / R10 by default) and any other `required=true` rows so each section can plan how it satisfies them. Sections that lack a credible plan for a load-bearing criterion get flagged before drafting starts.
- `source.list(article_id)` — the research-source rows the brief seeded with `used=false`. Every source the brief marked `required=true` must be assigned to at least one outline section in step 5; voluntary sources may remain unbound until drafting picks them up.
- `meta.enums` — surfaces the canonical enum values when the section roster or outline metadata needs to reference status / category / position keys without hard-coding them.

## Steps

1. **Read the brief.** Resolve the brief from `articles.brief_json`. Confirm the article is in `status='outlined'` (the only legal entry status — `set_brief` advanced it). If status is anything else, abort with a clear message; the procedure runner will route to repair. Capture the live `step_etag` from the response envelope; every later mutating call in this run echoes it back.
2. **Choose archetypes.** From the brief's `opening_archetype` (when present) and the voice profile, pick one of the four intro archetypes:
   - **Direct** — opens with the thesis stated plainly, then unpacks. Default for transactional and review intent.
   - **Contextual** — opens with a one-paragraph backdrop framing why the topic matters now, then states the thesis. Default for informational evergreen content.
   - **Narrative** — opens with a brief scene or anecdote that surfaces the problem, then names the thesis. Default for opinion and personal-experience content where the voice profile permits first-person.
   - **Tension** — opens by naming a contradiction the article will resolve. Useful when the topic has competing camps (e.g., "is X dead?" pieces).
   For the conclusion, pick one of six closing archetypes:
   - **Summary** — recaps the load-bearing claims, optionally numbered.
   - **Call_to_action** — directs the reader toward a specific next step (sign up, download, compare, contact).
   - **Open_question** — leaves a deliberately unresolved question for the reader to chew on; appropriate when the article opened a debate rather than closed one.
   - **Callback** — returns to the intro's hook (anecdote, contradiction, scene) and closes the loop.
   - **Provocation** — restates the thesis as a sharper claim to lodge in the reader's memory.
   - **Key_takeaways** — a bulleted "if you remember nothing else" list, tuned for skim readers.
   Persist both choices in `runs.metadata_json.outline.archetypes = {opening, closing}` so the draft skills inherit them without re-deriving.
3. **Sketch the H1.** The H1 is the article title. Pull `brief_json.title` as the starting point; refine only when the brief title obviously fails the voice tone (too generic, too clickbaity, too long for SERP). When refining, capture the original in `runs.metadata_json.outline.h1_alternates[]` so the operator can audit the change. The final H1 lands at the top of `outline_md` as a single `# ` line.
4. **Draft the H2 roster.** Translate the brief's `outline_hint_md` into 4–10 H2 sections. Each H2 owns one load-bearing claim from the brief or one stage in the reader's journey from problem to resolution. Aim for sections that are roughly equal in expected word weight — a 1800-word target with 6 H2 sections gives each section ~300 words after the intro and conclusion budget. Sections to consider in standard ordering:
   - **Definition / orientation** — what is the topic and why should the reader care.
   - **Stake / evidence** — the central claim and the data that backs it.
   - **Comparative / breakdown** — sub-cases, options, trade-offs.
   - **Practical / application** — how the reader uses this in their context.
   - **Common mistakes / counter-arguments** — what trips people up.
   - **Decision frame** — how to choose, when to escalate, when to stop.
   The exact section types depend on intent; informational pieces lean toward orientation + evidence + practical, commercial pieces lean toward breakdown + comparative + decision frame, transactional pieces lean toward decision frame + practical + counter-argument. Capture each H2 with a one-line description of its load-bearing claim.
5. **Bind required sources.** Walk every `research_sources` row with `required=true`. For each, pick the H2 (or new sub-section) where the source's evidence will land. The binding map gets persisted in `runs.metadata_json.outline.source_bindings[]` as `{source_id, section_index, role}` triples where role is one of `primary` (a load-bearing citation in the section's central claim), `supporting` (a corroborating cite), or `counter` (the source carries a counter-argument the section addresses). If a required source cannot find a home, surface it before drafting — drop it from required, add a section, or let the operator decide.
6. **Plan EEAT signal placement.** Cross-walk the brief's `eeat_plan` against the section roster. For each `tier='core'` and `required=true` criterion the brief flagged, note which section will surface the signal:
   - **T04 (credentialed-author bio)** — typically a hover-card or footer mention in the conclusion, but some voice profiles surface it inline in the intro.
   - **C01 (compliance disclosure)** — the conclusion's compliance footer (rendered by skill #9) handles `position='footer'` rules; sections with affiliate links surface `position='after-intro'` rules at the section's first occurrence.
   - **R10 (primary-source citation)** — every load-bearing claim in the body sections must cite a research-source row by stable index `[^N]`. Note which section owns each load-bearing citation.
   - **Recommended-tier rows** — cite where the section can. The EEAT gate (#11) does not block on these but does score them.
   Persist the placement plan in `runs.metadata_json.outline.eeat_placement[]`.
7. **Add H3 subsections.** Where an H2 owns more than ~400 expected words or covers more than two distinct points, split it into 2–4 H3 subsections. H3s are most useful in the comparative / breakdown and practical / application sections; intro and conclusion rarely benefit from them. Each H3 carries its own one-line description so the body draft skill knows what to write into it. H4 and deeper nesting is forbidden — the editor pass (#10) tightens prose, not structure.
8. **Section confirmation phase.** Before persisting, present the proposed roster to the operator (when running interactively) or to the procedure runner's verification step (when running headless). The operator can split a section into two, combine two adjacent sections, reorder, or drop. Iterate until the roster is approved. In headless mode, the runner accepts the first complete roster that satisfies the bound-source and EEAT-placement checks; an operator can override by editing `outline_md` after the run and re-running downstream. Capture the iteration count in `runs.metadata_json.outline.confirmation_iterations`.
9. **Render `outline_md`.** Compose the markdown:
   - One `# H1` line at the top (the title).
   - Each H2 as `## ` followed by the section title; immediately below, an HTML comment with the one-line description and load-bearing claim, e.g., `<!-- claim: <one line>; sources: [^3,^7]; eeat: T04,R10 -->`. The comment is invisible in rendered output but the draft skills parse it for their own prompts.
   - Each H3 as `### ` followed by the subsection title; immediately below, the same HTML-comment pattern.
   - At the very bottom, a horizontal rule plus an HTML comment carrying the archetypes, e.g., `<!-- opening: contextual; closing: summary -->`. The intro and conclusion skills read this to choose the right hook.
   Do not include any draft prose; the outline is structure only. Citation markers `[^N]` appear later when the body skill writes the section.
10. **Persist.** Call `article.setOutline(article_id, outline_md=..., expected_etag=<live etag>)`. The repository writes `outline_md`, rotates `step_etag`, and leaves `articles.status='outlined'` (the brief skill already advanced; the draft phase will explicitly close via `mark_drafted` after skill #9). Capture the new etag for the procedure runner to hand to skill #7.
11. **Finish.** Call `run.finish` with `{article_id, h1, section_count, h3_count, archetypes, sources_bound, eeat_placement_count, iterations}`. Heartbeats fire after the section roster is drafted (step 4) and after each iteration of the confirmation phase (step 8) so a long iteration loop stays visible in the runs UI.

## Outputs

- `articles.outline_md` — full markdown with H1 + H2/H3 hierarchy and per-section HTML-comment metadata.
- `articles.step_etag` — rotated; the procedure runner hands the new value to skill #7.
- `runs.metadata_json.outline` — `{archetypes, h1_alternates, source_bindings, eeat_placement, confirmation_iterations}`.

## Failure handling

- **Status not `outlined`.** Abort with `articles.status` mismatch; the procedure runner routes to either `set_brief` (if briefing) or `set_edited`-class repair (if drafted/edited). Do not silently force the status.
- **Brief missing required keys.** Abort. The brief skill should have populated title, thesis, intent, audience, target word count, sources, EEAT plan, and compliance jurisdictions. A truncated brief means a misordered procedure run; surface the missing keys so the runner knows what to repair.
- **Required source has no plausible section home.** Pause for operator review (interactive mode) or write `runs.metadata_json.outline.unbound_sources[]` and continue (headless mode). The body skill will surface the unbound list again at draft time.
- **Iterations exceed cap.** Default cap is 4 iterations; once exceeded, persist the current best roster, mark `partial=true`, and finish so the operator can audit. The cap is generous on purpose — outline iteration is cheap relative to drafting.
- **Etag mismatch.** Means another writer touched the article between read and write. Refuse to overwrite; the procedure runner refreshes by calling `article.get` again and retries.

## Variants

- **`fast`** — skip the explicit confirmation phase; render the first roster that satisfies the bound-source and EEAT-placement checks; useful inside `bulk-content-launch` (procedure 5) where outline-by-committee is too slow.
- **`standard`** — the default flow above, with up to 4 confirmation iterations.
- **`pillar`** — relaxes the section-count cap to 12 H2 sections and raises the H3 budget per section to 6, in service of pillar-shaped articles (4000-word target). Picks the `summary` or `key_takeaways` closing archetype by default to match the longer reader.
