<script setup lang="ts">
import { computed } from 'vue'

import { UiBadge } from '@/components/ui'
import type { TrackerVueNodeData } from '@/lib/task-tracker/graphModel'

import TrackerStatusBadge from './TrackerStatusBadge.vue'

const props = defineProps<{
  data: TrackerVueNodeData
}>()

const initials = computed(() =>
  props.data.label
    .split(/\s+/)
    .slice(0, 2)
    .map((item) => item[0]?.toUpperCase() ?? '')
    .join(''),
)
</script>

<template>
  <div class="task-graph-node">
    <div class="flex items-start gap-3">
      <div class="task-graph-node__mark">
        {{ initials }}
      </div>
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2">
          <p class="truncate text-sm font-semibold text-text">{{ data.label }}</p>
          <TrackerStatusBadge :status="data.status" />
        </div>
        <p
          v-if="data.subtitle"
          class="mt-1 line-clamp-2 text-xs text-text-muted"
        >
          {{ data.subtitle }}
        </p>
      </div>
    </div>
    <div class="mt-3 flex flex-wrap gap-2">
      <UiBadge
        tone="neutral"
        variant="outline"
        size="sm"
      >
        {{ data.priorityKey }}
      </UiBadge>
      <UiBadge
        tone="neutral"
        variant="outline"
        size="sm"
      >
        {{ data.laneKey }}
      </UiBadge>
    </div>
  </div>
</template>

<style scoped>
.task-graph-node {
  box-sizing: border-box;
  width: 100%;
  min-width: 312px;
  border: 1px solid var(--color-border-subtle);
  border-radius: 8px;
  background: var(--color-bg-surface);
  box-shadow: var(--shadow-sm);
  padding: 14px;
}

.task-graph-node__mark {
  display: grid;
  width: 34px;
  height: 34px;
  flex: none;
  place-items: center;
  border-radius: 8px;
  background: var(--color-bg-surface-alt);
  color: var(--color-fg-muted);
  font-size: 11px;
  font-weight: 700;
}
</style>
