// Smoke tests for GscView.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import GscView from './GscView.vue'

const ORIG_FETCH = globalThis.fetch

function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/projects/:id/gsc', name: 'project-gsc', component: GscView }],
  })
  void router.push('/projects/1/gsc')
  return router
}

describe('GscView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders title + tab bar with three tabs', async () => {
    globalThis.fetch = vi.fn(async (input) => {
      const url = String(input)
      if (url.includes('/redirects')) {
        return new Response(
          JSON.stringify({ items: [], next_cursor: null, total_estimate: 0 }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        )
      }
      if (url.includes('/articles')) {
        return new Response(
          JSON.stringify({ items: [], next_cursor: null, total_estimate: 0 }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        )
      }
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const router = mountView()
    await router.isReady()
    const w = mount(GscView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 0))
    expect(w.text()).toContain('GSC Metrics')
    expect(w.text()).toContain('Raw')
    expect(w.text()).toContain('Daily Rollup')
    expect(w.text()).toContain('Redirects')
  })
})
