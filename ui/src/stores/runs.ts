// Runs store — list / get / children / abort / heartbeat.
//
// Wires to:
// - `GET  /api/v1/projects/{id}/runs?kind=&status=&parent_run_id=&limit=&after=`
//        cursor-paginated; sorts by id desc server-side per repository.
// - `GET  /api/v1/runs/{id}`              — single run row
// - `GET  /api/v1/runs/{id}/children`     — direct children
// - `POST /api/v1/runs/{id}/abort?cascade=true|false`
// - `POST /api/v1/runs/{id}/heartbeat`    — admin/test
//
// The wire shape is `RunOut` per `runs` table — there is NO endpoint that
// returns run_steps + run_step_calls keyed by run id at M5.C. That's PLAN.md
// L603 and audit M-29 surfacing as a backend gap; the RunsView's
// "step expansion" feature falls back to `runs.metadata_json` shaped as
// `{step_index, step_id, ...}` from the procedure_run_steps endpoint
// (`/api/v1/procedures/runs/{run_id}`). This is documented in the M5.C
// report quality concerns.

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, apiWrite } from '@/lib/client'
import type { components } from '@/api'

export type Run = components['schemas']['RunOut']
export type RunStatus = components['schemas']['RunStatus']
export type RunKind = components['schemas']['RunKind']
type RunsPage = components['schemas']['PageResponse_RunOut_']
type ProcedureRunResponse = components['schemas']['ProcedureRunResponse']

const DEFAULT_LIMIT = 50

export interface RunFilters {
  kind: RunKind | null
  status: RunStatus | null
  parent_run_id: number | null
  /** ISO datetime — clients narrow by `started_at >= since` client-side. */
  since: string | null
  /** ISO datetime — clients narrow by `started_at < until` client-side. */
  until: string | null
}

export type RunSortKey = 'started_at' | '-started_at' | 'id' | '-id'

export const useRunsStore = defineStore('runs', () => {
  const items = ref<Run[]>([])
  const totalEstimate = ref<number>(0)
  const nextCursor = ref<number | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentProjectId = ref<number | null>(null)
  const currentDetail = ref<Run | null>(null)
  /** Children by parent run id — the detail view fetches once and caches. */
  const childrenByParent = ref<Map<number, Run[]>>(new Map())
  const filters = ref<RunFilters>({
    kind: null,
    status: null,
    parent_run_id: null,
    since: null,
    until: null,
  })
  const sort = ref<RunSortKey>('-started_at')

  function _buildParams(after?: number | null): URLSearchParams {
    const params = new URLSearchParams({ limit: String(DEFAULT_LIMIT) })
    if (filters.value.kind) params.set('kind', filters.value.kind)
    if (filters.value.status) params.set('status', filters.value.status)
    if (filters.value.parent_run_id !== null) {
      params.set('parent_run_id', String(filters.value.parent_run_id))
    }
    if (after !== undefined && after !== null) params.set('after', String(after))
    return params
  }

  function _ingestPage(page: RunsPage, append: boolean): void {
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
      const page = await apiFetch<RunsPage>(
        `/api/v1/projects/${projectId}/runs?${_buildParams().toString()}`,
      )
      _ingestPage(page, false)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load runs'
    } finally {
      loading.value = false
    }
  }

  async function loadMore(projectId: number): Promise<void> {
    if (nextCursor.value === null || loading.value) return
    loading.value = true
    try {
      const page = await apiFetch<RunsPage>(
        `/api/v1/projects/${projectId}/runs?${_buildParams(nextCursor.value).toString()}`,
      )
      _ingestPage(page, true)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load more runs'
    } finally {
      loading.value = false
    }
  }

  async function get(runId: number): Promise<Run> {
    const row = await apiFetch<Run>(`/api/v1/runs/${runId}`)
    currentDetail.value = row
    return row
  }

  async function children(runId: number): Promise<Run[]> {
    const rows = await apiFetch<Run[]>(`/api/v1/runs/${runId}/children`)
    childrenByParent.value.set(runId, rows)
    return rows
  }

  async function abort(runId: number, cascade = false): Promise<Run> {
    const params = new URLSearchParams()
    if (cascade) params.set('cascade', 'true')
    const url = params.toString() === ''
      ? `/api/v1/runs/${runId}/abort`
      : `/api/v1/runs/${runId}/abort?${params.toString()}`
    const row = await apiWrite<Run>(url, { method: 'POST' })
    _replaceLocal(row)
    if (currentDetail.value?.id === runId) currentDetail.value = row
    return row
  }

  async function heartbeat(runId: number): Promise<Run | null> {
    interface Envelope {
      data: Run | null
      run_id: number | null
      project_id: number | null
    }
    const envelope = await apiFetch<Envelope>(`/api/v1/runs/${runId}/heartbeat`, {
      method: 'POST',
    })
    if (envelope.data) {
      _replaceLocal(envelope.data)
      if (currentDetail.value?.id === runId) currentDetail.value = envelope.data
    }
    return envelope.data
  }

  /**
   * Fetch the procedure-run companion view for a run that originated from a
   * procedure. The endpoint returns `{run, steps[]}` where `steps` are
   * procedure_run_steps rows (per audit M-29). For non-procedure runs this
   * call returns 404 and we resolve to `null`.
   */
  async function getProcedureRunSteps(runId: number): Promise<ProcedureRunResponse | null> {
    try {
      return await apiFetch<ProcedureRunResponse>(`/api/v1/procedures/runs/${runId}`)
    } catch {
      return null
    }
  }

  function _replaceLocal(row: Run): void {
    const idx = items.value.findIndex((r) => r.id === row.id)
    if (idx >= 0) items.value.splice(idx, 1, row)
  }

  function getById(id: number): Run | null {
    if (currentDetail.value?.id === id) return currentDetail.value
    return items.value.find((r) => r.id === id) ?? null
  }

  function setFilter<K extends keyof RunFilters>(key: K, value: RunFilters[K]): void {
    filters.value = { ...filters.value, [key]: value }
  }

  function setSort(key: RunSortKey): void {
    sort.value = key
  }

  /**
   * Client-side date narrowing. The REST endpoint doesn't natively accept
   * since/until so we keep this in the store; it's also where the sort
   * order is applied (the wire returns id desc).
   */
  const filteredItems = computed<Run[]>(() => {
    let arr = items.value
    if (filters.value.since) {
      const lo = filters.value.since
      arr = arr.filter((r) => r.started_at >= lo)
    }
    if (filters.value.until) {
      const hi = filters.value.until
      arr = arr.filter((r) => r.started_at < hi)
    }
    const key = sort.value
    const dir = key.startsWith('-') ? -1 : 1
    const field = key.replace(/^-/, '') as 'id' | 'started_at'
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
    childrenByParent.value = new Map()
    filters.value = {
      kind: null,
      status: null,
      parent_run_id: null,
      since: null,
      until: null,
    }
    sort.value = '-started_at'
  }

  return {
    items,
    totalEstimate,
    nextCursor,
    loading,
    error,
    currentProjectId,
    currentDetail,
    childrenByParent,
    filters,
    sort,
    filteredItems,
    refresh,
    loadMore,
    get,
    children,
    abort,
    heartbeat,
    getProcedureRunSteps,
    setFilter,
    setSort,
    getById,
    reset,
  }
})
