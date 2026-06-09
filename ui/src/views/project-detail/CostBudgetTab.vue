<script setup lang="ts">
// CostBudgetTab — read-only current-month cost and budget visibility.

import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import {
  UiBadge,
  UiButton,
  UiCallout,
  UiCard,
  UiEmptyState,
  UiMetricCard,
  UiProgressBar,
  UiSectionHeader,
} from '@/components/ui'
import {
  INTEGRATION_KINDS,
  useCostsStore,
  type IntegrationBudget,
  type IntegrationKind,
} from '@/stores/costs'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const costsStore = useCostsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))
const { cost, budgets, history, hasNoSpendYet, month, loading } = storeToRefs(costsStore)

type IntegrationKindLabels = { [Key in IntegrationKind]: string }

const integrationLabels: IntegrationKindLabels = {
  dataforseo: 'DataForSEO',
  firecrawl: 'Firecrawl',
  'openai-images': 'OpenAI Images',
  reddit: 'Reddit',
  'google-paa': 'Google PAA',
  jina: 'Jina Reader',
  ahrefs: 'Ahrefs',
}

const integrationCostRows = computed(() => {
  if (!cost.value) return []
  return Object.entries(cost.value.by_integration).map(([kind, spend]) => ({
    id: kind,
    integration: integrationLabel(kind),
    spend,
  }))
})

const integrationColumns: DataTableColumn<{
  id: string
  integration: string
  spend: number
}>[] = [
  { key: 'integration', label: 'Integration' },
  { key: 'spend', label: 'Spend (USD)', format: (value) => `$${Number(value).toFixed(2)}` },
]

const totalBudgetCap = computed(() =>
  budgets.value.reduce((sum, budget) => sum + budget.monthly_budget_usd, 0),
)

const totalBudgetCalls = computed(() =>
  budgets.value.reduce((sum, budget) => sum + budget.current_month_calls, 0),
)

const budgetUsagePercent = computed(() =>
  totalBudgetCap.value > 0
    ? Math.min(100, (Number(cost.value?.total_usd ?? 0) / totalBudgetCap.value) * 100)
    : 0,
)

interface SparklinePoint {
  x: number
  y: number
  ym: string
  total: number
}

const sparkline = computed<SparklinePoint[]>(() => {
  if (history.value.length === 0) return []
  const width = 200
  const height = 40
  const max = Math.max(...history.value.map((row) => row.total_usd), 1)
  return history.value.map((row, index) => ({
    x: (index / Math.max(history.value.length - 1, 1)) * width,
    y: height - (row.total_usd / max) * height,
    ym: row.period_start.slice(0, 7),
    total: row.total_usd,
  }))
})

