// Tests for ProceduresView.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import ProceduresView from './ProceduresView.vue'

const ORIG_FETCH = globalThis.fetch

function mountView(projectId = '1') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/projects/:id/procedures',
        name: 'project-procedures',
        component: ProceduresView,
      },
    ],
  })
  void router.push(`/projects/${projectId}/procedures`)
  return router
}

describe('ProceduresView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders heading + tab bar with Available / Recent Runs', async () => {
    globalThis.fetch = vi.fn(async (input) => {
      const url = String(input)
      if (url.endsWith('/api/v1/procedures')) {
        return new Response(
          JSON.stringify([
            {
              slug: 'bootstrap',
              name: 'Bootstrap a project',
              version: '1.0.0',
              description: 'First-run setup',
            },
          ]),
          { status: 200, headers: { 'content-type': 'application/json' } },
        )
      }
      return new Response(
        JSON.stringify({ items: [], next_cursor: null, total_estimate: 0 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch
    const router = mountView()
    await router.isReady()
    const w = mount(ProceduresView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 10))
    expect(w.text()).toContain('Procedures')
    expect(w.text()).toContain('Available')
    expect(w.text()).toContain('Recent Runs')
    // procedure list table has the slug
    expect(w.text()).toContain('bootstrap')
  })

  it('submits procedure runs with project_id and args', async () => {
    const bodies: unknown[] = []
    globalThis.fetch = vi.fn(async (input, init) => {
      const url = String(input)
      if (url.endsWith('/api/v1/procedures')) {
        return new Response(
          JSON.stringify([
            {
              slug: '04-topic-to-published',
              name: 'Topic to published',
              version: '1.0.0',
              description: 'Publish one approved topic',
            },
          ]),
          { status: 200, headers: { 'content-type': 'application/json' } },
        )
      }
      if (url.endsWith('/api/v1/procedures/04-topic-to-published/run')) {
        bodies.push(JSON.parse(String(init?.body)))
        return new Response(
          JSON.stringify({
            run_id: 11,
            run_token: 'token',
            status_url: '/api/v1/procedures/runs/11',
            slug: '04-topic-to-published',
            project_id: 7,
            started: true,
            parent_run_id: null,
          }),
          { status: 202, headers: { 'content-type': 'application/json' } },
        )
      }
      return new Response(
        JSON.stringify({ items: [], next_cursor: null, total_estimate: 0 }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      )
    }) as typeof fetch

    const router = mountView('7')
    await router.isReady()
    const w = mount(ProceduresView, { global: { plugins: [router] } })
    await flushPromises()

    await w.find('button[aria-label="Run procedure 04-topic-to-published"]').trigger('click')
    expect(w.text()).not.toContain('M7')
    await w.find('textarea').setValue('{"topic_id":42}')
    const submit = w.findAll('button').find((button) => button.text() === 'Run procedure')
    expect(submit).toBeTruthy()
    await submit!.trigger('click')
    await flushPromises()

    expect(bodies).toEqual([{ project_id: 7, args: { topic_id: 42 } }])
  })
})
