<script setup lang="ts">
import { computed } from 'vue'

import { UiBadge, UiCallout } from '@/components/ui'

interface GraphIssue {
  id: string
  message: string
}

const props = defineProps<{
  warnings: string[]
}>()

const issues = computed<GraphIssue[]>(() =>
  props.warnings.map((message, index) => ({
    id: `${index}:${message}`,
    message,
  })),
)

const warningCount = computed(() => issues.value.length)
const summaryText = computed(() => `This task has ${formatCount(warningCount.value, 'warning')}.`)

function formatCount(count: number, label: string): string {
  return `${count} ${label}${count === 1 ? '' : 's'}`
}
</script>

<template>
  <UiCallout
    v-if="issues.length"
    tone="warning"
    density="compact"
  >
    <details class="tracker-warning-summary">
      <summary class="tracker-warning-summary__header focus-ring">
        <span class="tracker-warning-summary__title">{{ summaryText }}</span>
        <span class="tracker-warning-summary__badges">
          <UiBadge
            v-if="warningCount"
            tone="warning"
            variant="outline"
          >
            {{ formatCount(warningCount, 'warning') }}
          </UiBadge>
          <span class="tracker-warning-summary__toggle">Details</span>
        </span>
      </summary>
      <ul class="tracker-warning-summary__list">
        <li
          v-for="issue in issues"
          :key="issue.id"
          class="tracker-warning-summary__item"
        >
          <UiBadge
            tone="warning"
            variant="subtle"
          >
            Warning
          </UiBadge>
          <span>{{ issue.message }}</span>
        </li>
      </ul>
    </details>
  </UiCallout>
</template>

<style scoped>
.tracker-warning-summary {
  min-width: 0;
}

.tracker-warning-summary__header {
  display: flex;
  min-width: 0;
  cursor: pointer;
  list-style: none;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-radius: var(--radius-xs);
}

.tracker-warning-summary__header::-webkit-details-marker {
  display: none;
}

.tracker-warning-summary__title {
  min-width: 0;
  color: currentColor;
  font-size: var(--fs-sm);
  font-weight: var(--fw-medium);
}

.tracker-warning-summary__badges {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
}

.tracker-warning-summary__toggle {
  color: var(--color-fg-muted);
  font-size: var(--fs-xs);
  font-weight: var(--fw-medium);
}

.tracker-warning-summary__toggle::after {
  content: " +";
}

.tracker-warning-summary[open] .tracker-warning-summary__toggle::after {
  content: " -";
}

.tracker-warning-summary__list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.tracker-warning-summary__item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: start;
  gap: 10px;
  color: currentColor;
  font-size: var(--fs-sm);
  line-height: var(--lh-sm);
}
</style>
