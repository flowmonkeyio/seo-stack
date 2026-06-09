<!--
  UiLoadingState — generic in-progress state with optional message.
  Use UiSkeleton for layout-shaped placeholders.
-->
<script setup lang="ts">
import UiIcon from './UiIcon.vue';

defineProps<{
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  /** Inline (in a row) vs block-centered. */
  inline?: boolean;
}>();
</script>

<template>
  <div
    role="status"
    :aria-live="'polite'"
    :class="[
      'ui-loading-state inline-flex items-center gap-2 text-fg-muted',
      !inline && 'w-full justify-center py-8',
    ]"
  >
    <UiIcon
      name="loader"
      :class="[
        'animate-spin text-fg-subtle shrink-0',
        size === 'sm' ? 'h-3 w-3 text-xs' : size === 'lg' ? 'h-5 w-5 text-xl' : 'h-4 w-4 text-lg',
      ]"
      aria-hidden="true"
    />
    <span :class="[size === 'sm' ? 'text-xs' : 'text-sm']">{{ label ?? 'Loading…' }}</span>
  </div>
</template>
