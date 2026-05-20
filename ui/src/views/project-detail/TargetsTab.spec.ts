// Smoke tests for the provider-shaped publish targets dialog.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import TargetsTab from './TargetsTab.vue'

const ORIG_FETCH = globalThis.fetch

function mountTab() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/projects/:id/targets',
        name: 'project-detail-targets',
        component: TargetsTab,
      },
    ],
  })
  void router.push('/projects/1/targets')
  return router
}

describe('TargetsTab', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders target readiness without create controls', async () => {
    const bodies: unknown[] = []
    globalThis.fetch = vi.fn(async (_input, init) => {
      if (init?.method === 'POST') bodies.push(JSON.parse(String(init.body)))
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch

    const router = mountTab()
    await router.isReady()
    const w = mount(TargetsTab, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 0))

    expect(w.text()).toContain('No publish targets')
    expect(w.findAll('button').some((button) => button.text() === 'New target')).toBe(false)
    expect(w.findAll('button').some((button) => button.text() === 'Create target')).toBe(false)
    expect(bodies).toHaveLength(0)
  })

  it('renders advanced file-target config without edit controls', async () => {
    const bodies: unknown[] = []
    globalThis.fetch = vi.fn(async (input, init) => {
      const url = String(input)
      if (url.endsWith('/api/v1/projects/1/publish-targets/7') && init?.method === 'PATCH') {
        bodies.push(JSON.parse(String(init.body)))
        return new Response(
          JSON.stringify({
            data: {
              id: 7,
              project_id: 1,
              kind: 'nuxt-content',
              config_json: JSON.parse(String(init.body)).config_json,
              is_primary: true,
              is_active: true,
            },
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        )
      }
      return new Response(
        JSON.stringify([
          {
            id: 7,
            project_id: 1,
            kind: 'nuxt-content',
            config_json: {
              repo_path: '/Users/me/site',
              content_subdir: 'content/articles',
              public_subdir: 'public/images',
              branch: 'main',
              git_remote: 'origin',
              public_url_pattern: 'https://example.com/articles/{slug}',
            },
            is_primary: true,
            is_active: true,
          },
        ]),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch

    const router = mountTab()
    await router.isReady()
    const w = mount(TargetsTab, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 0))

    expect(w.text()).toContain('/Users/me/site')
    expect(w.text()).toContain('Procedure ready')
    expect(w.findAll('button').some((button) => button.text() === 'Edit target')).toBe(false)
    expect(w.findAll('button').some((button) => button.text() === 'Save changes')).toBe(false)
    expect(bodies).toHaveLength(0)
  })

  it('does not label unsupported active targets as ready', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(
        JSON.stringify([
          {
            id: 31,
            project_id: 1,
            kind: 'wordpress',
            config_json: { wp_url: 'https://wp.example' },
            is_primary: true,
            is_active: true,
          },
        ]),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch

    const router = mountTab()
    await router.isReady()
    const w = mount(TargetsTab, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 0))

    expect(w.text()).toContain('Primary active')
    expect(w.text()).toContain('Unsupported by procedure')
    const targetCard = w.find('article')
    expect(targetCard.text()).not.toContain('Actions Ready')
  })
})
