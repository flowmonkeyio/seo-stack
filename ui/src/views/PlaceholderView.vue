<script setup lang="ts">
// PlaceholderView — generic shell used by views that land in M5.B / M5.C.
// Displays a heading + milestone tag so the route is browseable while
// the real implementation is incoming.

interface Props {
  title: string
  milestone: string
  description?: string
}

withDefaults(defineProps<Props>(), {
  description: '',
})
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <header class="mb-4 flex items-baseline gap-3">
      <h1 class="text-2xl font-bold tracking-tight">
        {{ title }}
      </h1>
      <span
        class="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
      >
        coming in {{ milestone }}
      </span>
    </header>
    <p
      v-if="description"
      class="text-sm text-gray-600 dark:text-gray-400"
    >
      {{ description }}
    </p>
    <p
      v-else
      class="text-sm text-gray-500 dark:text-gray-400"
    >
      This view is part of milestone {{ milestone }}. The route is wired so
      navigation works; the real content lands when {{ milestone }} ships.
    </p>
  </div>
</template>
