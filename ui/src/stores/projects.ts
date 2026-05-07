// Projects store — list + active project.
//
// Wires to:
// - `GET /api/v1/projects` (cursor-paginated)
// - `POST /api/v1/projects` (create)
// - `POST /api/v1/projects/{id}/activate` (single-active invariant E1)
//
// Pagination follows PLAN.md L531-538: `?limit=&after=` returning
// `{items, next_cursor, total_estimate}`.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, apiWrite } from '@/lib/client'
import type { components } from '@/api'

export type Project = components['schemas']['ProjectOut']
type ProjectCreateRequest = components['schemas']['ProjectCreateRequest']
type ProjectUpdateRequest = components['schemas']['ProjectUpdateRequest']
type ProjectsPage = components['schemas']['PageResponse_ProjectOut_']

const DEFAULT_LIMIT = 50

export const useProjectsStore = defineStore('projects', () => {
  const items = ref<Project[]>([])
  const totalEstimate = ref<number>(0)
  const nextCursor = ref<number | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const activeProjectId = ref<number | null>(null)

  const activeProject = computed<Project | null>(() => {
    if (activeProjectId.value === null) return null
    return items.value.find((p) => p.id === activeProjectId.value) ?? null
  })

  function _ingestPage(page: ProjectsPage, append: boolean): void {
    if (append) {
      items.value = [...items.value, ...page.items]
    } else {
      items.value = [...page.items]
    }
    nextCursor.value = page.next_cursor ?? null
    totalEstimate.value = page.total_estimate ?? items.value.length
    // Keep activeProjectId aligned with the freshly-loaded items if possible.
    const explicit = items.value.find((p) => p.is_active)
    if (explicit) activeProjectId.value = explicit.id
  }

  async function refresh(activeOnly = false): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams({ limit: String(DEFAULT_LIMIT) })
      if (activeOnly) params.set('active_only', 'true')
      const page = await apiFetch<ProjectsPage>(`/api/v1/projects?${params.toString()}`)
      _ingestPage(page, false)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load projects'
    } finally {
      loading.value = false
    }
  }

  async function loadMore(): Promise<void> {
    if (nextCursor.value === null || loading.value) return
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams({
        limit: String(DEFAULT_LIMIT),
        after: String(nextCursor.value),
      })
      const page = await apiFetch<ProjectsPage>(`/api/v1/projects?${params.toString()}`)
      _ingestPage(page, true)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load more projects'
    } finally {
      loading.value = false
    }
  }

  async function create(body: ProjectCreateRequest): Promise<Project> {
    const row = await apiWrite<Project>('/api/v1/projects', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    items.value = [row, ...items.value]
    totalEstimate.value = totalEstimate.value + 1
    return row
  }

  async function update(id: number, patch: ProjectUpdateRequest): Promise<Project> {
    const row = await apiWrite<Project>(`/api/v1/projects/${id}`, {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(patch),
    })
    const idx = items.value.findIndex((p) => p.id === id)
    if (idx >= 0) items.value.splice(idx, 1, row)
    return row
  }

  async function activate(id: number): Promise<Project> {
    const row = await apiWrite<Project>(`/api/v1/projects/${id}/activate`, {
      method: 'POST',
    })
    activeProjectId.value = id
    // Refresh list to pick up other rows' is_active=false flips.
    await refresh()
    return row
  }

  function setActiveProjectId(id: number | null): void {
    activeProjectId.value = id
  }

  function getById(id: number): Project | null {
    return items.value.find((p) => p.id === id) ?? null
  }

  return {
    items,
    totalEstimate,
    nextCursor,
    loading,
    error,
    activeProjectId,
    activeProject,
    refresh,
    loadMore,
    create,
    update,
    activate,
    setActiveProjectId,
    getById,
  }
})
