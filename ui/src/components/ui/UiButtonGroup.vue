<!--
  UiButtonGroup — visually attached cluster of UiButton elements.
  Use for segmented controls or paired actions (Save / Save & New).
-->
<script setup lang="ts">
defineProps<{
  /** Aria role — defaults to 'group'. Use 'toolbar' for action bars. */
  role?: 'group' | 'toolbar' | 'radiogroup';
  ariaLabel?: string;
  attached?: boolean;
}>();
</script>

<template>
  <div
    :role="role ?? 'group'"
    :aria-label="ariaLabel"
    :class="[
      'ui-button-group inline-flex',
      attached !== false ? 'ui-button-group--attached' : 'gap-2',
    ]"
  >
    <slot />
  </div>
</template>

<style scoped>
.ui-button-group--attached :deep(.ui-button) {
  border-radius: 0;
}
.ui-button-group--attached :deep(.ui-button:first-child) {
  border-top-left-radius: var(--radius-sm);
  border-bottom-left-radius: var(--radius-sm);
}
.ui-button-group--attached :deep(.ui-button:last-child) {
  border-top-right-radius: var(--radius-sm);
  border-bottom-right-radius: var(--radius-sm);
}
.ui-button-group--attached :deep(.ui-button + .ui-button) {
  margin-left: -1px;
}
.ui-button-group--attached :deep(.ui-button:focus-visible),
.ui-button-group--attached :deep(.ui-button:hover) {
  z-index: 1;
}
</style>
