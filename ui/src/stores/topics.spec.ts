import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useTopicsStore } from './topics'

const ORIG_FETCH = globalThis.fetch

const TOPIC_QUEUED = {
  id: 1,
  project_id: 1,
  cluster_id: null,
  title: 'How to evaluate a sportsbook',
  primary_kw: 'best sportsbook',
  secondary_kws: null,
  intent: 'informational' as const,
  status: 'queued' as const,
  priority: 50,
  source: 'manual' as const,
  created_at: '2026-05-01T00:00:00Z',
  updated_at: '2026-05-01T00:00:00Z',
}

describe('topics store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('refresh() builds the URL with sort and filter params', async () => {
    let captured = ''
    globalThis.fetch = vi.fn(async (input) => {
      captured = String(input)
      return new Response(
        JSON.stringify({ items: [TOPIC_QUEUED], next_cursor: null, total_estimate: 1 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useTopicsStore()
    store.setFilter('status', 'queued' as never)
    store.setSort('-priority')
    await store.refresh(1)
    expect(captured).toContain('/api/v1/projects/1/topics')
    expect(captured).toContain('status=queued')
    expect(captured).toContain('sort=-priority')
  })

  it('does not expose topic mutation methods to the UI store', () => {
    const store = useTopicsStore()
    const exposed = store as unknown as Record<string, unknown>
    expect(exposed.create).toBeUndefined()
    expect(exposed.approve).toBeUndefined()
    expect(exposed.reject).toBeUndefined()
    expect(exposed.bulkUpdateStatus).toBeUndefined()
  })

  it('filteredItems narrows by intent client-side', () => {
    const store = useTopicsStore()
    store.items = [
      { ...TOPIC_QUEUED, intent: 'informational' },
      { ...TOPIC_QUEUED, id: 9, intent: 'commercial' },
    ] as never
    store.setFilter('intent', 'commercial' as never)
    expect(store.filteredItems.length).toBe(1)
    expect(store.filteredItems[0].id).toBe(9)
  })

  it('records error state when refresh fails', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify({ detail: 'nope' }), {
        status: 500,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useTopicsStore()
    await store.refresh(1)
    expect(store.error).not.toBeNull()
  })
})
