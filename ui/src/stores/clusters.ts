// Clusters store — list / get / create per project.
//
// Wires to:
// - `GET /api/v1/projects/{id}/clusters` (cursor-paginated)
// - `POST /api/v1/projects/{id}/clusters`
// - `GET /api/v1/clusters/{id}`
//
// Hierarchy: PLAN.md §clusters — `parent_id` self-FK lets the UI render
// a tree without a second call. We keep the items list flat and expose a
// `tree` getter that groups spokes/hubs/comparisons/resources under their
// parent pillar. Orphan rows (parent_id missing from the loaded set)
// fall through to the top level so the UI never silently drops a row.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, apiWrite } from '@/lib/client'
import type { components } from '@/api'

export type Cluster = components['schemas']['ClusterOut']
type ClusterCreateRequest = components['schemas']['ClusterCreateRequest']
type ClustersPage = components['schemas']['PageResponse_ClusterOut_']

export interface ClusterTreeNode extends Cluster {
  children: ClusterTreeNode[]
}

const DEFAULT_LIMIT = 200

export const useClustersStore = defineStore('clusters', () => {
  const items = ref<Cluster[]>([])
  const totalEstimate = ref<number>(0)
  const nextCursor = ref<number | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentProjectId = ref<number | null>(null)

  function _ingestPage(page: ClustersPage, append: boolean): void {
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
      const params = new URLSearchParams({ limit: String(DEFAULT_LIMIT) })
      const page = await apiFetch<ClustersPage>(
        `/api/v1/projects/${projectId}/clusters?${params.toString()}`,
      )
      _ingestPage(page, false)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load clusters'
    } finally {
      loading.value = false
    }
  }

  async function loadMore(projectId: number): Promise<void> {
    if (nextCursor.value === null || loading.value) return
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams({
        limit: String(DEFAULT_LIMIT),
        after: String(nextCursor.value),
      })
      const page = await apiFetch<ClustersPage>(
        `/api/v1/projects/${projectId}/clusters?${params.toString()}`,
      )
      _ingestPage(page, true)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load more clusters'
    } finally {
      loading.value = false
    }
  }

  async function create(projectId: number, body: ClusterCreateRequest): Promise<Cluster> {
    const row = await apiWrite<Cluster>(`/api/v1/projects/${projectId}/clusters`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    items.value = [...items.value, row]
    totalEstimate.value = totalEstimate.value + 1
    return row
  }

  async function get(clusterId: number): Promise<Cluster> {
    return apiFetch<Cluster>(`/api/v1/clusters/${clusterId}`)
  }

  function getById(id: number): Cluster | null {
    return items.value.find((c) => c.id === id) ?? null
  }

  /**
   * Pillar-rooted tree built from the loaded items.
   *
   * Top-level rows: `type='pillar'` first, then any row whose parent_id is
   * not in the loaded set (so orphans surface). Children sorted by
   * created_at ASC so the UI is deterministic across reloads.
   */
  const tree = computed<ClusterTreeNode[]>(() => {
    const map = new Map<number, ClusterTreeNode>()
    for (const c of items.value) {
      map.set(c.id, { ...c, children: [] })
    }
    const roots: ClusterTreeNode[] = []
    for (const c of items.value) {
      const node = map.get(c.id)
      if (!node) continue
      const parent = c.parent_id !== null ? map.get(c.parent_id) : undefined
      if (parent) {
        parent.children.push(node)
      } else {
        roots.push(node)
      }
    }
    // Sort: pillars first, then by created_at ASC.
    const cmp = (a: ClusterTreeNode, b: ClusterTreeNode): number => {
      if (a.type === 'pillar' && b.type !== 'pillar') return -1
      if (b.type === 'pillar' && a.type !== 'pillar') return 1
      return a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0
    }
    function sortRecursive(nodes: ClusterTreeNode[]): void {
      nodes.sort(cmp)
      for (const n of nodes) sortRecursive(n.children)
    }
    sortRecursive(roots)
    return roots
  })

  function reset(): void {
    items.value = []
    totalEstimate.value = 0
    nextCursor.value = null
    error.value = null
    currentProjectId.value = null
  }

  return {
    items,
    totalEstimate,
    nextCursor,
    loading,
    error,
    currentProjectId,
    tree,
    refresh,
    loadMore,
    create,
    get,
    getById,
    reset,
  }
})
