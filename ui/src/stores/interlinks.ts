// Interlinks store — list / suggest / apply / dismiss / repair / bulk_apply.
//
// Wires to:
// - `GET    /api/v1/projects/{id}/interlinks` (cursor-paginated;
//   server-side filters: status, from_article_id, to_article_id)
// - `POST   /api/v1/projects/{id}/interlinks` (single create — for tests)
// - `POST   /api/v1/projects/{id}/interlinks/suggest` (bulk suggestion)
// - `POST   /api/v1/projects/{id}/interlinks/{link_id}/apply`
// - `POST   /api/v1/projects/{id}/interlinks/{link_id}/dismiss`
// - `POST   /api/v1/projects/{id}/interlinks/repair`
// - `POST   /api/v1/projects/{id}/interlinks/bulk-apply`
//
// Score is a UI-only convenience: the wire row doesn't carry a score field
// (the suggester ranks server-side; we display position as a stand-in).
// A later milestone may extend the wire shape; for now we sort by id.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, apiWrite } from '@/lib/client'
import type { components } from '@/api'

export type InternalLink = components['schemas']['InternalLinkOut']
export type InternalLinkStatus = components['schemas']['InternalLinkStatus']
type InternalLinksPage = components['schemas']['PageResponse_InternalLinkOut_']
type InterlinkSuggestion = components['schemas']['InterlinkSuggestion']
type SuggestRequest = components['schemas']['SuggestRequest']
type RepairRequest = components['schemas']['RepairRequest']
type BulkApplyRequest = components['schemas']['BulkApplyRequest']
type CreateInterlinkRequest = components['schemas']['CreateInterlinkRequest']

const DEFAULT_LIMIT = 50

export interface InterlinkFilters {
  status: InternalLinkStatus | null
  from_article_id: number | null
  to_article_id: number | null
  /** Lower bound on (uniformly distributed) row id used as a stable
   *  client-side sort heuristic when the server doesn't expose score. */
  score_min: number
}

export type InterlinkSortKey = 'id' | '-id' | 'created_at' | '-created_at'

export const useInterlinksStore = defineStore('interlinks', () => {
  const items = ref<InternalLink[]>([])
  const totalEstimate = ref<number>(0)
  const nextCursor = ref<number | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentProjectId = ref<number | null>(null)
  const filters = ref<InterlinkFilters>({
    status: null,
    from_article_id: null,
    to_article_id: null,
    score_min: 0,
  })
  const sort = ref<InterlinkSortKey>('-id')

  function _buildParams(after?: number | null): URLSearchParams {
    const params = new URLSearchParams({ limit: String(DEFAULT_LIMIT) })
    if (filters.value.status) params.set('status', filters.value.status)
    if (filters.value.from_article_id !== null) {
      params.set('from_article_id', String(filters.value.from_article_id))
    }
    if (filters.value.to_article_id !== null) {
      params.set('to_article_id', String(filters.value.to_article_id))
    }
    if (after !== undefined && after !== null) params.set('after', String(after))
    return params
  }

  function _ingestPage(page: InternalLinksPage, append: boolean): void {
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
      const page = await apiFetch<InternalLinksPage>(
        `/api/v1/projects/${projectId}/interlinks?${_buildParams().toString()}`,
      )
      _ingestPage(page, false)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load interlinks'
    } finally {
      loading.value = false
    }
  }

  async function loadMore(projectId: number): Promise<void> {
    if (nextCursor.value === null || loading.value) return
    loading.value = true
    try {
      const page = await apiFetch<InternalLinksPage>(
        `/api/v1/projects/${projectId}/interlinks?${_buildParams(nextCursor.value).toString()}`,
      )
      _ingestPage(page, true)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load more interlinks'
    } finally {
      loading.value = false
    }
  }

  function setFilter<K extends keyof InterlinkFilters>(key: K, value: InterlinkFilters[K]): void {
    filters.value = { ...filters.value, [key]: value }
  }

  function setSort(key: InterlinkSortKey): void {
    sort.value = key
  }

  async function suggest(
    projectId: number,
    suggestions: InterlinkSuggestion[],
  ): Promise<InternalLink[]> {
    const body: SuggestRequest = { suggestions }
    const rows = await apiWrite<InternalLink[]>(
      `/api/v1/projects/${projectId}/interlinks/suggest`,
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      },
    )
    items.value = [...rows, ...items.value]
    totalEstimate.value = totalEstimate.value + rows.length
    return rows
  }

  async function create(
    projectId: number,
    body: CreateInterlinkRequest,
  ): Promise<InternalLink[]> {
    const rows = await apiWrite<InternalLink[]>(`/api/v1/projects/${projectId}/interlinks`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    items.value = [...rows, ...items.value]
    totalEstimate.value = totalEstimate.value + rows.length
    return rows
  }

  async function apply(projectId: number, linkId: number): Promise<InternalLink> {
    const row = await apiWrite<InternalLink>(
      `/api/v1/projects/${projectId}/interlinks/${linkId}/apply`,
      { method: 'POST' },
    )
    _replaceLocal(row)
    return row
  }

  async function dismiss(projectId: number, linkId: number): Promise<InternalLink> {
    const row = await apiWrite<InternalLink>(
      `/api/v1/projects/${projectId}/interlinks/${linkId}/dismiss`,
      { method: 'POST' },
    )
    _replaceLocal(row)
    return row
  }

  async function bulkApply(projectId: number, ids: number[]): Promise<InternalLink[]> {
    const body: BulkApplyRequest = { ids }
    const rows = await apiWrite<InternalLink[]>(
      `/api/v1/projects/${projectId}/interlinks/bulk-apply`,
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      },
    )
    for (const row of rows) _replaceLocal(row)
    return rows
  }

  async function repair(projectId: number, articleId: number): Promise<InternalLink[]> {
    const body: RepairRequest = { article_id: articleId }
    const rows = await apiWrite<InternalLink[]>(
      `/api/v1/projects/${projectId}/interlinks/repair`,
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      },
    )
    for (const row of rows) _replaceLocal(row)
    return rows
  }

  function _replaceLocal(row: InternalLink): void {
    const idx = items.value.findIndex((l) => l.id === row.id)
    if (idx >= 0) items.value.splice(idx, 1, row)
  }

  /**
   * Client-side sort+filter view honouring `score_min` (a UI heuristic —
   * the wire shape doesn't expose a score column; we treat row id as a
   * proxy so the slider still gives users a way to narrow the result set).
   */
  const filteredItems = computed<InternalLink[]>(() => {
    let arr = items.value
    const minId = Math.floor(filters.value.score_min * 1000)
    if (minId > 0) arr = arr.filter((l) => l.id >= minId)
    const key = sort.value
    const dir = key.startsWith('-') ? -1 : 1
    const field = key.replace(/^-/, '') as 'id' | 'created_at'
    return [...arr].sort((a, b) => {
      const av = a[field] ?? ''
      const bv = b[field] ?? ''
      if (av < bv) return -1 * dir
      if (av > bv) return 1 * dir
      return 0
    })
  })

  function reset(): void {
    items.value = []
    totalEstimate.value = 0
    nextCursor.value = null
    error.value = null
    currentProjectId.value = null
    filters.value = {
      status: null,
      from_article_id: null,
      to_article_id: null,
      score_min: 0,
    }
    sort.value = '-id'
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
    suggest,
    create,
    apply,
    dismiss,
    bulkApply,
    repair,
    reset,
  }
})
