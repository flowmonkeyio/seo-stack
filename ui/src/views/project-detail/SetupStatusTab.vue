<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  UiBadge,
  UiButton,
  UiCallout,
  UiMetricCard,
  UiPanel,
  UiProgressBar,
  UiSectionHeader,
} from '@/components/ui'
import type {
  SchemaActionOut,
  SchemaAuthProviderOut,
  SchemaAuthStatusOut,
  SchemaHealthResponse,
  SchemaPageResponseRunOut,
  SchemaPluginOut,
  SchemaWorkflowTemplateListOut,
} from '@/api'
import { apiFetch, formatApiError } from '@/lib/client'

type ChecklistStatus = 'done' | 'todo' | 'attention'

interface ChecklistItem {
  key: string
  label: string
  detail: string
  status: ChecklistStatus
  to?: string
}

const route = useRoute()
const router = useRouter()

const projectId = computed(() => Number.parseInt(route.params.id as string, 10))
const loading = ref(false)
const error = ref<string | null>(null)
const health = ref<SchemaHealthResponse | null>(null)
const plugins = ref<SchemaPluginOut[]>([])
const authProviders = ref<SchemaAuthProviderOut[]>([])
const authStatus = ref<SchemaAuthStatusOut | null>(null)
const templates = ref(0)
const actions = ref(0)
const runPlans = ref(0)

const enabledPlugins = computed(() =>
  plugins.value.filter((plugin) => plugin.enabled_for_project !== false),
)

const activeConnections = computed(() =>
  (authStatus.value?.connections ?? []).filter((connection) => connection.revoked_at === null),
)

const connectedConnections = computed(() =>
  activeConnections.value.filter((connection) => connection.status === 'connected'),
)

const checklist = computed<ChecklistItem[]>(() => {
  const id = projectId.value
  const healthReady = health.value !== null
  return [
    {
      key: 'daemon',
      label: 'Daemon',
      detail: healthReady ? `${health.value?.version ?? '-'} on 127.0.0.1` : 'Unavailable',
      status: healthReady ? 'done' : 'attention',
    },
    {
      key: 'database',
      label: 'Database',
      detail: health.value?.db_status ?? 'Unknown',
      status: health.value?.db_status === 'ok' ? 'done' : 'attention',
    },
    {
      key: 'scheduler',
      label: 'Scheduler',
      detail: health.value?.scheduler_running ? 'Running' : 'Stopped',
      status: health.value?.scheduler_running ? 'done' : 'attention',
    },
    {
      key: 'project',
      label: 'Project',
      detail: Number.isNaN(id) ? 'Not selected' : `#${id}`,
      status: Number.isNaN(id) ? 'attention' : 'done',
    },
    {
      key: 'plugins',
      label: 'Enabled plugins',
      detail: `${enabledPlugins.value.length} of ${plugins.value.length}`,
      status: enabledPlugins.value.length > 0 ? 'done' : 'todo',
      to: 'plugins',
    },
    {
      key: 'providers',
      label: 'Provider methods',
      detail: `${authProviders.value.length} available`,
      status: authProviders.value.length > 0 ? 'done' : 'attention',
      to: 'connections',
    },
    {
      key: 'connections',
      label: 'Connections',
      detail: `${connectedConnections.value.length} connected`,
      status: connectedConnections.value.length > 0 ? 'done' : 'todo',
      to: 'connections',
    },
    {
      key: 'templates',
      label: 'Workflow templates',
      detail: `${templates.value} available`,
      status: templates.value > 0 ? 'done' : 'todo',
      to: 'workflow-templates',
    },
    {
      key: 'actions',
      label: 'Action contracts',
      detail: `${actions.value} callable contracts`,
      status: actions.value > 0 ? 'done' : 'attention',
      to: 'operations',
    },
    {
      key: 'runs',
      label: 'Run plans',
      detail: runPlans.value > 0 ? 'Existing run history' : 'None yet',
      status: runPlans.value > 0 ? 'done' : 'todo',
      to: 'runs',
    },
  ]
})

const readyItems = computed(() => checklist.value.filter((item) => item.status === 'done'))
const attentionItems = computed(() => checklist.value.filter((item) => item.status === 'attention'))
const todoItems = computed(() => checklist.value.filter((item) => item.status === 'todo'))
const readiness = computed(() =>
  Math.round((readyItems.value.length / checklist.value.length) * 100),
)

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
    const [healthRow, pluginRows, providerRows, statusRow, templateRows, actionRows, runPage] =
      await Promise.all([
        fetchOr<SchemaHealthResponse | null>('/api/v1/health', null),
        apiFetch<SchemaPluginOut[]>(`/api/v1/plugins?project_id=${id}`),
        fetchOr<SchemaAuthProviderOut[]>('/api/v1/auth/providers', []),
        fetchOr<SchemaAuthStatusOut>(`/api/v1/projects/${id}/auth/status`, {
          project_id: id,
          provider_key: null,
          providers: [],
          connections: [],
        }),
        fetchOr<SchemaWorkflowTemplateListOut>(`/api/v1/projects/${id}/workflow-templates`, {
          templates: [],
          include_shadowed: false,
        }),
        fetchOr<SchemaActionOut[]>(`/api/v1/actions?project_id=${id}`, []),
        fetchOr<SchemaPageResponseRunOut>(`/api/v1/projects/${id}/runs?kind=run-plan&limit=1`, {
          items: [],
          next_cursor: null,
          total_estimate: 0,
        }),
      ])
    health.value = healthRow
    plugins.value = pluginRows
    authProviders.value = providerRows
    authStatus.value = statusRow
    templates.value = templateRows.templates.length
    actions.value = actionRows.length
    runPlans.value = runPage.total_estimate ?? runPage.items.length
  } catch (err) {
    error.value = formatApiError(err, 'failed to load setup status')
  } finally {
    loading.value = false
  }
}

