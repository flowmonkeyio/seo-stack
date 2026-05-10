<!--
  UiCallout — inline message inside content. NOT a toast.
  Used for pre-action warnings, persistent errors on a form, info notes.
-->
<script setup lang="ts">
import { computed } from 'vue';

export interface UiCalloutProps {
  tone?: 'info' | 'success' | 'warning' | 'danger' | 'neutral';
  title?: string;
  /** Allow user to dismiss. Emits `dismiss`. */
  dismissible?: boolean;
  /** Compact spacing. */
  density?: 'compact' | 'comfortable';
}

const props = withDefaults(defineProps<UiCalloutProps>(), {
  tone: 'info',
  density: 'comfortable',
});

defineEmits<{ (e: 'dismiss'): void }>();

const toneStyles = computed(() => ({
  info:    { bg: 'bg-info-subtle',    border: 'border-info-border',    fg: 'text-info-fg',    icon: 'M13 16h-1v-4h-1m1-4h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z' },
  success: { bg: 'bg-success-subtle', border: 'border-success-border', fg: 'text-success-fg', icon: 'm5 12 5 5 9-12' },
  warning: { bg: 'bg-warning-subtle', border: 'border-warning-border', fg: 'text-warning-fg', icon: 'M12 2 2 22h20L12 2zM12 9v4m0 4h.01' },
  danger:  { bg: 'bg-danger-subtle',  border: 'border-danger-border',  fg: 'text-danger-fg',  icon: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0ZM15 9l-6 6m0-6 6 6' },
  neutral: { bg: 'bg-neutral-subtle', border: 'border-neutral-border', fg: 'text-neutral-fg', icon: 'M12 16v-4m0-4h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z' },
}[props.tone]));
</script>

<template>
  <div
    role="status"
    :aria-live="tone === 'danger' ? 'assertive' : 'polite'"
    :class="[
      'ui-callout flex gap-3 rounded-md border',
      toneStyles.bg,
      toneStyles.border,
      density === 'compact' ? 'p-2.5' : 'p-3',
    ]"
  >
    <svg :class="['shrink-0 mt-0.5', toneStyles.fg]" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path :d="toneStyles.icon" />
    </svg>
    <div class="ui-callout__body flex-1 min-w-0">
      <p v-if="title" :class="['t-h3', toneStyles.fg, 'mb-0.5']">{{ title }}</p>
      <div :class="['text-sm', toneStyles.fg, 'opacity-90 [&_a]:underline [&_a]:underline-offset-2']">
        <slot />
      </div>
      <div v-if="$slots.actions" class="mt-2 flex gap-2">
        <slot name="actions" />
      </div>
    </div>
    <button
      v-if="dismissible"
      type="button"
      :class="['ui-callout__dismiss focus-ring shrink-0 rounded-xs p-0.5', toneStyles.fg, 'opacity-60 hover:opacity-100']"
      aria-label="Dismiss"
      @click="$emit('dismiss')"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
    </button>
  </div>
</template>
