// Articles store — list / get / list_due_for_refresh + 12 mutating verbs.
//
// Wires to:
// - `GET /api/v1/projects/{id}/articles` (cursor-paginated; filters: status, topic_id)
// - `POST /api/v1/projects/{id}/articles`
// - `GET /api/v1/articles/{id}`
// - `PATCH /api/v1/articles/{id}` (UI-permissive escape hatch; If-Match)
// - `GET /api/v1/projects/{id}/articles/refresh-due`
// - `POST /api/v1/articles/{id}/brief` — set_brief
// - `POST /api/v1/articles/{id}/outline` — set_outline
// - `POST /api/v1/articles/{id}/draft?append=true|false` — set_draft
// - `POST /api/v1/articles/{id}/draft/mark-drafted` — mark_drafted
// - `POST /api/v1/articles/{id}/edit` — set_edited
// - `POST /api/v1/articles/{id}/eeat-pass` — mark_eeat_passed
// - `POST /api/v1/articles/{id}/publish` — mark_published
// - `POST /api/v1/articles/{id}/refresh-due` — mark_refresh_due
// - `POST /api/v1/articles/{id}/version` — create_version
// - `GET /api/v1/articles/{id}/versions` — list_versions
//
// Each mutating call carries `expected_etag` from the current article's
// `step_etag`. The repository regenerates the etag on every successful
// transition; we update the local cache from the response so the next
// call carries the fresh value. Stale etag → 409/-32008 from the server,
// surfaced as a structured error so the caller can show a reload prompt.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, apiWrite, ApiError } from '@/lib/client'
import type { components } from '@/api'

export type Article = components['schemas']['ArticleOut']
export type ArticleStatus = components['schemas']['ArticleStatus']
export type ArticleVersion = components['schemas']['ArticleVersionOut']
type ArticleCreateRequest = components['schemas']['ArticleCreateRequest']
type ArticlePatchRequest = components['schemas']['ArticlePatchRequest']
type ArticlesPage = components['schemas']['PageResponse_ArticleOut_']
type VersionsPage = components['schemas']['PageResponse_ArticleVersionOut_']
type SetBriefRequest = components['schemas']['SetBriefRequest']
type SetOutlineRequest = components['schemas']['SetOutlineRequest']
type SetDraftRequest = components['schemas']['SetDraftRequest']
type SetEditedRequest = components['schemas']['SetEditedRequest']
type MarkDraftedRequest = components['schemas']['MarkDraftedRequest']
type MarkEeatPassedRequest = components['schemas']['MarkEeatPassedRequest']
type MarkPublishedRequest = components['schemas']['MarkPublishedRequest']
type MarkRefreshDueRequest = components['schemas']['MarkRefreshDueRequest']

const DEFAULT_LIMIT = 50

export interface ArticleFilters {
  status: ArticleStatus | null
  topic_id: number | null
  cluster_id: number | null
  author_id: number | null
}

export type ArticleSortKey = 'created_at' | '-created_at' | 'updated_at' | '-updated_at' | 'title'

/**
 * Shape of the structured ETag mismatch surfaced by the daemon on a stale
 * write. Returned as a fresh `ArticleEtagError` from any mutating call so
 * the UI can render a reload prompt without parsing wire JSON.
 */
export class ArticleEtagError extends Error {
  current_etag: string | null
  current_updated_at: string | null
  constructor(message: string, current_etag: string | null, current_updated_at: string | null) {
    super(message)
    this.name = 'ArticleEtagError'
    this.current_etag = current_etag
    this.current_updated_at = current_updated_at
  }
}

