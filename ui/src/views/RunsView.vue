<script setup lang="ts">
// RunsView — audit trail with kind/status/parent filters.
//
// Per audit M-29: the per-step grain is shown in `RunDetailView` (sibling
// component) which is wired through the `:run_id?` sub-route. Selecting
// a row navigates to /projects/:id/runs/:run_id.
//
// Wires to:
// - `GET  /api/v1/projects/{id}/runs?kind=&status=&parent_run_id=&limit=&after=`
// - `POST /api/v1/runs/{id}/abort?cascade=true|false`
// - `POST /api/v1/runs/{id}/heartbeat`

import { computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import RunDetail from './RunDetail.vue'
import { useRunsStore, type Run } from '@/stores/runs'
import { useToastsStore } from '@/stores/toasts'
import { RunKind as RunKindEnum, RunStatus as RunStatusEnum } from '@/api'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const router = useRouter()
const runsStore = useRunsStore()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))
const runId = computed<number | null>(() => {
  const raw = route.params.run_id
  if (!raw || raw === '') return null
  const n = Number.parseInt(String(raw), 10)
  return Number.isNaN(n) ? null : n
})

const { filteredItems, loading, nextCursor, error, filters } = storeToRefs(runsStore)

const STATUS_OPTIONS: { key: 'all' | `${RunStatusEnum}`; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'running', label: 'Running' },
  { key: 'success', label: 'Success' },
  { key: 'failed', label: 'Failed' },
  { key: 'aborted', label: 'Aborted' },
]

const KIND_OPTIONS = Object.values(RunKindEnum)

