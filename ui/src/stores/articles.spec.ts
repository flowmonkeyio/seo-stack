import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useArticlesStore, ArticleEtagError } from './articles'

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

  it('setBrief() POSTs and updates the local cache with fresh etag', async () => {
    let capturedBody: string | null = null
    const advanced = { ...ARTICLE_BRIEFING, status: 'outlined' as const, step_etag: 'etag-2' }
    globalThis.fetch = vi.fn(async (_url, init) => {
      capturedBody = String(init?.body)
      return new Response(JSON.stringify({ data: advanced, project_id: 1 }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useArticlesStore()
    store.items = [ARTICLE_BRIEFING] as never
    const row = await store.setBrief(1, { expected_etag: 'etag-1', brief_json: { foo: 'bar' } })
    expect(row.status).toBe('outlined')
    expect(row.step_etag).toBe('etag-2')
    expect(capturedBody).toContain('"expected_etag":"etag-1"')
    // Local cache picks up the fresh row.
    expect(store.items[0].status).toBe('outlined')
    expect(store.currentDetail?.step_etag).toBe('etag-2')
  })

  it('setDraft() with append=true puts ?append=true in the URL', async () => {
    let capturedUrl = ''
    globalThis.fetch = vi.fn(async (url) => {
      capturedUrl = String(url)
      return new Response(JSON.stringify({ data: ARTICLE_BRIEFING, project_id: 1 }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const store = useArticlesStore()
    await store.setDraft(1, { expected_etag: 'etag-1', draft_md: 'hello' }, true)
    expect(capturedUrl).toContain('/draft?append=true')
  })

  it('mutations surface ArticleEtagError on 409 with structured payload', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          detail: {
            data: { current_etag: 'fresh-etag', current_updated_at: '2026-05-02T00:00:00Z' },
          },
        }),
        { status: 409, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const store = useArticlesStore()
    let caught: unknown = null
    try {
      await store.setOutline(1, { expected_etag: 'stale', outline_md: '# hi' })
    } catch (err) {
      caught = err
    }
    expect(caught).toBeInstanceOf(ArticleEtagError)
    if (caught instanceof ArticleEtagError) {
      expect(caught.current_etag).toBe('fresh-etag')
      expect(caught.current_updated_at).toBe('2026-05-02T00:00:00Z')
    }
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
