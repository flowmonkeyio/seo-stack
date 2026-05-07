// Smoke + happy-path tests for TopicsView.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import TopicsView from './TopicsView.vue'

const ORIG_FETCH = globalThis.fetch

function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/projects/:id/topics', name: 'project-topics', component: TopicsView }],
  })
  void router.push('/projects/1/topics')
  return router
}

const TOPIC = {
  id: 1,
  project_id: 1,
  cluster_id: null,
  title: 'Best sportsbook',
  primary_kw: 'sportsbook',
  secondary_kws: null,
  intent: 'informational',
  status: 'queued',
  priority: 50,
  source: 'manual',
  created_at: '2026-05-01T00:00:00Z',
  updated_at: '2026-05-01T00:00:00Z',
}

describe('TopicsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders the heading + status pill bar + new-topic button', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ items: [], next_cursor: null, total_estimate: 0 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const router = mountView()
    await router.isReady()
    const w = mount(TopicsView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 0))
    expect(w.text()).toContain('Topics')
    expect(w.text()).toContain('Queued')
    expect(w.find('button[role="tab"]').exists()).toBe(true)
  })

  it('renders the topics table when items load', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ items: [TOPIC], next_cursor: null, total_estimate: 1 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const router = mountView()
    await router.isReady()
    const w = mount(TopicsView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 10))
    expect(w.text()).toContain('Best sportsbook')
  })
})
