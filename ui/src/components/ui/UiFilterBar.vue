<!--
  UiFilterBar — opinionated filter cluster. Search input + named filter
  controls + a "clear all" affordance + active-filter chips.

  Filters are described declaratively; the consumer owns state.
-->
<script setup lang="ts">
import UiInput from './UiInput.vue';
import UiBadge from './UiBadge.vue';
import UiButton from './UiButton.vue';

export interface ActiveFilter {
  key: string;
  label: string;
  /** Human display of value. */
  value: string;
}

defineProps<{
  /** Search input value (two-way). */
  search?: string;
  searchPlaceholder?: string;
  /** Active filter chips — caller renders the controls themselves in the slot. */
  active?: ActiveFilter[];
  ariaLabel?: string;
  /** Hide the search box. */
  noSearch?: boolean;
}>();

defineEmits<{
  (e: 'update:search', v: string): void;
  (e: 'remove', key: string): void;
  (e: 'clearAll'): void;
}>();
</script>

<template>
  <div
    role="region"
    :aria-label="ariaLabel ?? 'Filters'"
    class="ui-filter-bar flex flex-col gap-2"
  >
    <div class="flex flex-wrap items-center gap-2">
      <UiInput
        v-if="!noSearch"
        :model-value="search"
        :placeholder="searchPlaceholder ?? 'Search…'"
        size="sm"
        clearable
        :block="false"
        class="flex-1 min-w-[200px] max-w-sm"
        @update:model-value="(v: any) => $emit('update:search', String(v ?? ''))"
      >
        <template #prefix>
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          ><circle
            cx="11"
            cy="11"
            r="8"
          /><path d="m21 21-4.3-4.3" /></svg>
        </template>
      </UiInput>
      <slot />
      <div class="ml-auto flex items-center gap-2">
        <slot name="right" />
      </div>
    </div>
    <div
      v-if="active && active.length"
      class="flex items-center flex-wrap gap-1.5"
    >
      <UiBadge
        v-for="f in active"
        :key="f.key"
        tone="info"
        variant="subtle"
        size="sm"
        interactive
        @click="$emit('remove', f.key)"
      >
        <span class="text-fg-muted font-normal mr-1">{{ f.label }}:</span>
        <span>{{ f.value }}</span>
        <svg
          class="ml-1 -mr-0.5"
          width="10"
          height="10"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
        ><path d="M18 6 6 18M6 6l12 12" /></svg>
      </UiBadge>
      <UiButton
        variant="link"
        size="sm"
        @click="$emit('clearAll')"
      >
        Clear all
      </UiButton>
    </div>
  </div>
</template>
