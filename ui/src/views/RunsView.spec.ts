// Smoke tests for RunsView (list + filter pills).

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import RunsView from './RunsView.vue'

const ORIG_FETCH = globalThis.fetch

function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/projects/:id/runs', name: 'project-runs', component: RunsView },
      { path: '/projects/:id/runs/:run_id', name: 'project-run-detail', component: RunsView },
    ],
  })
  void router.push('/projects/1/runs')
  return router
}

describe('RunsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders heading + status pill bar + kind/status filters', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ items: [], next_cursor: null, total_estimate: 0 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const router = mountView()
    await router.isReady()
    const w = mount(RunsView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 0))
    expect(w.text()).toContain('Runs')
    expect(w.text()).toContain('Running')
    expect(w.text()).toContain('Success')
    expect(w.text()).toContain('Failed')
    expect(w.text()).toContain('Aborted')
    expect(w.text()).toContain('Kind')
  })
})
