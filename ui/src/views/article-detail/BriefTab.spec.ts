import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import BriefTab from './BriefTab.vue'
import { useArticlesStore } from '@/stores/articles'

const ORIG_FETCH = globalThis.fetch

function articleWithBrief(brief: Record<string, unknown> | null) {
  return {
    id: 1,
    project_id: 1,
    topic_id: null,
    author_id: null,
    reviewer_author_id: null,
    canonical_target_id: null,
    owner_run_id: null,
    slug: 'a',
    title: 'A',
    status: 'briefing',
    brief_json: brief,
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
}

describe('BriefTab', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders empty state when brief_json is empty', () => {
    const store = useArticlesStore()
    store.currentDetail = articleWithBrief({}) as never
    const w = mount(BriefTab, { props: { articleId: 1 } })
    expect(w.text()).toContain('Brief not yet written')
  })

  it('renders the keys when brief is populated', () => {
    const store = useArticlesStore()
    store.currentDetail = articleWithBrief({
      voice_id: 1,
      primary_kw: 'sportsbook',
      target_word_count: 1800,
    }) as never
    const w = mount(BriefTab, { props: { articleId: 1 } })
    expect(w.text()).toContain('voice_id')
    expect(w.text()).toContain('primary_kw')
    expect(w.text()).toContain('sportsbook')
  })

  it('switches to JSON edit mode on Edit click', async () => {
    const store = useArticlesStore()
    store.currentDetail = articleWithBrief({}) as never
    const w = mount(BriefTab, { props: { articleId: 1 } })
    await w.findAll('button').find((b) => b.text() === 'Edit')!.trigger('click')
    expect(w.text()).toContain('Brief JSON')
    expect(w.find('textarea').exists()).toBe(true)
  })
})
