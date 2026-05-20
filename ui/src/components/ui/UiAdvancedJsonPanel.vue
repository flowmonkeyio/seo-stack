<script setup lang="ts">
import UiJsonBlock from './UiJsonBlock.vue'

withDefaults(defineProps<{
  title?: string
  summary?: string
  data: unknown
  open?: boolean
  maxHeight?: string
}>(), {
  title: 'Advanced',
  summary: 'Raw JSON',
  open: false,
  maxHeight: '24rem',
})
</script>

<template>
  <details
    class="rounded-md border border-subtle bg-bg-surface"
    :open="open"
  >
    <summary class="cursor-pointer px-3 py-2 text-sm font-medium text-fg-default hover:bg-bg-surface-alt focus-ring">
      {{ title }}
      <span class="ml-2 text-xs font-normal text-fg-muted">{{ summary }}</span>
    </summary>
    <div class="border-t border-subtle p-3">
      <UiJsonBlock
        :data="data"
        :max-height="maxHeight"
        density="compact"
        wrap
        aria-label="Advanced JSON"
      />
    </div>
  </details>
</template>