function go(path: string): void {
  void router.push(`/projects/${projectId.value}/${path}`)
}

function statusTone(status: ChecklistStatus): 'success' | 'warning' | 'danger' {
  if (status === 'done') return 'success'
  if (status === 'todo') return 'warning'
  return 'danger'
}

function statusLabel(status: ChecklistStatus): string {
  if (status === 'done') return 'Ready'
  if (status === 'todo') return 'Open'
  return 'Check'
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <div class="space-y-4">
    <UiCallout v-if="error" tone="danger">
      {{ error }}
    </UiCallout>

    <div class="grid gap-3 md:grid-cols-4">
      <UiMetricCard label="Readiness" :value="`${readiness}%`" />
      <UiMetricCard label="Ready" :value="readyItems.length" />
      <UiMetricCard label="Open" :value="todoItems.length" />
      <UiMetricCard label="Check" :value="attentionItems.length" />
    </div>

    <UiPanel class="p-4">
      <UiSectionHeader title="Setup Status" as="h3">
        <template #actions>
          <UiBadge
            :tone="
              attentionItems.length > 0 ? 'danger' : todoItems.length > 0 ? 'warning' : 'success'
            "
          >
            {{ readyItems.length }} / {{ checklist.length }}
          </UiBadge>
          <UiButton size="sm" variant="secondary" :disabled="loading" @click="load">
            Refresh
          </UiButton>
        </template>
      </UiSectionHeader>

      <UiProgressBar
        :value="readyItems.length"
        :max="checklist.length"
        :tone="attentionItems.length > 0 ? 'danger' : todoItems.length > 0 ? 'warning' : 'success'"
        show-label
        aria-label="Setup readiness"
      />

      <div class="mt-4 grid gap-2 md:grid-cols-2">
        <div
          v-for="item in checklist"
          :key="item.key"
          class="flex min-h-16 items-center justify-between gap-3 rounded-md border border-subtle bg-bg-surface-alt px-3 py-2"
        >
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <UiBadge :tone="statusTone(item.status)" dot>
                {{ statusLabel(item.status) }}
              </UiBadge>
              <p class="truncate text-sm font-medium text-fg-strong">
                {{ item.label }}
              </p>
            </div>
            <p class="mt-1 truncate text-xs text-fg-muted">
              {{ item.detail }}
            </p>
          </div>
          <UiButton v-if="item.to" size="sm" variant="ghost" @click="go(item.to)"> Open </UiButton>
        </div>
      </div>
    </UiPanel>

    <div class="grid gap-4 lg:grid-cols-3">
      <UiPanel class="p-4">
        <UiSectionHeader title="Runtime" as="h3" />
        <dl class="grid gap-3 text-sm">
          <div class="flex items-center justify-between gap-3">
            <dt class="text-fg-muted">Version</dt>
            <dd class="font-medium">{{ health?.version ?? '-' }}</dd>
          </div>
          <div class="flex items-center justify-between gap-3">
            <dt class="text-fg-muted">Database</dt>
            <dd class="font-medium">{{ health?.db_status ?? '-' }}</dd>
          </div>
          <div class="flex items-center justify-between gap-3">
            <dt class="text-fg-muted">Scheduler</dt>
            <dd class="font-medium">{{ health?.scheduler_running ? 'running' : '-' }}</dd>
          </div>
        </dl>
      </UiPanel>

      <UiPanel class="p-4">
        <UiSectionHeader title="Project Surface" as="h3" />
        <dl class="grid gap-3 text-sm">
          <div class="flex items-center justify-between gap-3">
            <dt class="text-fg-muted">Installed plugins</dt>
            <dd class="font-medium">{{ plugins.length }}</dd>
          </div>
          <div class="flex items-center justify-between gap-3">
            <dt class="text-fg-muted">Templates</dt>
            <dd class="font-medium">{{ templates }}</dd>
          </div>
          <div class="flex items-center justify-between gap-3">
            <dt class="text-fg-muted">Actions</dt>
            <dd class="font-medium">{{ actions }}</dd>
          </div>
        </dl>
      </UiPanel>

      <UiPanel class="p-4">
        <UiSectionHeader title="Connections" as="h3" />
        <dl class="grid gap-3 text-sm">
          <div class="flex items-center justify-between gap-3">
            <dt class="text-fg-muted">Providers</dt>
            <dd class="font-medium">{{ authProviders.length }}</dd>
          </div>
          <div class="flex items-center justify-between gap-3">
            <dt class="text-fg-muted">Active</dt>
            <dd class="font-medium">{{ activeConnections.length }}</dd>
          </div>
          <div class="flex items-center justify-between gap-3">
            <dt class="text-fg-muted">Connected</dt>
            <dd class="font-medium">{{ connectedConnections.length }}</dd>
          </div>
        </dl>
      </UiPanel>
    </div>
  </div>
</template>
