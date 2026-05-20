// Topics store — read-only list with filters and client-side intent narrowing.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch } from '@/lib/client'
import type { components } from '@/api'

export type Topic = components['schemas']['TopicOut']
export type TopicStatus = components['schemas']['TopicStatus']
export type TopicSource = components['schemas']['TopicSource']
export type TopicIntent = components['schemas']['TopicIntent']
type TopicsPage = components['schemas']['PageResponse_TopicOut_']

const DEFAULT_LIMIT = 50

export interface TopicFilters {
  status: TopicStatus | null
  source: TopicSource | null
  intent: TopicIntent | null
  cluster_id: number | null
}

export type TopicSortKey = 'priority' | '-priority' | 'id' | '-id'

export const useTopicsStore = defineStore('topics', () => {
  const items = ref<Topic[]>([])
  const totalEstimate = ref<number>(0)
  const nextCursor = ref<number | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentProjectId = ref<number | null>(null)
  const filters = ref<TopicFilters>({
    status: null,
    source: null,
    intent: null,
    cluster_id: null,
  })
  const sort = ref<TopicSortKey>('priority')

  function _buildParams(after?: number | null): URLSearchParams {
    const params = new URLSearchParams({ limit: String(DEFAULT_LIMIT) })
    if (filters.value.status) params.set('status', filters.value.status)
    if (filters.value.source) params.set('source', filters.value.source)
    if (filters.value.cluster_id !== null) params.set('cluster_id', String(filters.value.cluster_id))
    params.set('sort', sort.value)
    if (after !== undefined && after !== null) params.set('after', String(after))
    return params
  }

  function _ingestPage(page: TopicsPage, append: boolean): void {
    items.value = append ? [...items.value, ...page.items] : [...page.items]
    nextCursor.value = page.next_cursor ?? null
    totalEstimate.value = page.total_estimate ?? items.value.length
  }

  async function refresh(projectId: number): Promise<void> {
    currentProjectId.value = projectId
    loading.value = true
    error.value = null
    try {
      const page = await apiFetch<TopicsPage>(
        `/api/v1/projects/${projectId}/topics?${_buildParams().toString()}`,
      )
      _ingestPage(page, false)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load topics'
    } finally {
      loading.value = false
    }
  }

  async function loadMore(projectId: number): Promise<void> {
    if (nextCursor.value === null || loading.value) return
    loading.value = true
    try {
      const page = await apiFetch<TopicsPage>(
        `/api/v1/projects/${projectId}/topics?${_buildParams(nextCursor.value).toString()}`,
      )
      _ingestPage(page, true)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load more topics'
    } finally {
      loading.value = false
    }
  }

  function setFilter<K extends keyof TopicFilters>(key: K, value: TopicFilters[K]): void {
    filters.value = { ...filters.value, [key]: value }
  }

  function setSort(key: TopicSortKey): void {
    sort.value = key
  }

  function getById(id: number): Topic | null {
    return items.value.find((topic) => topic.id === id) ?? null
  }

  const filteredItems = computed<Topic[]>(() => {
    if (filters.value.intent === null) return items.value
    return items.value.filter((topic) => topic.intent === filters.value.intent)
  })

  function reset(): void {
    items.value = []
    totalEstimate.value = 0
    nextCursor.value = null
    error.value = null
    currentProjectId.value = null
    filters.value = { status: null, source: null, intent: null, cluster_id: null }
    sort.value = 'priority'
  }

  return {
    items,
    totalEstimate,
    nextCursor,
    loading,
    error,
    currentProjectId,
    filters,
    sort,
    filteredItems,
    refresh,
    loadMore,
    setFilter,
    setSort,
    getById,
    reset,
  }
})