const sparklinePath = computed<string>(() => {
  return sparkline.value
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x.toFixed(1)},${point.y.toFixed(1)}`)
    .join(' ')
})

const historyHasSpend = computed(() =>
  history.value.some((row) => Number(row.total_usd) > 0),
)

function integrationLabel(kind: string): string {
  return INTEGRATION_KINDS.includes(kind as IntegrationKind)
    ? integrationLabels[kind as IntegrationKind]
    : kind
}

function formatUsd(value: number | null | undefined): string {
  return `$${Number(value ?? 0).toFixed(2)}`
}

function budgetUsage(budget: IntegrationBudget): number {
  if (budget.monthly_budget_usd <= 0) return 0
  return Math.min(100, (budget.current_month_spend / budget.monthly_budget_usd) * 100)
}

function budgetTone(budget: IntegrationBudget): 'success' | 'warning' | 'danger' {
  const pct = budgetUsage(budget)
  if (pct >= 100) return 'danger'
  if (pct >= budget.alert_threshold_pct) return 'warning'
  return 'success'
}

function budgetStatusLabel(budget: IntegrationBudget): string {
  const pct = budgetUsage(budget)
  if (pct >= 100) return 'Over cap'
  if (pct >= budget.alert_threshold_pct) return 'Near alert'
  return 'Healthy'
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  await Promise.all([
    costsStore.refreshCost(projectId.value),
    costsStore.refreshBudgets(projectId.value),
    costsStore.refreshHistory(projectId.value, 12),
  ])
}

onMounted(load)
</script>

<template>
  <section class="space-y-5">
    <UiSectionHeader
      title="Cost & budget"
      description="Read-only spend, budget caps, and vendor pacing for agent-owned integrations."
    >
      <template #actions>
        <UiButton
          size="sm"
          variant="secondary"
          :disabled="loading"
          @click="load"
        >
          {{ loading ? 'Refreshing...' : 'Refresh' }}
        </UiButton>
      </template>
    </UiSectionHeader>

    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <UiMetricCard
        label="Current month"
        :value="formatUsd(cost?.total_usd)"
        :delta="month ?? undefined"
        delta-label="period"
        delta-tone="neutral"
        density="compact"
        :loading="loading && !cost"
      />
      <UiMetricCard
        label="Budget cap"
        :value="formatUsd(totalBudgetCap)"
        :delta="`${budgetUsagePercent.toFixed(0)}%`"
        delta-label="used"
        :delta-tone="
          budgetUsagePercent >= 100 ? 'negative' : budgetUsagePercent >= 80 ? 'neutral' : 'positive'
        "
        density="compact"
      />
      <UiMetricCard
        label="Tracked calls"
        :value="totalBudgetCalls"
        delta-label="this month"
        delta-tone="neutral"
        density="compact"
      />
      <UiMetricCard
        label="Configured caps"
        :value="budgets.length"
        :delta="`${INTEGRATION_KINDS.length} vendors`"
        delta-label="available"
        delta-tone="neutral"
        density="compact"
      />
    </div>

    <UiCallout
      v-if="hasNoSpendYet"
      tone="info"
      title="No spend recorded yet"
    >
      Cost rows will appear after integrations make tracked vendor calls.
    </UiCallout>

    <section aria-label="Current month spend">
      <UiSectionHeader
        title="Current month spend"
        :description="`Vendor spend recorded for ${month ?? 'the selected period'}.`"
        as="h3"
      />
      <DataTable
        :items="integrationCostRows"
        :columns="integrationColumns"
        :loading="loading"
        aria-label="Cost breakdown by integration"
        empty-message="No integration cost data yet."
      />
    </section>

    <section aria-label="Budget caps">
      <UiSectionHeader
        title="Budget caps"
        description="Per-vendor monthly caps, alert thresholds, and request pacing."
        as="h3"
      />

      <UiEmptyState
        v-if="!loading && budgets.length === 0"
        title="No budget caps"
        description="Agent-owned caps will appear here with alert thresholds and pacing."
        icon="banknotes"
        class="rounded-lg border border-dashed border-default bg-bg-surface"
      />

      <div
        v-else
        class="grid gap-4"
      >
        <UiCard
          v-for="budget in budgets"
          :key="budget.id"
        >
          <template #header>
            <h4 class="t-h3 text-fg-strong">
              {{ integrationLabel(budget.kind) }}
            </h4>
            <UiBadge :tone="budgetTone(budget)">
              {{ budgetStatusLabel(budget) }}
            </UiBadge>
          </template>

          <p class="text-sm text-fg-muted">
            {{ formatUsd(budget.current_month_spend) }} spent from a
            {{ formatUsd(budget.monthly_budget_usd) }} monthly cap.
          </p>

          <UiProgressBar
            class="mt-3"
            :value="budget.current_month_spend"
            :max="budget.monthly_budget_usd || 1"
            :tone="budgetTone(budget)"
            show-label
            :format="() => `${budgetUsage(budget).toFixed(0)}%`"
            :aria-label="`${integrationLabel(budget.kind)} budget usage`"
          />

          <template #footer>
            <dl class="grid w-full gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
              <div>
                <dt class="text-xs font-medium text-fg-muted">
                  Alert
                </dt>
                <dd class="mt-0.5 tabular-nums text-fg-default">
                  {{ Number(budget.alert_threshold_pct).toFixed(0) }}%
                </dd>
              </div>
              <div>
                <dt class="text-xs font-medium text-fg-muted">
                  Calls
                </dt>
                <dd class="mt-0.5 tabular-nums text-fg-default">
                  {{ budget.current_month_calls }}
                </dd>
              </div>
              <div>
                <dt class="text-xs font-medium text-fg-muted">
                  QPS
                </dt>
                <dd class="mt-0.5 tabular-nums text-fg-default">
                  {{ budget.qps }}
                </dd>
              </div>
              <div>
                <dt class="text-xs font-medium text-fg-muted">
                  Run-plan guard
                </dt>
                <dd class="mt-0.5 text-fg-muted">
                  Checked before vendor calls.
                </dd>
              </div>
            </dl>
          </template>
        </UiCard>
      </div>
    </section>

    <section aria-label="12-month history">
      <UiSectionHeader
        title="12-month history"
        description="Quick trend view for vendor spend over time."
        as="h3"
      />

      <UiEmptyState
        v-if="sparkline.length === 0 || !historyHasSpend"
        title="No cost history yet"
        description="The trend appears once a monthly snapshot records vendor spend."
        icon="banknotes"
        class="rounded-lg border border-dashed border-default bg-bg-surface"
      />
      <UiCard v-else>
        <svg
          viewBox="0 0 200 40"
          width="100%"
          height="60"
          role="img"
          aria-label="Cost sparkline (last 12 months)"
        >
          <path
            :d="sparklinePath"
            fill="none"
            stroke-width="2"
            style="stroke: var(--color-accent-primary)"
          />
          <circle
            v-for="point in sparkline"
            :key="point.ym"
            :cx="point.x"
            :cy="point.y"
            r="2"
            style="fill: var(--color-accent-primary)"
          >
            <title>{{ point.ym }}: ${{ point.total.toFixed(2) }}</title>
          </circle>
        </svg>
        <ul class="mt-2 grid grid-cols-4 gap-1 text-xs text-fg-muted lg:grid-cols-6">
          <li
            v-for="point in sparkline"
            :key="point.ym"
          >
            {{ point.ym }}: ${{ point.total.toFixed(2) }}
          </li>
        </ul>
      </UiCard>
    </section>
  </section>
</template>
