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

  it('does not expose interlink mutation methods to the UI store', () => {
    const store = useInterlinksStore()
    const exposed = store as unknown as Record<string, unknown>
    expect(exposed.apply).toBeUndefined()
    expect(exposed.dismiss).toBeUndefined()
    expect(exposed.bulkApply).toBeUndefined()
    expect(exposed.repair).toBeUndefined()
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
