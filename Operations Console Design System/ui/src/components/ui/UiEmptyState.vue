<!--
  UiEmptyState — for zero-data states. Should always include guidance and
  ideally one primary action.
-->
<script setup lang="ts">
defineProps<{
  title: string;
  description?: string;
  /** Lucide icon name — caller is responsible for rendering it via slot[icon]. */
  icon?: string;
  /** Compact (inline) variant — for empty table rows, inside cards. */
  size?: 'sm' | 'md' | 'lg';
}>();
</script>

<template>
  <div
    :class="[
      'ui-empty-state flex flex-col items-center text-center mx-auto',
      size === 'sm' ? 'py-6 max-w-sm gap-2' : size === 'lg' ? 'py-16 max-w-md gap-4' : 'py-10 max-w-md gap-3',
    ]"
  >
    <div v-if="$slots.icon || icon" :class="[
      'ui-empty-state__icon flex items-center justify-center rounded-full bg-bg-sunken text-fg-muted',
      size === 'sm' ? 'w-9 h-9' : 'w-12 h-12',
    ]">
      <slot name="icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>
      </slot>
    </div>
    <div class="flex flex-col gap-1">
      <p :class="[size === 'lg' ? 't-h1' : 't-h2', 'text-fg-default']">{{ title }}</p>
      <p v-if="description" class="text-sm text-fg-muted text-balance">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="flex flex-wrap justify-center gap-2 mt-1">
      <slot name="actions" />
    </div>
  </div>
</template>
