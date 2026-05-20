// Schedules store — read-only scheduled jobs.

import { ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch } from '@/lib/client'
import type { components } from '@/api'

export type ScheduledJob = components['schemas']['ScheduledJobOut']

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
    reset,
  }
})
