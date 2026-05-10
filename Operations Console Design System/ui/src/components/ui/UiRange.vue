<!--
  UiRange — numeric range slider with optional value display.
-->
<script setup lang="ts">
import { computed } from 'vue';

export interface UiRangeProps {
  modelValue?: number;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  showValue?: boolean;
  /** Function to format the displayed value. */
  format?: (v: number) => string;
  id?: string;
  ariaLabel?: string;
}

const props = withDefaults(defineProps<UiRangeProps>(), {
  modelValue: 0,
  min: 0,
  max: 100,
  step: 1,
  showValue: true,
});

const emit = defineEmits<{ (e: 'update:modelValue', value: number): void }>();

const percent = computed(() => {
  const range = props.max - props.min;
  if (range <= 0) return 0;
  return ((props.modelValue - props.min) / range) * 100;
});

const display = computed(() =>
  props.format ? props.format(props.modelValue) : String(props.modelValue)
);
</script>

<template>
  <div class="ui-range flex items-center gap-3">
    <input
      type="range"
      :id="id"
      :value="modelValue"
      :min="min"
      :max="max"
      :step="step"
      :disabled="disabled"
      :aria-label="ariaLabel"
      :class="[
        'ui-range__input flex-1 appearance-none bg-transparent focus-ring',
        disabled && 'opacity-60 cursor-not-allowed',
      ]"
      :style="{ '--range-percent': percent + '%' } as any"
      @input="(ev) => $emit('update:modelValue', Number((ev.target as HTMLInputElement).value))"
    />
    <span v-if="showValue" class="ui-range__value font-mono text-xs text-fg-muted tabular-nums min-w-[2.5rem] text-right">
      {{ display }}
    </span>
  </div>
</template>

<style scoped>
.ui-range__input {
  height: 18px;
}
.ui-range__input::-webkit-slider-runnable-track {
  height: 4px;
  border-radius: 9999px;
  background: linear-gradient(
    to right,
    var(--color-accent-primary) 0%,
    var(--color-accent-primary) var(--range-percent),
    var(--color-bg-sunken) var(--range-percent),
    var(--color-bg-sunken) 100%
  );
}
.ui-range__input::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 9999px;
  background: var(--color-bg-surface);
  border: 2px solid var(--color-accent-primary);
  margin-top: -5px;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
}
.ui-range__input::-moz-range-track {
  height: 4px;
  border-radius: 9999px;
  background: var(--color-bg-sunken);
}
.ui-range__input::-moz-range-progress {
  height: 4px;
  border-radius: 9999px;
  background: var(--color-accent-primary);
}
.ui-range__input::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 9999px;
  background: var(--color-bg-surface);
  border: 2px solid var(--color-accent-primary);
  cursor: pointer;
}
</style>
