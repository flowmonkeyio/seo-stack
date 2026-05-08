# Upstream attribution

content-stack is a stand-alone implementation. We do **not** vendor any upstream code or prompts. We learn from the upstream repos listed below — patterns, taxonomies, threshold heuristics — and re-author every skill against our own DB schema (PLAN.md §"Database schema") and MCP contract (PLAN.md §"MCP tool contract"). For two of the three skill-source repos we apply a stricter **clean-room** rule (D1, D2): skill authors do **not** read upstream files at all when writing the corresponding skills.

This document, plus the per-skill `derived_from:` field in `skills/<phase>/<skill>/SKILL.md` frontmatter, is the canonical attribution surface. Updated whenever a skill's source pin or posture changes.

## Pinned reference clones

These four repos are cloned read-only at `.upstream/<name>` (gitignored — never committed) for skill-author reference. Pinned commits last verified 2026-05-07 against `git rev-parse HEAD` in each `.upstream/<repo>/` working tree.

| Repo | URL | HEAD SHA | License | Role |
|---|---|---|---|---|
| `codex-seo` | https://github.com/AgriciDaniel/codex-seo | `97c59bcdac3c9538bf0e3ae456c1e73aa387f85a` | **Mixed** — README/pyproject/manifest claim MIT; actual `LICENSE` is "Avalon Reset" proprietary. Treated as proprietary by us. | Pattern reference for skills #1, #2, #3, #14, #16, #20, #21, #22 |
| `cody-article-writer` | https://github.com/ibuildwith-ai/cody-article-writer | `981ab435d192c8c37c17b2948a83e260fb3c0691` | Custom restrictive — `LICENSE.md` "No Adaptation or Derivative Works". | Pattern reference for skills #4, #6, #7, #8, #9, #10, #24 |
| `seo-geo-claude-skills` | https://github.com/aaron-he-zhu/seo-geo-claude-skills | `7ecc77b181190fe17a8e3c22a5f6fe705569dc09` | Apache-2.0 | Pattern reference for skills #11 (CORE-EEAT 80-item rubric) and #15 (interlinker) |
| `codex-plugin-cc` | https://github.com/openai/codex-plugin-cc | `807e03ac9d5aa23bc395fdec8c3767500a86b3cf` | Apache-2.0 | Optional in-product feature: adversarial EEAT review seam. Plugin is **not installed by us**; users install it themselves via Claude Code's plugin marketplace if they want the seam (per D2 cascade). |

## Posture by repo

### `codex-seo` (proprietary "Avalon Reset" — clean-room per D2)

The `LICENSE` file at the repo root is a proprietary "Avalon Reset" license that explicitly forbids derivative works for distribution and requires "active membership in the copyright holder's community program." Six other metadata files (README, pyproject.toml, plugin manifest, per-skill `LICENSE.txt` shims, CITATION.cff) all claim MIT. This is a packaging defect upstream — almost certainly a botched fork chain. We treat the proprietary text as authoritative.

**Our posture (D2, locked):**

1. **No `--with-codex-seo` install flag.** We do not run `git clone` against this repo from any of our install scripts. Users who want it install it themselves directly from the upstream URL.
2. **Skill authors for #1, #2, #3, #14, #16, #20, #21, #22 do not paraphrase codex-seo prompt text or scripts.** They may *read* the upstream for concept verification (the SERP-overlap clustering algorithm, the GSC striking-distance heuristic, the on-page audit checklist categories). They may not copy. The skills are re-authored from PLAN.md and our own knowledge.
3. **No verbatim text** — no prompts, no scripts, no docstrings, no tables transcribed from the upstream. Patterns and taxonomies only.
4. **CI fingerprint check** — `tests/unit/test_no_upstream_substrings.py` (lands at M7 with the first skill) loads `tests/fixtures/upstream-fingerprints.json` and rejects any match in `skills/**/*.md`.
5. **Reconciliation request** — the upstream maintainer should fix the LICENSE-vs-metadata mismatch. If they relicense to MIT, we re-evaluate our posture and may relax to "reference, with attribution."

### `cody-article-writer` (custom restrictive — clean-room per D1)

`LICENSE.md` lines 18–25 read: "**No Adaptation or Derivative Works:** You may not adapt, translate, extend, or otherwise use the codebase to create a different or competing framework, tool, or product." content-stack is, on its face, "a different or competing framework." Attribution does not cure the prohibition.

