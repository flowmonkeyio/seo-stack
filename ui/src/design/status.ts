/**
 * Canonical status / severity mappings.
 *
 * Single source of truth: every domain status string in the product maps to
 * one of the visual `tone` slots. Components like `StatusBadge` read from
 * these maps, so a backend status string is enough to render correctly —
 * UIs never repeat their own ad-hoc tone logic.
 *
 * Tone slots align with semantic colors in `tokens.ts`:
 *   neutral | info | success | warning | danger | eeat
 *
 * Each entry also carries:
 *   - label: short human form for the badge
 *   - description: tooltip / sr-only longer form
 *   - icon: lucide icon name (rendered via lucide-vue-next)
 *   - dot: whether to prepend a colored dot (for "in-flight" states)
 */

export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'eeat';

export interface StatusDef {
  label: string;
  tone: Tone;
  description?: string;
  /** Lucide icon name. Resolved by consumer. */
  icon?: string;
  /** Show a leading dot — typically for in-progress states. */
  dot?: boolean;
  /** True if this is a transitional state — pulses the dot. */
  inFlight?: boolean;
}

// Build a typed map factory so each map keeps its narrow string-literal keys.
function defineStatuses<K extends string>(map: Record<K, StatusDef>): Record<K, StatusDef> {
  return map;
}

// ---------------------------------------------------------------------------
// Topic statuses — research/ideation pipeline
// ---------------------------------------------------------------------------

export const topicStatus = defineStatuses({
  queued:     { label: 'Queued',     tone: 'neutral', icon: 'clock',         description: 'Waiting for review or assignment.' },
  proposed:   { label: 'Proposed',   tone: 'neutral', icon: 'lightbulb',     description: 'Suggested but not yet reviewed.' },
  approved:   { label: 'Approved',   tone: 'info',    icon: 'check',         description: 'Cleared for clustering or article assignment.' },
  drafting:   { label: 'Drafting',   tone: 'info',    icon: 'pen-line',      dot: true, inFlight: true },
  published:  { label: 'Published',  tone: 'success', icon: 'check-circle' },
  rejected:   { label: 'Rejected',   tone: 'neutral', icon: 'x',             description: 'Removed from active backlog.' },
  clustered:  { label: 'Clustered',  tone: 'info',    icon: 'git-merge',     description: 'Grouped into a topic cluster.' },
  assigned:   { label: 'Assigned',   tone: 'info',    icon: 'user-check',    description: 'Linked to an article in production.' },
  archived:   { label: 'Archived',   tone: 'neutral', icon: 'archive' },
});

// ---------------------------------------------------------------------------
// Article statuses
// ---------------------------------------------------------------------------

export const articleStatus = defineStatuses({
  briefing:    { label: 'Briefing',     tone: 'info',    icon: 'file-text' },
  brief:       { label: 'Brief',        tone: 'neutral', icon: 'file-text' },
  outlined:    { label: 'Outlined',     tone: 'info',    icon: 'list' },
  outline:     { label: 'Outline',      tone: 'info',    icon: 'list' },
  drafting:    { label: 'Drafting',     tone: 'info',    icon: 'pen-line',  dot: true, inFlight: true },
  drafted:     { label: 'Drafted',      tone: 'warning', icon: 'file-edit' },
  draft:       { label: 'Draft',        tone: 'info',    icon: 'file-edit' },
  inReview:    { label: 'In review',    tone: 'warning', icon: 'eye',       dot: true },
  edited:      { label: 'Edited',       tone: 'info',    icon: 'check' },
  eeat_passed: { label: 'EEAT passed',  tone: 'eeat',    icon: 'shield-check' },
  approved:    { label: 'Approved',     tone: 'success', icon: 'shield-check' },
  scheduled:   { label: 'Scheduled',    tone: 'info',    icon: 'calendar-clock' },
  publishing:  { label: 'Publishing',   tone: 'info',    icon: 'upload',    dot: true, inFlight: true },
  published:   { label: 'Published',    tone: 'success', icon: 'check-circle' },
  failed:      { label: 'Failed',       tone: 'danger',  icon: 'alert-triangle' },
  needsRevision: { label: 'Needs revision', tone: 'warning', icon: 'rotate-ccw' },
  refresh_due: { label: 'Refresh due',  tone: 'warning', icon: 'rotate-ccw' },
  'aborted-publish': { label: 'Aborted publish', tone: 'danger', icon: 'x-circle' },
  archived:    { label: 'Archived',     tone: 'neutral', icon: 'archive' },
});

