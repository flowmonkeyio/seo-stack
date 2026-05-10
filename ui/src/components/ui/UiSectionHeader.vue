<!--
  UiSectionHeader — group heading inside a page or card.
  Smaller than UiPageHeader; right-aligned slot for inline actions.
-->
<script setup lang="ts">
defineProps<{
  title: string;
  description?: string;
  /** Heading level (h2..h4). Default h2. */
  as?: 'h2' | 'h3' | 'h4';
}>();
</script>

<template>
  <div class="ui-section-header flex items-end justify-between gap-3 mb-3">
    <div class="min-w-0">
      <component
        :is="as ?? 'h2'"
        class="t-h2 text-fg-strong"
      >
        {{ title }}
      </component>
      <p
        v-if="description"
        class="text-xs text-fg-muted mt-0.5"
      >
        {{ description }}
      </p>
    </div>
    <div
      v-if="$slots.actions"
      class="flex items-center gap-2 shrink-0"
    >
      <slot name="actions" />
    </div>
  </div>
</template>
