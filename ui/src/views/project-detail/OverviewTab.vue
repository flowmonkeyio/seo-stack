<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { UiBadge, UiButton, UiCallout, UiCard, UiMetricCard, UiSectionHeader } from '@/components/ui'
import type { DataTableColumn } from '@/components/types'
import { apiFetch, formatApiError } from '@/lib/client'
import { formatDateTime } from '@/lib/stackos/json'
import type {
  SchemaAuthStatusOut,
  SchemaIntegrationBudgetOut,
  SchemaPageResponseResourceRecordOut,
  SchemaPageResponseRunOut,
  SchemaPluginOut,
  SchemaResourceRecordOut,
  SchemaRunOut,
  SchemaScheduledJobOut,
  SchemaWorkflowTemplateListOut,
} from '@/api'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => Number.parseInt(route.params.id as string, 10))
const loading = ref(false)
const error = ref<string | null>(null)
const plugins = ref<SchemaPluginOut[]>([])
const templates = ref(0)
const runPlans = ref(0)
const resourceRecords = ref<SchemaResourceRecordOut[]>([])
const runs = ref<SchemaRunOut[]>([])
const connections = ref(0)
const schedules = ref<SchemaScheduledJobOut[]>([])
const budgets = ref<SchemaIntegrationBudgetOut[]>([])

const enabledPlugins = computed(() =>
  plugins.value.filter((plugin) => plugin.enabled_for_project !== false),
)
const activeSchedules = computed(() => schedules.value.filter((schedule) => schedule.enabled))
const activeBudgets = computed(() => budgets.value.filter((budget) => budget.monthly_budget_usd > 0))
const runningRuns = computed(() => runs.value.filter((run) => run.status === 'running'))
const failedRuns = computed(() =>
  runs.value.filter((run) => run.status === 'failed' || run.status === 'aborted'),
)

const runColumns: DataTableColumn<SchemaRunOut>[] = [
  { key: 'kind', label: 'Kind' },
  { key: 'status', label: 'Status' },
  { key: 'last_step', label: 'Last step', format: (value) => String(value ?? '-') },
  { key: 'started_at', label: 'Started', format: (value) => formatDateTime(String(value)) },
]

const resourceColumns: DataTableColumn<SchemaResourceRecordOut>[] = [
  { key: 'plugin_slug', label: 'Plugin' },
  { key: 'resource_key', label: 'Resource' },
  { key: 'title', label: 'Title', format: (value) => String(value ?? '-') },
  { key: 'updated_at', label: 'Updated', format: (value) => formatDateTime(String(value)) },
]

async function fetchOr<T>(path: string, fallback: T): Promise<T> {
  try {
    return await apiFetch<T>(path)
  } catch {
    return fallback
  }
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  loading.value = true
  error.value = null
  try {
    const id = projectId.value
    const [pluginRows, templateRows, runPage, resourcePage, authStatus, scheduleRows, budgetRows] =
      await Promise.all([
        apiFetch<SchemaPluginOut[]>(`/api/v1/plugins?project_id=${id}`),
        fetchOr<SchemaWorkflowTemplateListOut>(
          `/api/v1/projects/${id}/workflow-templates`,
          { templates: [], include_shadowed: false },
        ),
        fetchOr<SchemaPageResponseRunOut>(
          `/api/v1/projects/${id}/runs?limit=8`,
          { items: [], next_cursor: null, total_estimate: 0 },
        ),
        fetchOr<SchemaPageResponseResourceRecordOut>(
          `/api/v1/projects/${id}/resource-records?limit=8`,
          { items: [], next_cursor: null, total_estimate: 0 },
        ),
        fetchOr<SchemaAuthStatusOut>(
          `/api/v1/projects/${id}/auth/status`,
          { project_id: id, provider_key: null, providers: [], connections: [] },
        ),
        fetchOr<SchemaScheduledJobOut[]>(`/api/v1/projects/${id}/schedules`, []),
        fetchOr<SchemaIntegrationBudgetOut[]>(`/api/v1/projects/${id}/budgets`, []),
      ])
    plugins.value = pluginRows
    templates.value = templateRows.templates.length
    runs.value = runPage.items
    runPlans.value = runs.value.filter((run) => run.kind === 'run-plan').length
    resourceRecords.value = resourcePage.items
    connections.value = authStatus.connections.filter(
      (connection) => connection.status !== 'revoked',
    ).length
    schedules.value = scheduleRows
    budgets.value = budgetRows
  } catch (err) {
    error.value = formatApiError(err, 'failed to load project overview')
  } finally {
    loading.value = false
  }
}