// ---------------------------------------------------------------------------
// Run statuses (procedure execution)
// ---------------------------------------------------------------------------

export const runStatus = defineStatuses({
  queued:    { label: 'Queued',    tone: 'neutral', icon: 'clock' },
  running:   { label: 'Running',   tone: 'info',    icon: 'loader',  dot: true, inFlight: true },
  paused:    { label: 'Paused',    tone: 'warning', icon: 'pause' },
  success:   { label: 'Success',   tone: 'success', icon: 'check-circle' },
  succeeded: { label: 'Succeeded', tone: 'success', icon: 'check-circle' },
  failed:    { label: 'Failed',    tone: 'danger',  icon: 'x-circle' },
  aborted:   { label: 'Aborted',   tone: 'neutral', icon: 'circle-slash' },
  canceled:  { label: 'Canceled',  tone: 'neutral', icon: 'circle-slash' },
  timedOut:  { label: 'Timed out', tone: 'danger',  icon: 'timer-off' },
  partial:   { label: 'Partial',   tone: 'warning', icon: 'circle-dashed' },
});

// ---------------------------------------------------------------------------
// Procedure / job statuses (definition-level, not per-run)
// ---------------------------------------------------------------------------

export const procedureStatus = defineStatuses({
  pending:    { label: 'Pending',   tone: 'neutral', icon: 'clock' },
  running:    { label: 'Running',   tone: 'info',    icon: 'loader', dot: true, inFlight: true },
  success:    { label: 'Success',   tone: 'success', icon: 'check-circle' },
  failed:     { label: 'Failed',    tone: 'danger',  icon: 'x-circle' },
  skipped:    { label: 'Skipped',   tone: 'neutral', icon: 'skip-forward' },
  enabled:    { label: 'Enabled',   tone: 'success', icon: 'circle-check' },
  disabled:   { label: 'Disabled',  tone: 'neutral', icon: 'circle' },
  paused:     { label: 'Paused',    tone: 'warning', icon: 'pause' },
  draft:      { label: 'Draft',     tone: 'neutral', icon: 'file' },
  deprecated: { label: 'Deprecated',tone: 'warning', icon: 'archive-x' },
});

// ---------------------------------------------------------------------------
// Interlink statuses
// ---------------------------------------------------------------------------

export const interlinkStatus = defineStatuses({
  suggested:  { label: 'Suggested',  tone: 'info',    icon: 'sparkles' },
  accepted:   { label: 'Accepted',   tone: 'success', icon: 'check' },
  rejected:   { label: 'Rejected',   tone: 'neutral', icon: 'x' },
  applied:    { label: 'Applied',    tone: 'success', icon: 'link' },
  dismissed:  { label: 'Dismissed',  tone: 'neutral', icon: 'x' },
  broken:     { label: 'Broken',     tone: 'danger',  icon: 'unlink' },
  stale:      { label: 'Stale',      tone: 'warning', icon: 'history' },
});

// ---------------------------------------------------------------------------
// Publish statuses
// ---------------------------------------------------------------------------

export const publishStatus = defineStatuses({
  pending:    { label: 'Pending',    tone: 'neutral', icon: 'clock' },
  pushing:    { label: 'Pushing',    tone: 'info',    icon: 'upload', dot: true, inFlight: true },
  live:       { label: 'Live',       tone: 'success', icon: 'globe' },
  published:  { label: 'Published',  tone: 'success', icon: 'globe' },
  failed:     { label: 'Failed',     tone: 'danger',  icon: 'alert-triangle' },
  rolledBack: { label: 'Rolled back',tone: 'warning', icon: 'rotate-ccw' },
  reverted:   { label: 'Reverted',   tone: 'warning', icon: 'rotate-ccw' },
  unpublished:{ label: 'Unpublished',tone: 'neutral', icon: 'eye-off' },
});

