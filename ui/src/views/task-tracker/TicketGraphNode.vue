<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'

import type { TrackerVueNodeData } from '@/lib/task-tracker/graphModel'
import { isTerminalTrackerStatus } from '@/lib/task-tracker/status'

const props = defineProps<{
  data: TrackerVueNodeData
}>()

const isOpen = computed(() => !isTerminalTrackerStatus(props.data.status))
const isBlocked = computed(() => isOpen.value && (props.data.blockedBy?.length ?? 0) > 0)
const statusClass = computed(() => `ticket-graph-node--status-${props.data.status}`)
</script>

<template>
  <div
    class="ticket-graph-node"
    :class="[statusClass, { 'ticket-graph-node--blocked': isBlocked }]"
  >
    <Handle
      id="in"
      type="target"
      :position="Position.Left"
      :connectable="false"
      class="ticket-graph-node__handle ticket-graph-node__handle--target"
    />
    <Handle
      id="out"
      type="source"
      :position="Position.Right"
      :connectable="false"
      class="ticket-graph-node__handle ticket-graph-node__handle--source"
    />

    <div class="ticket-graph-node__top">
      <p class="ticket-graph-node__title">
        {{ data.label }}
      </p>
      <span
        class="ticket-graph-node__dot"
        :title="data.status"
      />
    </div>

    <p
      v-if="data.subtitle"
      class="ticket-graph-node__subtitle"
    >
      {{ data.subtitle }}
    </p>

    <div class="ticket-graph-node__meta">
      <span class="ticket-graph-node__key">{{ data.itemKey }}</span>
      <span>{{ data.priorityKey }}</span>
      <span>{{ data.laneKey }}</span>
      <span v-if="data.assignee">{{ data.assignee }}</span>
      <span v-if="data.runPlanId">Run {{ data.runPlanId }}</span>
    </div>

    <p
      v-if="isBlocked"
      class="ticket-graph-node__blocked"
    >
      Blocked by {{ data.blockedBy?.join(', ') }}
    </p>
  </div>
</template>

<style scoped>
.ticket-graph-node {
  --ticket-node-status: var(--color-neutral-default);

  position: relative;
  box-sizing: border-box;
  width: 236px;
  min-height: 84px;
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-md);
  background: var(--color-bg-surface);
  box-shadow: var(--shadow-xs);
  padding: 9px 10px 9px 14px;
}

/* 2px status accent strip flush with the left edge. */
.ticket-graph-node::before {
  content: '';
  position: absolute;
  top: -1px;
  bottom: -1px;
  left: -1px;
  width: 2px;
  border-radius: var(--radius-md) 0 0 var(--radius-md);
  background: var(--ticket-node-status);
}

.ticket-graph-node:hover {
  box-shadow: var(--shadow-sm);
}

.ticket-graph-node--status-complete {
  --ticket-node-status: var(--color-success-default);
}

.ticket-graph-node--status-in-progress {
  --ticket-node-status: var(--color-info-default);
}

.ticket-graph-node--status-deferred {
  --ticket-node-status: var(--color-warning-default);
}

.ticket-graph-node--status-aborted,
.ticket-graph-node--status-failed {
  --ticket-node-status: var(--color-danger-default);
}

.ticket-graph-node--blocked {
  border-color: color-mix(in srgb, var(--color-danger-default) 45%, var(--color-border-default));
}

.ticket-graph-node__handle {
  width: 8px;
  height: 8px;
  border: 1px solid var(--color-border-strong);
  background: var(--color-bg-surface);
}

.ticket-graph-node__handle--target {
  left: -1px;
}

.ticket-graph-node__handle--source {
  right: -1px;
}

.ticket-graph-node__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.ticket-graph-node__title {
  overflow: hidden;
  min-width: 0;
  color: var(--color-fg-strong);
  font-size: var(--fs-2xs);
  font-weight: var(--fw-medium);
  line-height: var(--lh-2xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ticket-graph-node__dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  flex: none;
  border-radius: var(--radius-full);
  background: var(--ticket-node-status);
}

.ticket-graph-node__subtitle {
  overflow: hidden;
  margin-top: 3px;
  color: var(--color-fg-muted);
  font-size: var(--fs-2xs);
  line-height: var(--lh-2xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ticket-graph-node__meta {
  display: flex;
  gap: 7px;
  overflow: hidden;
  margin-top: 8px;
  color: var(--color-fg-subtle);
  font-size: var(--fs-2xs);
  line-height: 1;
  white-space: nowrap;
}

.ticket-graph-node__meta span {
  overflow: hidden;
  max-width: 82px;
  text-overflow: ellipsis;
}

.ticket-graph-node__key {
  font-family: var(--font-mono);
}

.ticket-graph-node__blocked {
  overflow: hidden;
  margin-top: 5px;
  color: var(--color-danger-fg);
  font-size: var(--fs-2xs);
  line-height: var(--lh-2xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
