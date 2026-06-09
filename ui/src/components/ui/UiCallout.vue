<!--
  UiCallout — inline message inside content. NOT a toast.
  Used for pre-action warnings, persistent errors on a form, info notes.
-->
<script setup lang="ts">
import { computed } from 'vue';
import UiIcon from './UiIcon.vue';

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
  title: undefined,
  density: 'comfortable',
});

defineEmits<{ (e: 'dismiss'): void }>();

const CALLOUT_TONE_STYLES = {
  info:    { bg: 'bg-info-subtle',    border: 'border-info-border',    fg: 'text-info-fg',    icon: 'info' },
  success: { bg: 'bg-success-subtle', border: 'border-success-border', fg: 'text-success-fg', icon: 'check-circle' },
  warning: { bg: 'bg-warning-subtle', border: 'border-warning-border', fg: 'text-warning-fg', icon: 'alert-triangle' },
  danger:  { bg: 'bg-danger-subtle',  border: 'border-danger-border',  fg: 'text-danger-fg',  icon: 'x-circle' },
  neutral: { bg: 'bg-neutral-subtle', border: 'border-neutral-border', fg: 'text-neutral-fg', icon: 'info' },
} as const;

const toneStyles = computed(() => CALLOUT_TONE_STYLES[props.tone]);
</script>

<template>
  <div
    role="status"
    :aria-live="tone === 'danger' ? 'assertive' : 'polite'"
    :class="[
      'ui-callout flex gap-2.5 rounded-lg border',
      toneStyles.bg,
      toneStyles.border,
      density === 'compact' ? 'p-2.5' : 'p-3',
    ]"
  >
    <UiIcon
      :name="toneStyles.icon"
      :class="['mt-0.5 h-4 w-4 shrink-0', toneStyles.fg]"
      aria-hidden="true"
    />
    <div class="ui-callout__body flex-1 min-w-0">
      <p
        v-if="title"
        :class="['text-sm font-medium', toneStyles.fg, 'mb-0.5']"
      >
        {{ title }}
      </p>
      <div :class="['text-sm', toneStyles.fg, '[&_a]:underline [&_a]:underline-offset-2']">
        <slot />
      </div>
      <div
        v-if="$slots.actions"
        class="mt-2 flex gap-2"
      >
        <slot name="actions" />
      </div>
    </div>
    <button
      v-if="dismissible"
      type="button"
      :class="[
        'ui-callout__dismiss focus-ring -m-1 shrink-0 self-start rounded-sm p-1 opacity-60 transition-opacity duration-fast hover:opacity-100',
        toneStyles.fg,
      ]"
      aria-label="Dismiss"
      @click="$emit('dismiss')"
    >
      <UiIcon
        name="close"
        class="h-3.5 w-3.5"
        aria-hidden="true"
      />
    </button>
  </div>
</template>
