// Articles store — read-only list / detail / refresh-due / versions.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, formatApiError } from '@/lib/client'
import type { components } from '@/api'

export type Article = components['schemas']['ArticleOut']
export type ArticleStatus = components['schemas']['ArticleStatus']
export type ArticleVersion = components['schemas']['ArticleVersionOut']
type ArticlesPage = components['schemas']['PageResponse_ArticleOut_']
type VersionsPage = components['schemas']['PageResponse_ArticleVersionOut_']

const DEFAULT_LIMIT = 50

export interface ArticleFilters {
  status: ArticleStatus | null
  topic_id: number | null
  cluster_id: number | null
  author_id: number | null
}

export type ArticleSortKey = 'created_at' | '-created_at' | 'updated_at' | '-updated_at' | 'title'

export const useArticlesStore = defineStore('articles', () => {
  const items = ref<Article[]>([])
  const totalEstimate = ref<number>(0)
  const nextCursor = ref<number | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentProjectId = ref<number | null>(null)
  const currentDetail = ref<Article | null>(null)
  const filters = ref<ArticleFilters>({
    status: null,
    topic_id: null,
    cluster_id: null,
    author_id: null,
  })
  const sort = ref<ArticleSortKey>('-created_at')

  function _buildParams(after?: number | null, refreshDue = false): URLSearchParams {
    const params = new URLSearchParams({ limit: String(DEFAULT_LIMIT) })
    if (filters.value.status && !refreshDue) params.set('status', filters.value.status)
    if (filters.value.topic_id !== null) params.set('topic_id', String(filters.value.topic_id))
    if (after !== undefined && after !== null) params.set('after', String(after))
    return params
  }

  function _ingestPage(page: ArticlesPage, append: boolean): void {
    items.value = append ? [...items.value, ...page.items] : [...page.items]
    nextCursor.value = page.next_cursor ?? null
    totalEstimate.value = page.total_estimate ?? items.value.length
  }

  async function refresh(projectId: number): Promise<void> {
    currentProjectId.value = projectId
    loading.value = true
    error.value = null
    try {
      const page = await apiFetch<ArticlesPage>(
        `/api/v1/projects/${projectId}/articles?${_buildParams().toString()}`,
      )
      _ingestPage(page, false)
    } catch (err) {
      error.value = formatApiError(err, 'failed to load articles')
    } finally {
      loading.value = false
    }
  }

  async function loadMore(projectId: number): Promise<void> {
    if (nextCursor.value === null || loading.value) return
    loading.value = true
    try {
      const page = await apiFetch<ArticlesPage>(
        `/api/v1/projects/${projectId}/articles?${_buildParams(nextCursor.value).toString()}`,
      )
      _ingestPage(page, true)
    } catch (err) {
      error.value = formatApiError(err, 'failed to load more articles')
    } finally {
      loading.value = false
    }
  }

  async function listDueForRefresh(projectId: number): Promise<Article[]> {
    const params = new URLSearchParams({ limit: String(DEFAULT_LIMIT) })
    const page = await apiFetch<ArticlesPage>(
      `/api/v1/projects/${projectId}/articles/refresh-due?${params.toString()}`,
    )
    return page.items
  }

  async function get(articleId: number): Promise<Article> {
    const row = await apiFetch<Article>(`/api/v1/articles/${articleId}`)
    currentDetail.value = row
    _replaceLocal(row)
    return row
  }

  async function listVersions(articleId: number): Promise<ArticleVersion[]> {
    const params = new URLSearchParams({ limit: '200' })
    const page = await apiFetch<VersionsPage>(
      `/api/v1/articles/${articleId}/versions?${params.toString()}`,
    )
    return page.items
  }

  function setFilter<K extends keyof ArticleFilters>(key: K, value: ArticleFilters[K]): void {
    filters.value = { ...filters.value, [key]: value }
  }

  function setSort(key: ArticleSortKey): void {
    sort.value = key
  }

  function _replaceLocal(row: Article): void {
    const idx = items.value.findIndex((article) => article.id === row.id)
    if (idx >= 0) items.value.splice(idx, 1, row)
  }

  function getById(id: number): Article | null {
    if (currentDetail.value?.id === id) return currentDetail.value
    return items.value.find((article) => article.id === id) ?? null
  }

  const filteredItems = computed<Article[]>(() => {
    let arr = items.value
    if (filters.value.author_id !== null) {
      const target = filters.value.author_id
      arr = arr.filter((article) => article.author_id === target)
    }
    const key = sort.value
    const dir = key.startsWith('-') ? -1 : 1
    const field = key.replace(/^-/, '') as 'created_at' | 'updated_at' | 'title'
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
    currentDetail.value = null
    filters.value = { status: null, topic_id: null, cluster_id: null, author_id: null }
    sort.value = '-created_at'
  }

  return {
    items,
    totalEstimate,
    nextCursor,
    loading,
    error,
    currentProjectId,
    currentDetail,
    filters,
    sort,
    filteredItems,
    refresh,
    loadMore,
    listDueForRefresh,
    get,
    listVersions,
    setFilter,
    setSort,
    getById,
    reset,
  }
})