**Our posture (D1, locked):**

1. **Skill authors for #4, #6, #7, #8, #9, #10, #24 do not read any cody-article-writer file.** Not the SKILL.md, not the references, not the LICENSE, not the README. Skills are authored from PLAN.md's data model (`articles`, `voice_profiles`, `compliance_rules`, `eeat_criteria`, `research_sources`) and the author's general editorial-workflow knowledge. The "ideas" we keep are public-domain editorial-pipeline concepts (brief → outline → draft → editor → polish → publish), not Cody's specific prompt text.
2. **CI fingerprint check** as above (D2 §4) — `tests/fixtures/upstream-fingerprints.json` loads identifying phrases from the upstream so any inadvertent paraphrase trips a build failure.
3. **No "Cody-style" frontmatter fields** — the upstream's structured `voice.tone`, `voice.humor`, `formatting.em_dashes`, `style.opening` fields are **not** carried into our schema. Our `voice_profiles.voice_md` is intentionally free-form markdown so we don't unintentionally encode Cody's design.
4. **No "Cody"-shaped names** — no skill, table, column, or doc filename uses "Cody" or near-clone names.
5. **Optional written exception** — if upstream grants a written license addendum, we relax to "reference, with attribution." We have not requested this; the clean-room path is the conservative default.

### `seo-geo-claude-skills` (Apache-2.0 — reference, with attribution)

The cleanest of the three skill-source repos. Apache-2.0 grants permissive use including derivatives, with attribution + change notice + NOTICE preservation. We rely on this repo for two of the highest-leverage skills:

- **#11 eeat-gate** — the 80-item CORE-EEAT framework (8 dimensions × 10 items, with three veto items T04/C01/R10). We seed our `eeat_criteria` table with these 80 items at project-creation time (per `seed.py`); the rubric then becomes project-customizable per D7 with the three vetoes locked as `tier='core'` and undeactivatable.
- **#15 interlinker** — the 7-step internal-linking workflow + anchor variation table + hard targets.

**Our posture (Apache-2.0):**

1. **Read freely**, paraphrase patterns and tables.
2. **Do not copy verbatim** — re-author every paragraph in our voice and against our schema (e.g., per-criterion grain lives in the `eeat_evaluations` table, not in the upstream's flat audit format).
3. **NOTICE file at repo root** acknowledges Apache-2.0 dependencies (this repo + codex-plugin-cc).
4. **Per-skill `derived_from:` frontmatter** in `skills/02-content/eeat-gate/SKILL.md` and `skills/04-publishing/interlinker/SKILL.md` names this repo + the pinned SHA above + the license.
5. **Version drift** — the CORE-EEAT benchmark is itself a separate repo (`github.com/aaron-he-zhu/core-eeat-content-benchmark`) that evolves. Our seed pins to v3.0; bumping requires a manual `db/seed.py` update with a documented procedure.

### `codex-plugin-cc` (Apache-2.0 — optional in-product feature, not installed by us)

Used as the implementation of the optional adversarial-EEAT-review feature inside content-stack (PLAN.md §"Codex-plugin-cc seam"). Apache-2.0.

**Our posture:**

1. **Not installed by us.** Per D2 cascade, our installer does not pull this plugin. End users install it themselves via Claude Code's plugin marketplace if they want the seam. Disabled by default per project (`integration_credentials.codex-plugin-cc.config_json.enabled=false`).
2. **NOTICE file** at repo root credits OpenAI's Apache-2.0 plugin if the optional install is recommended in our docs.
3. **No vendoring** — we never ship the plugin's code; we shell out to `${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs` at runtime via a daemon-side helper (`integrations/codex_plugin_cc.py`) when the plugin is present and enabled.
4. **Runtime-conditional** — the seam fires only when the calling LLM is Claude Code AND the plugin is enabled per project. Codex CLI sessions hitting our MCP do not invoke this path.

## Pin maintenance

Update this document **and** the per-skill `derived_from:` SHA whenever:

- A skill is re-authored against a newer upstream commit (read-only reference for Apache-2.0 sources; clean-room remains for cody/codex-seo).
- A new upstream is added.
- A licensing posture changes (e.g., upstream relicenses, written exception granted).

The pinned SHAs above are the audit-trail anchor: any future reviewer can `git clone --depth 1` at the pinned SHA and verify what we read or did-not-read at the time of authoring.
