<!--
  UiSegmentedControl — compact segmented choice control for status filters
  and short mode toggles.
-->
<script setup lang="ts">
export interface UiSegmentedOption {
  key: string | number;
  label: string;
  disabled?: boolean;
}

withDefaults(defineProps<{
  modelValue: string | number;
  options: UiSegmentedOption[];
  label: string;
  size?: 'sm' | 'md';
}>(), {
  size: 'sm',
});

defineEmits<{
  (e: 'update:modelValue', value: string | number): void;
  (e: 'select', value: string | number): void;
}>();
</script>

<template>
  <div
    role="tablist"
    :aria-label="label"
    class="ui-segmented-control inline-flex flex-wrap items-center gap-1 rounded-md border border-subtle bg-bg-surface-alt p-1"
  >
    <button
      v-for="option in options"
      :key="option.key"
      type="button"
      role="tab"
      :aria-selected="modelValue === option.key"
      :disabled="option.disabled"
      :class="[
        'focus-ring rounded-sm border border-transparent font-medium transition-colors duration-fast disabled:cursor-not-allowed disabled:opacity-50',
        size === 'sm' ? 'h-7 px-2.5 text-sm' : 'h-8 px-3 text-sm',
        modelValue === option.key
          ? 'bg-bg-surface text-fg-strong border-default shadow-xs'
          : 'text-fg-muted hover:text-fg-default hover:bg-bg-surface',
      ]"
      @click="$emit('update:modelValue', option.key); $emit('select', option.key)"
    >
      {{ option.label }}
    </button>
  </div>
</template>
