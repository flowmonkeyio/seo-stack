<script setup lang="ts">
// ProceduresView — browse + run procedures + recent runs polling.
//
// Wires to:
// - `GET  /api/v1/procedures`              — list procedure summaries
// - `POST /api/v1/procedures/{slug}/run`   — currently 501 at M5.C (M7)
// - `GET  /api/v1/procedures/runs/{id}`    — `{run, steps[]}` for polling
// - `GET  /api/v1/projects/{id}/runs?kind=procedure`
//
// The "Run" button submits free-form JSON args and surfaces the 501 +
// "Will be available in M7" hint per the milestone scope. Recent runs
// poll every 5s for in-flight rows.

import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import TabBar from '@/components/TabBar.vue'
import {
  ProcedureNotImplementedError,
  useProceduresStore,
  type ProcedureSummary,
} from '@/stores/procedures'
import { useRunsStore, type Run } from '@/stores/runs'
import { useToastsStore } from '@/stores/toasts'
import { RunKind as RunKindEnum } from '@/api'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const router = useRouter()
const proceduresStore = useProceduresStore()
const runsStore = useRunsStore()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { items, loading, error } = storeToRefs(proceduresStore)
const { items: runs } = storeToRefs(runsStore)

const activeTab = ref<'list' | 'recent'>('list')
const runOpen = ref<ProcedureSummary | null>(null)
const argsJson = ref<string>('{}')
const submittingRun = ref(false)
const pollHandle = ref<ReturnType<typeof setInterval> | null>(null)

const tabs = [
  { key: 'list', label: 'Available' },
  { key: 'recent', label: 'Recent Runs' },
]

/** ProcedureSummary doesn't carry a numeric id — DataTable's row contract
 *  needs `id: number | string`. We synthesize `id = slug` so the existing
 *  generic table renders. */
interface ProcedureRow extends ProcedureSummary {
  id: string
}

const procedureRows = computed<ProcedureRow[]>(() =>
  items.value.map((p) => ({ ...p, id: p.slug })),
)

const columns: DataTableColumn<ProcedureRow>[] = [
  { key: 'slug', label: 'Slug', cellClass: 'font-mono text-sm' },
  { key: 'name', label: 'Name' },
  { key: 'version', label: 'Version', format: (v) => (v as string) ?? '—', widthClass: 'w-24' },
  {
    key: 'description',
    label: 'Description',
    format: (v) => (v as string) ?? '—',
  },
]

