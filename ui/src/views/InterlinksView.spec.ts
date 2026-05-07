// Smoke tests for InterlinksView.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import InterlinksView from './InterlinksView.vue'

const ORIG_FETCH = globalThis.fetch

function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/projects/:id/interlinks', name: 'project-interlinks', component: InterlinksView },
    ],
  })
  void router.push('/projects/1/interlinks')
  return router
}

describe('InterlinksView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders heading + status pills + suggest button', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ items: [], next_cursor: null, total_estimate: 0 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const router = mountView()
    await router.isReady()
    const w = mount(InterlinksView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 0))
    expect(w.text()).toContain('Interlinks')
    expect(w.text()).toContain('Suggest')
    expect(w.text()).toContain('Suggested')
    expect(w.text()).toContain('Applied')
    expect(w.text()).toContain('Dismissed')
    expect(w.text()).toContain('Broken')
  })

  it('shows empty state when no rows', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ items: [], next_cursor: null, total_estimate: 0 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const router = mountView()
    await router.isReady()
    const w = mount(InterlinksView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 10))
    expect(w.text()).toContain('No interlinks yet')
  })
})
