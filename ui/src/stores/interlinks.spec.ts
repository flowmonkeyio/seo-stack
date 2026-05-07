import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useInterlinksStore } from './interlinks'

const ORIG_FETCH = globalThis.fetch

const LINK_SUGGESTED = {
  id: 1,
  project_id: 1,
  from_article_id: 10,
  to_article_id: 20,
  anchor_text: 'best sportsbook',
  position: 5,
  status: 'suggested' as const,
  created_at: '2026-05-01T00:00:00Z',
  updated_at: '2026-05-01T00:00:00Z',
}

const LINK_APPLIED = { ...LINK_SUGGESTED, id: 2, status: 'applied' as const }

describe('interlinks store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('refresh() sends status filter on the wire', async () => {
    let captured = ''
    globalThis.fetch = vi.fn(async (input) => {
      captured = String(input)
      return new Response(
        JSON.stringify({ items: [LINK_SUGGESTED], next_cursor: null, total_estimate: 1 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useInterlinksStore()
    store.setFilter('status', 'suggested' as never)
    await store.refresh(1)
    expect(captured).toContain('/api/v1/projects/1/interlinks')
    expect(captured).toContain('status=suggested')
    expect(store.items.length).toBe(1)
  })

  it('apply() flips status in items', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ data: { ...LINK_SUGGESTED, status: 'applied' }, project_id: 1 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useInterlinksStore()
    store.items = [LINK_SUGGESTED] as never
    await store.apply(1, 1)
    expect(store.items[0].status).toBe('applied')
  })

  it('bulkApply() merges all returned rows', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          data: [
            { ...LINK_SUGGESTED, status: 'applied' },
            { ...LINK_APPLIED, status: 'applied' },
          ],
          project_id: 1,
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useInterlinksStore()
    store.items = [LINK_SUGGESTED, LINK_APPLIED] as never
    await store.bulkApply(1, [1, 2])
    expect(store.items.find((l) => l.id === 1)?.status).toBe('applied')
    expect(store.items.find((l) => l.id === 2)?.status).toBe('applied')
  })

  it('repair() POSTs the article id', async () => {
    let body: string | null = null
    globalThis.fetch = vi.fn(async (_input, init) => {
      body = String(init?.body ?? '')
      return new Response(
        JSON.stringify({ data: [], project_id: 1 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useInterlinksStore()
    await store.repair(1, 42)
    expect(body).toContain('"article_id":42')
  })

  it('records error state when refresh fails', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify({ detail: 'nope' }), {
        status: 500,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useInterlinksStore()
    await store.refresh(1)
    expect(store.error).not.toBeNull()
  })
})
