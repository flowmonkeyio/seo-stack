<!--
  StatusBadge — domain-aware status rendering.
  Reads from src/design/status.ts so backend status strings resolve to
  consistent label + tone + icon across the app.

  <StatusBadge domain="article" status="published" />
  <StatusBadge domain="run"     status="running" />
-->
<script setup lang="ts">
import { computed } from 'vue';
import UiBadge from './ui/UiBadge.vue';
import { resolveStatus, type StatusDomain } from '../design/status';

type LegacyKind = StatusDomain | 'job';

export interface StatusBadgeProps {
  domain?: StatusDomain;
  /** Backward-compatible alias used by the pre-design-system UI. */
  kind?: LegacyKind;
  status: string;
  /** Override label rendering. */
  label?: string;
  /** Force tone (rare — escape hatch). */
  tone?: 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'eeat';
  size?: 'sm' | 'md';
  variant?: 'subtle' | 'solid' | 'outline';
  /** Backward-compatible small variant used by current tables. */
  small?: boolean;
  /** Hide icon. */
  noIcon?: boolean;
  /** Hide label, show icon + dot only (use with title attr). */
  iconOnly?: boolean;
}

const props = withDefaults(defineProps<StatusBadgeProps>(), {
  domain: undefined,
  kind: undefined,
  label: undefined,
  tone: undefined,
  size: 'sm',
  variant: 'subtle',
  small: false,
});

const domain = computed<StatusDomain>(() => {
  const value = props.domain ?? props.kind ?? 'topic';
  return value === 'job' ? 'procedure' : value;
});

const def = computed(() => resolveStatus(domain.value, props.status));
const tone = computed(() => props.tone ?? def.value.tone);
const label = computed(() => props.label ?? def.value.label);
const size = computed(() => props.size ?? (props.small ? 'sm' : 'sm'));
</script>

<template>
  <UiBadge
    :tone="tone"
    :variant="variant"
    :size="size"
    :dot="def.dot"
    :pulse="def.inFlight"
    :title="def.description ?? label"
    :aria-label="iconOnly ? label : undefined"
    :data-status="status"
    :data-kind="kind ?? domain"
  >
    <template v-if="!iconOnly">
      <slot>{{ label }}</slot>
    </template>
  </UiBadge>
</template>
