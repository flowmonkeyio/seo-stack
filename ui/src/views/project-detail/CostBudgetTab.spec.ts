// Smoke tests for CostBudgetTab.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import CostBudgetTab from './CostBudgetTab.vue'

const ORIG_FETCH = globalThis.fetch

function mountTab() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/projects/:id/cost-budget',
        name: 'project-detail-cost-budget',
        component: CostBudgetTab,
      },
    ],
  })
  void router.push('/projects/1/cost-budget')
  return router
}

describe('CostBudgetTab', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders the no-spend badge when total_usd=0', async () => {
    globalThis.fetch = vi.fn(async (input) => {
      const url = String(input)
      if (url.includes('/cost')) {
        return new Response(
          JSON.stringify({
            by_integration: { dataforseo: 0 },
            total_usd: 0,
            period_start: '2026-05-01T00:00:00Z',
            period_end: '2026-06-01T00:00:00Z',
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        )
      }
      return new Response(JSON.stringify({ detail: 'not found' }), {
        status: 404,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const router = mountTab()
    await router.isReady()
    const w = mount(CostBudgetTab, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 50))
    expect(w.text()).toContain('Current month')
    expect(w.text()).toContain('No spend recorded yet')
    expect(w.text()).toContain('Budget caps')
  })
})
