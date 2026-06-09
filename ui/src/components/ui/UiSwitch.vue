<!--
  UiSwitch — boolean toggle. Use only when state takes effect immediately
  (e.g. enable/disable a feature). Otherwise prefer UiCheckbox.
-->
<script setup lang="ts">
import { computed } from 'vue'

export interface UiSwitchProps {
  modelValue?: boolean
  disabled?: boolean
  size?: 'sm' | 'md'
  id?: string
  ariaLabel?: string
  ariaLabelledby?: string
}

const props = withDefaults(defineProps<UiSwitchProps>(), {
  size: 'md',
  id: undefined,
  ariaLabel: undefined,
  ariaLabelledby: undefined,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'change', value: boolean): void
}>()

const dims = computed(() =>
  props.size === 'sm'
    ? { track: 'w-8 h-[18px]', thumb: 'w-3.5 h-3.5', translate: 'translate-x-3' }
    : { track: 'w-9 h-5', thumb: 'w-4 h-4', translate: 'translate-x-3.5' },
)

const trackStateClass = computed(() => {
  if (props.disabled) {
    return props.modelValue
      ? 'cursor-not-allowed bg-fg-disabled border-fg-disabled'
      : 'cursor-not-allowed bg-bg-sunken border-default'
  }
  return props.modelValue ? 'bg-accent border-accent' : 'bg-bg-sunken border-strong'
})

function toggle() {
  if (props.disabled) return
  emit('update:modelValue', !props.modelValue)
  emit('change', !props.modelValue)
}
</script>

<template>
  <button
    :id="id"
    type="button"
    role="switch"
    :aria-checked="!!modelValue"
    :aria-label="ariaLabel"
    :aria-labelledby="ariaLabelledby"
    :disabled="disabled"
    :class="[
      'ui-switch focus-ring inline-flex shrink-0 items-center rounded-full border transition-colors duration-fast ease-standard',
      dims.track,
      trackStateClass,
    ]"
    @click="toggle"
  >
    <span
      aria-hidden="true"
      :class="[
        'ui-switch__thumb pointer-events-none ml-0.5 inline-block rounded-full bg-fg-on-accent shadow-sm transition-transform duration-fast ease-standard',
        dims.thumb,
        modelValue ? dims.translate : 'translate-x-0',
      ]"
    />
  </button>
</template>
