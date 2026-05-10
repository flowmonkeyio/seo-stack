<!--
  UiLoadingState — generic in-progress state with optional message.
  Use UiSkeleton for layout-shaped placeholders.
-->
<script setup lang="ts">
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
    <svg
      :class="['animate-spin text-fg-subtle']"
      :width="size === 'sm' ? 12 : size === 'lg' ? 20 : 16"
      :height="size === 'sm' ? 12 : size === 'lg' ? 20 : 16"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="9"
        stroke="currentColor"
        stroke-opacity="0.25"
        stroke-width="3"
      />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        stroke-width="3"
        stroke-linecap="round"
      />
    </svg>
    <span :class="[size === 'sm' ? 'text-xs' : 'text-sm']">{{ label ?? 'Loading…' }}</span>
  </div>
</template>
