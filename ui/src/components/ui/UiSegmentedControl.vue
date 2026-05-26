<!--
  UiSegmentedControl — compact segmented choice control for status filters
  and short mode toggles.
-->
<script setup lang="ts">
import { hasIcon } from './icons'
import UiIcon from './UiIcon.vue'

export interface UiSegmentedOption {
  key: string | number
  label: string
  icon?: string
  disabled?: boolean
}

withDefaults(
  defineProps<{
    modelValue: string | number
    options: UiSegmentedOption[]
    label: string
    size?: 'sm' | 'md'
  }>(),
  {
    size: 'sm',
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | number): void
  (e: 'select', value: string | number): void
}>()

function selectOption(value: string | number): void {
  emit('update:modelValue', value)
  emit('select', value)
}
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
        'focus-ring inline-flex items-center gap-1.5 rounded-sm border border-transparent font-medium transition-colors duration-fast disabled:cursor-not-allowed disabled:opacity-50',
        size === 'sm' ? 'h-7 px-2.5 text-sm' : 'h-8 px-3 text-sm',
        modelValue === option.key
          ? 'bg-bg-surface text-fg-strong border-default shadow-xs'
          : 'text-fg-muted hover:text-fg-default hover:bg-bg-surface',
      ]"
      @click="selectOption(option.key)"
    >
      <UiIcon v-if="hasIcon(option.icon)" :name="option.icon" class="ui-segmented-control__icon" />
      <span>{{ option.label }}</span>
    </button>
  </div>
</template>

<style scoped>
.ui-segmented-control__icon {
  width: 14px;
  height: 14px;
  flex: none;
}
</style>
