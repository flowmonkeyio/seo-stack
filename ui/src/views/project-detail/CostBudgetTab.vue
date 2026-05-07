<script setup lang="ts">
// CostBudgetTab — current-month cost summary + budget cap form + 12-month
// sparkline. Wires to the costs store.
//
// At M5.C the CostResponse may legitimately return zero across the board
// (no integration calls accumulated yet). We surface an info badge in that
// case rather than a misleading "no data" banner.

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import {
  INTEGRATION_KINDS,
  useCostsStore,
  type IntegrationBudget,
} from '@/stores/costs'
import { useToastsStore } from '@/stores/toasts'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const costsStore = useCostsStore()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { cost, budgets, history, hasNoSpendYet, month, loading } = storeToRefs(costsStore)

const formOpen = ref<IntegrationBudget | null>(null)
const formNew = ref(false)
const submitting = ref(false)
const draft = ref({
  kind: 'dataforseo',
  monthly_budget_usd: 50,
  alert_threshold_pct: 80,
  qps: 1,
})

const columns: DataTableColumn<IntegrationBudget>[] = [
  { key: 'kind', label: 'Integration', cellClass: 'font-mono text-sm' },
  {
    key: 'monthly_budget_usd',
    label: 'Monthly cap',
    format: (v) => `$${Number(v).toFixed(2)}`,
  },
  {
    key: 'current_month_spend',
    label: 'Spent',
    format: (v) => `$${Number(v).toFixed(2)}`,
  },
  {
    key: 'alert_threshold_pct',
    label: 'Alert pct',
    format: (v) => `${Number(v).toFixed(0)}%`,
  },
  { key: 'qps', label: 'QPS' },
]

const integrationCostRows = computed(() => {
  if (!cost.value) return []
  return Object.entries(cost.value.by_integration).map(([k, v]) => ({
    id: k,
    integration: k,
    spend: v,
  }))
})

const integrationColumns: DataTableColumn<{
  id: string
  integration: string
  spend: number
}>[] = [
  { key: 'integration', label: 'Integration', cellClass: 'font-mono text-sm' },
  { key: 'spend', label: 'Spend (USD)', format: (v) => `$${Number(v).toFixed(2)}` },
]

interface SparklinePoint {
  x: number
  y: number
  ym: string
  total: number
}

/**
 * Compute a 100×30 sparkline from `history`. We render inline SVG so we
 * don't pull in a chart library; matches PLAN.md's "no chart deps" hint.
 */
const sparkline = computed<SparklinePoint[]>(() => {
  if (history.value.length === 0) return []
  const W = 200
  const H = 40
  const max = Math.max(...history.value.map((c) => c.total_usd), 1)
  return history.value.map((c, i) => ({
    x: (i / Math.max(history.value.length - 1, 1)) * W,
    y: H - (c.total_usd / max) * H,
    ym: c.period_start.slice(0, 7),
    total: c.total_usd,
  }))
})

const sparklinePath = computed<string>(() => {
  return sparkline.value
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(' ')
})

function openNew(): void {
  formNew.value = true
  formOpen.value = null
  draft.value = {
    kind: 'dataforseo',
    monthly_budget_usd: 50,
    alert_threshold_pct: 80,
    qps: 1,
  }
}

function openEdit(b: IntegrationBudget): void {
  formNew.value = false
  formOpen.value = b
  draft.value = {
    kind: b.kind,
    monthly_budget_usd: b.monthly_budget_usd,
    alert_threshold_pct: b.alert_threshold_pct,
    qps: b.qps,
  }
}

function closeForm(): void {
  if (submitting.value) return
  formOpen.value = null
  formNew.value = false
}

