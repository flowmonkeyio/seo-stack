import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useRunsStore } from './runs'

const ORIG_FETCH = globalThis.fetch

const RUN_RUNNING = {
  id: 1,
  project_id: 1,
  kind: 'skill-run' as const,
  parent_run_id: null,
  procedure_slug: null,
  client_session_id: null,
  started_at: '2026-05-05T00:00:00Z',
  ended_at: null,
  status: 'running' as const,
  error: null,
  heartbeat_at: '2026-05-05T00:00:30Z',
  last_step: 'outline',
  last_step_at: '2026-05-05T00:00:25Z',
  metadata_json: { foo: 'bar' },
}

describe('runs store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('refresh() includes kind/status filters', async () => {
    let captured = ''
    globalThis.fetch = vi.fn(async (input) => {
      captured = String(input)
      return new Response(
        JSON.stringify({ items: [RUN_RUNNING], next_cursor: null, total_estimate: 1 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useRunsStore()
    store.setFilter('kind', 'skill-run' as never)
    store.setFilter('status', 'running' as never)
    await store.refresh(1)
    expect(captured).toContain('/api/v1/projects/1/runs')
    expect(captured).toContain('kind=skill-run')
    expect(captured).toContain('status=running')
  })

  it('abort() updates the local row', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          data: { ...RUN_RUNNING, status: 'aborted', ended_at: '2026-05-05T01:00:00Z' },
          project_id: 1,
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useRunsStore()
    store.items = [RUN_RUNNING] as never
    await store.abort(1, true)
    expect(store.items[0].status).toBe('aborted')
  })

  it('children() caches by parent run id', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify([{ ...RUN_RUNNING, id: 99, parent_run_id: 1 }]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useRunsStore()
    const rows = await store.children(1)
    expect(rows.length).toBe(1)
    expect(store.childrenByParent.get(1)?.length).toBe(1)
  })

  it('client-side date filter narrows by since', () => {
    const store = useRunsStore()
    const older = { ...RUN_RUNNING, id: 1, started_at: '2026-04-01T00:00:00Z' }
    const newer = { ...RUN_RUNNING, id: 2, started_at: '2026-05-05T00:00:00Z' }
    store.items = [older, newer] as never
    store.setFilter('since', '2026-05-01T00:00:00Z')
    expect(store.filteredItems.length).toBe(1)
    expect(store.filteredItems[0].id).toBe(2)
  })
})
