<script setup lang="ts">
// OverviewTab — project operator dashboard.

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  UiButton,
  UiCallout,
  UiMetricCard,
  UiPanel,
  UiSectionHeader,
} from '@/components/ui'
import { apiFetch } from '@/lib/client'
import { useProjectsStore } from '@/stores/projects'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type Article = components['schemas']['ArticleOut']
type ArticlesPage = components['schemas']['PageResponse_ArticleOut_']
type ComplianceRule = components['schemas']['ComplianceRuleOut']
type EeatCriterion = components['schemas']['EeatCriterionOut']
type Integration = components['schemas']['IntegrationCredentialOut']
type Run = components['schemas']['RunOut']
type RunsPage = components['schemas']['PageResponse_RunOut_']
type Schedule = components['schemas']['ScheduledJobOut']
type Target = components['schemas']['PublishTargetOut']
type Topic = components['schemas']['TopicOut']
type TopicsPage = components['schemas']['PageResponse_TopicOut_']
type VoicesPage = components['schemas']['PageResponse_VoiceProfileOut_']

interface Page<T> {
  items: T[]
  total_estimate?: number | null
  next_cursor?: number | null
}

interface ReadinessItem {
  key: string
  label: string
  detail: string
  ready: boolean
  to: string
}

interface NextAction {
  label: string
  detail: string
  to: string
  variant?: 'primary' | 'secondary'
}

const route = useRoute()
const router = useRouter()
const projects = useProjectsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))
const project = computed(() => projects.getById(projectId.value))

const loading = ref(false)
const warnings = ref<string[]>([])
const runs = ref<Run[]>([])
const topics = ref<Topic[]>([])
const articles = ref<Article[]>([])
const targets = ref<Target[]>([])
const integrations = ref<Integration[]>([])
const schedules = ref<Schedule[]>([])
const voiceTotal = ref(0)
const compliance = ref<ComplianceRule[]>([])
const eeat = ref<EeatCriterion[]>([])

