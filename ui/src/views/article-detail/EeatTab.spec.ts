import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import EeatTab from './EeatTab.vue'

const ORIG_FETCH = globalThis.fetch

const FAILED_VETO_REPORT = {
  score: {
    dimension_scores: {
      C: 60,
      O: 80,
      R: 50,
      E: 70,
      Exp: 90,
      Ept: 80,
      A: 70,
      T: 70,
    },
    system_scores: { GEO: 65, SEO: 78 },
    coverage: { C: true, O: true, R: true, E: true, Exp: true, Ept: true, A: true, T: true },
    vetoes_failed: ['T04'],
    total_evaluations: 12,
  },
  evaluations: [
    {
      id: 1,
      article_id: 1,
      criterion_id: 5,
      run_id: 99,
      verdict: 'fail',
      notes: 'Missing veto item',
      evaluated_at: '2026-05-01T00:00:00Z',
    },
  ],
}

const CORE_CRITERIA = [
  {
    id: 5,
    project_id: 1,
    code: 'T04',
    category: 'T',
    description: 'YMYL trust',
    text: 'YMYL trust',
    weight: 100,
    required: true,
    active: true,
    tier: 'core',
    version: 1,
  },
]

describe('EeatTab (article-detail)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('shows the veto banner when vetoes_failed is non-empty', async () => {
    let firstCall = true
    globalThis.fetch = vi.fn(async () => {
      const body = firstCall ? FAILED_VETO_REPORT : CORE_CRITERIA
      firstCall = false
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch
    const w = mount(EeatTab, { props: { articleId: 1, projectId: 1 } })
    await new Promise((r) => setTimeout(r, 30))
    expect(w.find('[data-testid="cs-eeat-veto-banner"]').exists()).toBe(true)
    expect(w.text()).toContain('Cannot ship — veto item failed')
    expect(w.text()).toContain('T04')
    const verdict = w.find('[data-testid="cs-eeat-verdict"]')
    expect(verdict.exists()).toBe(true)
    expect(verdict.text()).toContain('BLOCK')
  })

  it('shows "unscored" when no evaluations exist', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          score: {
            dimension_scores: {},
            system_scores: { GEO: 0, SEO: 0 },
            coverage: {},
            vetoes_failed: [],
            total_evaluations: 0,
          },
          evaluations: [],
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const w = mount(EeatTab, { props: { articleId: 1, projectId: 1 } })
    await new Promise((r) => setTimeout(r, 30))
    const verdict = w.find('[data-testid="cs-eeat-verdict"]')
    expect(verdict.text()).toContain('unscored')
  })
})
