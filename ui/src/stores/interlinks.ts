// Interlinks store — read-only link inventory with filters.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch } from '@/lib/client'
import type { components } from '@/api'

export type InternalLink = components['schemas']['InternalLinkOut']
export type InternalLinkStatus = components['schemas']['InternalLinkStatus']
type InternalLinksPage = components['schemas']['PageResponse_InternalLinkOut_']

const DEFAULT_LIMIT = 50

export interface InterlinkFilters {
  status: InternalLinkStatus | null
  from_article_id: number | null
  to_article_id: number | null
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
    items.value = append ? [...items.value, ...page.items] : [...page.items]
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

  const filteredItems = computed<InternalLink[]>(() => {
    let arr = items.value
    const minId = Math.floor(filters.value.score_min * 1000)
    if (minId > 0) arr = arr.filter((link) => link.id >= minId)
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
    reset,
  }
})
