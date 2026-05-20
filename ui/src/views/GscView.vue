<script setup lang="ts">
// GscView — read-only GSC rows, daily rollups, and redirects.

import { computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import { UiCallout, UiFormField, UiInput, UiPageShell, UiPanel } from '@/components/ui'
import { useArticlesStore } from '@/stores/articles'
import { useGscStore, type GscMetric, type Redirect } from '@/stores/gsc'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const gscStore = useGscStore()
const articlesStore = useArticlesStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { rawRows, redirects, loading, redirectsLoading, error, filters, dailyRollup } =
  storeToRefs(gscStore)

const rawColumns: DataTableColumn<GscMetric>[] = [
  { key: 'query', label: 'Query', format: (value) => (value as string) ?? '-' },
  { key: 'page', label: 'Page', format: (value) => (value as string) ?? '-' },
  { key: 'country', label: 'Country', format: (value) => (value as string) ?? '-', widthClass: 'w-20' },
  { key: 'device', label: 'Device', format: (value) => (value as string) ?? '-', widthClass: 'w-24' },
  { key: 'impressions', label: 'Impressions', widthClass: 'w-28' },
  { key: 'clicks', label: 'Clicks', widthClass: 'w-20' },
  {
    key: 'ctr',
    label: 'CTR',
    format: (value) => `${(Number(value) * 100).toFixed(2)}%`,
    widthClass: 'w-20',
  },
  {
    key: 'avg_position',
    label: 'Avg pos',
    format: (value) => Number(value).toFixed(2),
    widthClass: 'w-20',
  },
  {
    key: 'captured_at',
    label: 'Captured',
    format: (value) => (value ? new Date(String(value)).toLocaleString() : ''),
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
  { key: 'ctr', label: 'CTR', format: (value) => `${(Number(value) * 100).toFixed(2)}%` },
  { key: 'avg_position', label: 'Avg pos', format: (value) => Number(value).toFixed(2) },
]

const redirectColumns: DataTableColumn<Redirect>[] = [
  { key: 'from_url', label: 'From URL', cellClass: 'font-mono text-xs' },
  { key: 'to_article_id', label: 'To article' },
  { key: 'kind', label: 'Kind', widthClass: 'w-20' },
  {
    key: 'created_at',
    label: 'Created',
    format: (value) => (value ? new Date(String(value)).toLocaleString() : ''),
  },
]

const rawEmpty = computed<boolean>(() => !loading.value && rawRows.value.length === 0)
const dailyEmpty = computed<boolean>(() => !loading.value && dailyRollup.value.length === 0)
const redirectsEmpty = computed<boolean>(() => !redirectsLoading.value && redirects.value.length === 0)

function articleTitle(id: number | null): string {
  if (id === null) return '-'
  return articlesStore.getById(id)?.title ?? `#${id}`
}

function setSince(value: string): void {
  if (!value) return
  gscStore.setFilter('since', `${value}T00:00:00Z`)
  void gscStore.refresh(projectId.value)
}

function setUntil(value: string): void {
  if (!value) return
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
    articlesStore.items.length === 0 ? articlesStore.refresh(projectId.value) : Promise.resolve(),
  ])
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
    />

    <UiCallout
      v-if="error"
      tone="danger"
    >
      {{ error }}
    </UiCallout>

    <UiPanel
      aria-label="Search Console filters"
      class="p-4"
    >
      <div class="grid gap-3 md:grid-cols-[180px_180px_1fr]">
        <UiFormField label="Since">
          <UiInput
            type="date"
            :model-value="dateOnly(filters.since)"
            aria-label="Since date"
            @change="(value) => setSince(String(value ?? ''))"
          />
        </UiFormField>
        <UiFormField label="Until">
          <UiInput
            type="date"
            :model-value="dateOnly(filters.until)"
            aria-label="Until date"
            @change="(value) => setUntil(String(value ?? ''))"
          />
        </UiFormField>
        <p class="self-end pb-2 text-sm text-fg-muted">
          Date filters reload the read-only Search Console snapshot for this project.
        </p>
      </div>
    </UiPanel>

    <div class="grid gap-6">
      <section
        class="rounded-md border border-default bg-bg-surface shadow-xs"
        aria-labelledby="cs-gsc-raw"
      >
        <div class="border-b border-subtle px-4 py-3">
          <h2
            id="cs-gsc-raw"
            class="text-sm font-semibold text-fg-strong"
          >
            Search Console rows
          </h2>
          <p class="mt-0.5 text-sm text-fg-muted">
            Query, page, country, and device performance in the selected date window.
          </p>
        </div>
        <div class="p-3">
          <DataTable
            v-if="!rawEmpty"
            :items="rawRows"
            :columns="rawColumns"
            :loading="loading"
            aria-label="Raw GSC rows"
            empty-message="No GSC rows in this window."
          />
          <div
            v-else
            class="rounded-md border border-dashed border-subtle bg-bg-surface-alt px-5 py-8 text-center"
          >
            <h3 class="text-sm font-semibold text-fg-strong">
              No Search Console rows
            </h3>
            <p class="mx-auto mt-1 max-w-lg text-sm text-fg-muted">
              Rows appear here after the agent imports query and page performance for the selected date window.
            </p>
          </div>
        </div>
      </section>

      <div class="grid gap-6 xl:grid-cols-2">
        <section
          class="rounded-md border border-default bg-bg-surface shadow-xs"
          aria-labelledby="cs-gsc-rollup"
        >
          <div class="border-b border-subtle px-4 py-3">
            <h2
              id="cs-gsc-rollup"
              class="text-sm font-semibold text-fg-strong"
            >
              Daily rollup
            </h2>
            <p class="mt-0.5 text-sm text-fg-muted">
              Day-level totals from imported Search Console rows.
            </p>
          </div>
          <div class="p-3">
            <DataTable
              v-if="!dailyEmpty"
              :items="dailyRollup"
              :columns="dailyColumns"
              :loading="loading"
              aria-label="Daily GSC rollup"
              empty-message="No GSC rows to roll up."
            />
            <div
              v-else
              class="rounded-md border border-dashed border-subtle bg-bg-surface-alt px-5 py-8 text-center"
            >
              <h3 class="text-sm font-semibold text-fg-strong">
                No daily rollup yet
              </h3>
              <p class="mt-1 text-sm text-fg-muted">
                Daily totals appear after agent-owned Search Console processing.
              </p>
            </div>
          </div>
        </section>

        <section
          class="rounded-md border border-default bg-bg-surface shadow-xs"
          aria-labelledby="cs-gsc-redirects"
        >
          <div class="border-b border-subtle px-4 py-3">
            <h2
              id="cs-gsc-redirects"
              class="text-sm font-semibold text-fg-strong"
            >
              Redirects
            </h2>
            <p class="mt-0.5 text-sm text-fg-muted">
              Old paths mapped to tracked article destinations.
            </p>
          </div>
          <div class="p-3">
            <DataTable
              v-if="!redirectsEmpty"
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
            <div
              v-else
              class="rounded-md border border-dashed border-subtle bg-bg-surface-alt px-5 py-8 text-center"
            >
              <h3 class="text-sm font-semibold text-fg-strong">
                No redirects
              </h3>
              <p class="mt-1 text-sm text-fg-muted">
                Agent-created redirects will appear here with source URL and destination article.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  </UiPageShell>
</template>
