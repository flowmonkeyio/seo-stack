# Changelog

## Unreleased

- Added the `marketing` plugin: `marketing.campaign-production` workflow
  template (brief intake, campaign workspace with `campaign.md`, planned media
  manifest, operator plan approval, media production, landing page variants,
  visual signoff, local gallery, closeout), `brand-profile` /
  `campaign-brief` / `campaign-evidence` resources, five campaign agent
  presets, and the campaign production orchestrator skill preset.
- Added `utils.image.edit`: GPT Image edits with input reference images from
  generated assets for product-faithful marketing shots, including
  `input_fidelity` handling and gpt-image-2 free-form sizes on both image
  actions.
- Added the provider-neutral `video-generation` provider with credential
  wiring and the deferred `utils.video.generate` action contract
  (`deferred-video-backend-selection`); execution becomes available once a
  supported vendor backend connector lands.

## 1.0.0 - 2026-05-26

- Pivoted the product architecture to StackOS: project-scoped plugins,
  workflow templates, run plans, generic resources/artifacts, no-secret auth
  references, context, learnings, experiments, decisions, and action execution.
- Reframed SEO as a first-party plugin domain rather than the core product
  shape.
- Simplified the UI direction around generic StackOS renderers.
- Updated documentation to describe the current clean-cut architecture.
