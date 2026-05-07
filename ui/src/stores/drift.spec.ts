import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useDriftStore } from './drift'

const ORIG_FETCH = globalThis.fetch

const BASELINE = {
  id: 1,
  article_id: 10,
  baseline_md: '# Baseline',
  baseline_at: '2026-05-01T00:00:00Z',
  current_score: 0.42,
}

describe('drift store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('refreshAcrossArticles fans out + tags rows with parent_article_id', async () => {
    globalThis.fetch = vi.fn(async (input) => {
      const url = String(input)
      const m = url.match(/articles\/(\d+)\/drift/)
      const articleId = m ? Number.parseInt(m[1], 10) : 0
      return new Response(JSON.stringify([{ ...BASELINE, article_id: articleId }]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useDriftStore()
    await store.refreshAcrossArticles([10, 20])
    expect(store.items.length).toBe(2)
    expect(store.items.find((r) => r.parent_article_id === 10)).toBeDefined()
    expect(store.items.find((r) => r.parent_article_id === 20)).toBeDefined()
  })

  it('snapshot() prepends a row to items', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ data: BASELINE, project_id: 1 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useDriftStore()
    await store.snapshot(10, { baseline_md: '# Hello' })
    expect(store.items.length).toBe(1)
    expect(store.items[0].parent_article_id).toBe(10)
  })

  it('threshold filter narrows by current_score', () => {
    const store = useDriftStore()
    store.items = [
      { ...BASELINE, parent_article_id: 10, current_score: 0.8, id: 1 },
      { ...BASELINE, parent_article_id: 11, current_score: 0.2, id: 2 },
    ] as never
    store.setThreshold(0.5)
    expect(store.filteredItems.length).toBe(1)
    expect(store.filteredItems[0].id).toBe(1)
  })

  it('null current_score still passes the threshold filter (pre-M6 watcher)', () => {
    const store = useDriftStore()
    store.items = [
      { ...BASELINE, parent_article_id: 10, current_score: null, id: 1 },
    ] as never
    store.setThreshold(0.5)
    expect(store.filteredItems.length).toBe(1)
  })
})
