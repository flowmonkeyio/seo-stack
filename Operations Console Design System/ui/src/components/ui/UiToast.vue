<!--
  UiToast — single toast. Mount inside a fixed-position UiToastViewport.
  Toast container manages aria-live and stacking; this is the visual unit.

  In practice, use a `useToast()` composable to push toasts; this is the
  display primitive.
-->
<script setup lang="ts">
import { computed } from 'vue';

export type ToastTone = 'info' | 'success' | 'warning' | 'danger' | 'neutral';

export interface UiToastProps {
  tone?: ToastTone;
  title: string;
  description?: string;
  /** Optional action label (renders right-aligned button). */
  actionLabel?: string;
  /** Show dismiss button. */
  dismissible?: boolean;
}

const props = withDefaults(defineProps<UiToastProps>(), {
  tone: 'neutral',
  dismissible: true,
});

defineEmits<{
  (e: 'action'): void;
  (e: 'dismiss'): void;
}>();

const toneClass = computed(() => ({
  info:    'border-l-info',
  success: 'border-l-success',
  warning: 'border-l-warning',
  danger:  'border-l-danger',
  neutral: 'border-l-neutral',
}[props.tone]));
</script>

<template>
  <div
    role="status"
    :aria-live="tone === 'danger' ? 'assertive' : 'polite'"
    :class="[
      'ui-toast pointer-events-auto flex items-start gap-3 min-w-[320px] max-w-md rounded-md border border-default border-l-4 bg-bg-surface px-3 py-2.5 shadow-md',
      toneClass,
    ]"
  >
    <div class="flex-1 min-w-0">
      <p class="t-h3 text-fg-strong leading-tight">{{ title }}</p>
      <p v-if="description" class="text-sm text-fg-muted mt-0.5 leading-snug">{{ description }}</p>
    </div>
    <div class="flex items-center gap-1 shrink-0">
      <button
        v-if="actionLabel"
        type="button"
        class="focus-ring text-sm font-medium text-accent-fg hover:underline px-1.5 py-0.5 rounded-xs"
        @click="$emit('action')"
      >{{ actionLabel }}</button>
      <button
        v-if="dismissible"
        type="button"
        class="focus-ring text-fg-subtle hover:text-fg-default rounded-xs p-0.5"
        aria-label="Dismiss"
        @click="$emit('dismiss')"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
      </button>
    </div>
  </div>
</template>
