// Topics store — list / get / create / bulk_create / approve / reject /
// bulk_update_status. Cursor pagination + filters.
//
// Wires to:
// - `GET /api/v1/projects/{id}/topics` (cursor-paginated; filters: status, source, cluster_id; sort: priority|id)
// - `POST /api/v1/projects/{id}/topics` (single create)
// - `POST /api/v1/projects/{id}/topics/bulk` (N rows)
// - `POST /api/v1/projects/{id}/topics/bulk-update-status` (N ids → new status)
// - `POST /api/v1/topics/{id}/approve` / `/reject`
// - `PATCH /api/v1/topics/{id}` (UI-permissive; status transitions go through validate)
//
// Filter behaviour: every change to filters resets the cursor and reloads.
// The store keeps the full result set in `items` so the DataTable can
// drive selection without re-fetching.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, apiWrite } from '@/lib/client'
import type { components } from '@/api'

export type Topic = components['schemas']['TopicOut']
export type TopicStatus = components['schemas']['TopicStatus']
export type TopicSource = components['schemas']['TopicSource']
export type TopicIntent = components['schemas']['TopicIntent']
type TopicCreateRequest = components['schemas']['TopicCreateRequest']
type TopicUpdateRequest = components['schemas']['TopicUpdateRequest']
type BulkTopicCreateRequest = components['schemas']['BulkTopicCreateRequest']
type BulkUpdateStatusRequest = components['schemas']['BulkUpdateStatusRequest']
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
    // intent is filtered client-side because the REST endpoint doesn't
    // accept it (audit M1). The store still records it so the UI can
    // narrow by intent without losing the existing rows.
    if (filters.value.cluster_id !== null)
      params.set('cluster_id', String(filters.value.cluster_id))
    params.set('sort', sort.value)
    if (after !== undefined && after !== null) params.set('after', String(after))
    return params
  }

  function _ingestPage(page: TopicsPage, append: boolean): void {
    if (append) {
      items.value = [...items.value, ...page.items]
    } else {
      items.value = [...page.items]
    }
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

  async function create(projectId: number, body: TopicCreateRequest): Promise<Topic> {
    const row = await apiWrite<Topic>(`/api/v1/projects/${projectId}/topics`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    // Insert at top of the in-memory list — the priority sort may move
    // it lower on the next refresh; that's expected.
    items.value = [row, ...items.value]
    totalEstimate.value = totalEstimate.value + 1
    return row
  }

  async function bulkCreate(
    projectId: number,
    body: BulkTopicCreateRequest,
  ): Promise<Topic[]> {
    const rows = await apiWrite<Topic[]>(`/api/v1/projects/${projectId}/topics/bulk`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    items.value = [...rows, ...items.value]
    totalEstimate.value = totalEstimate.value + rows.length
    return rows
  }

  async function approve(topicId: number): Promise<Topic> {
    const row = await apiWrite<Topic>(`/api/v1/topics/${topicId}/approve`, { method: 'POST' })
    _replaceLocal(row)
    return row
  }

  async function reject(topicId: number): Promise<Topic> {
    const row = await apiWrite<Topic>(`/api/v1/topics/${topicId}/reject`, { method: 'POST' })
    _replaceLocal(row)
    return row
  }

  async function update(topicId: number, patch: TopicUpdateRequest): Promise<Topic> {
    const row = await apiWrite<Topic>(`/api/v1/topics/${topicId}`, {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(patch),
    })
    _replaceLocal(row)
    return row
  }

  async function bulkUpdateStatus(
    projectId: number,
    body: BulkUpdateStatusRequest,
  ): Promise<Topic[]> {
    const rows = await apiWrite<Topic[]>(
      `/api/v1/projects/${projectId}/topics/bulk-update-status`,
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      },
    )
    for (const row of rows) _replaceLocal(row)
    return rows
  }

  function _replaceLocal(row: Topic): void {
    const idx = items.value.findIndex((t) => t.id === row.id)
    if (idx >= 0) items.value.splice(idx, 1, row)
  }

  function getById(id: number): Topic | null {
    return items.value.find((t) => t.id === id) ?? null
  }

  /**
   * Client-side filtered view of `items` honouring the `intent` filter
   * (which the REST endpoint doesn't accept server-side).
   */
  const filteredItems = computed<Topic[]>(() => {
    if (filters.value.intent === null) return items.value
    return items.value.filter((t) => t.intent === filters.value.intent)
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
    create,
    bulkCreate,
    approve,
    reject,
    update,
    bulkUpdateStatus,
    getById,
    reset,
  }
})
