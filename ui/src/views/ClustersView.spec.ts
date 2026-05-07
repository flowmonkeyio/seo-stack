// Rendering smoke + happy-path tests for ClustersView.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import ClustersView from './ClustersView.vue'
import { useClustersStore } from '@/stores/clusters'

const ORIG_FETCH = globalThis.fetch

function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/projects/:id/clusters', name: 'project-clusters', component: ClustersView }],
  })
  void router.push('/projects/1/clusters')
  return router
}

describe('ClustersView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders the heading + create button', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ items: [], next_cursor: null, total_estimate: 0 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const router = mountView()
    await router.isReady()
    const w = mount(ClustersView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 0))
    expect(w.text()).toContain('Clusters')
    expect(w.text()).toContain('No clusters yet')
  })

  it('renders the tree with pillar + spoke', async () => {
    const PILLAR = {
      id: 1,
      project_id: 1,
      name: 'How-tos',
      type: 'pillar',
      parent_id: null,
      created_at: '2026-05-01T00:00:00Z',
    }
    const SPOKE = {
      id: 2,
      project_id: 1,
      name: 'Sportsbook how-to',
      type: 'spoke',
      parent_id: 1,
      created_at: '2026-05-02T00:00:00Z',
    }
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ items: [PILLAR, SPOKE], next_cursor: null, total_estimate: 2 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const router = mountView()
    await router.isReady()
    const w = mount(ClustersView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 10))
    expect(w.text()).toContain('How-tos')
    expect(w.text()).toContain('Sportsbook how-to')
    const store = useClustersStore()
    expect(store.tree.length).toBe(1)
    expect(store.tree[0].children.length).toBe(1)
  })
})
