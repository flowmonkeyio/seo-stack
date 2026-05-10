# UI Component Inventory

A flat, honest list of what's shipped, what's coming, and what to migrate.

## Shipped — primitives (`ui/src/components/ui/`)

| Component | Notes |
|---|---|
| `UiButton` | variants: primary, secondary, ghost, danger; sizes sm/md/lg; loading; iconLeft/Right |
| `UiIconButton` | square; aria-label required |
| `UiButtonGroup` | segmented |
| `UiInput` | label/help/error wired via UiFormField |
| `UiTextarea` | autosize optional |
| `UiSelect` | native; UiDropdownMenu for rich |
| `UiCheckbox` | indeterminate supported |
| `UiSwitch` | role="switch" |
| `UiRadioGroup` | keyboard arrows |
| `UiRange` | tick marks optional |
| `UiSecretInput` | reveal + copy |
| `UiFormField` | label + control + help/error/dirty |
| `UiDialog` | trap focus; H/B/F |
| `UiConfirmDialog` | builds on Dialog |
| `UiSidePanel` | left/right; 480/720 |
| `UiDropdownMenu` | keyboard arrows; sections |
| `UiPopover` | floating-ui placement |
| `UiTooltip` | hover + focus |
| `UiCard` | density compact/comfortable; optional padding; no nested cards |
| `UiPanel` | flat alt-surface; for sub-sections |
| `UiCallout` | info/warning/danger/success |
| `UiEmptyState` | icon + title + body + primary action |
| `UiLoadingState` | for async regions |
| `UiSkeleton` | shimmer |
| `UiToast` | live region; 5s auto-dismiss |
| `UiBadge` | status, neutral; sm/md |
| `UiProgressBar` | determinate + indeterminate |
| `UiScoreMeter` | radial 0–100 |
| `UiCodeBlock` | copy button |
| `UiJsonBlock` | folding optional |
| `UiDiffBlock` | unified + side-by-side |
| `UiPageHeader` | title + slug + description + actions |
| `UiSectionHeader` | inside cards/panels |
| `UiToolbar` | sticky action bar |
| `UiFilterBar` | search + chips + filters |
| `UiBulkActionBar` | replaces filter bar on selection |
| `UiMetricCard` | label + value + delta |
| `UiDescriptionList` | label/value rows |

## Shipped — domain (`ui/src/components/domain/`)

| Component | Notes |
|---|---|
| `ProjectHeader` | name + slug + state + action slot |
| `ProjectStatusSummary` | grid of UiMetricCard |
| `IntegrationProviderCard` | provider + health + connect/configure/disconnect |
| `IntegrationSetupDialog` | provider credential setup, daemon-owned secrets, OAuth/API/local modes |
| `RunTimeline` | step accordion with progress |
| `RunStepAccordion` | collapsible step output viewer for logs and JSON payloads |
| `ArticleStatusStepper` | 7-step linear stepper |
| `ArticleActionBar` | sticky article detail save/publish/refresh actions |
| `ArticleAssetCard` | asset preview, kind, dimensions, alt text, and actions |
| `EeatScoreCard` | radial + breakdown rows |
| `BudgetMeter` | spend/cap + tone band |
| `LinkSuggestionCard` | interlink candidate row with accept/dismiss/inspect |
| `GscOpportunityCard` | GSC query opportunity with CTR / position metrics |
| `DriftBaselineCard` | drift severity, score, changed fields, and diff action |
| `ScheduleRuleCard` | cron, cap, next-run preview, and run-now actions |
| `ProcedureCard` | procedure list card with run/view actions |
| `SourceLedger` | citations and provenance rows |
| `SchemaEditorPanel` | JSON-LD editor with schema.org type picker |
| `ComplianceRuleRow` | compliance rule state and edit/toggle actions |
| `EeatCriterionRow` | expandable EEAT criterion review row |
| `PublishingTargetCard` | target status, last publish, retry/configure actions |
| `CredentialHealthBadge` | integration status badge backed by `status.ts` |
| `MarkdownSectionEditor` | Markdown editor with toolbar, dirty state, and sanitized preview |

## Design-system showcase

The implementation surface is available at `/__design-system`. It renders the
semantic tokens, canonical status mappings, shipped primitives, and shipped
domain components with content-stack examples.

## Inline duplication patterns to remove

These are the common copy-paste patterns I'd expect to find in views — when migrating, replace each with the listed primitive:

| Inline pattern | Replace with |
|---|---|
| `<button class="bg-blue-600 text-white px-3 py-1.5 rounded">…` | `UiButton variant="primary"` |
| Ad-hoc badge spans with status colors | `UiBadge` + `getStatusTone()` from `status.ts` |
| `<input class="border rounded px-2 py-1">` with separate label/error divs | `UiFormField` + `UiInput` |
| Custom modal with backdrop + dialog box | `UiDialog` |
| Custom dropdown built from `<select>` styled to look rich | `UiDropdownMenu` |
| `<table>` with hand-styled headers | upgraded `DataTable` consuming tokens |
| Hand-rolled tab bars | `TabBar` (upgraded) |
| Inline copy-to-clipboard buttons | `UiCodeBlock` / `UiSecretInput` |
| Hand-rolled empty placeholders | `UiEmptyState` |

## Migration map (representative views)

| View | Primary primitives | Domain components |
|---|---|---|
| Projects list | UiPageHeader, UiFilterBar, UiBadge, UiButton | (none) |
| Project overview | UiPageHeader, UiCard, UiDescriptionList, UiMetricCard | ProjectHeader, ProjectStatusSummary, BudgetMeter |
| Project integrations tab | UiCard, UiButton, UiCallout, UiDialog | IntegrationProviderCard, IntegrationSetupDialog |
| Articles list | UiFilterBar, UiBulkActionBar, DataTable, UiBadge | (none) |
| Article detail | UiPageHeader, UiTabBar, UiCard | ArticleStatusStepper, EeatScoreCard, ArticleActionBar |
| Topics list | UiFilterBar, DataTable, UiBadge | (none) |
| Runs list | UiFilterBar, DataTable, UiBadge | (none) |
| Run detail | UiPageHeader, UiCard, UiCodeBlock, UiJsonBlock | RunTimeline, RunStepAccordion |
| Procedures list | DataTable, UiBadge | ProcedureCard |
| GSC | DataTable, UiMetricCard | GscOpportunityCard |
| Drift | DataTable, UiBadge, UiDiffBlock | DriftBaselineCard |

## Refactor priority

If you're carving up the work:

1. **Articles list** — highest reuse impact (filter bar + bulk + table + badges).
2. **Article detail header/status area** — proves stepper + score card + action bar shapes.
3. **Project integrations tab** — proves card + dialog modal-heavy flow.
4. **Runs / Run detail** — proves timeline + accordion.
5. **Topics list** — duplicate of articles patterns; should drop in trivially after #1.
6. Everything else — incremental.
