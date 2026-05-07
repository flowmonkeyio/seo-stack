import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useGscStore } from './gsc'

const ORIG_FETCH = globalThis.fetch

const ROW_A = {
  id: 1,
  project_id: 1,
  article_id: null,
  captured_at: '2026-05-05T00:00:00Z',
  query: 'best sportsbook',
  query_normalized: 'best sportsbook',
  page: 'https://example.com/best-sportsbook',
  country: 'us',
  device: 'desktop',
  dimensions_hash: 'abc',
  impressions: 100,
  clicks: 5,
  ctr: 0.05,
  avg_position: 3.4,
}

const ROW_B = {
  ...ROW_A,
  id: 2,
  captured_at: '2026-05-05T00:00:00Z',
  impressions: 200,
  clicks: 10,
  ctr: 0.05,
  avg_position: 4.2,
}

const REDIRECT = {
  id: 1,
  project_id: 1,
  from_url: '/old-url',
  to_article_id: null,
  kind: '301' as const,
  created_at: '2026-05-01T00:00:00Z',
}

describe('gsc store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('refresh() sends since/until on the wire', async () => {
    let captured = ''
    globalThis.fetch = vi.fn(async (input) => {
      captured = String(input)
      return new Response(JSON.stringify([ROW_A]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useGscStore()
    await store.refresh(1)
    expect(captured).toContain('/api/v1/projects/1/gsc')
    expect(captured).toContain('since=')
    expect(captured).toContain('until=')
    expect(store.rawRows.length).toBe(1)
  })

  it('dailyRollup aggregates raw rows by captured_at::date', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify([ROW_A, ROW_B]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useGscStore()
    await store.refresh(1)
    expect(store.dailyRollup.length).toBe(1)
    expect(store.dailyRollup[0].clicks).toBe(15)
    expect(store.dailyRollup[0].impressions).toBe(300)
  })

  it('createRedirect inserts at the top of items', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ data: REDIRECT, project_id: 1 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useGscStore()
    store.redirects = [] as never
    await store.createRedirect(1, { from_url: '/old', kind: '301' as never })
    expect(store.redirects.length).toBe(1)
  })

  it('rollupDay sends the day query param', async () => {
    let captured = ''
    globalThis.fetch = vi.fn(async (input) => {
      captured = String(input)
      return new Response(
        JSON.stringify({ data: { ingested: 0, deduped: 0 }, project_id: 1 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useGscStore()
    await store.rollupDay(1, '2026-05-05')
    expect(captured).toContain('day=2026-05-05')
  })
})
