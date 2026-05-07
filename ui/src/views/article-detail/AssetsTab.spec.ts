import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import AssetsTab from './AssetsTab.vue'

const ORIG_FETCH = globalThis.fetch

const ASSET = {
  id: 1,
  article_id: 1,
  kind: 'hero',
  prompt: 'A nice hero',
  url: 'https://images.example.com/hero.png',
  alt_text: 'A hero',
  width: 1200,
  height: 630,
  position: null,
  created_at: '2026-05-01T00:00:00Z',
}

describe('AssetsTab', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders the asset gallery cards', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify([ASSET]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const w = mount(AssetsTab, { props: { articleId: 1 } })
    await new Promise((r) => setTimeout(r, 30))
    expect(w.text()).toContain('Assets')
    expect(w.text()).toContain('https://images.example.com/hero.png')
    expect(w.text()).toContain('alt: A hero')
    expect(w.text()).toContain('1200×630')
  })

  it('shows the "no assets" empty state', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const w = mount(AssetsTab, { props: { articleId: 1 } })
    await new Promise((r) => setTimeout(r, 30))
    expect(w.text()).toContain('No assets yet')
  })
})