// ---------------------------------------------------------------------------
// Project states
// ---------------------------------------------------------------------------

export const projectState = defineStatuses({
  active:    { label: 'Active',    tone: 'success', icon: 'play-circle' },
  inactive:  { label: 'Inactive',  tone: 'neutral', icon: 'circle' },
  paused:    { label: 'Paused',    tone: 'warning', icon: 'pause' },
  archived:  { label: 'Archived',  tone: 'neutral', icon: 'archive' },
  setup:     { label: 'Setup',     tone: 'info',    icon: 'settings' },
  blocked:   { label: 'Blocked',   tone: 'danger',  icon: 'octagon-alert' },
});

// ---------------------------------------------------------------------------
// Integration health
// ---------------------------------------------------------------------------

export const integrationHealth = defineStatuses({
  healthy:    { label: 'Healthy',    tone: 'success', icon: 'check-circle' },
  degraded:   { label: 'Degraded',   tone: 'warning', icon: 'alert-triangle' },
  failing:    { label: 'Failing',    tone: 'danger',  icon: 'x-circle' },
  notConnected: { label: 'Not connected', tone: 'neutral', icon: 'plug' },
  expiring:   { label: 'Expiring',   tone: 'warning', icon: 'key-round' },
  expired:    { label: 'Expired',    tone: 'danger',  icon: 'key-round' },
});

// ---------------------------------------------------------------------------
// Drift severity
// ---------------------------------------------------------------------------

export const driftSeverity = defineStatuses({
  none:     { label: 'No drift',   tone: 'success', icon: 'check' },
  low:      { label: 'Low',        tone: 'info',    icon: 'arrow-down' },
  medium:   { label: 'Medium',     tone: 'warning', icon: 'arrow-right' },
  high:     { label: 'High',       tone: 'danger',  icon: 'arrow-up' },
  critical: { label: 'Critical',   tone: 'danger',  icon: 'siren' },
});

// ---------------------------------------------------------------------------
// EEAT verdict — uses reserved violet tone slot.
// ---------------------------------------------------------------------------

export const eeatVerdict = defineStatuses({
  unevaluated: { label: 'Unevaluated', tone: 'neutral', icon: 'circle-help' },
  failing:     { label: 'Failing',     tone: 'danger',  icon: 'shield-x' },
  marginal:    { label: 'Marginal',    tone: 'warning', icon: 'shield-alert' },
  passing:     { label: 'Passing',     tone: 'eeat',    icon: 'shield-check' },
  exemplary:   { label: 'Exemplary',   tone: 'eeat',    icon: 'shield-check' },
});

// ---------------------------------------------------------------------------
// Budget / cost states
// ---------------------------------------------------------------------------

export const budgetState = defineStatuses({
  underBudget: { label: 'Under budget', tone: 'success', icon: 'circle-check' },
  onTrack:     { label: 'On track',     tone: 'info',    icon: 'gauge' },
  approaching: { label: 'Approaching',  tone: 'warning', icon: 'trending-up' },
  overBudget:  { label: 'Over budget',  tone: 'danger',  icon: 'alert-octagon' },
  capped:      { label: 'Capped',       tone: 'neutral', icon: 'lock' },
});

// ---------------------------------------------------------------------------
// Aggregate registry — addressable by domain key.
// ---------------------------------------------------------------------------

export const statusRegistry = {
  topic:        topicStatus,
  article:      articleStatus,
  run:          runStatus,
  procedure:    procedureStatus,
  interlink:    interlinkStatus,
  publish:      publishStatus,
  project:      projectState,
  integration:  integrationHealth,
  drift:        driftSeverity,
  eeat:         eeatVerdict,
  budget:       budgetState,
} as const;

export type StatusDomain = keyof typeof statusRegistry;

/**
 * Resolve a status string within a domain. Returns a synthesized neutral
 * fallback rather than throwing — UI should never crash on an unknown status.
 */
export function resolveStatus(domain: StatusDomain, key: string): StatusDef {
  const map = statusRegistry[domain] as Record<string, StatusDef>;
  return map[key] ?? {
    label: key.replace(/[_-]/g, ' '),
    tone: 'neutral',
    description: `Unknown ${domain} status: ${key}`,
  };
}
