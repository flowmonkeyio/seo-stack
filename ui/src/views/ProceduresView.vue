<script setup lang="ts">
// ProceduresView — browse procedures + recent runs polling.

import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { UiButton, UiCallout, UiEmptyState, UiPageShell } from '@/components/ui'
import { RunKind as RunKindEnum } from '@/api'
import { useProceduresStore, type ProcedureSummary } from '@/stores/procedures'
import { useRunsStore, type Run } from '@/stores/runs'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const router = useRouter()
const proceduresStore = useProceduresStore()
const runsStore = useRunsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { items, loading, error } = storeToRefs(proceduresStore)
const { items: runs } = storeToRefs(runsStore)

const pollHandle = ref<ReturnType<typeof setInterval> | null>(null)

interface ProcedureRow extends ProcedureSummary {
  id: string
}

const procedureRows = computed<ProcedureRow[]>(() =>
  items.value.map((p) => ({ ...p, id: p.slug })),
)

const columns: DataTableColumn<ProcedureRow>[] = [
  { key: 'name', label: 'Operation' },
  {
    key: 'description',
    label: 'Purpose',
    format: (v) => cleanDescription(v),
  },
  { key: 'version', label: 'Version', format: (v) => (v as string) ?? '-', widthClass: 'w-24' },
]

const recentRunColumns: DataTableColumn<Run>[] = [
  { key: 'id', label: 'ID', widthClass: 'w-16' },
  { key: 'procedure_slug', label: 'Procedure', format: (v) => (v as string) ?? '-' },
  { key: 'status', label: 'Status', widthClass: 'w-24' },
  {
    key: 'started_at',
    label: 'Started',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
]

const procedureRuns = computed<Run[]>(() => runs.value.filter((r) => r.kind === 'procedure'))

function titleCaseProcedure(value: string): string {
  return value
    .replace(/^\d+-/, '')
    .split('-')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function cleanDescription(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : ''
  if (!text || text === '|' || text === '-') return 'No description provided.'
  return text
}

function clearProcedureQuery(): void {
  const slug = typeof route.query.procedure === 'string' ? route.query.procedure : ''
  if (!slug) return
  const query = { ...route.query }
  delete query.procedure
  delete query.topic_id
  void router.replace({ query })
}

function openRunDetail(row: Run): void {
  void router.push(`/projects/${projectId.value}/runs/${row.id}`)
}

async function refreshRecentRuns(): Promise<void> {
  runsStore.setFilter('kind', RunKindEnum.procedure)
  await runsStore.refresh(projectId.value)
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  proceduresStore.reset()
  await Promise.all([proceduresStore.refresh(), refreshRecentRuns()])
  clearProcedureQuery()
}

function startPolling(): void {
  if (pollHandle.value !== null) return
  pollHandle.value = setInterval(() => {
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
watch(() => route.query.procedure, clearProcedureQuery)
</script>

<template>
  <UiPageShell>
    <ProjectPageHeader
      :project-id="projectId"
      title="Procedures"
      description="Browse available content operations and inspect recent procedure runs for this project."
      :breadcrumbs="[{ label: 'Procedures' }]"
    />

    <UiCallout
      v-if="error"
      tone="danger"
    >
      {{ error }}
    </UiCallout>

    <div class="grid gap-6">
      <section
        class="rounded-md border border-default bg-bg-surface shadow-xs"
        aria-labelledby="cs-procedures-available"
      >
        <div class="border-b border-subtle px-4 py-3">
          <h2
            id="cs-procedures-available"
            class="text-sm font-semibold text-fg-strong"
          >
            Available procedures
          </h2>
          <p class="mt-0.5 text-sm text-fg-muted">
            Agent-run operations available for this project.
          </p>
        </div>
        <div class="p-3">
          <DataTable
            :items="procedureRows"
            :columns="columns"
            :loading="loading"
            aria-label="Available procedures"
            empty-message="No procedures registered."
          >
            <template #cell:name="{ row }">
              <div>
                <div class="font-medium text-fg-strong">
                  {{ titleCaseProcedure((row as ProcedureRow).name || (row as ProcedureRow).slug) }}
                </div>
                <div class="mt-0.5 font-mono text-xs text-fg-muted">
                  {{ (row as ProcedureRow).slug }}
                </div>
              </div>
            </template>
            <template #cell:description="{ row }">
              <div class="flex items-center justify-between gap-3">
                <span>{{ cleanDescription((row as ProcedureRow).description) }}</span>
                <span
                  class="rounded-sm border border-subtle bg-bg-surface-alt px-2 py-1 text-xs font-medium text-fg-muted"
                >
                  Agent-owned
                </span>
              </div>
            </template>
          </DataTable>
        </div>
      </section>

      <section
        class="rounded-md border border-default bg-bg-surface shadow-xs"
        aria-labelledby="cs-procedures-recent"
      >
        <div class="flex flex-wrap items-center justify-between gap-3 border-b border-subtle px-4 py-3">
          <div>
            <h2
              id="cs-procedures-recent"
              class="text-sm font-semibold text-fg-strong"
            >
              Recent procedure runs
            </h2>
            <p class="mt-0.5 text-sm text-fg-muted">
              Inspect recent execution without leaving this workflow.
            </p>
          </div>
          <UiButton
            size="sm"
            variant="secondary"
            @click="router.push(`/projects/${projectId}/runs`)"
          >
            Open run audit
          </UiButton>
        </div>
        <div class="p-3">
          <DataTable
            v-show="procedureRuns.length > 0 || loading"
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
          <UiEmptyState
            v-if="!loading && procedureRuns.length === 0"
            title="No procedure runs yet"
            description="No agent procedure runs are recorded for this project yet."
            size="sm"
          />
        </div>
      </section>
    </div>
  </UiPageShell>
</template>