function _wrapEtagError(err: unknown): never {
  if (err instanceof ApiError && (err.status === 409 || err.status === 412)) {
    const body = err.body as
      | { data?: { current_etag?: string; current_updated_at?: string }; detail?: { data?: { current_etag?: string; current_updated_at?: string } } }
      | null
    const data = body?.data ?? body?.detail?.data ?? null
    throw new ArticleEtagError(
      err.message,
      data?.current_etag ?? null,
      data?.current_updated_at ?? null,
    )
  }
  throw err
}

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
      const page = await apiFetch<ArticlesPage>(
        `/api/v1/projects/${projectId}/articles?${_buildParams().toString()}`,
      )
      _ingestPage(page, false)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load articles'
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
      error.value = err instanceof Error ? err.message : 'failed to load more articles'
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

  function setFilter<K extends keyof ArticleFilters>(key: K, value: ArticleFilters[K]): void {
    filters.value = { ...filters.value, [key]: value }
  }

  function setSort(key: ArticleSortKey): void {
    sort.value = key
  }

  async function create(projectId: number, body: ArticleCreateRequest): Promise<Article> {
    const row = await apiWrite<Article>(`/api/v1/projects/${projectId}/articles`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    items.value = [row, ...items.value]
    totalEstimate.value = totalEstimate.value + 1
    return row
  }

  async function get(articleId: number): Promise<Article> {
    const row = await apiFetch<Article>(`/api/v1/articles/${articleId}`)
    currentDetail.value = row
    _replaceLocal(row)
    return row
  }

  async function patchEscape(
    articleId: number,
    patch: ArticlePatchRequest,
    ifMatch: string | null,
  ): Promise<Article> {
    try {
      const row = await apiWrite<Article>(`/api/v1/articles/${articleId}`, {
        method: 'PATCH',
        headers: {
          'content-type': 'application/json',
          ...(ifMatch ? { 'If-Match': ifMatch } : {}),
        },
        body: JSON.stringify(patch),
      })
      currentDetail.value = row
      _replaceLocal(row)
      return row
    } catch (err) {
      _wrapEtagError(err)
    }
  }

  async function setBrief(
    articleId: number,
    body: SetBriefRequest,
  ): Promise<Article> {
    try {
      const row = await apiWrite<Article>(`/api/v1/articles/${articleId}/brief`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      })
      currentDetail.value = row
      _replaceLocal(row)
      return row
    } catch (err) {
      _wrapEtagError(err)
    }
  }

  async function setOutline(
    articleId: number,
    body: SetOutlineRequest,
  ): Promise<Article> {
    try {
      const row = await apiWrite<Article>(`/api/v1/articles/${articleId}/outline`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      })
      currentDetail.value = row
      _replaceLocal(row)
      return row
    } catch (err) {
      _wrapEtagError(err)
    }
  }

  async function setDraft(
    articleId: number,
    body: SetDraftRequest,
    append = false,
  ): Promise<Article> {
    const url = `/api/v1/articles/${articleId}/draft${append ? '?append=true' : ''}`
    try {
      const row = await apiWrite<Article>(url, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      })
      currentDetail.value = row
      _replaceLocal(row)
      return row
    } catch (err) {
      _wrapEtagError(err)
    }
  }

  async function setEdited(
    articleId: number,
    body: SetEditedRequest,
  ): Promise<Article> {
    try {
      const row = await apiWrite<Article>(`/api/v1/articles/${articleId}/edit`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      })
      currentDetail.value = row
      _replaceLocal(row)
      return row
    } catch (err) {
      _wrapEtagError(err)
    }
  }

  async function markDrafted(
    articleId: number,
    body: MarkDraftedRequest,
  ): Promise<Article> {
    try {
      const row = await apiWrite<Article>(`/api/v1/articles/${articleId}/draft/mark-drafted`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      })
      currentDetail.value = row
      _replaceLocal(row)
      return row
    } catch (err) {
      _wrapEtagError(err)
    }
  }

  async function markEeatPassed(
    articleId: number,
    body: MarkEeatPassedRequest,
  ): Promise<Article> {
    try {
      const row = await apiWrite<Article>(`/api/v1/articles/${articleId}/eeat-pass`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      })
      currentDetail.value = row
      _replaceLocal(row)
      return row
    } catch (err) {
      _wrapEtagError(err)
    }
  }

  async function markPublished(
    articleId: number,
    body: MarkPublishedRequest,
  ): Promise<Article> {
    try {
      const row = await apiWrite<Article>(`/api/v1/articles/${articleId}/publish`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      })
      currentDetail.value = row
      _replaceLocal(row)
      return row
    } catch (err) {
      _wrapEtagError(err)
    }
  }

  async function markRefreshDue(
    articleId: number,
    body: MarkRefreshDueRequest,
  ): Promise<Article> {
    const row = await apiWrite<Article>(`/api/v1/articles/${articleId}/refresh-due`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    currentDetail.value = row
    _replaceLocal(row)
    return row
  }

  async function createVersion(articleId: number): Promise<ArticleVersion> {
    return apiWrite<ArticleVersion>(`/api/v1/articles/${articleId}/version`, { method: 'POST' })
  }

  async function listVersions(articleId: number): Promise<ArticleVersion[]> {
    const params = new URLSearchParams({ limit: '200' })
    const page = await apiFetch<VersionsPage>(
      `/api/v1/articles/${articleId}/versions?${params.toString()}`,
    )
    return page.items
  }

  function _replaceLocal(row: Article): void {
    const idx = items.value.findIndex((a) => a.id === row.id)
    if (idx >= 0) items.value.splice(idx, 1, row)
  }

  function getById(id: number): Article | null {
    if (currentDetail.value?.id === id) return currentDetail.value
    return items.value.find((a) => a.id === id) ?? null
  }

  /**
   * Client-side filtered view of `items` honouring filters that the
   * server-side endpoint doesn't natively understand (cluster_id, author_id).
   */
  const filteredItems = computed<Article[]>(() => {
    let arr = items.value
    if (filters.value.author_id !== null) {
      const tgt = filters.value.author_id
      arr = arr.filter((a) => a.author_id === tgt)
    }
    // Client-side sort honouring the selected sort key.
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
    setFilter,
    setSort,
    create,
    get,
    patchEscape,
    setBrief,
    setOutline,
    setDraft,
    setEdited,
    markDrafted,
    markEeatPassed,
    markPublished,
    markRefreshDue,
    createVersion,
    listVersions,
    getById,
    reset,
  }
})
