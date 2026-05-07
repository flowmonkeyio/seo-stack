<script setup lang="ts">
// SchedulesTab — list / set / toggle scheduled jobs.
//
// Wires to the schedules store (GET /schedules + POST/PATCH/DELETE).
// Repository upserts on `(project_id, kind)` so the form is "schedule kind X
// at cron Y, enabled boolean" — submitting the same kind twice replaces the
// row.

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useSchedulesStore, type ScheduledJob } from '@/stores/schedules'
import { useToastsStore } from '@/stores/toasts'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const schedulesStore = useSchedulesStore()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { items, loading, error } = storeToRefs(schedulesStore)

const formOpen = ref(false)
const submitting = ref(false)
const draft = ref({
  kind: 'gsc-pull',
  cron_expr: '0 2 * * *',
  enabled: true,
})

const SCHEDULE_KINDS = [
  'gsc-pull',
  'drift-check',
  'refresh-detector',
  'oauth-refresh',
  'crawl-error-watch',
] as const

const columns: DataTableColumn<ScheduledJob>[] = [
  { key: 'kind', label: 'Kind', cellClass: 'font-mono text-sm' },
  { key: 'cron_expr', label: 'Cron', cellClass: 'font-mono text-sm' },
  {
    key: 'next_run_at',
    label: 'Next run',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : '—'),
  },
  {
    key: 'last_run_at',
    label: 'Last run',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : '—'),
  },
  { key: 'last_run_status', label: 'Last status', widthClass: 'w-28' },
  { key: 'enabled', label: 'Enabled', widthClass: 'w-24' },
]

/** Minimal cron validity: 5 space-separated tokens. */
function cronValid(s: string): boolean {
  return /^\s*\S+\s+\S+\s+\S+\s+\S+\s+\S+\s*$/.test(s)
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  await schedulesStore.refresh(projectId.value)
}

function openForm(): void {
  formOpen.value = true
  draft.value = { kind: 'gsc-pull', cron_expr: '0 2 * * *', enabled: true }
}

function closeForm(): void {
  if (submitting.value) return
  formOpen.value = false
}

async function submit(): Promise<void> {
  if (!cronValid(draft.value.cron_expr)) {
    toasts.error('Invalid cron expression', 'Need 5 space-separated tokens.')
    return
  }
  submitting.value = true
  try {
    await schedulesStore.set(projectId.value, {
      kind: draft.value.kind,
      cron_expr: draft.value.cron_expr,
      enabled: draft.value.enabled,
    })
    toasts.success('Schedule saved', draft.value.kind)
    formOpen.value = false
    await schedulesStore.refresh(projectId.value)
  } catch (err) {
    toasts.error('Failed to save', err instanceof Error ? err.message : undefined)
  } finally {
    submitting.value = false
  }
}

async function toggleRow(row: ScheduledJob): Promise<void> {
  try {
    await schedulesStore.toggle(projectId.value, row.id, !row.enabled)
    toasts.success('Schedule toggled', `${row.kind} → ${!row.enabled ? 'on' : 'off'}`)
  } catch (err) {
    toasts.error('Toggle failed', err instanceof Error ? err.message : undefined)
  }
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-baseline justify-between gap-3">
      <h2 class="text-base font-semibold">
        Scheduled jobs
      </h2>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        @click="openForm"
      >
        Add schedule
      </button>
    </div>

    <p
      v-if="error"
      class="rounded bg-red-50 p-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200"
    >
      {{ error }}
    </p>

    <DataTable
      :items="items"
      :columns="columns"
      :loading="loading"
      aria-label="Scheduled jobs"
      empty-message="No scheduled jobs yet."
    >
      <template #cell:last_run_status="{ row }">
        <StatusBadge
          v-if="(row as ScheduledJob).last_run_status"
          :status="(row as ScheduledJob).last_run_status as string"
          kind="job"
          :small="true"
        />
        <span v-else>—</span>
      </template>
      <template #cell:enabled="{ row }">
        <button
          type="button"
          class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          :aria-label="(row as ScheduledJob).enabled ? `Disable ${(row as ScheduledJob).kind}` : `Enable ${(row as ScheduledJob).kind}`"
          @click.stop="toggleRow(row as ScheduledJob)"
        >
          {{ (row as ScheduledJob).enabled ? 'On' : 'Off' }}
        </button>
      </template>
    </DataTable>

    <div
      v-if="formOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-schedule-form-title"
      @click.self="closeForm"
    >
      <div
        class="w-full max-w-md rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h3
          id="cs-schedule-form-title"
          class="mb-3 text-lg font-semibold"
        >
          Add schedule
        </h3>
        <label class="mb-3 block text-sm">
          <span class="font-medium">Kind</span>
          <select
            v-model="draft.kind"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
          >
            <option
              v-for="k in SCHEDULE_KINDS"
              :key="k"
              :value="k"
            >
              {{ k }}
            </option>
          </select>
        </label>
        <label class="mb-3 block text-sm">
          <span class="font-medium">Cron expression</span>
          <input
            v-model="draft.cron_expr"
            type="text"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-sm dark:border-gray-700 dark:bg-gray-800"
            placeholder="0 2 * * *"
          >
        </label>
        <label class="mb-3 inline-flex items-center gap-2 text-sm">
          <input
            v-model="draft.enabled"
            type="checkbox"
            class="h-4 w-4"
          >
          <span>Enabled</span>
        </label>
        <div class="flex justify-end gap-2">
          <button
            type="button"
            class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            :disabled="submitting"
            @click="closeForm"
          >
            Cancel
          </button>
          <button
            type="button"
            class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            :disabled="submitting"
            @click="submit"
          >
            {{ submitting ? 'Saving…' : 'Save schedule' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
