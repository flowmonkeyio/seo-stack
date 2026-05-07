import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { ProcedureNotImplementedError, useProceduresStore } from './procedures'

const ORIG_FETCH = globalThis.fetch

const PROC = {
  slug: 'bootstrap',
  name: 'Bootstrap a project',
  version: '1.0.0',
  description: 'First-run setup',
}

describe('procedures store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('refresh() lists procedures', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify([PROC]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useProceduresStore()
    await store.refresh()
    expect(store.items.length).toBe(1)
    expect(store.items[0].slug).toBe('bootstrap')
  })

  it('runProcedure() raises ProcedureNotImplementedError on 501', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify({ detail: 'M7' }), {
        status: 501,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useProceduresStore()
    await expect(store.runProcedure('bootstrap', {})).rejects.toBeInstanceOf(
      ProcedureNotImplementedError,
    )
  })

  it('getRun() caches the response', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          run: {
            id: 1,
            project_id: 1,
            kind: 'procedure',
            parent_run_id: null,
            procedure_slug: 'bootstrap',
            client_session_id: null,
            started_at: '2026-05-05T00:00:00Z',
            ended_at: null,
            status: 'running',
            error: null,
            heartbeat_at: null,
            last_step: null,
            last_step_at: null,
            metadata_json: null,
          },
          steps: [],
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useProceduresStore()
    const r = await store.getRun(1)
    expect(r.run.id).toBe(1)
    expect(store.currentRun?.run.id).toBe(1)
  })
})