const runColumns: DataTableColumn<Run>[] = [
  { key: 'kind', label: 'Kind' },
  { key: 'status', label: 'Status' },
  {
    key: 'started_at',
    label: 'Started',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
  {
    key: 'last_step',
    label: 'Last step',
    format: (v) => (v ? String(v) : '—'),
  },
]

function emptyPage<T>(): Page<T> {
  return { items: [], total_estimate: 0, next_cursor: null }
}

async function fetchOr<T>(label: string, path: string, fallback: T): Promise<T> {
  try {
    return await apiFetch<T>(path)
  } catch (err) {
    warnings.value.push(`${label}: ${err instanceof Error ? err.message : 'request failed'}`)
    return fallback
  }
}

async function loadDashboard(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  loading.value = true
  warnings.value = []
  try {
    if (projects.items.length === 0) {
      await projects.refresh()
    }

    const id = projectId.value
    const [
      runsPage,
      topicsPage,
      articlesPage,
      targetRows,
      integrationRows,
      scheduleRows,
      voicesPage,
      complianceRows,
      eeatRows,
    ] = await Promise.all([
      fetchOr<RunsPage>('Runs', `/api/v1/projects/${id}/runs?limit=10&sort=-started_at`, emptyPage<Run>() as RunsPage),
      fetchOr<TopicsPage>('Topics', `/api/v1/projects/${id}/topics?limit=200&sort=priority`, emptyPage<Topic>() as TopicsPage),
      fetchOr<ArticlesPage>('Articles', `/api/v1/projects/${id}/articles?limit=200`, emptyPage<Article>() as ArticlesPage),
      fetchOr<Target[]>('Publish targets', `/api/v1/projects/${id}/publish-targets`, []),
      fetchOr<Integration[]>('Integrations', `/api/v1/projects/${id}/integrations`, []),
      fetchOr<Schedule[]>('Schedules', `/api/v1/projects/${id}/schedules`, []),
      fetchOr<VoicesPage>('Voice profiles', `/api/v1/projects/${id}/voice/variants?limit=200`, emptyPage() as VoicesPage),
      fetchOr<ComplianceRule[]>('Compliance rules', `/api/v1/projects/${id}/compliance`, []),
      fetchOr<EeatCriterion[]>('EEAT criteria', `/api/v1/projects/${id}/eeat`, []),
    ])

    runs.value = runsPage.items ?? []
    topics.value = topicsPage.items ?? []
    articles.value = articlesPage.items ?? []
    targets.value = targetRows
    integrations.value = integrationRows
    schedules.value = scheduleRows
    voiceTotal.value = voicesPage.total_estimate ?? voicesPage.items?.length ?? 0
    compliance.value = complianceRows
    eeat.value = eeatRows
  } finally {
    loading.value = false
  }
}

type StatusCounts = { [Status in string]: number }

function countByStatus<T extends { status: string }>(items: T[]): StatusCounts {
  return items.reduce<StatusCounts>((acc, item) => {
    acc[item.status] = (acc[item.status] ?? 0) + 1
    return acc
  }, {})
}

const topicCounts = computed(() => countByStatus(topics.value))
const articleCounts = computed(() => countByStatus(articles.value))

const failedRuns = computed(() =>
  runs.value.filter((r) => r.status === 'failed' || r.status === 'aborted'),
)

const runningRuns = computed(() =>
  runs.value.filter((r) => r.status === 'running'),
)

const primaryTarget = computed(() =>
  targets.value.find((t) => t.is_primary && t.is_active) ?? null,
)

const activeSchedules = computed(() => schedules.value.filter((s) => s.enabled))
const activeCompliance = computed(() => compliance.value.filter((r) => r.is_active))
const activeEeat = computed(() => eeat.value.filter((r) => r.active))
const activeIntegrations = computed(() => integrations.value.length)

const readinessItems = computed<ReadinessItem[]>(() => [
  {
    key: 'project',
    label: 'Project',
    ready: project.value?.is_active === true,
    detail: project.value?.is_active ? 'Active' : 'Inactive',
    to: '/projects',
  },
  {
    key: 'voice',
    label: 'Voice',
    ready: voiceTotal.value > 0,
    detail: voiceTotal.value > 0 ? `${voiceTotal.value} profile${voiceTotal.value === 1 ? '' : 's'}` : 'No voice profile',
    to: `/projects/${projectId.value}/voice`,
  },
  {
    key: 'compliance',
    label: 'Compliance',
    ready: activeCompliance.value.length > 0,
    detail: activeCompliance.value.length > 0 ? `${activeCompliance.value.length} active rule${activeCompliance.value.length === 1 ? '' : 's'}` : 'No active rules',
    to: `/projects/${projectId.value}/compliance`,
  },
  {
    key: 'eeat',
    label: 'EEAT',
    ready: activeEeat.value.length > 0,
    detail: activeEeat.value.length > 0 ? `${activeEeat.value.length} active ${activeEeat.value.length === 1 ? 'criterion' : 'criteria'}` : 'No active criteria',
    to: `/projects/${projectId.value}/eeat`,
  },
  {
    key: 'targets',
    label: 'Publishing',
    ready: primaryTarget.value !== null,
    detail: primaryTarget.value ? `${primaryTarget.value.kind} primary target` : 'No active primary target',
    to: `/projects/${projectId.value}/targets`,
  },
  {
    key: 'integrations',
    label: 'Integrations',
    ready: activeIntegrations.value > 0,
    detail: activeIntegrations.value > 0 ? `${activeIntegrations.value} configured` : 'No credentials configured',
    to: `/projects/${projectId.value}/integrations`,
  },
  {
    key: 'schedules',
    label: 'Schedules',
    ready: activeSchedules.value.length > 0,
    detail: activeSchedules.value.length > 0 ? `${activeSchedules.value.length} enabled` : 'No enabled schedules',
    to: `/projects/${projectId.value}/schedules`,
  },
])

const readinessReadyCount = computed(() =>
  readinessItems.value.filter((item) => item.ready).length,
)

const readinessLabel = computed(() =>
  `${readinessReadyCount.value}/${readinessItems.value.length}`,
)

const articleInProduction = computed(() =>
  articles.value.filter((a) => !['published', 'refresh_due'].includes(a.status)).length,
)

const publishReadyArticles = computed(() => articleCounts.value.eeat_passed ?? 0)

const nextAction = computed<NextAction>(() => {
  const missingSetup = readinessItems.value.find((item) => !item.ready)
  if (failedRuns.value.length > 0) {
    return {
      label: 'Failed runs',
      detail: `${failedRuns.value.length} recent run${failedRuns.value.length === 1 ? '' : 's'} need attention before starting more work.`,
      to: `/projects/${projectId.value}/runs`,
    }
  }
  if (missingSetup) {
    return {
      label: missingSetup.label,
      detail: missingSetup.detail,
      to: missingSetup.to,
    }
  }
  if ((topicCounts.value.queued ?? 0) > 0) {
    return {
      label: 'Queued topics',
      detail: `${topicCounts.value.queued} topic${topicCounts.value.queued === 1 ? '' : 's'} waiting for approval.`,
      to: `/projects/${projectId.value}/topics`,
    }
  }
  if ((topicCounts.value.approved ?? 0) > 0) {
    return {
      label: 'Approved topics',
      detail: `${topicCounts.value.approved} approved topic${topicCounts.value.approved === 1 ? '' : 's'} waiting for an agent article run.`,
      to: `/projects/${projectId.value}/topics`,
    }
  }
  if (publishReadyArticles.value > 0) {
    return {
      label: 'Ready articles',
      detail: `${publishReadyArticles.value} article${publishReadyArticles.value === 1 ? '' : 's'} passed EEAT and awaits an agent publish run.`,
      to: `/projects/${projectId.value}/articles`,
    }
  }
  return {
    label: 'Topic queue',
    detail: 'The project is ready. New topic intake is agent-owned.',
    to: `/projects/${projectId.value}/topics`,
  }
})

function goTo(to: string): void {
  void router.push(to)
}

onMounted(loadDashboard)
watch(projectId, loadDashboard)
</script>

<template>
  <section class="space-y-4">
    <UiCallout
      v-if="warnings.length > 0"
      tone="warning"
      density="compact"
    >
      Some dashboard data could not be loaded. The rest of the project remains usable.
    </UiCallout>

    <UiPanel class="p-4">
      <UiSectionHeader
        title="Suggested view"
        :description="nextAction.detail"
      >
        <template #actions>
          <UiButton
            size="sm"
            :variant="nextAction.variant ?? 'secondary'"
            @click="goTo(nextAction.to)"
          >
            {{ nextAction.label }}
          </UiButton>
        </template>
      </UiSectionHeader>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <UiMetricCard
          label="Setup ready"
          :value="readinessLabel"
          :loading="loading"
          delta-tone="neutral"
          :delta="`${readinessReadyCount} ready`"
        />
        <UiMetricCard
          label="Queued topics"
          :value="topicCounts.queued ?? 0"
          :loading="loading"
          :delta="topicCounts.approved ?? 0"
          delta-label="approved"
          delta-tone="neutral"
        />
        <UiMetricCard
          label="Articles in production"
          :value="articleInProduction"
          :loading="loading"
          :delta="publishReadyArticles"
          delta-label="ready to publish"
          delta-tone="neutral"
        />
        <UiMetricCard
          label="Recent blockers"
          :value="failedRuns.length"
          :loading="loading"
          :delta="runningRuns.length"
          delta-label="running"
          :delta-tone="failedRuns.length > 0 ? 'negative' : 'neutral'"
        />
      </div>
    </UiPanel>

    <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <UiPanel class="p-4">
        <UiSectionHeader
          title="Setup readiness"
          description="The minimum operating surface for reliable content work."
        />
        <ul class="divide-y divide-border-subtle rounded-md border border-subtle bg-bg-surface">
          <li
            v-for="item in readinessItems"
            :key="item.key"
            class="flex items-center justify-between gap-3 px-3 py-2 text-sm"
          >
            <div class="min-w-0">
              <p class="font-medium text-fg-default">
                {{ item.label }}
              </p>
              <p class="truncate text-xs text-fg-muted">
                {{ item.detail }}
              </p>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <StatusBadge
                :status="item.ready ? 'active' : 'inactive'"
                kind="project"
                :small="true"
              />
              <UiButton
                v-if="!item.ready"
                size="sm"
                variant="secondary"
                @click="goTo(item.to)"
              >
                Open
              </UiButton>
            </div>
          </li>
        </ul>
      </UiPanel>

      <UiPanel class="p-4">
        <UiSectionHeader
          title="Recent activity"
          description="Latest project runs, with failed and running work visible from the dashboard."
        >
          <template #actions>
            <UiButton
              size="sm"
              variant="secondary"
              @click="goTo(`/projects/${projectId}/runs`)"
            >
              All runs
            </UiButton>
          </template>
        </UiSectionHeader>
        <DataTable
          :items="runs"
          :columns="runColumns"
          :loading="loading"
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
    </div>

    <UiPanel
      v-if="project"
      class="p-4"
    >
      <UiSectionHeader
        title="Project identity"
        description="The project selected in the operator console."
      />
      <div class="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <p class="text-xs text-fg-muted">
            Name
          </p>
          <p class="font-medium text-fg-default">
            {{ project.name }}
          </p>
        </div>
        <div>
          <p class="text-xs text-fg-muted">
            Domain
          </p>
          <p class="font-medium text-fg-default">
            {{ project.domain }}
          </p>
        </div>
        <div>
          <p class="text-xs text-fg-muted">
            Locale
          </p>
          <p class="font-medium text-fg-default">
            {{ project.locale }}
          </p>
        </div>
        <div>
          <p class="text-xs text-fg-muted">
            Niche
          </p>
          <p class="font-medium text-fg-default">
            {{ project.niche ?? '—' }}
          </p>
        </div>
      </div>
    </UiPanel>
  </section>
</template>
