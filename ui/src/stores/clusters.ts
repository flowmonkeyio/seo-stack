// Clusters store — read-only list / detail / tree.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch } from '@/lib/client'
import type { components } from '@/api'

export type Cluster = components['schemas']['ClusterOut']
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
    items.value = append ? [...items.value, ...page.items] : [...page.items]
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

  async function get(clusterId: number): Promise<Cluster> {
    return apiFetch<Cluster>(`/api/v1/clusters/${clusterId}`)
  }

  function getById(id: number): Cluster | null {
    return items.value.find((cluster) => cluster.id === id) ?? null
  }

  const tree = computed<ClusterTreeNode[]>(() => {
    const map = new Map<number, ClusterTreeNode>()
    for (const cluster of items.value) {
      map.set(cluster.id, { ...cluster, children: [] })
    }
    const roots: ClusterTreeNode[] = []
    for (const cluster of items.value) {
      const node = map.get(cluster.id)
      if (!node) continue
      const parent = cluster.parent_id !== null ? map.get(cluster.parent_id) : undefined
      if (parent) parent.children.push(node)
      else roots.push(node)
    }
    const cmp = (a: ClusterTreeNode, b: ClusterTreeNode): number => {
      if (a.type === 'pillar' && b.type !== 'pillar') return -1
      if (b.type === 'pillar' && a.type !== 'pillar') return 1
      return a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0
    }
    function sortRecursive(nodes: ClusterTreeNode[]): void {
      nodes.sort(cmp)
      for (const node of nodes) sortRecursive(node.children)
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
    get,
    getById,
    reset,
  }
})