const columns: DataTableColumn<Run>[] = [
  { key: 'id', label: 'ID', widthClass: 'w-20' },
  { key: 'kind', label: 'Kind' },
  { key: 'status', label: 'Status', widthClass: 'w-24' },
  { key: 'parent_run_id', label: 'Parent', widthClass: 'w-20' },
  {
    key: 'started_at',
    label: 'Started',
    sortable: true,
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
  {
    key: 'ended_at',
    label: 'Duration',
    format: (_v, row) => {
      const r = row as Run
      if (!r.ended_at) return r.status === 'running' ? 'running…' : '—'
      const ms = new Date(r.ended_at).getTime() - new Date(r.started_at).getTime()
      const s = Math.round(ms / 1000)
      return s < 60 ? `${s}s` : `${Math.round(s / 60)}m`
    },
    widthClass: 'w-24',
  },
  { key: 'last_step', label: 'Last step', format: (v) => (v as string) ?? '—' },
]

function setStatusFilter(opt: 'all' | `${RunStatusEnum}`): void {
  runsStore.setFilter('status', opt === 'all' ? null : (opt as RunStatusEnum))
  void runsStore.refresh(projectId.value)
}

function setKindFilter(value: string): void {
  runsStore.setFilter('kind', value === '' ? null : (value as RunKindEnum))
  void runsStore.refresh(projectId.value)
}

function setParentFilter(value: string): void {
  runsStore.setFilter('parent_run_id', value === '' ? null : Number.parseInt(value, 10))
  void runsStore.refresh(projectId.value)
}

function setSince(value: string): void {
  runsStore.setFilter('since', value === '' ? null : `${value}T00:00:00Z`)
}

function setUntil(value: string): void {
  runsStore.setFilter('until', value === '' ? null : `${value}T00:00:00Z`)
}

function onRowClick(row: Run): void {
  void router.push(`/projects/${projectId.value}/runs/${row.id}`)
}

async function abortRow(row: Run): Promise<void> {
  if (row.status !== 'running') return
  try {
    await runsStore.abort(row.id, true)
    toasts.success('Run aborted', `#${row.id}`)
  } catch (err) {
    toasts.error('Abort failed', err instanceof Error ? err.message : undefined)
  }
}

async function heartbeatRow(row: Run): Promise<void> {
  try {
    await runsStore.heartbeat(row.id)
    toasts.success('Heartbeat sent', `#${row.id}`)
  } catch (err) {
    toasts.error('Heartbeat failed', err instanceof Error ? err.message : undefined)
  }
}

async function loadMore(): Promise<void> {
  await runsStore.loadMore(projectId.value)
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  runsStore.reset()
  await runsStore.refresh(projectId.value)
}

onMounted(load)
watch(projectId, load)
watch(runId, () => {
  // The detail view loads its own data via the store; the watch is here so
  // the breadcrumb/title updates when the URL changes.
})
</script>

<template>
  <div class="mx-auto max-w-7xl">
    <header class="mb-4 flex flex-wrap items-baseline justify-between gap-3">
      <h1 class="text-2xl font-bold tracking-tight">
        Runs
        <span
          v-if="runId !== null"
          class="text-sm font-normal text-gray-500 dark:text-gray-400"
        >
          / #{{ runId }}
        </span>
      </h1>
      <div
        v-if="runId !== null"
        class="flex flex-wrap gap-2"
      >
        <button
          type="button"
          class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          @click="router.push(`/projects/${projectId}/runs`)"
        >
          ← Back to list
        </button>
      </div>
    </header>

    <p
      v-if="error"
      class="mb-3 rounded bg-red-50 p-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200"
    >
      {{ error }}
    </p>

    <RunDetail
      v-if="runId !== null"
      :key="runId"
      :run-id="runId"
      :project-id="projectId"
    />

    <div v-else>
      <div
        role="tablist"
        aria-label="Run status filter"
        class="mb-3 flex flex-wrap gap-1"
      >
        <button
          v-for="opt in STATUS_OPTIONS"
          :key="opt.key"
          type="button"
          role="tab"
          :aria-selected="(filters.status === null && opt.key === 'all') || filters.status === opt.key"
          class="rounded-full border px-3 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
          :class="
            (filters.status === null && opt.key === 'all') || filters.status === opt.key
              ? 'border-blue-600 bg-blue-50 font-medium text-blue-800 dark:border-blue-500 dark:bg-blue-900/40 dark:text-blue-200'
              : 'border-gray-300 text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800'
          "
          @click="setStatusFilter(opt.key)"
        >
          {{ opt.label }}
        </button>
      </div>

      <div class="mb-3 flex flex-wrap items-center gap-3 text-sm">
        <label class="flex items-center gap-2">
          <span class="text-gray-600 dark:text-gray-400">Kind</span>
          <select
            :value="filters.kind ?? ''"
            class="rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
            aria-label="Filter kind"
            @change="setKindFilter(($event.target as HTMLSelectElement).value)"
          >
            <option value="">
              All
            </option>
            <option
              v-for="k in KIND_OPTIONS"
              :key="k"
              :value="k"
            >
              {{ k }}
            </option>
          </select>
        </label>
        <label class="flex items-center gap-2">
          <span class="text-gray-600 dark:text-gray-400">Parent run id</span>
          <input
            type="number"
            min="1"
            :value="filters.parent_run_id ?? ''"
            class="w-24 rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
            aria-label="Parent run id"
            @change="setParentFilter(($event.target as HTMLInputElement).value)"
          >
        </label>
        <label class="flex items-center gap-2">
          <span class="text-gray-600 dark:text-gray-400">Since</span>
          <input
            type="date"
            class="rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
            aria-label="Since date"
            @change="setSince(($event.target as HTMLInputElement).value)"
          >
        </label>
        <label class="flex items-center gap-2">
          <span class="text-gray-600 dark:text-gray-400">Until</span>
          <input
            type="date"
            class="rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
            aria-label="Until date"
            @change="setUntil(($event.target as HTMLInputElement).value)"
          >
        </label>
      </div>

      <DataTable
        :items="filteredItems"
        :columns="columns"
        :loading="loading"
        :next-cursor="nextCursor"
        aria-label="Runs"
        empty-message="No runs match the filters."
        :sort-key="runsStore.sort.replace(/^-/, '')"
        :sort-dir="runsStore.sort.startsWith('-') ? 'desc' : 'asc'"
        @row-click="onRowClick"
        @sort="(col: string, dir: 'asc' | 'desc' | null) => runsStore.setSort(`${dir === 'desc' ? '-' : ''}${col}` as 'started_at' | '-started_at' | 'id' | '-id')"
        @load-more="loadMore"
      >
        <template #cell:status="{ row }">
          <div class="flex items-center gap-2">
            <StatusBadge
              :status="(row as Run).status"
              kind="run"
            />
            <button
              v-if="(row as Run).status === 'running'"
              type="button"
              class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
              :aria-label="`Abort run ${(row as Run).id}`"
              @click.stop="abortRow(row as Run)"
            >
              Abort
            </button>
            <button
              v-if="(row as Run).status === 'running'"
              type="button"
              class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
              :aria-label="`Heartbeat run ${(row as Run).id}`"
              @click.stop="heartbeatRow(row as Run)"
            >
              Heartbeat
            </button>
          </div>
        </template>
        <template #cell:parent_run_id="{ row }">
          <button
            v-if="(row as Run).parent_run_id !== null"
            type="button"
            class="text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:text-blue-300"
            @click.stop="router.push(`/projects/${projectId}/runs/${(row as Run).parent_run_id}`)"
          >
            #{{ (row as Run).parent_run_id }}
          </button>
          <span v-else>—</span>
        </template>
      </DataTable>
    </div>
  </div>
</template>
