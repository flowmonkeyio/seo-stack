import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useClustersStore } from './clusters'

const ORIG_FETCH = globalThis.fetch

const PILLAR = {
  id: 1,
  project_id: 1,
  name: 'How-to guides',
  type: 'pillar' as const,
  parent_id: null,
  created_at: '2026-05-01T00:00:00Z',
}

const SPOKE = {
  id: 2,
  project_id: 1,
  name: 'Sportsbook how-to',
  type: 'spoke' as const,
  parent_id: 1,
  created_at: '2026-05-02T00:00:00Z',
}

const ORPHAN = {
  id: 3,
  project_id: 1,
  name: 'Orphan',
  type: 'spoke' as const,
  parent_id: 99,
  created_at: '2026-05-03T00:00:00Z',
}

describe('clusters store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('refresh() loads the first page and ingests rows', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ items: [PILLAR, SPOKE], next_cursor: null, total_estimate: 2 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useClustersStore()
    await store.refresh(1)
    expect(store.items.length).toBe(2)
    expect(store.totalEstimate).toBe(2)
    expect(store.nextCursor).toBeNull()
    expect(store.currentProjectId).toBe(1)
  })

  it('tree getter nests spokes under their pillar parent', () => {
    const store = useClustersStore()
    store.items = [PILLAR, SPOKE] as never
    const tree = store.tree
    expect(tree.length).toBe(1)
    expect(tree[0].id).toBe(1)
    expect(tree[0].children.length).toBe(1)
    expect(tree[0].children[0].id).toBe(2)
  })

  it('tree getter surfaces orphan rows at the top level', () => {
    const store = useClustersStore()
    store.items = [PILLAR, ORPHAN] as never
    const tree = store.tree
    expect(tree.length).toBe(2)
    const ids = tree.map((n) => n.id).sort()
    expect(ids).toEqual([1, 3])
  })

  it('create() POSTs and prepends the row', async () => {
    const created = { ...PILLAR, id: 5, name: 'New pillar' }
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify({ data: created, project_id: 1 }), {
        status: 201,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useClustersStore()
    const row = await store.create(1, { name: 'New pillar', type: 'pillar' } as never)
    expect(row.name).toBe('New pillar')
    expect(store.items.find((c) => c.id === 5)).toBeTruthy()
  })

  it('records error state when refresh fails', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify({ detail: 'nope' }), {
        status: 500,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useClustersStore()
    await store.refresh(1)
    expect(store.error).not.toBeNull()
    expect(store.items.length).toBe(0)
  })
})
