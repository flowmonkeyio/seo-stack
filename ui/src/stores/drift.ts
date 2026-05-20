// Drift store — read-only drift baseline listing.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch } from '@/lib/client'
import type { components } from '@/api'

export type DriftBaseline = components['schemas']['DriftBaselineOut']

export interface DriftRow extends DriftBaseline {
  parent_article_id: number
}

export const useDriftStore = defineStore('drift', () => {
  const items = ref<DriftRow[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const thresholdScore = ref<number>(0)

  async function listForArticle(articleId: number): Promise<DriftBaseline[]> {
    const rows = await apiFetch<DriftBaseline[]>(`/api/v1/articles/${articleId}/drift`)
    return Array.isArray(rows) ? rows : []
  }

  async function refreshAcrossArticles(articleIds: number[]): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const results = await Promise.allSettled(
        articleIds.map(async (id) => {
          const rows = await apiFetch<DriftBaseline[]>(`/api/v1/articles/${id}/drift`)
          return rows.map((row) => ({ ...row, parent_article_id: id }))
        }),
      )
      const next: DriftRow[] = []
      for (const result of results) {
        if (result.status === 'fulfilled') next.push(...result.value)
      }
      items.value = next
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load drift baselines'
    } finally {
      loading.value = false
    }
  }

  function setThreshold(value: number): void {
    thresholdScore.value = value
  }

  const filteredItems = computed<DriftRow[]>(() => {
    if (thresholdScore.value <= 0) return items.value
    return items.value.filter(
      (row) => row.current_score === null || (row.current_score ?? 0) >= thresholdScore.value,
    )
  })

  function reset(): void {
    items.value = []
    error.value = null
    thresholdScore.value = 0
  }

  return {
    items,
    loading,
    error,
    thresholdScore,
    filteredItems,
    listForArticle,
    refreshAcrossArticles,
    setThreshold,
    reset,
  }
})
