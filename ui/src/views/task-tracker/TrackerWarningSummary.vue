<script setup lang="ts">
import { computed } from 'vue'

import { UiBadge, UiCallout } from '@/components/ui'

type GraphIssueSeverity = 'error' | 'warning'

interface GraphIssue {
  id: string
  message: string
  severity: GraphIssueSeverity
}

const props = defineProps<{
  warnings: string[]
}>()

const issues = computed<GraphIssue[]>(() =>
  props.warnings.map((message, index) => ({
    id: `${index}:${message}`,
    message,
    severity: graphIssueSeverity(message),
  })),
)

const errorCount = computed(() => issues.value.filter((issue) => issue.severity === 'error').length)
const warningCount = computed(
  () => issues.value.filter((issue) => issue.severity === 'warning').length,
)
const tone = computed(() => (errorCount.value > 0 ? 'danger' : 'warning'))
const summaryText = computed(
  () =>
    `This task has ${formatCount(errorCount.value, 'error')} and ${formatCount(
      warningCount.value,
      'warning',
    )}.`,
)

function graphIssueSeverity(message: string): GraphIssueSeverity {
  const text = message.toLowerCase()
  const workflowBlocking =
    text.includes('workflow') &&
    [
      'bypass',
      'closeout',
      'dependency bridge',
      'outside the dependency spine',
      'remain open',
      'terminal child',
      'not reachable',
    ].some((needle) => text.includes(needle))
  if (workflowBlocking || text.includes('failed') || text.includes('missing')) {
    return 'error'
  }
  return 'warning'
}

function formatCount(count: number, label: string): string {
  return `${count} ${label}${count === 1 ? '' : 's'}`
}
</script>

<template>
  <UiCallout v-if="issues.length" :tone="tone" density="compact">
    <details class="tracker-warning-summary">
      <summary class="tracker-warning-summary__header focus-ring">
        <span class="tracker-warning-summary__title">{{ summaryText }}</span>
        <span class="tracker-warning-summary__badges">
          <UiBadge v-if="errorCount" tone="danger" variant="outline">
            {{ formatCount(errorCount, 'error') }}
          </UiBadge>
          <UiBadge v-if="warningCount" tone="warning" variant="outline">
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
          <UiBadge :tone="issue.severity === 'error' ? 'danger' : 'warning'" variant="subtle">
            {{ issue.severity === 'error' ? 'Error' : 'Warning' }}
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
  border-radius: 4px;
}

.tracker-warning-summary__header::-webkit-details-marker {
  display: none;
}

.tracker-warning-summary__title {
  min-width: 0;
  color: currentColor;
  font-size: 13px;
  font-weight: 700;
}

.tracker-warning-summary__badges {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
}

.tracker-warning-summary__toggle {
  color: var(--color-fg-muted);
  font-size: 12px;
  font-weight: 700;
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
  font-size: 13px;
  line-height: 1.45;
}
</style>