function go(path: string): void {
  void router.push(`/projects/${projectId.value}/${path}`)
}

onMounted(load)
</script>

<template>
  <div class="space-y-5">
    <UiCallout
      v-if="error"
      tone="danger"
    >
      {{ error }}
    </UiCallout>

    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <UiMetricCard
        label="Enabled plugins"
        :value="enabledPlugins.length"
      />
      <UiMetricCard
        label="Workflow templates"
        :value="templates"
      />
      <UiMetricCard
        label="Resource records"
        :value="resourceRecords.length"
      />
      <UiMetricCard
        label="Connections"
        :value="connections"
      />
    </div>

    <div class="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
      <section aria-label="Recent runs">
        <UiSectionHeader
          title="Recent runs"
          as="h3"
        >
          <template #actions>
            <UiBadge
              v-if="runningRuns.length"
              tone="info"
              dot
              pulse
            >
              {{ runningRuns.length }} running
            </UiBadge>
            <UiBadge
              v-if="failedRuns.length"
              tone="danger"
            >
              {{ failedRuns.length }} need review
            </UiBadge>
            <UiButton
              size="sm"
              variant="secondary"
              @click="go('runs')"
            >
              View all
            </UiButton>
          </template>
        </UiSectionHeader>
        <DataTable
          :items="runs"
          :columns="runColumns"
          :loading="loading"
          aria-label="Recent runs"
          empty-message="No runs yet — agents create runs when they execute workflows."
        >
          <template #cell:status="{ value }">
            <StatusBadge
              :status="String(value)"
              kind="run"
            />
          </template>
        </DataTable>
      </section>

      <UiCard section>
        <template #header>
          <h3 class="t-h3 text-fg-strong">
            Setup
          </h3>
          <UiButton
            size="sm"
            variant="secondary"
            @click="go('connections')"
          >
            Connections
          </UiButton>
        </template>
        <dl class="grid gap-3 text-sm">
          <div class="flex items-center justify-between gap-3">
            <dt class="text-fg-muted">Active schedules</dt>
            <dd class="font-medium tabular-nums text-fg-strong">{{ activeSchedules.length }}</dd>
          </div>
          <div class="flex items-center justify-between gap-3">
            <dt class="text-fg-muted">Budgets</dt>
            <dd class="font-medium tabular-nums text-fg-strong">{{ activeBudgets.length }}</dd>
          </div>
          <div class="flex items-center justify-between gap-3">
            <dt class="text-fg-muted">Run-plan audit rows</dt>
            <dd class="font-medium tabular-nums text-fg-strong">{{ runPlans }}</dd>
          </div>
        </dl>
        <div class="mt-4 flex flex-wrap gap-2 border-t border-subtle pt-3">
          <UiButton
            size="sm"
            variant="ghost"
            icon-left="puzzle"
            @click="go('plugins')"
          >
            Plugins
          </UiButton>
          <UiButton
            size="sm"
            variant="ghost"
            icon-left="library"
            @click="go('workflow-templates')"
          >
            Templates
          </UiButton>
          <UiButton
            size="sm"
            variant="ghost"
            icon-left="folder"
            @click="go('resources')"
          >
            Resources
          </UiButton>
        </div>
      </UiCard>
    </div>

    <section aria-label="Latest resource records">
      <UiSectionHeader
        title="Latest resource records"
        as="h3"
      >
        <template #actions>
          <UiButton
            size="sm"
            variant="secondary"
            @click="go('resources')"
          >
            View all
          </UiButton>
        </template>
      </UiSectionHeader>
      <DataTable
        :items="resourceRecords"
        :columns="resourceColumns"
        :loading="loading"
        aria-label="Latest resource records"
        empty-message="No resource records yet — records appear as plugins store data."
      >
        <template #cell:plugin_slug="{ value }">
          <UiBadge tone="accent">{{ value }}</UiBadge>
        </template>
      </DataTable>
    </section>
  </div>
</template>
