// Schedules store — list / set / toggle.
//
// Wires to:
// - `GET    /api/v1/projects/{id}/schedules`
// - `POST   /api/v1/projects/{id}/schedules`         — upsert by (project_id, kind)
// - `PATCH  /api/v1/projects/{id}/schedules/{job_id}` — id-keyed update
// - `DELETE /api/v1/projects/{id}/schedules/{job_id}` — disable (toggle off)
//
// Repository upserts on `(project_id, kind)` so we surface `set` as the
// project-level POST and `toggle` as a PATCH with `enabled` flipped. Hard
// delete is M9 maintenance work.

import { ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch, apiWrite } from '@/lib/client'
import type { components } from '@/api'

export type ScheduledJob = components['schemas']['ScheduledJobOut']
type ScheduleUpsertRequest = components['schemas']['ScheduleUpsertRequest']

export const useSchedulesStore = defineStore('schedules', () => {
  const items = ref<ScheduledJob[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentProjectId = ref<number | null>(null)

  async function refresh(projectId: number): Promise<void> {
    currentProjectId.value = projectId
    loading.value = true
    error.value = null
    try {
      const rows = await apiFetch<ScheduledJob[]>(`/api/v1/projects/${projectId}/schedules`)
      items.value = Array.isArray(rows) ? rows : []
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'failed to load schedules'
    } finally {
      loading.value = false
    }
  }

  async function set(
    projectId: number,
    body: ScheduleUpsertRequest,
  ): Promise<ScheduledJob> {
    const row = await apiWrite<ScheduledJob>(`/api/v1/projects/${projectId}/schedules`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    _replaceLocalByKind(row)
    return row
  }

  async function toggle(
    projectId: number,
    jobId: number,
    enabled: boolean,
  ): Promise<ScheduledJob> {
    const existing = items.value.find((s) => s.id === jobId)
    if (!existing) {
      throw new Error(`schedule ${jobId} not found in store`)
    }
    const body: ScheduleUpsertRequest = {
      kind: existing.kind,
      cron_expr: existing.cron_expr,
      enabled,
    }
    const row = await apiWrite<ScheduledJob>(
      `/api/v1/projects/${projectId}/schedules/${jobId}`,
      {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      },
    )
    _replaceLocalById(row)
    return row
  }

  async function disable(projectId: number, jobId: number): Promise<void> {
    await apiWrite<unknown>(`/api/v1/projects/${projectId}/schedules/${jobId}`, {
      method: 'DELETE',
    })
    items.value = items.value.filter((s) => s.id !== jobId)
  }

  function _replaceLocalByKind(row: ScheduledJob): void {
    const idx = items.value.findIndex((s) => s.kind === row.kind)
    if (idx >= 0) items.value.splice(idx, 1, row)
    else items.value = [row, ...items.value]
  }

  function _replaceLocalById(row: ScheduledJob): void {
    const idx = items.value.findIndex((s) => s.id === row.id)
    if (idx >= 0) items.value.splice(idx, 1, row)
  }

  function reset(): void {
    items.value = []
    error.value = null
    currentProjectId.value = null
  }

  return {
    items,
    loading,
    error,
    currentProjectId,
    refresh,
    set,
    toggle,
    disable,
    reset,
  }
})
