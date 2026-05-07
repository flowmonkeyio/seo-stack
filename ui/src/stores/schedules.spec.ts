import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useSchedulesStore } from './schedules'

const ORIG_FETCH = globalThis.fetch

const JOB = {
  id: 1,
  project_id: 1,
  kind: 'gsc-pull',
  cron_expr: '0 2 * * *',
  next_run_at: '2026-05-06T02:00:00Z',
  last_run_at: '2026-05-05T02:00:00Z',
  last_run_status: 'success',
  enabled: true,
}

describe('schedules store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('refresh() loads the list', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify([JOB]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useSchedulesStore()
    await store.refresh(1)
    expect(store.items.length).toBe(1)
  })

  it('toggle() flips enabled and replaces locally', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ data: { ...JOB, enabled: false }, project_id: 1 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useSchedulesStore()
    store.items = [JOB] as never
    await store.toggle(1, 1, false)
    expect(store.items[0].enabled).toBe(false)
  })

  it('set() upserts by kind', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          data: { ...JOB, kind: 'drift-check', cron_expr: '0 3 * * 0' },
          project_id: 1,
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useSchedulesStore()
    store.items = [JOB] as never
    await store.set(1, { kind: 'drift-check', cron_expr: '0 3 * * 0', enabled: true })
    expect(store.items.find((s) => s.kind === 'drift-check')).toBeDefined()
    expect(store.items.find((s) => s.kind === 'gsc-pull')).toBeDefined()
  })
})
