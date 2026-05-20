// Procedures store — read-only procedure catalog and run inspection.

import { ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, formatApiError } from '@/lib/client'
import type { components } from '@/api'

export type ProcedureSummary = components['schemas']['ProcedureSummary']
export type ProcedureRunResponse = components['schemas']['ProcedureRunResponse']
export type ProcedureRunStep = components['schemas']['ProcedureRunStepOut']

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
      error.value = formatApiError(err, 'failed to load procedures')
    } finally {
      loading.value = false
    }
  }

  async function getRun(runId: number): Promise<ProcedureRunResponse> {
    const row = await apiFetch<ProcedureRunResponse>(`/api/v1/procedures/runs/${runId}`)
    currentRun.value = row
    return row
  }

  function getBySlug(slug: string): ProcedureSummary | null {
    return items.value.find((procedure) => procedure.slug === slug) ?? null
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
    getRun,
    getBySlug,
    reset,
  }
})