const recentRunColumns: DataTableColumn<Run>[] = [
  { key: 'id', label: 'ID', widthClass: 'w-16' },
  { key: 'procedure_slug', label: 'Procedure', format: (v) => (v as string) ?? '—' },
  { key: 'status', label: 'Status', widthClass: 'w-24' },
  {
    key: 'started_at',
    label: 'Started',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
]

const procedureRuns = computed<Run[]>(() => runs.value.filter((r) => r.kind === 'procedure'))

function openRunModal(p: ProcedureSummary): void {
  runOpen.value = p
  argsJson.value = '{}'
}

function closeRunModal(): void {
  if (submittingRun.value) return
  runOpen.value = null
}

async function submitRun(): Promise<void> {
  if (!runOpen.value) return
  let args: Record<string, unknown> = {}
  try {
    args = JSON.parse(argsJson.value) as Record<string, unknown>
  } catch (err) {
    toasts.error('Invalid JSON', err instanceof Error ? err.message : undefined)
    return
  }
  submittingRun.value = true
  try {
    await proceduresStore.runProcedure(runOpen.value.slug, args)
    toasts.success('Procedure run started', runOpen.value.slug)
    runOpen.value = null
    await runsStore.refresh(projectId.value)
  } catch (err) {
    if (err instanceof ProcedureNotImplementedError) {
      toasts.info(
        'Procedure runner not yet available',
        'The runner ships in M7 — the route is wired but returns 501 today.',
      )
    } else {
      toasts.error('Run failed', err instanceof Error ? err.message : undefined)
    }
  } finally {
    submittingRun.value = false
  }
}

function openRunDetail(row: Run): void {
  void router.push(`/projects/${projectId.value}/runs/${row.id}`)
}

async function refreshRecentRuns(): Promise<void> {
  // Filter to procedure-kind runs only.
  runsStore.setFilter('kind', RunKindEnum.procedure)
  await runsStore.refresh(projectId.value)
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  proceduresStore.reset()
  await Promise.all([proceduresStore.refresh(), refreshRecentRuns()])
}

function startPolling(): void {
  if (pollHandle.value !== null) return
  pollHandle.value = setInterval(() => {
    if (activeTab.value !== 'recent') return
    const hasRunning = procedureRuns.value.some((r) => r.status === 'running')
    if (hasRunning) {
      void refreshRecentRuns()
    }
  }, 5000)
}

function stopPolling(): void {
  if (pollHandle.value !== null) {
    clearInterval(pollHandle.value)
    pollHandle.value = null
  }
}

onMounted(() => {
  void load()
  startPolling()
})

onUnmounted(stopPolling)

watch(projectId, load)
watch(activeTab, async (tab) => {
  if (tab === 'recent') await refreshRecentRuns()
})
</script>

<template>
  <div class="mx-auto max-w-6xl">
    <header class="mb-4 flex flex-wrap items-baseline justify-between gap-3">
      <h1 class="text-2xl font-bold tracking-tight">
        Procedures
      </h1>
    </header>

    <p
      v-if="error"
      class="mb-3 rounded bg-red-50 p-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200"
    >
      {{ error }}
    </p>

    <TabBar
      :tabs="tabs"
      :active-key="activeTab"
      aria-label="Procedure sections"
      @change="(key: string) => activeTab = key as 'list' | 'recent'"
    />

    <div
      :id="`cs-tabpanel-${activeTab}`"
      role="tabpanel"
      :aria-labelledby="`cs-tab-${activeTab}`"
      class="mt-4"
    >
      <DataTable
        v-if="activeTab === 'list'"
        :items="procedureRows"
        :columns="columns"
        :loading="loading"
        aria-label="Available procedures"
        empty-message="No procedures registered."
      >
        <template #cell:description="{ row }">
          <div class="flex items-center justify-between gap-3">
            <span>{{ (row as ProcedureRow).description ?? '—' }}</span>
            <button
              type="button"
              class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
              :aria-label="`Run procedure ${(row as ProcedureRow).slug}`"
              @click.stop="openRunModal(row as ProcedureRow)"
            >
              Run
            </button>
          </div>
        </template>
      </DataTable>

      <DataTable
        v-if="activeTab === 'recent'"
        :items="procedureRuns"
        :columns="recentRunColumns"
        :loading="loading"
        aria-label="Recent procedure runs"
        empty-message="No procedure runs yet."
        @row-click="openRunDetail"
      >
        <template #cell:status="{ row }">
          <StatusBadge
            :status="(row as Run).status"
            kind="run"
          />
        </template>
      </DataTable>
    </div>

    <!-- Run procedure modal -->
    <div
      v-if="runOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-procedure-run-title"
      @click.self="closeRunModal"
    >
      <div
        class="w-full max-w-lg rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h2
          id="cs-procedure-run-title"
          class="mb-3 text-lg font-semibold"
        >
          Run procedure: {{ runOpen.name }}
        </h2>
        <p class="mb-3 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
          Procedure runner ships in <strong>M7</strong>. The route is wired and
          returns 501 at M5.C — you'll see a "not yet available" toast when
          you submit. Once M7 lands, the daemon will accept these args and
          orchestrate the per-skill LLM sessions.
        </p>
        <label class="mb-3 block text-sm">
          <span class="font-medium">Args (JSON)</span>
          <textarea
            v-model="argsJson"
            rows="6"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs dark:border-gray-700 dark:bg-gray-800"
          />
        </label>
        <div class="flex justify-end gap-2">
          <button
            type="button"
            class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            :disabled="submittingRun"
            @click="closeRunModal"
          >
            Cancel
          </button>
          <button
            type="button"
            class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            :disabled="submittingRun"
            @click="submitRun"
          >
            {{ submittingRun ? 'Submitting…' : 'Run procedure' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
