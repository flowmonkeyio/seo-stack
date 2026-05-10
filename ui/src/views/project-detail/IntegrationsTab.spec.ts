// Smoke tests for the guided vendor integrations tab.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import IntegrationsTab from './IntegrationsTab.vue'

const ORIG_FETCH = globalThis.fetch

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
    globalThis.fetch = vi.fn(async () => {
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
    expect(w.text()).toContain('Connect Google')
    expect(w.text()).not.toContain('New integration')
    expect(w.text()).not.toContain('Kind is required')
  })

  it('highlights agent-required integrations from the URL', async () => {
    globalThis.fetch = vi.fn(async () => {
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
    expect(w.text()).toContain('DataForSEO · Not connected')
    expect(w.text()).toContain('OpenAI Images · Not connected')
  })
})
