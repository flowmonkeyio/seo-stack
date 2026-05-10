<!--
  UiSelect — native <select> styled to match UiInput. Use for short option lists.
  For typeahead / large lists, use UiCombobox (not in this base set).

  Options can be either strings or {value, label, disabled?, group?}.
-->
<script setup lang="ts">
import { computed, useAttrs } from 'vue';

defineOptions({ inheritAttrs: false });

export type UiSelectOption =
  | string
  | { value: string | number; label: string; disabled?: boolean; group?: string };

export interface UiSelectProps {
  modelValue?: string | number | null;
  options: UiSelectOption[];
  size?: 'sm' | 'md' | 'lg';
  placeholder?: string;
  disabled?: boolean;
  invalid?: boolean;
  required?: boolean;
  block?: boolean;
  id?: string;
  ariaDescribedby?: string;
}

const props = withDefaults(defineProps<UiSelectProps>(), {
  size: 'md',
  block: true,
});

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | number | null): void;
  (e: 'change', value: string | number | null): void;
}>();

const attrs = useAttrs();

const sizeClass = computed(() => ({
  sm: 'h-7 text-sm pl-2 pr-7',
  md: 'h-8 text-sm pl-2.5 pr-8',
  lg: 'h-10 text-base pl-3 pr-9',
}[props.size]));

interface NormalizedOption { value: string | number; label: string; disabled?: boolean; group?: string }
const normalized = computed<NormalizedOption[]>(() =>
  props.options.map(o =>
    typeof o === 'string' ? { value: o, label: o } : o
  )
);

const grouped = computed(() => {
  const groups = new Map<string | null, NormalizedOption[]>();
  for (const opt of normalized.value) {
    const k = opt.group ?? null;
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k)!.push(opt);
  }
  return Array.from(groups.entries());
});

function onChange(ev: Event) {
  const value = (ev.target as HTMLSelectElement).value;
  // Coerce back to number if matching option was numeric.
  const matched = normalized.value.find(o => String(o.value) === value);
  const out = matched && typeof matched.value === 'number' ? matched.value : value;
  emit('update:modelValue', out);
  emit('change', out);
}
</script>

<template>
  <div
    :class="[
      'ui-select relative inline-flex items-center rounded-sm border bg-bg-surface transition-colors duration-fast',
      invalid ? 'border-danger' : 'border-default hover:border-strong',
      disabled && 'bg-bg-sunken cursor-not-allowed opacity-60',
      block && 'w-full',
    ]"
  >
    <select
      v-bind="attrs"
      :id="id"
      :value="modelValue ?? ''"
      :disabled="disabled"
      :required="required"
      :aria-invalid="invalid || undefined"
      :aria-describedby="ariaDescribedby"
      :class="[
        'ui-select__field focus-ring w-full appearance-none bg-transparent border-0 outline-none text-fg-default disabled:cursor-not-allowed',
        sizeClass,
      ]"
      @change="onChange"
    >
      <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
      <template v-for="([group, opts]) in grouped" :key="group ?? '_none'">
        <optgroup v-if="group" :label="group">
          <option v-for="o in opts" :key="o.value" :value="o.value" :disabled="o.disabled">{{ o.label }}</option>
        </optgroup>
        <template v-else>
          <option v-for="o in opts" :key="o.value" :value="o.value" :disabled="o.disabled">{{ o.label }}</option>
        </template>
      </template>
    </select>
    <span class="ui-select__chevron pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-fg-subtle" aria-hidden="true">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
    </span>
  </div>
</template>
