// Smoke tests for ProceduresView.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import ProceduresView from './ProceduresView.vue'

const ORIG_FETCH = globalThis.fetch

function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/projects/:id/procedures',
        name: 'project-procedures',
        component: ProceduresView,
      },
    ],
  })
  void router.push('/projects/1/procedures')
  return router
}

describe('ProceduresView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders heading + tab bar with Available / Recent Runs', async () => {
    globalThis.fetch = vi.fn(async (input) => {
      const url = String(input)
      if (url.endsWith('/api/v1/procedures')) {
        return new Response(
          JSON.stringify([
            {
              slug: 'bootstrap',
              name: 'Bootstrap a project',
              version: '1.0.0',
              description: 'First-run setup',
            },
          ]),
          { status: 200, headers: { 'content-type': 'application/json' } },
        )
      }
      return new Response(
        JSON.stringify({ items: [], next_cursor: null, total_estimate: 0 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const router = mountView()
    await router.isReady()
    const w = mount(ProceduresView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 10))
    expect(w.text()).toContain('Procedures')
    expect(w.text()).toContain('Available')
    expect(w.text()).toContain('Recent Runs')
    // procedure list table has the slug
    expect(w.text()).toContain('bootstrap')
  })
})
