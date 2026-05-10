# UI Design System

The canonical reference. Tokens live in code; rules live here. If you find yourself making a one-off button, you're wrong — extend the primitive instead.

## 1. Product UI principles

1. **Operational, not promotional.** This is admin tooling. Calm > exciting.
2. **Density is a feature.** Operators scan many rows. 13/18 body, 32px controls.
3. **Keyboard-first.** Every action reachable with `Tab` + `Enter`/`Space`. Focus rings always visible.
4. **Predictability over delight.** Same shape, same place, same shortcut, every screen.
5. **State is information.** Loading, dirty, saved, error, disabled — all explicit, all consistent.
6. **No surprises.** Destructive actions confirm. Navigation does not. Auto-save is communicated.

## 2. Visual language

- Neutral grayscale base; one blue accent.
- Status tones used semantically only: emerald (success), amber (warning), red (danger), blue (info), violet (EEAT only).
- Subtle borders > heavy shadows.
- 8px max radius. 4px on controls, 6px on cards, 8px on dialogs.
- Dark mode flips the semantic layer; component CSS does not branch.

## 3. Tokens

All defined in `ui/src/design/tokens.ts` and mirrored as CSS variables in `colors_and_type.css`. Categories:

| Token group | Examples |
|---|---|
| Color · surface | `bg.app`, `bg.surface`, `bg.surfaceAlt`, `bg.sunken`, `bg.inverse`, `bg.overlay` |
| Color · foreground | `fg.strong`, `fg.default`, `fg.muted`, `fg.subtle`, `fg.disabled`, `fg.inverse`, `fg.link`, `fg.onAccent` |
| Color · border | `border.subtle`, `border.default`, `border.strong`, `border.focus` |
| Color · accent | `accent.primary`, `accent.primaryHover`, `accent.primarySubtle`, `accent.primaryFg` |
| Color · status | `success.*`, `warning.*`, `danger.*`, `info.*`, `neutral.*`, `eeat.*` |
| Spacing | `0–24` (4px grid) |
| Radius | `xs:2`, `sm:4`, `md:6`, `lg:8`, `full` |
| Shadow | `xs`, `sm`, `md`, `lg`, `xl` |
| Z-index | `dropdown:1000`, `sticky:1100`, `popover:1200`, `tooltip:1300`, `modal:1400`, `toast:1500` |
| Typography | `display.lg`, `display.md`, `h1`, `h2`, `h3`, `body.lg`, `body`, `body.sm`, `overline`, `mono` |
| Layout | `width.narrow:768`, `width.default:1280`, `width.wide:1536`, `sidebar:240`, `topbar:52` |
| Focus | `ring.width:2`, `ring.offset:2`, `ring.color: border.focus` |

**Rule:** components consume semantic tokens. They never reference raw palette values.

## 4. Layout rules

- Sidebar: 240px, collapsible to 56px.
- Top bar: 52px. Sticky. Solid `bg.surface`, no blur.
- Page content: max `1536px` (wide), `1280px` (default), `768px` (reading).
- Page header: title, slug, description, action cluster (right). Breadcrumbs optional, above title.
- Tab bar separates the page header from page body. 32px tab height, 2px active underline in `accent.primary`.
- List pages: filter bar (sticky), table, pagination/footer. Bulk action bar appears on selection, takes filter bar's slot.
- Detail pages: page header, tab bar, tab content. No nested cards.

## 5. Component usage rules

**UiButton.** Default `secondary`. `primary` only for the page's single dominant action. `danger` only on destructive verbs. Never two `primary`s in one cluster.

**UiCard.** For real things — projects, articles, runs, integrations. **Never nested.** When you want a card inside a card, you want a `UiPanel` or a `UiSectionHeader` + plain divider.

**UiDialog.** Header / body / footer. Footer right-aligned, ghost cancel + primary confirm. Trap focus. `Esc` closes unless `dirty`.

**UiSidePanel.** Right edge, 480px default, 720px for editors. Same H/B/F structure as dialog.

**UiToast.** Top-right, 320px, auto-dismiss after 5s except `danger` (sticky). One queue, max 3 visible. Live region.

**UiFormField.** Label + control + help OR error (not both) + dirty indicator. 12–16px between rows.

**UiCallout.** Use sparingly. One per region. `info` for context, `warning` for attention, `danger` for failure, `success` for confirmation.

**UiBadge.** Status only. Never decorative. Always paired with `status.ts` mapping — never inline string compares.

**Tables.** Compact density (32px row), comfortable for editor density (40px row). Never auto-wrap; use `truncate` + tooltip on overflow. Sticky header. Selection column: 32px.

## 6. Accessibility

- WCAG AA contrast for all text (semantic tokens are tuned for this in both modes).
- All interactive elements have a focus ring (2px outline, 2px offset, `--color-border-focus`).
- `aria-label` on icon-only buttons.
- Dialogs trap focus, restore on close, label via `aria-labelledby`.
- Toasts go in a `role="status"` live region (or `role="alert"` for danger).
- Keyboard: `?` opens shortcut help, `⌘K` opens command palette, `j/k` move list selection, `Esc` cancels.
- Headings are semantic (`<h1>` per page, then nested), not styled `<div>`s.
- Tables use `<th scope>`. Sort buttons inside `<th>` with `aria-sort`.
- Forms: every input has a `<label for>`. Errors linked via `aria-describedby`.

## 7. Responsive behavior

- ≥1280px: full layout, sidebar visible, tables full-width.
- 1024–1280px: sidebar collapses to 56px icon rail.
- 768–1024px: sidebar becomes a drawer (`UiSidePanel` from left). Filter bar wraps.
- <768px: page header stacks (title above actions). Tables go horizontally scrollable in a wrapper. Dialogs go full-screen with safe-area insets.
- Forms: never inline labels at <768px. Always above-the-input.

## 8. Dark mode

- Triggered by `data-theme="dark"` on `<html>`.
- Component CSS uses tokens only. **Do not write `dark:` Tailwind variants** in components.
- Backgrounds invert (lightest → darkest), foregrounds invert, borders soften.
- Status tones desaturate slightly to avoid neon in low light.
- Focus ring keeps the same accent — recognition matters across themes.

## 9. Anti-patterns

- ❌ Marketing hero sections with oversized type or background gradients.
- ❌ Cards inside cards. Panels inside cards is fine. Cards inside panels is fine.
- ❌ Decorative gradients, mesh, blobs, glass/blur backgrounds.
- ❌ Emoji as status indicators.
- ❌ Hand-rolled icon SVG when Lucide ships one.
- ❌ Two primary buttons in one cluster.
- ❌ Toast for non-actionable info that belongs in the page state.
- ❌ Spinners on synchronous transitions.
- ❌ `dark:bg-...` in component code — use semantic tokens instead.
- ❌ Bouncy / spring animations.
- ❌ Purple as a primary brand color.
- ❌ Hidden focus styles (`outline: none` without replacement).
