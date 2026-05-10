<script setup lang="ts">
// GscView — raw GSC table + daily rollup + redirects.
//
// Wires to:
// - `GET /api/v1/projects/{id}/gsc?since=&until=` (raw rows)
// - `POST /api/v1/projects/{id}/gsc/rollup?day=YYYY-MM-DD` (operator)
// - `GET / POST /api/v1/projects/{id}/redirects`
//
// Daily rollup is computed client-side because the daemon doesn't expose a
// dedicated `GET /gsc/daily` route at M5.C — flagged in the milestone
// report. The "Run rollup now" button still hits the POST endpoint to
// populate `gsc_metrics_daily` for downstream M9 consumers.

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import TabBar from '@/components/TabBar.vue'
import {
  UiButton,
  UiCallout,
  UiDialog,
  UiPageShell,
} from '@/components/ui'
import { useGscStore, type GscMetric, type Redirect } from '@/stores/gsc'
import { useArticlesStore } from '@/stores/articles'
import { useToastsStore } from '@/stores/toasts'
import { RedirectKind as RedirectKindEnum } from '@/api'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const gscStore = useGscStore()
const articlesStore = useArticlesStore()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { rawRows, redirects, loading, redirectsLoading, error, filters, dailyRollup } =
  storeToRefs(gscStore)

const activeTab = ref<'raw' | 'daily' | 'redirects'>('raw')
const showCreateRedirect = ref(false)
const submittingRedirect = ref(false)
const showRollup = ref(false)
const rollupDay = ref<string>(new Date().toISOString().slice(0, 10))
const rollupPending = ref(false)

const newRedirect = ref({
  from_url: '',
  to_article_id: null as number | null,
  kind: '301' as `${RedirectKindEnum}`,
})

const tabs = [
  { key: 'raw', label: 'Raw' },
  { key: 'daily', label: 'Daily Rollup' },
  { key: 'redirects', label: 'Redirects' },
]

