<!--
  UiSectionHeader — group heading inside a page or card.
  Smaller than UiPageHeader; right-aligned slot for inline actions.
  `as` sets the semantic heading level only — the visual is always t-h3.
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
  <div class="ui-section-header mb-3 flex items-start justify-between gap-3">
    <div class="min-w-0">
      <component
        :is="as ?? 'h2'"
        class="t-h3 text-fg-strong"
      >
        {{ title }}
      </component>
      <p
        v-if="description"
        class="mt-0.5 text-sm text-fg-muted"
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
