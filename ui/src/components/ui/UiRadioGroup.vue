<!--
  UiRadioGroup — single-selection. Renders a vertical or horizontal stack
  of options, each a styled radio.
-->
<script setup lang="ts">
import { computed } from 'vue';

export interface UiRadioOption {
  value: string | number;
  label: string;
  description?: string;
  disabled?: boolean;
}

export interface UiRadioGroupProps {
  modelValue?: string | number | null;
  options: UiRadioOption[];
  name: string;
  orientation?: 'horizontal' | 'vertical';
  disabled?: boolean;
  invalid?: boolean;
  /** When true, renders option as a card-style segment instead of a dot. */
  variant?: 'radio' | 'card';
  ariaLabel?: string;
  ariaLabelledby?: string;
}

const props = withDefaults(defineProps<UiRadioGroupProps>(), {
  modelValue: null,
  orientation: 'vertical',
  variant: 'radio',
  ariaLabel: undefined,
  ariaLabelledby: undefined,
});

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | number): void;
  (e: 'change', value: string | number): void;
}>();

const stackClass = computed(() =>
  props.orientation === 'horizontal' ? 'flex flex-row flex-wrap gap-3' : 'flex flex-col gap-2'
);

function isOptionDisabled(optDisabled?: boolean): boolean {
  return props.disabled || !!optDisabled;
}

function dotClass(opt: UiRadioOption): string {
  if (isOptionDisabled(opt.disabled)) return 'border-default bg-bg-sunken';
  if (props.modelValue === opt.value) return 'border-accent bg-bg-surface';
  if (props.invalid) return 'border-danger bg-bg-surface';
  return 'border-strong bg-bg-surface';
}

function select(v: string | number, optDisabled?: boolean) {
  if (props.disabled || optDisabled) return;
  emit('update:modelValue', v);
  emit('change', v);
}
</script>

<template>
  <div
    role="radiogroup"
    :aria-label="ariaLabel"
    :aria-labelledby="ariaLabelledby"
    :aria-invalid="invalid || undefined"
    :class="['ui-radio-group', stackClass]"
  >
    <label
      v-for="opt in options"
      :key="opt.value"
      :class="[
        'inline-flex items-start gap-2 select-none',
        isOptionDisabled(opt.disabled) ? 'cursor-not-allowed' : 'cursor-pointer',
        variant === 'card' && 'rounded-lg border p-3 shadow-xs transition-colors duration-fast',
        variant === 'card' &&
          (modelValue === opt.value ? 'border-accent bg-accent-subtle' : 'border-default bg-bg-surface'),
        variant === 'card' &&
          modelValue !== opt.value &&
          !isOptionDisabled(opt.disabled) &&
          'hover:border-strong',
      ]"
    >
      <span class="relative inline-flex items-center justify-center mt-0.5">
        <input
          type="radio"
          :name="name"
          :value="opt.value"
          :checked="modelValue === opt.value"
          :disabled="disabled || opt.disabled"
          class="peer sr-only"
          @change="select(opt.value, opt.disabled)"
        >
        <span
          :class="[
            'w-4 h-4 inline-flex items-center justify-center rounded-full border transition-colors duration-fast',
            dotClass(opt),
            'peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-focus peer-focus-visible:outline-offset-2',
          ]"
          aria-hidden="true"
        >
          <span
            v-if="modelValue === opt.value"
            :class="[
              'w-2 h-2 rounded-full',
              isOptionDisabled(opt.disabled) ? 'bg-fg-disabled' : 'bg-accent',
            ]"
          />
        </span>
      </span>
      <span class="flex flex-col leading-tight">
        <span
          :class="['text-sm', isOptionDisabled(opt.disabled) ? 'text-fg-disabled' : 'text-fg-default']"
        >{{ opt.label }}</span>
        <span
          v-if="opt.description"
          :class="['text-xs mt-0.5', isOptionDisabled(opt.disabled) ? 'text-fg-disabled' : 'text-fg-muted']"
        >{{ opt.description }}</span>
      </span>
    </label>
  </div>
</template>
