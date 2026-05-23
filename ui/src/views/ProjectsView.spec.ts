import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import ProjectsView from './ProjectsView.vue'

const ORIG_FETCH = globalThis.fetch

describe('ProjectsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('creates the first project and routes to setup status', async () => {
    const postedBodies: unknown[] = []
    globalThis.fetch = vi.fn(async (input, init) => {
      const url = String(input)
      if (init?.body) postedBodies.push(JSON.parse(String(init.body)))
      if (url.startsWith('/api/v1/projects?')) {
        return json({ items: [], next_cursor: null, total_estimate: 0 })
      }
      if (url === '/api/v1/projects' && init?.method === 'POST') {
        return json({
          data: {
            id: 7,
            slug: 'acme',
            name: 'Acme',
            domain: 'example.com',
            niche: null,
            locale: 'en-US',
            is_active: true,
            schedule_json: null,
            created_at: '2026-05-22T00:00:00Z',
            updated_at: '2026-05-22T00:00:00Z',
          },
          run_id: null,
          project_id: 7,
        })
      }
      return json({})
    }) as typeof fetch

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/projects', component: ProjectsView },
        { path: '/projects/:id/setup', component: { template: '<div>setup</div>' } },
      ],
    })
    await router.push('/projects')
    await router.isReady()

    const wrapper = mount(ProjectsView, { global: { plugins: [router] } })

    await vi.waitFor(() => expect(wrapper.text()).toContain('No projects yet'))
    await clickButton(wrapper, 'New project')
    await wrapper.find('input[placeholder="Acme"]').setValue('Acme')
    expect((wrapper.find('input[placeholder="acme"]').element as HTMLInputElement).value).toBe(
      'acme',
    )
    await wrapper.find('input[placeholder="acme"]').setValue('acme-growth')
    await wrapper.find('input[placeholder="example.com"]').setValue('example.com')
    await clickButton(wrapper, 'Create')
    await flushPromises()

    expect(postedBodies).toContainEqual({
      name: 'Acme',
      slug: 'acme-growth',
      domain: 'example.com',
      niche: null,
      locale: 'en-US',
      schedule_json: null,
    })
    expect(router.currentRoute.value.fullPath).toBe('/projects/7/setup')
  })
})

async function clickButton(wrapper: ReturnType<typeof mount>, label: string): Promise<void> {
  const button = wrapper.findAll('button').find((candidate) => candidate.text().trim() === label)
  expect(button, `${label} button`).toBeDefined()
  await button?.trigger('click')
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  })
}
