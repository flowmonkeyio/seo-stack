// GSC store — raw rows + redirects + ad-hoc rollup.
//
// Wires to:
// - `GET  /api/v1/projects/{id}/gsc?since=ISO&until=ISO` — raw rows in window
// - `POST /api/v1/gsc/bulk` — operator-driven bulk ingest (M5+)
// - `POST /api/v1/projects/{id}/gsc/rollup?day=YYYY-MM-DD` — ad-hoc rollup
// - `GET  /api/v1/projects/{id}/redirects` (cursor pagination)
// - `POST /api/v1/projects/{id}/redirects` — create 301/302
// - `GET  /api/v1/articles/{id}/gsc?since=&until=` — per-article query
//
// The raw "daily rollup" view is filled from `gsc_metrics_daily` rows but the
// daemon doesn't (yet) expose a dedicated GET for that table — we surface the
// raw rows aggregated by `captured_at::date` for now and flag it as a known
// quality concern in the M5.C report. This is an explicit deferral and not a
// scope-creep fix here.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, apiWrite } from '@/lib/client'
import type { components } from '@/api'

export type GscMetric = components['schemas']['GscMetricOut']
export type Redirect = components['schemas']['RedirectOut']
type RedirectsPage = components['schemas']['PageResponse_RedirectOut_']
type CreateRedirectRequest = components['schemas']['CreateRedirectRequest']

export interface GscFilters {
  /** ISO datetime — inclusive lower bound. */
  since: string
  /** ISO datetime — exclusive upper bound. */
  until: string
}

function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setUTCDate(d.getUTCDate() - days)
  d.setUTCHours(0, 0, 0, 0)
  return d.toISOString()
}

function isoNow(): string {
  const d = new Date()
  d.setUTCHours(0, 0, 0, 0)
  return d.toISOString()
}

export const useGscStore = defineStore('gsc', () => {
  const rawRows = ref<GscMetric[]>([])
  const redirects = ref<Redirect[]>([])
  const redirectsCursor = ref<number | null>(null)
  const loading = ref(false)
  const redirectsLoading = ref(false)
  const error = ref<string | null>(null)
  const currentProjectId = ref<number | null>(null)
  const filters = ref<GscFilters>({
    since: isoDaysAgo(30),
    until: isoNow(),
  })

  async function refresh(projectId: number): Promise<void> {
    currentProjectId.value = projectId
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams({
        since: filters.value.since,
        until: filters.value.until,
      })
      const rows = await apiFetch<GscMetric[]>(
        `/api/v1/projects/${projectId}/gsc?${params.toString()}`,
      )
      rawRows.value = Array.isArray(rows) ? rows : []
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load GSC rows'
    } finally {
      loading.value = false
    }
  }

  async function refreshRedirects(projectId: number): Promise<void> {
    redirectsLoading.value = true
    try {
      const params = new URLSearchParams({ limit: '50' })
      const page = await apiFetch<RedirectsPage>(
        `/api/v1/projects/${projectId}/redirects?${params.toString()}`,
      )
      redirects.value = page.items
      redirectsCursor.value = page.next_cursor ?? null
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load redirects'
    } finally {
      redirectsLoading.value = false
    }
  }

  async function loadMoreRedirects(projectId: number): Promise<void> {
    if (redirectsCursor.value === null || redirectsLoading.value) return
    redirectsLoading.value = true
    try {
      const params = new URLSearchParams({
        limit: '50',
        after: String(redirectsCursor.value),
      })
      const page = await apiFetch<RedirectsPage>(
        `/api/v1/projects/${projectId}/redirects?${params.toString()}`,
      )
      redirects.value = [...redirects.value, ...page.items]
      redirectsCursor.value = page.next_cursor ?? null
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load redirects'
    } finally {
      redirectsLoading.value = false
    }
  }

  async function createRedirect(
    projectId: number,
    body: CreateRedirectRequest,
  ): Promise<Redirect> {
    const row = await apiWrite<Redirect>(`/api/v1/projects/${projectId}/redirects`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    redirects.value = [row, ...redirects.value]
    return row
  }

  async function rollupDay(projectId: number, day: string): Promise<unknown> {
    const params = new URLSearchParams({ day })
    return apiWrite<unknown>(
      `/api/v1/projects/${projectId}/gsc/rollup?${params.toString()}`,
      { method: 'POST' },
    )
  }

  async function queryArticle(
    articleId: number,
    since: string,
    until: string,
  ): Promise<GscMetric[]> {
    const params = new URLSearchParams({ since, until })
    return apiFetch<GscMetric[]>(`/api/v1/articles/${articleId}/gsc?${params.toString()}`)
  }

  function setFilter<K extends keyof GscFilters>(key: K, value: GscFilters[K]): void {
    filters.value = { ...filters.value, [key]: value }
  }

  /**
   * Client-side daily rollup: groups raw rows by `captured_at::date` and
   * sums clicks/impressions, averaging position. This is a stand-in for a
   * dedicated `GET /gsc/daily` endpoint (PLAN.md §schema lists
   * gsc_metrics_daily but no read REST API exists at M5.C — flagged as a
   * quality concern in the milestone report).
   */
  const dailyRollup = computed(() => {
    interface Bucket {
      day: string
      impressions: number
      clicks: number
      avg_position_sum: number
      count: number
      ctr_sum: number
    }
    const buckets = new Map<string, Bucket>()
    for (const r of rawRows.value) {
      const day = r.captured_at.slice(0, 10)
      const b = buckets.get(day) ?? {
        day,
        impressions: 0,
        clicks: 0,
        avg_position_sum: 0,
        count: 0,
        ctr_sum: 0,
      }
      b.impressions += r.impressions
      b.clicks += r.clicks
      b.avg_position_sum += r.avg_position
      b.ctr_sum += r.ctr
      b.count += 1
      buckets.set(day, b)
    }
    const out = Array.from(buckets.values()).map((b) => ({
      id: b.day,
      day: b.day,
      impressions: b.impressions,
      clicks: b.clicks,
      ctr: b.count === 0 ? 0 : b.ctr_sum / b.count,
      avg_position: b.count === 0 ? 0 : b.avg_position_sum / b.count,
    }))
    out.sort((a, b) => (a.day < b.day ? 1 : -1))
    return out
  })

  function reset(): void {
    rawRows.value = []
    redirects.value = []
    redirectsCursor.value = null
    error.value = null
    currentProjectId.value = null
    filters.value = { since: isoDaysAgo(30), until: isoNow() }
  }

  return {
    rawRows,
    redirects,
    redirectsCursor,
    loading,
    redirectsLoading,
    error,
    currentProjectId,
    filters,
    dailyRollup,
    refresh,
    refreshRedirects,
    loadMoreRedirects,
    createRedirect,
    rollupDay,
    queryArticle,
    setFilter,
    reset,
  }
})
