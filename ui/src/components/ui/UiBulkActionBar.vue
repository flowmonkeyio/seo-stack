<!--
  UiBulkActionBar — appears at the top/bottom of a list when items are
  selected. Shows selection count + actions.

  Anchor it to the table header or as a sticky bar above the list.
-->
<script setup lang="ts">
defineProps<{
  count: number;
  /** Total available, for "select all" affordance. */
  total?: number;
  /** Show "select all" button when not all rows selected. */
  selectableAll?: boolean;
  ariaLabel?: string;
}>();

defineEmits<{
  (e: 'clear'): void;
  (e: 'selectAll'): void;
}>();
</script>

<template>
  <div
    role="region"
    :aria-label="ariaLabel ?? 'Bulk actions'"
    aria-live="polite"
    class="ui-bulk-action-bar flex items-center justify-between gap-3 rounded-lg border border-default bg-bg-surface px-3 py-2 shadow-lg"
  >
    <div class="flex items-center gap-3 min-w-0">
      <span class="text-sm font-medium text-fg-strong">
        {{ count }} selected<span v-if="total"> of {{ total }}</span>
      </span>
      <button
        v-if="selectableAll && total && count < total"
        type="button"
        class="focus-ring text-xs font-medium text-fg-link hover:underline rounded-xs"
        @click="$emit('selectAll')"
      >
        Select all {{ total }}
      </button>
      <button
        type="button"
        class="focus-ring rounded-xs text-xs text-fg-muted transition-colors duration-fast hover:text-fg-default"
        @click="$emit('clear')"
      >
        Clear
      </button>
    </div>
    <div class="flex items-center gap-2 shrink-0">
      <slot />
    </div>
  </div>
</template>
