<script setup lang="ts">
import { computed } from 'vue'

import type { SchemaContextItemOut, SchemaContextQueryOut } from '@/api'
import { UiBadge, UiJsonBlock, UiPanel } from '@/components/ui'
import { formatDateTime, sanitizeForDisplay } from '@/lib/stackos/json'

const props = withDefaults(defineProps<{
  title?: string
  query?: SchemaContextQueryOut | null
  items?: SchemaContextItemOut[]
}>(), {
  title: 'Context',
  query: null,
  items: () => [],
})

const rows = computed(() => props.query?.items ?? props.items)
const sources = computed(() => props.query?.sources ?? Array.from(new Set(rows.value.map((r) => r.source))))
</script>

<template>
  <UiPanel :aria-label="title">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h3 class="t-h3 text-fg-strong">
        {{ title }}
      </h3>
      <div
        v-if="sources.length"
        class="flex shrink-0 flex-wrap items-center justify-end gap-1.5"
      >
        <UiBadge
          v-for="source in sources"
          :key="source"
          tone="info"
        >
          {{ source }}
        </UiBadge>
      </div>
    </div>

    <p
      v-if="rows.length === 0"
      class="mt-2 text-sm text-fg-muted"
    >
      No context rows for this query.
    </p>
    <ol
      v-else
      class="mt-3 space-y-2"
    >
      <li
        v-for="item in rows"
        :key="`${item.source}-${item.id}`"
        class="rounded-md border border-subtle bg-bg-surface p-2.5"
      >
        <div class="mb-2 flex flex-wrap items-center gap-2">
          <UiBadge tone="accent">
            {{ item.source }}
          </UiBadge>
          <span class="font-mono text-2xs text-fg-subtle">#{{ item.id }}</span>
          <span class="min-w-0 flex-1 truncate text-sm font-medium text-fg-default">
            {{ item.title ?? '—' }}
          </span>
          <span class="shrink-0 text-2xs text-fg-subtle">
            {{ formatDateTime(item.occurred_at) }}
          </span>
        </div>
        <UiJsonBlock
          :data="sanitizeForDisplay(item.fields)"
          density="compact"
          max-height="12rem"
          wrap
        />
      </li>
    </ol>
  </UiPanel>
</template>
