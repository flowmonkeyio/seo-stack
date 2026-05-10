<script setup lang="ts">
// OverviewTab — read-only project summary + recent runs.

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import KvList from '@/components/KvList.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  UiCallout,
  UiJsonBlock,
  UiPanel,
  UiSectionHeader,
} from '@/components/ui'
import { apiFetch } from '@/lib/client'
import { useProjectsStore } from '@/stores/projects'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type Run = components['schemas']['RunOut']
type RunsPage = components['schemas']['PageResponse_RunOut_']

const route = useRoute()
const projects = useProjectsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))
const project = computed(() => projects.getById(projectId.value))

const runs = ref<Run[]>([])
const runsLoading = ref(false)
const runsError = ref<string | null>(null)

const kvItems = computed(() => {
  const p = project.value
  if (!p) return []
  return [
    { key: 'created', label: 'Created', value: p.created_at },
    { key: 'updated', label: 'Updated', value: p.updated_at },
    { key: 'locale', label: 'Locale', value: p.locale },
    { key: 'niche', label: 'Niche', value: p.niche ?? '—' },
    { key: 'is_active', label: 'Active', value: p.is_active ? 'active' : 'inactive' },
    {
      key: 'schedule',
      label: 'Schedule',
      value: p.schedule_json ?? null,
    },
  ]
})

const runColumns: DataTableColumn<Run>[] = [
  { key: 'kind', label: 'Kind' },
  { key: 'status', label: 'Status' },
  {
    key: 'started_at',
    label: 'Started',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
  {
    key: 'ended_at',
    label: 'Ended',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
]

async function loadRuns(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  runsLoading.value = true
  runsError.value = null
  try {
    const params = new URLSearchParams({ limit: '10', sort: '-started_at' })
    const res = await apiFetch<RunsPage>(
      `/api/v1/projects/${projectId.value}/runs?${params.toString()}`,
    )
    runs.value = res.items ?? []
  } catch (err) {
    runsError.value = err instanceof Error ? err.message : 'failed to load runs'
  } finally {
    runsLoading.value = false
  }
}

onMounted(loadRuns)
watch(projectId, loadRuns)
</script>

<template>
  <section class="space-y-4">
    <UiPanel
      v-if="project"
      class="p-4"
    >
      <UiSectionHeader title="Project details" />
      <KvList :items="kvItems">
        <template #item:schedule="{ value }">
          <UiJsonBlock
            v-if="value"
            :data="value"
            density="compact"
            max-height="12rem"
          />
          <span
            v-else
            class="text-fg-muted"
          >—</span>
        </template>
      </KvList>
    </UiPanel>

    <UiPanel class="p-4">
      <UiSectionHeader
        title="Recent activity"
        description="Last 10 runs"
      />
      <UiCallout
        v-if="runsError"
        tone="danger"
        class="mb-3"
      >
        {{ runsError }}
      </UiCallout>
      <DataTable
        :items="runs"
        :columns="runColumns"
        :loading="runsLoading"
        empty-message="No runs yet."
        aria-label="Recent runs"
      >
        <template #cell:status="{ row }">
          <StatusBadge
            :status="(row as Run).status"
            kind="run"
          />
        </template>
      </DataTable>
    </UiPanel>
  </section>
</template>