async function submit(): Promise<void> {
  submitting.value = true
  try {
    await costsStore.upsertBudget(projectId.value, {
      kind: draft.value.kind,
      monthly_budget_usd: draft.value.monthly_budget_usd,
      alert_threshold_pct: draft.value.alert_threshold_pct,
      qps: draft.value.qps,
    })
    toasts.success('Budget saved', draft.value.kind)
    formOpen.value = null
    formNew.value = false
    await costsStore.refreshBudgets(projectId.value)
  } catch (err) {
    toasts.error('Failed to save budget', err instanceof Error ? err.message : undefined)
  } finally {
    submitting.value = false
  }
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
watch(projectId, load)
</script>

<template>
  <section class="space-y-6">
    <div>
      <div class="mb-2 flex flex-wrap items-baseline gap-3">
        <h2 class="text-base font-semibold">
          Current month
          <span class="text-sm text-gray-500 dark:text-gray-400">{{ month ?? '' }}</span>
        </h2>
        <span
          v-if="hasNoSpendYet"
          class="rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-900/40 dark:text-blue-200"
        >
          No spend recorded yet
        </span>
      </div>
      <p class="mb-3 text-sm text-gray-600 dark:text-gray-400">
        Total: <strong>${{ Number(cost?.total_usd ?? 0).toFixed(2) }}</strong>
      </p>
      <DataTable
        :items="integrationCostRows"
        :columns="integrationColumns"
        :loading="loading"
        aria-label="Cost breakdown by integration"
        empty-message="No integration cost data yet."
      />
    </div>

    <div>
      <div class="mb-2 flex flex-wrap items-baseline justify-between gap-3">
        <h2 class="text-base font-semibold">
          Budget caps
        </h2>
        <button
          type="button"
          class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
          @click="openNew"
        >
          Set budget
        </button>
      </div>
      <DataTable
        :items="budgets"
        :columns="columns"
        :loading="loading"
        aria-label="Budget caps"
        empty-message="No budgets defined."
        @row-click="openEdit"
      />
    </div>

    <div>
      <h2 class="mb-2 text-base font-semibold">
        12-month history
      </h2>
      <p
        v-if="sparkline.length === 0"
        class="text-sm text-gray-500 dark:text-gray-400"
      >
        No history yet.
      </p>
      <div
        v-else
        class="rounded border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900"
      >
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
            stroke="currentColor"
            stroke-width="2"
            class="text-blue-600 dark:text-blue-400"
          />
          <circle
            v-for="p in sparkline"
            :key="p.ym"
            :cx="p.x"
            :cy="p.y"
            r="2"
            class="fill-blue-600 dark:fill-blue-400"
          >
            <title>{{ p.ym }}: ${{ p.total.toFixed(2) }}</title>
          </circle>
        </svg>
        <ul class="mt-2 grid grid-cols-2 gap-1 text-xs text-gray-600 sm:grid-cols-4 dark:text-gray-400">
          <li
            v-for="p in sparkline"
            :key="p.ym"
          >
            {{ p.ym }}: ${{ p.total.toFixed(2) }}
          </li>
        </ul>
      </div>
    </div>

    <div
      v-if="formOpen || formNew"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-budget-form-title"
      @click.self="closeForm"
    >
      <div
        class="w-full max-w-md rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h3
          id="cs-budget-form-title"
          class="mb-3 text-lg font-semibold"
        >
          {{ formNew ? 'Set new budget' : `Edit budget: ${formOpen?.kind ?? ''}` }}
        </h3>
        <label class="mb-3 block text-sm">
          <span class="font-medium">Integration kind</span>
          <select
            v-model="draft.kind"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            :disabled="!formNew"
          >
            <option
              v-for="k in INTEGRATION_KINDS"
              :key="k"
              :value="k"
            >
              {{ k }}
            </option>
          </select>
        </label>
        <label class="mb-3 block text-sm">
          <span class="font-medium">Monthly cap (USD)</span>
          <input
            v-model.number="draft.monthly_budget_usd"
            type="number"
            min="0"
            step="0.01"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
          >
        </label>
        <label class="mb-3 block text-sm">
          <span class="font-medium">Alert threshold (%)</span>
          <input
            v-model.number="draft.alert_threshold_pct"
            type="number"
            min="0"
            max="100"
            step="1"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
          >
        </label>
        <label class="mb-3 block text-sm">
          <span class="font-medium">QPS (queries per second)</span>
          <input
            v-model.number="draft.qps"
            type="number"
            min="0"
            step="0.1"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
          >
        </label>
        <div class="flex justify-end gap-2">
          <button
            type="button"
            class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            :disabled="submitting"
            @click="closeForm"
          >
            Cancel
          </button>
          <button
            type="button"
            class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            :disabled="submitting"
            @click="submit"
          >
            {{ submitting ? 'Saving…' : 'Save budget' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