const rawColumns: DataTableColumn<GscMetric>[] = [
  { key: 'query', label: 'Query', format: (v) => (v as string) ?? '—' },
  { key: 'page', label: 'Page', format: (v) => (v as string) ?? '—' },
  { key: 'country', label: 'Country', format: (v) => (v as string) ?? '—', widthClass: 'w-20' },
  { key: 'device', label: 'Device', format: (v) => (v as string) ?? '—', widthClass: 'w-24' },
  { key: 'impressions', label: 'Impressions', widthClass: 'w-28' },
  { key: 'clicks', label: 'Clicks', widthClass: 'w-20' },
  { key: 'ctr', label: 'CTR', format: (v) => `${(Number(v) * 100).toFixed(2)}%`, widthClass: 'w-20' },
  { key: 'avg_position', label: 'Avg pos', format: (v) => Number(v).toFixed(2), widthClass: 'w-20' },
  {
    key: 'captured_at',
    label: 'Captured',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
]

interface DailyRow {
  id: string
  day: string
  impressions: number
  clicks: number
  ctr: number
  avg_position: number
}

const dailyColumns: DataTableColumn<DailyRow>[] = [
  { key: 'day', label: 'Day' },
  { key: 'impressions', label: 'Impressions' },
  { key: 'clicks', label: 'Clicks' },
  { key: 'ctr', label: 'CTR', format: (v) => `${(Number(v) * 100).toFixed(2)}%` },
  { key: 'avg_position', label: 'Avg pos', format: (v) => Number(v).toFixed(2) },
]

const redirectColumns: DataTableColumn<Redirect>[] = [
  { key: 'from_url', label: 'From URL', cellClass: 'font-mono text-xs' },
  { key: 'to_article_id', label: 'To article' },
  { key: 'kind', label: 'Kind', widthClass: 'w-20' },
  {
    key: 'created_at',
    label: 'Created',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
]

function articleTitle(id: number | null): string {
  if (id === null) return '—'
  return articlesStore.getById(id)?.title ?? `#${id}`
}

function setSince(value: string): void {
  // value comes from <input type="date"> as YYYY-MM-DD
  gscStore.setFilter('since', `${value}T00:00:00Z`)
  void gscStore.refresh(projectId.value)
}

function setUntil(value: string): void {
  gscStore.setFilter('until', `${value}T00:00:00Z`)
  void gscStore.refresh(projectId.value)
}

function dateOnly(iso: string): string {
  return iso.slice(0, 10)
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  gscStore.reset()
  await Promise.all([
    gscStore.refresh(projectId.value),
    gscStore.refreshRedirects(projectId.value),
    articlesStore.items.length === 0
      ? articlesStore.refresh(projectId.value)
      : Promise.resolve(),
  ])
}

async function submitRollup(): Promise<void> {
  rollupPending.value = true
  try {
    await gscStore.rollupDay(projectId.value, rollupDay.value)
    toasts.success('Rollup complete', `gsc_metrics_daily updated for ${rollupDay.value}`)
    showRollup.value = false
  } catch (err) {
    toasts.error('Rollup failed', err instanceof Error ? err.message : undefined)
  } finally {
    rollupPending.value = false
  }
}

async function submitRedirect(): Promise<void> {
  if (!newRedirect.value.from_url.trim()) {
    toasts.error('From URL required')
    return
  }
  submittingRedirect.value = true
  try {
    await gscStore.createRedirect(projectId.value, {
      from_url: newRedirect.value.from_url.trim(),
      to_article_id: newRedirect.value.to_article_id,
      kind: newRedirect.value.kind as RedirectKindEnum,
    })
    toasts.success('Redirect added')
    showCreateRedirect.value = false
    newRedirect.value = { from_url: '', to_article_id: null, kind: '301' }
  } catch (err) {
    toasts.error('Failed to add redirect', err instanceof Error ? err.message : undefined)
  } finally {
    submittingRedirect.value = false
  }
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <UiPageShell>
    <ProjectPageHeader
      :project-id="projectId"
      title="GSC Metrics"
      description="Inspect Search Console rows, daily rollups, and redirect coverage for the project."
      :breadcrumbs="[{ label: 'GSC Metrics' }]"
    >
      <template #actions>
        <div class="flex flex-wrap items-center justify-end gap-2 text-sm">
          <label class="flex items-center gap-1">
            <span class="text-fg-muted">Since</span>
            <input
              type="date"
              :value="dateOnly(filters.since)"
              class="h-8 rounded-sm border border-default bg-bg-surface px-2 text-sm text-fg-default focus-ring"
              aria-label="Since date"
              @change="setSince(($event.target as HTMLInputElement).value)"
            >
          </label>
          <label class="flex items-center gap-1">
            <span class="text-fg-muted">Until</span>
            <input
              type="date"
              :value="dateOnly(filters.until)"
              class="h-8 rounded-sm border border-default bg-bg-surface px-2 text-sm text-fg-default focus-ring"
              aria-label="Until date"
              @change="setUntil(($event.target as HTMLInputElement).value)"
            >
          </label>
          <UiButton
            variant="secondary"
            size="sm"
            @click="showRollup = true"
          >
            Run rollup now
          </UiButton>
        </div>
      </template>
      <template #tabs>
        <TabBar
          :tabs="tabs"
          :active-key="activeTab"
          aria-label="GSC sections"
          @change="(key: string) => activeTab = key as 'raw' | 'daily' | 'redirects'"
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
        v-if="activeTab === 'raw'"
        :items="rawRows"
        :columns="rawColumns"
        :loading="loading"
        aria-label="Raw GSC rows"
        empty-message="No GSC rows in this window."
      />

      <DataTable
        v-if="activeTab === 'daily'"
        :items="dailyRollup"
        :columns="dailyColumns"
        :loading="loading"
        aria-label="Daily GSC rollup"
        empty-message="No GSC rows to roll up."
      />

      <div v-if="activeTab === 'redirects'">
        <div class="mb-3 flex justify-end">
          <UiButton
            variant="primary"
            @click="showCreateRedirect = true"
          >
            New Redirect
          </UiButton>
        </div>
        <DataTable
          :items="redirects"
          :columns="redirectColumns"
          :loading="redirectsLoading"
          aria-label="Redirects"
          empty-message="No redirects defined."
        >
          <template #cell:to_article_id="{ row }">
            {{ articleTitle((row as Redirect).to_article_id) }}
          </template>
        </DataTable>
      </div>
    </div>

    <UiDialog
      :model-value="showRollup"
      title="Run GSC rollup"
      description="Aggregate gsc_metrics for one day into gsc_metrics_daily."
      size="md"
      @update:model-value="(open: boolean) => showRollup = open"
    >
      <UiCallout
        tone="info"
        density="compact"
        class="mb-3"
      >
        M9 schedules this nightly; this is the operator escape hatch.
      </UiCallout>
      <label class="mb-3 block text-sm">
        <span class="font-medium">Day</span>
        <input
          v-model="rollupDay"
          type="date"
          class="mt-1 w-full rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
        >
      </label>
      <template #footer>
        <UiButton
          variant="secondary"
          :disabled="rollupPending"
          @click="showRollup = false"
        >
          Cancel
        </UiButton>
        <UiButton
          variant="primary"
          :loading="rollupPending"
          @click="submitRollup"
        >
          Run rollup
        </UiButton>
      </template>
    </UiDialog>

    <UiDialog
      :model-value="showCreateRedirect"
      title="New redirect"
      description="Create a redirect from an old URL to a tracked article."
      size="md"
      @update:model-value="(open: boolean) => showCreateRedirect = open"
    >
      <label class="mb-3 block text-sm">
        <span class="font-medium">From URL</span>
        <input
          v-model="newRedirect.from_url"
          type="text"
          placeholder="/old-path"
          class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-sm dark:border-gray-700 dark:bg-gray-800"
        >
      </label>
      <label class="mb-3 block text-sm">
        <span class="font-medium">To article</span>
        <select
          v-model="newRedirect.to_article_id"
          class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
        >
          <option :value="null">
            — none —
          </option>
          <option
            v-for="a in articlesStore.items"
            :key="a.id"
            :value="a.id"
          >
            {{ a.title }}
          </option>
        </select>
      </label>
      <label class="mb-3 block text-sm">
        <span class="font-medium">Kind</span>
        <select
          v-model="newRedirect.kind"
          class="mt-1 w-32 rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
        >
          <option value="301">
            301
          </option>
          <option value="302">
            302
          </option>
        </select>
      </label>
      <template #footer>
        <UiButton
          variant="secondary"
          :disabled="submittingRedirect"
          @click="showCreateRedirect = false"
        >
          Cancel
        </UiButton>
        <UiButton
          variant="primary"
          :loading="submittingRedirect"
          @click="submitRedirect"
        >
          Add redirect
        </UiButton>
      </template>
    </UiDialog>
  </UiPageShell>
</template>
