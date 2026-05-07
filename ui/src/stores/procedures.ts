// Procedures store — list / get_run / poll status.
//
// Wires to:
// - `GET  /api/v1/procedures`              — list procedure summaries
// - `POST /api/v1/procedures/{slug}/run`   — currently 501 (M7)
// - `GET  /api/v1/procedures/runs/{id}`    — `{run, steps[]}`
//
// `runProcedure` is the only mutating verb here and the daemon returns 501
// at M5.C; the store surfaces a NotImplementedError so the view can show
// the "available in M7" hint in place of failing silently.

import { ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, apiWrite, ApiError } from '@/lib/client'
import type { components } from '@/api'

export type ProcedureSummary = components['schemas']['ProcedureSummary']
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

  async function runProcedure(slug: string, args: Record<string, unknown>): Promise<unknown> {
    try {
      return await apiWrite<unknown>(`/api/v1/procedures/${slug}/run`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(args),
      })
    } catch (err) {
      if (err instanceof ApiError && err.status === 501) {
        throw new ProcedureNotImplementedError(
          'Procedure runner is not yet implemented (M7)',
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
