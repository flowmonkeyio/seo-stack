// Procedures store — list / run / get_run / poll status.
//
// Wires to:
// - `GET  /api/v1/procedures`              — list procedure summaries
// - `POST /api/v1/procedures/{slug}/run`   — enqueue a daemon-side procedure run
// - `GET  /api/v1/procedures/runs/{id}`    — `{run, steps[]}`

import { ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, ApiError } from '@/lib/client'
import type { components } from '@/api'

export type ProcedureSummary = components['schemas']['ProcedureSummary']
export type ProcedureRunEnqueued = components['schemas']['ProcedureRunEnqueued']
export type ProcedureRunResponse = components['schemas']['ProcedureRunResponse']
export type ProcedureRunStep = components['schemas']['ProcedureRunStepOut']

export class ProcedureNotImplementedError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ProcedureNotImplementedError'
    this.status = status
  }
}

export const useProceduresStore = defineStore('procedures', () => {
  const items = ref<ProcedureSummary[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentRun = ref<ProcedureRunResponse | null>(null)

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const rows = await apiFetch<ProcedureSummary[]>(`/api/v1/procedures`)
      items.value = Array.isArray(rows) ? rows : []
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load procedures'
    } finally {
      loading.value = false
    }
  }

  async function runProcedure(
    slug: string,
    projectId: number,
    args: Record<string, unknown>,
  ): Promise<ProcedureRunEnqueued> {
    try {
      return await apiFetch<ProcedureRunEnqueued>(`/api/v1/procedures/${slug}/run`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ project_id: projectId, args }),
      })
    } catch (err) {
      if (err instanceof ApiError && err.status === 501) {
        throw new ProcedureNotImplementedError(
          'Procedure runner is not available on this daemon',
          err.status,
        )
      }
      throw err
    }
  }

  async function getRun(runId: number): Promise<ProcedureRunResponse> {
    const row = await apiFetch<ProcedureRunResponse>(`/api/v1/procedures/runs/${runId}`)
    currentRun.value = row
    return row
  }

  function getBySlug(slug: string): ProcedureSummary | null {
    return items.value.find((p) => p.slug === slug) ?? null
  }

  function reset(): void {
    items.value = []
    error.value = null
    currentRun.value = null
  }

  return {
    items,
    loading,
    error,
    currentRun,
    refresh,
    runProcedure,
    getRun,
    getBySlug,
    reset,
  }
})
