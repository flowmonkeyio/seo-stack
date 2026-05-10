// Costs store — query monthly cost per project + budget upsert.
//
// Wires to:
// - `GET    /api/v1/projects/{id}/cost?month=YYYY-MM`
// - `GET    /api/v1/projects/{id}/budgets/{kind}`     — per-kind budget
// - `POST   /api/v1/projects/{id}/budgets`            — upsert
// - `PATCH  /api/v1/projects/{id}/budgets/{kind}`     — partial update
//
// At M5.C the cost endpoint may legitimately return zeros across the board
// because the M4 integrations layer isn't recording cost rows yet (per the
// CostResponse docstring). The store + view treat that as a valid "no spend
// recorded yet" state rather than an error.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, apiWrite } from '@/lib/client'
import type { components } from '@/api'

export type CostResponse = components['schemas']['CostResponse']
export type IntegrationBudget = components['schemas']['IntegrationBudgetOut']
type BudgetUpsertRequest = components['schemas']['BudgetUpsertRequest']

/**
 * Standard list of integration kinds that the UI iterates when refreshing
 * budgets. Mirrors the IntegrationKind values in `meta/enums` —
 * intentionally hard-coded here so the budgets section can render before
 * meta is fetched. Stays in sync with PLAN.md's integrations list.
 */
export const INTEGRATION_KINDS = [
  'dataforseo',
  'firecrawl',
  'gsc',
  'openai-images',
  'reddit',
  'google-paa',
  'jina',
  'ahrefs',
] as const

export type IntegrationKind = (typeof INTEGRATION_KINDS)[number]

export const useCostsStore = defineStore('costs', () => {
  const cost = ref<CostResponse | null>(null)
  const budgets = ref<IntegrationBudget[]>([])
  const history = ref<CostResponse[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentProjectId = ref<number | null>(null)
  const month = ref<string | null>(null)

  function defaultMonth(): string {
    const d = new Date()
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`
  }

  async function refreshCost(projectId: number, ym: string | null = null): Promise<void> {
    currentProjectId.value = projectId
    if (!ym) ym = defaultMonth()
    month.value = ym
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams({ month: ym })
      cost.value = await apiFetch<CostResponse>(
        `/api/v1/projects/${projectId}/cost?${params.toString()}`,
      )
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load cost'
    } finally {
      loading.value = false
    }
  }

  async function refreshBudgets(projectId: number): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const results = await Promise.allSettled(
        INTEGRATION_KINDS.map(async (k) => {
          return apiFetch<IntegrationBudget>(
            `/api/v1/projects/${projectId}/budgets/${k}`,
          )
        }),
      )
      const next: IntegrationBudget[] = []
      for (const r of results) {
        if (r.status === 'fulfilled') next.push(r.value)
      }
      budgets.value = next
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load budgets'
    } finally {
      loading.value = false
    }
  }

  async function refreshHistory(projectId: number, months = 12): Promise<void> {
    const now = new Date()
    const ymRange: string[] = []
    for (let i = 0; i < months; i++) {
      const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - i, 1))
      const ym = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`
      ymRange.push(ym)
    }
    const results = await Promise.allSettled(
      ymRange.map(async (ym) => {
        const params = new URLSearchParams({ month: ym })
        return apiFetch<CostResponse>(
          `/api/v1/projects/${projectId}/cost?${params.toString()}`,
        )
      }),
    )
    const next: CostResponse[] = []
    for (const r of results) {
      if (r.status === 'fulfilled') next.push(r.value)
    }
    next.sort((a, b) => (a.period_start < b.period_start ? -1 : 1))
    history.value = next
  }

  async function upsertBudget(
    projectId: number,
    body: BudgetUpsertRequest,
  ): Promise<IntegrationBudget> {
    // Use POST per the wire — server upserts on `(project_id, kind)`.
    const row = await apiWrite<IntegrationBudget>(`/api/v1/projects/${projectId}/budgets`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    const idx = budgets.value.findIndex((b) => b.kind === row.kind)
    if (idx >= 0) budgets.value.splice(idx, 1, row)
    else budgets.value = [row, ...budgets.value]
    return row
  }

  /**
   * Helper for the Cost & Budget tab — true when this milestone's cost row
   * is all-zero so the view can render the "No spend recorded yet" badge
   * instead of the empty chart.
   */
  const hasNoSpendYet = computed<boolean>(() => {
    if (!cost.value) return false
    if (cost.value.total_usd > 0) return false
    return true
  })

  function reset(): void {
    cost.value = null
    budgets.value = []
    history.value = []
    error.value = null
    currentProjectId.value = null
    month.value = null
  }

  return {
    cost,
    budgets,
    history,
    loading,
    error,
    currentProjectId,
    month,
    hasNoSpendYet,
    refreshCost,
    refreshBudgets,
    refreshHistory,
    upsertBudget,
    reset,
  }
})
