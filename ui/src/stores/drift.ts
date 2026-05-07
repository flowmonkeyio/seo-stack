// Drift store — list / get / snapshot baselines.
//
// Wires to:
// - `GET  /api/v1/articles/{id}/drift`              — list per article
// - `POST /api/v1/articles/{id}/drift/snapshot`     — record a baseline
//
// IMPORTANT: M5.C surfaces baselines but NOT the comparison engine —
// `current_score` may be null until M6 ships the diff/score job.
// Project-wide listing is synthesized client-side from the per-article
// endpoint by walking published articles; the daemon doesn't yet expose a
// project-level `GET /projects/{id}/drift` aggregate. This is flagged in
// the M5.C report as a quality concern (an aggregate endpoint would be
// nicer for large projects but the per-article fanout keeps M5.C
// strictly UI-only).

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, apiWrite } from '@/lib/client'
import type { components } from '@/api'

export type DriftBaseline = components['schemas']['DriftBaselineOut']
type DriftSnapshotRequest = components['schemas']['DriftSnapshotRequest']

/**
 * Aggregate drift row + the article id it belongs to (synthesized
 * client-side because the wire shape is per-article).
 */
export interface DriftRow extends DriftBaseline {
  /** Belongs to article — copied from the parent path so the view can
   *  link back without a second fetch. Not on the wire. */
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

  /**
   * Load drift baselines for a list of article ids in parallel. The view
   * computes the `articleIds` from a list of published articles via the
   * articles store; we keep the fanout here so the view stays declarative.
   */
  async function refreshAcrossArticles(articleIds: number[]): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const results = await Promise.allSettled(
        articleIds.map(async (id) => {
          const rows = await apiFetch<DriftBaseline[]>(`/api/v1/articles/${id}/drift`)
          return rows.map((r) => ({ ...r, parent_article_id: id }))
        }),
      )
      const next: DriftRow[] = []
      for (const r of results) {
        if (r.status === 'fulfilled') next.push(...r.value)
      }
      items.value = next
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load drift baselines'
    } finally {
      loading.value = false
    }
  }

  async function snapshot(
    articleId: number,
    body: DriftSnapshotRequest,
  ): Promise<DriftBaseline> {
    const row = await apiWrite<DriftBaseline>(`/api/v1/articles/${articleId}/drift/snapshot`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    items.value = [{ ...row, parent_article_id: articleId }, ...items.value]
    return row
  }

  function setThreshold(value: number): void {
    thresholdScore.value = value
  }

  /**
   * Filtered view honouring the threshold slider. Rows with `current_score`
   * null (pre-M6 watcher) pass through so users can see the baseline rows
   * even before the engine ships.
   */
  const filteredItems = computed<DriftRow[]>(() => {
    if (thresholdScore.value <= 0) return items.value
    return items.value.filter(
      (r) => r.current_score === null || (r.current_score ?? 0) >= thresholdScore.value,
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
    snapshot,
    setThreshold,
    reset,
  }
})
