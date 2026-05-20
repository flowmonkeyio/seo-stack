// GSC store — read-only raw rows, redirects, and client-side daily rollup.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, formatApiError } from '@/lib/client'
import type { components } from '@/api'

export type GscMetric = components['schemas']['GscMetricOut']
export type Redirect = components['schemas']['RedirectOut']
type RedirectsPage = components['schemas']['PageResponse_RedirectOut_']

export interface GscFilters {
  since: string
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
      error.value = formatApiError(err, 'failed to load GSC rows')
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
      error.value = formatApiError(err, 'failed to load redirects')
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
      error.value = formatApiError(err, 'failed to load redirects')
    } finally {
      redirectsLoading.value = false
    }
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
    for (const row of rawRows.value) {
      const day = row.captured_at.slice(0, 10)
      const bucket = buckets.get(day) ?? {
        day,
        impressions: 0,
        clicks: 0,
        avg_position_sum: 0,
        count: 0,
        ctr_sum: 0,
      }
      bucket.impressions += row.impressions
      bucket.clicks += row.clicks
      bucket.avg_position_sum += row.avg_position
      bucket.ctr_sum += row.ctr
      bucket.count += 1
      buckets.set(day, bucket)
    }
    const out = Array.from(buckets.values()).map((bucket) => ({
      id: bucket.day,
      day: bucket.day,
      impressions: bucket.impressions,
      clicks: bucket.clicks,
      ctr: bucket.count === 0 ? 0 : bucket.ctr_sum / bucket.count,
      avg_position: bucket.count === 0 ? 0 : bucket.avg_position_sum / bucket.count,
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
    queryArticle,
    setFilter,
    reset,
  }
})
