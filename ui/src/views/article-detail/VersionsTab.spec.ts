import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import VersionsTab from './VersionsTab.vue'

const ORIG_FETCH = globalThis.fetch

const VERSION = {
  id: 10,
  article_id: 1,
  version: 1,
  brief_json: null,
  outline_md: null,
  draft_md: null,
  edited_md: 'foo\nbar',
  frontmatter_json: null,
  published_url: null,
  published_at: null,
  voice_id_used: null,
  eeat_criteria_version_used: null,
  created_at: '2026-05-01T00:00:00Z',
  refreshed_at: null,
  refresh_reason: null,
}

describe('VersionsTab', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders the versions list', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ items: [VERSION], next_cursor: null, total_estimate: 1 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const w = mount(VersionsTab, { props: { articleId: 1 } })
    await new Promise((r) => setTimeout(r, 30))
    expect(w.text()).toContain('v1 — compare to current')
  })

  it('shows the "no versions" empty state', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ items: [], next_cursor: null, total_estimate: 0 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const w = mount(VersionsTab, { props: { articleId: 1 } })
    await new Promise((r) => setTimeout(r, 30))
    expect(w.text()).toContain('No versions yet')
  })
})
