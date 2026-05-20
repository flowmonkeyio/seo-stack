// Smoke tests for the guided vendor integrations tab.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import IntegrationsTab from './IntegrationsTab.vue'

const ORIG_FETCH = globalThis.fetch
const GSC_INFO = {
  redirect_uri: 'http://127.0.0.1:5180/api/v1/integrations/gsc/oauth/callback',
  configured: true,
  missing: [],
  hint: null,
}

function mountTab(path = '/projects/1/integrations') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/projects/:id/integrations',
        name: 'project-detail-integrations',
        component: IntegrationsTab,
      },
    ],
  })
  void router.push(path)
  return router
}

describe('IntegrationsTab', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders vendor cards instead of raw kind-first setup', async () => {
    globalThis.fetch = vi.fn(async (input) => {
      if (String(input).endsWith('/api/v1/integrations/gsc/oauth/info')) {
        return new Response(JSON.stringify(GSC_INFO), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
      }
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch

    const router = mountTab()
    await router.isReady()
    const w = mount(IntegrationsTab, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 0))

    expect(w.text()).toContain('Vendor connections')
    expect(w.text()).toContain('DataForSEO')
    expect(w.text()).toContain('OpenAI Images')
    expect(w.text()).toContain('WordPress')
    expect(w.text()).toContain('Ghost')
    expect(w.text()).toContain(GSC_INFO.redirect_uri)
    expect(w.text()).not.toContain('New integration')
    expect(w.text()).not.toContain('Kind is required')
    expect(w.findAll('button').some((button) => button.text() === 'Connect')).toBe(false)
    expect(w.findAll('button').some((button) => button.text() === 'Test connection')).toBe(false)
  })

  it('highlights agent-required integrations from the URL', async () => {
    globalThis.fetch = vi.fn(async (input) => {
      if (String(input).endsWith('/api/v1/integrations/gsc/oauth/info')) {
        return new Response(JSON.stringify(GSC_INFO), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
      }
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch

    const router = mountTab('/projects/1/integrations?required=dataforseo,openai-images')
    await router.isReady()
    const w = mount(IntegrationsTab, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 0))

    expect(w.text()).toContain('Needed for the current agent flow')
    expect(w.text()).toContain('DataForSEO / Not connected')
    expect(w.text()).toContain('OpenAI Images / Not connected')
  })

  it('renders GSC OAuth missing-env setup state', async () => {
    globalThis.fetch = vi.fn(async (input) => {
      if (String(input).endsWith('/api/v1/integrations/gsc/oauth/info')) {
        return new Response(
          JSON.stringify({
            ...GSC_INFO,
            configured: false,
            missing: ['GSC_OAUTH_CLIENT_ID', 'GSC_OAUTH_CLIENT_SECRET'],
            hint: 'Set GSC OAuth env vars',
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        )
      }
      return new Response(
        JSON.stringify([
          {
            id: 44,
            project_id: 1,
            kind: 'gsc',
            config_json: { redirect_uri: GSC_INFO.redirect_uri },
            expires_at: null,
            created_at: '2026-05-01T00:00:00Z',
            updated_at: '2026-05-01T00:00:00Z',
          },
        ]),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch

    const router = mountTab()
    await router.isReady()
    const w = mount(IntegrationsTab, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 0))

    const gscCard = w
      .findAll('article')
      .find((card) => card.text().includes('Google Search Console'))
    expect(gscCard).toBeDefined()
    expect(gscCard!.text()).toContain('Needs env')
    expect(gscCard!.text()).toContain('Missing GSC_OAUTH_CLIENT_ID, GSC_OAUTH_CLIENT_SECRET')
    const testButton = gscCard!.findAll('button').find((button) => button.text() === 'Test connection')
    expect(testButton).toBeUndefined()
  })

  it('does not expose WordPress credential forms', async () => {
    const bodies: unknown[] = []
    globalThis.fetch = vi.fn(async (input, init) => {
      const url = String(input)
      if (url.endsWith('/api/v1/integrations/gsc/oauth/info')) {
        return new Response(JSON.stringify(GSC_INFO), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
      }
      if (url.endsWith('/api/v1/projects/1/integrations') && init?.method === 'POST') {
        bodies.push(JSON.parse(String(init.body)))
        return new Response(
          JSON.stringify({
            data: {
              id: 10,
              project_id: 1,
              kind: 'wordpress',
              config_json: { wp_url: 'https://wp.example', username: 'editor' },
              expires_at: null,
              created_at: '2026-05-01T00:00:00Z',
              updated_at: '2026-05-01T00:00:00Z',
            },
          }),
          { status: 201, headers: { 'content-type': 'application/json' } },
        )
      }
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }) as typeof fetch

    const router = mountTab()
    await router.isReady()
    const w = mount(IntegrationsTab, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 0))

    const wordpressCard = w.findAll('article').find((card) => card.text().includes('WordPress'))
    expect(wordpressCard).toBeDefined()
    const connect = wordpressCard!.findAll('button').find((button) => button.text() === 'Connect')
    expect(connect).toBeUndefined()
    expect(w.findAll('input')).toHaveLength(0)
    expect(bodies).toHaveLength(0)
  })
})
