<!--
  UiTextarea — multiline text. Pair with UiFormField.
-->
<script setup lang="ts">
import { computed, useAttrs } from 'vue';

defineOptions({ inheritAttrs: false });

export interface UiTextareaProps {
  modelValue?: string | null;
  rows?: number;
  size?: 'sm' | 'md' | 'lg';
  placeholder?: string;
  disabled?: boolean;
  readonly?: boolean;
  invalid?: boolean;
  required?: boolean;
  resize?: 'none' | 'vertical' | 'horizontal' | 'both';
  /** Auto-grow up to maxRows. */
  autoResize?: boolean;
  maxRows?: number;
  id?: string;
  ariaDescribedby?: string;
}

const props = withDefaults(defineProps<UiTextareaProps>(), {
  modelValue: '',
  rows: 4,
  size: 'md',
  placeholder: undefined,
  resize: 'vertical',
  maxRows: undefined,
  id: undefined,
  ariaDescribedby: undefined,
});

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
  (e: 'blur', ev: FocusEvent): void;
  (e: 'focus', ev: FocusEvent): void;
}>();

const attrs = useAttrs();

const sizeClass = computed(() => ({
  sm: 'text-sm px-2 py-1.5',
  md: 'text-sm px-2.5 py-2',
  lg: 'text-base px-3 py-2.5',
}[props.size]));

function onInput(ev: Event) {
  const ta = ev.target as HTMLTextAreaElement;
  if (props.autoResize) {
    ta.style.height = 'auto';
    const max = props.maxRows ? props.maxRows * 20 + 16 : 9999;
    ta.style.height = Math.min(ta.scrollHeight, max) + 'px';
  }
  emit('update:modelValue', ta.value);
}
</script>

<template>
  <textarea
    v-bind="attrs"
    :id="id"
    :rows="rows"
    :value="modelValue ?? ''"
    :placeholder="placeholder"
    :disabled="disabled"
    :readonly="readonly"
    :required="required"
    :aria-invalid="invalid || undefined"
    :aria-describedby="ariaDescribedby"
    :class="[
      'ui-textarea focus-ring w-full block rounded-sm border bg-bg-surface text-fg-default placeholder:text-fg-disabled transition-colors duration-fast',
      invalid ? 'border-danger' : 'border-default hover:border-strong',
      disabled && 'bg-bg-sunken cursor-not-allowed opacity-60',
      readonly && 'bg-bg-surface-alt',
      sizeClass,
      `resize-${resize}`,
    ]"
    :style="{ resize }"
    @input="onInput"
    @blur="$emit('blur', $event)"
    @focus="$emit('focus', $event)"
  />
</template>
