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

export interface StatusBadgeProps {
  domain: StatusDomain;
  status: string;
  /** Override label rendering. */
  label?: string;
  /** Force tone (rare — escape hatch). */
  tone?: 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'eeat';
  size?: 'sm' | 'md';
  variant?: 'subtle' | 'solid' | 'outline';
  /** Hide icon. */
  noIcon?: boolean;
  /** Hide label, show icon + dot only (use with title attr). */
  iconOnly?: boolean;
}

const props = withDefaults(defineProps<StatusBadgeProps>(), {
  size: 'sm',
  variant: 'subtle',
});

const def = computed(() => resolveStatus(props.domain, props.status));
const tone = computed(() => props.tone ?? def.value.tone);
const label = computed(() => props.label ?? def.value.label);
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
  >
    <span v-if="!noIcon && def.icon" class="i-lucide" :data-icon="def.icon" aria-hidden="true">
      <!-- icon placeholder; in-app, render lucide-vue-next <component :is="..."> -->
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="9"/>
      </svg>
    </span>
    <template v-if="!iconOnly">{{ label }}</template>
  </UiBadge>
</template>
