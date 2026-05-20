// Projects store — read-only list + active project marker from server state.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch } from '@/lib/client'
import type { components } from '@/api'

export type Project = components['schemas']['ProjectOut']
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
    return items.value.find((project) => project.id === activeProjectId.value) ?? null
  })

  function _ingestPage(page: ProjectsPage, append: boolean): void {
    items.value = append ? [...items.value, ...page.items] : [...page.items]
    nextCursor.value = page.next_cursor ?? null
    totalEstimate.value = page.total_estimate ?? items.value.length
    const explicit = items.value.find((project) => project.is_active)
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

  function setActiveProjectId(id: number | null): void {
    activeProjectId.value = id
  }

  function getById(id: number): Project | null {
    return items.value.find((project) => project.id === id) ?? null
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
    setActiveProjectId,
    getById,
  }
})
