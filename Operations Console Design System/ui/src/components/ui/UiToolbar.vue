<!--
  UiToolbar — horizontal cluster of controls. Use above tables, in dialog
  bodies for filters, etc. Keyboard accessible (role=toolbar).

  Children should be UiButtons / UiInputs / UiSelects.
-->
<script setup lang="ts">
defineProps<{
  ariaLabel?: string;
  /** Compact: tighter spacing, sm controls implied by children. */
  density?: 'compact' | 'comfortable';
  /** Visual treatment. */
  variant?: 'default' | 'sunken';
  /** Sticky to the top of its scroll parent. */
  sticky?: boolean;
}>();
</script>

<template>
  <div
    role="toolbar"
    :aria-label="ariaLabel"
    :class="[
      'ui-toolbar flex flex-wrap items-center',
      density === 'comfortable' ? 'gap-3 px-4 py-2.5' : 'gap-2 px-3 py-2',
      variant === 'sunken' ? 'bg-bg-surface-alt border-y border-subtle' : 'bg-bg-surface border border-default rounded-md',
      sticky && 'sticky top-0 z-sticky',
    ]"
  >
    <slot />
    <div v-if="$slots.right" class="ml-auto flex items-center gap-2">
      <slot name="right" />
    </div>
  </div>
</template>
