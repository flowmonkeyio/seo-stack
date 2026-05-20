import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useArticlesStore } from './articles'

const ORIG_FETCH = globalThis.fetch

const ARTICLE_BRIEFING = {
  id: 1,
  project_id: 1,
  topic_id: 1,
  author_id: null,
  reviewer_author_id: null,
  canonical_target_id: null,
  owner_run_id: null,
  slug: 'evaluate-a-sportsbook',
  title: 'How to evaluate a sportsbook',
  status: 'briefing' as const,
  brief_json: null,
  outline_md: null,
  draft_md: null,
  edited_md: null,
  voice_id_used: null,
  eeat_criteria_version_used: null,
  last_refreshed_at: null,
  last_evaluated_for_refresh_at: null,
  last_link_audit_at: null,
  version: 1,
  current_step: null,
  last_completed_step: null,
  step_started_at: null,
  step_etag: 'etag-1',
  lock_token: null,
  created_at: '2026-05-01T00:00:00Z',
  updated_at: '2026-05-01T00:00:00Z',
}

describe('articles store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('refresh() loads the article list', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({ items: [ARTICLE_BRIEFING], next_cursor: null, total_estimate: 1 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useArticlesStore()
    await store.refresh(1)
    expect(store.items.length).toBe(1)
    expect(store.items[0].title).toBe('How to evaluate a sportsbook')
  })

  it('does not expose article mutation methods to the UI store', () => {
    const store = useArticlesStore()
    const exposed = store as unknown as Record<string, unknown>
    expect(exposed.setBrief).toBeUndefined()
    expect(exposed.setDraft).toBeUndefined()
    expect(exposed.setOutline).toBeUndefined()
    expect(exposed.markPublished).toBeUndefined()
  })

  it('listVersions() unwraps the page envelope', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          items: [
            { id: 10, article_id: 1, version: 1, brief_json: null, outline_md: null, draft_md: null, edited_md: null, frontmatter_json: null, published_url: null, published_at: null, voice_id_used: null, eeat_criteria_version_used: null, created_at: '2026-05-01T00:00:00Z', refreshed_at: null, refresh_reason: null },
          ],
          next_cursor: null,
          total_estimate: 1,
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useArticlesStore()
    const versions = await store.listVersions(1)
    expect(versions.length).toBe(1)
    expect(versions[0].id).toBe(10)
  })

  it('filteredItems sorts by selected key', () => {
    const store = useArticlesStore()
    store.items = [
      { ...ARTICLE_BRIEFING, id: 1, title: 'Z', created_at: '2026-05-01T00:00:00Z' },
      { ...ARTICLE_BRIEFING, id: 2, title: 'A', created_at: '2026-05-02T00:00:00Z' },
    ] as never
    store.setSort('title')
    expect(store.filteredItems.map((a) => a.id)).toEqual([2, 1])
    store.setSort('-created_at')
    expect(store.filteredItems.map((a) => a.id)).toEqual([2, 1])
  })
})
