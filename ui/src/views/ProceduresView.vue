<script setup lang="ts">
// ProceduresView — browse + run procedures + recent runs polling.
//
// Wires to:
// - `GET  /api/v1/procedures`              — list procedure summaries
// - `POST /api/v1/procedures/{slug}/run`   — enqueue daemon-side procedure runs
// - `GET  /api/v1/procedures/runs/{id}`    — `{run, steps[]}` for polling
// - `GET  /api/v1/projects/{id}/runs?kind=procedure`
//
// The "Run" button submits free-form JSON args. Recent runs poll every 5s
// for in-flight rows.

import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import TabBar from '@/components/TabBar.vue'
import {
  UiButton,
  UiCallout,
  UiDialog,
  UiPageShell,
} from '@/components/ui'
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
  if (!projectId.value || Number.isNaN(projectId.value)) {
    toasts.error('Run failed', 'Invalid project id')
    return
  }
  let args: Record<string, unknown> = {}
  try {
    args = JSON.parse(argsJson.value) as Record<string, unknown>
  } catch (err) {
    toasts.error('Invalid JSON', err instanceof Error ? err.message : undefined)
    return
  }
  submittingRun.value = true
  try {
    await proceduresStore.runProcedure(runOpen.value.slug, projectId.value, args)
    toasts.success('Procedure run started', runOpen.value.slug)
    runOpen.value = null
    await runsStore.refresh(projectId.value)
  } catch (err) {
    if (err instanceof ProcedureNotImplementedError) {
      toasts.info(
        'Procedure runner unavailable',
        'This daemon does not expose procedure execution.',
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
  <UiPageShell>
    <ProjectPageHeader
      :project-id="projectId"
      title="Procedures"
      description="Browse available content operations and inspect recent procedure runs for this project."
      :breadcrumbs="[{ label: 'Procedures' }]"
    >
      <template #tabs>
        <TabBar
          :tabs="tabs"
          :active-key="activeTab"
          aria-label="Procedure sections"
          @change="(key: string) => activeTab = key as 'list' | 'recent'"
        />
      </template>
    </ProjectPageHeader>

    <UiCallout
      v-if="error"
      tone="danger"
    >
      {{ error }}
    </UiCallout>

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
            <UiButton
              size="sm"
              variant="secondary"
              :aria-label="`Run procedure ${(row as ProcedureRow).slug}`"
              @click.stop="openRunModal(row as ProcedureRow)"
            >
              Run
            </UiButton>
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

    <UiDialog
      :model-value="runOpen !== null"
      :title="runOpen ? `Run procedure: ${runOpen.name}` : 'Run procedure'"
      size="lg"
      @update:model-value="(open: boolean) => open ? undefined : closeRunModal()"
    >
      <UiCallout
        tone="info"
        density="compact"
        class="mb-3"
      >
        Runs start immediately using the JSON args below.
      </UiCallout>
      <label class="mb-3 block text-sm">
        <span class="font-medium">Args (JSON)</span>
        <textarea
          v-model="argsJson"
          rows="6"
          class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs dark:border-gray-700 dark:bg-gray-800"
        />
      </label>
      <template #footer>
        <UiButton
          variant="secondary"
          :disabled="submittingRun"
          @click="closeRunModal"
        >
          Cancel
        </UiButton>
        <UiButton
          variant="primary"
          :loading="submittingRun"
          @click="submitRun"
        >
          Run procedure
        </UiButton>
      </template>
    </UiDialog>
  </UiPageShell>
</template>
