<!--
  UiSkeleton — shaped placeholder for content that's loading.
  Match the size of the real content; do NOT use generic gray boxes
  larger than what's coming.
-->
<script setup lang="ts">
defineProps<{
  /** Shape preset. */
  shape?: 'line' | 'block' | 'circle';
  /** Width — number → px, string → CSS value. */
  width?: number | string;
  /** Height — same rules. */
  height?: number | string;
  /** When true, shows a row of N short lines (for paragraphs). */
  lines?: number;
}>();
</script>

<template>
  <div v-if="lines && lines > 1" class="flex flex-col gap-1.5" aria-hidden="true">
    <span
      v-for="i in lines"
      :key="i"
      class="ui-skeleton block rounded-xs bg-bg-sunken animate-pulse"
      :style="{ height: '0.75em', width: i === lines ? '60%' : '100%' }"
    />
  </div>
  <span
    v-else
    aria-hidden="true"
    :class="[
      'ui-skeleton block bg-bg-sunken animate-pulse',
      shape === 'circle' ? 'rounded-full' : shape === 'block' ? 'rounded-md' : 'rounded-xs',
    ]"
    :style="{
      width: typeof width === 'number' ? width + 'px' : (width ?? '100%'),
      height: typeof height === 'number' ? height + 'px' : (height ?? (shape === 'line' ? '0.75em' : '20px')),
    }"
  />
</template>
