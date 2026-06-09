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

const statusClass = computed(() => `task-graph-node--status-${props.data.status}`)
</script>

<template>
  <div
    class="task-graph-node"
    :class="statusClass"
  >
    <div class="flex items-start gap-3">
      <div class="task-graph-node__mark">
        {{ initials }}
      </div>
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2">
          <p class="truncate text-sm font-semibold text-fg-strong">
            {{ data.label }}
          </p>
          <TrackerStatusBadge :status="data.status" />
        </div>
        <p
          v-if="data.subtitle"
          class="mt-1 line-clamp-2 text-xs text-fg-muted"
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
  --task-node-status: var(--color-neutral-default);

  position: relative;
  box-sizing: border-box;
  width: 100%;
  min-width: 312px;
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-md);
  background: var(--color-bg-surface);
  box-shadow: var(--shadow-xs);
  padding: 14px 14px 14px 18px;
}

/* 2px status accent strip flush with the left edge. */
.task-graph-node::before {
  content: '';
  position: absolute;
  top: -1px;
  bottom: -1px;
  left: -1px;
  width: 2px;
  border-radius: var(--radius-md) 0 0 var(--radius-md);
  background: var(--task-node-status);
}

.task-graph-node:hover {
  box-shadow: var(--shadow-sm);
}

.task-graph-node--status-complete {
  --task-node-status: var(--color-success-default);
}

.task-graph-node--status-in-progress {
  --task-node-status: var(--color-info-default);
}

.task-graph-node--status-deferred {
  --task-node-status: var(--color-warning-default);
}

.task-graph-node--status-aborted,
.task-graph-node--status-failed {
  --task-node-status: var(--color-danger-default);
}

.task-graph-node__mark {
  display: grid;
  width: 34px;
  height: 34px;
  flex: none;
  place-items: center;
  border-radius: var(--radius-md);
  background: var(--color-bg-sunken);
  color: var(--color-fg-muted);
  font-size: var(--fs-2xs);
  font-weight: var(--fw-semibold);
}
</style>
