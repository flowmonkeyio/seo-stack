import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

import ProjectSwitcher from './ProjectSwitcher.vue'
import { useProjectsStore } from '@/stores/projects'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/projects', component: { template: '<div/>' } },
      { path: '/projects/:id/overview', component: { template: '<div/>' } },
    ],
  })
}

const sample = [
  {
    id: 1,
    name: 'Alpha',
    slug: 'alpha',
    domain: 'alpha.test',
    niche: 'a',
    locale: 'en-US',
    is_active: true,
    schedule_json: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Beta',
    slug: 'beta',
    domain: 'beta.test',
    niche: 'b',
    locale: 'en-US',
    is_active: false,
    schedule_json: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
]

describe('ProjectSwitcher', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows the active project name in the collapsed button', () => {
    const projects = useProjectsStore()
    projects.items = sample as never
    projects.activeProjectId = 1
    const router = makeRouter()
    const w = mount(ProjectSwitcher, {
      global: { plugins: [router] },
    })
    expect(w.find('button').text()).toContain('Alpha')
  })

  it('opens the dropdown on click and lists every project', async () => {
    const projects = useProjectsStore()
    projects.items = sample as never
    projects.activeProjectId = 1
    const router = makeRouter()
    const w = mount(ProjectSwitcher, {
      global: { plugins: [router] },
    })
    await w.find('button').trigger('click')
    const options = w.findAll('[role="option"]')
    expect(options.length).toBe(2)
    expect(options[0].text()).toContain('Alpha')
    expect(options[1].text()).toContain('Beta')
  })

  it('calls activate + navigates when a non-active project is picked', async () => {
    const projects = useProjectsStore()
    projects.items = sample as never
    projects.activeProjectId = 1
    const router = makeRouter()
    await router.push('/projects')
    const activateSpy = vi.spyOn(projects, 'activate').mockResolvedValue(sample[1] as never)
    const pushSpy = vi.spyOn(router, 'push')
    const w = mount(ProjectSwitcher, {
      global: { plugins: [router] },
    })
    await w.find('button').trigger('click')
    const options = w.findAll('[role="option"]')
    await options[1].trigger('click')
    await flushPromises()
    expect(activateSpy).toHaveBeenCalledWith(2)
    expect(pushSpy).toHaveBeenCalledWith('/projects/2/overview')
  })
})
