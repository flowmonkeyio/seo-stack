<!--
  UiSegmentedControl — compact segmented choice control for status filters
  and short mode toggles. Sunken rail with a raised "pill" for the active
  segment.
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
    class="ui-segmented-control inline-flex flex-wrap items-center gap-0.5 rounded-md border border-subtle bg-bg-sunken p-0.5"
  >
    <button
      v-for="option in options"
      :key="option.key"
      type="button"
      role="tab"
      :aria-selected="modelValue === option.key"
      :disabled="option.disabled"
      :class="[
        'focus-ring inline-flex items-center gap-1.5 rounded-sm font-medium transition-colors duration-fast ease-standard disabled:cursor-not-allowed',
        size === 'sm' ? 'h-7 px-2.5 text-sm' : 'h-8 px-3 text-sm',
        modelValue === option.key
          ? ['bg-bg-surface shadow-xs', option.disabled ? 'text-fg-disabled' : 'text-fg-strong']
          : option.disabled
            ? 'text-fg-disabled'
            : 'text-fg-muted hover:text-fg-default',
      ]"
      @click="selectOption(option.key)"
    >
      <UiIcon
        v-if="hasIcon(option.icon)"
        :name="option.icon"
        class="ui-segmented-control__icon"
      />
      <span>{{ option.label }}</span>
    </button>
  </div>
</template>

<style scoped>
.ui-segmented-control__icon {
  width: 1.07em;
  height: 1.07em;
  flex: none;
  stroke-width: 1.8;
}
</style>
