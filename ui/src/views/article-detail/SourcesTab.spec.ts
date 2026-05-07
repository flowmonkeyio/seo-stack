import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import SourcesTab from './SourcesTab.vue'

const ORIG_FETCH = globalThis.fetch

const SOURCE = {
  id: 1,
  article_id: 1,
  url: 'https://example.com/source',
  title: 'Example Source',
  snippet: 'A snippet',
  fetched_at: '2026-05-01T00:00:00Z',
  used: true,
}

describe('SourcesTab', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders the sources table with rows', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify([SOURCE]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const w = mount(SourcesTab, { props: { articleId: 1 } })
    await new Promise((r) => setTimeout(r, 30))
    expect(w.text()).toContain('Research sources')
    expect(w.text()).toContain('Example Source')
    expect(w.text()).toContain('https://example.com/source')
  })
})
