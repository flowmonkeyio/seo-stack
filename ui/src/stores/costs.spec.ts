import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useCostsStore } from './costs'

const ORIG_FETCH = globalThis.fetch

const ZERO_COST = {
  by_integration: { dataforseo: 0, firecrawl: 0 },
  total_usd: 0,
  period_start: '2026-05-01T00:00:00Z',
  period_end: '2026-06-01T00:00:00Z',
}

const BUDGET = {
  id: 1,
  project_id: 1,
  kind: 'dataforseo',
  monthly_budget_usd: 50,
  alert_threshold_pct: 80,
  current_month_spend: 0,
  current_month_calls: 0,
  qps: 1,
  last_reset: '2026-05-01T00:00:00Z',
}

describe('costs store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('refreshCost() loads the response and exposes hasNoSpendYet', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify(ZERO_COST), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useCostsStore()
    await store.refreshCost(1, '2026-05')
    expect(store.cost?.total_usd).toBe(0)
    expect(store.hasNoSpendYet).toBe(true)
  })

  it('refreshBudgets() collects per-kind rows ignoring 404s', async () => {
    let calls = 0
    globalThis.fetch = vi.fn(async (input) => {
      calls += 1
      const url = String(input)
      if (url.includes('dataforseo')) {
        return new Response(JSON.stringify(BUDGET), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
      }
      return new Response(JSON.stringify({ detail: 'not found' }), {
        status: 404,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useCostsStore()
    await store.refreshBudgets(1)
    expect(store.budgets.length).toBe(1)
    expect(calls).toBeGreaterThan(1)
  })

  it('upsertBudget() inserts at top when new', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ data: BUDGET, project_id: 1 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useCostsStore()
    store.budgets = [] as never
    await store.upsertBudget(1, {
      kind: 'dataforseo',
      monthly_budget_usd: 50,
      alert_threshold_pct: 80,
      qps: 1,
    })
    expect(store.budgets.length).toBe(1)
  })

  it('refreshHistory() pulls 12 months in parallel', async () => {
    let calls = 0
    globalThis.fetch = vi.fn(async () => {
      calls += 1
      return new Response(JSON.stringify(ZERO_COST), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useCostsStore()
    await store.refreshHistory(1, 12)
    expect(calls).toBe(12)
    expect(store.history.length).toBe(12)
  })
})
