<script setup lang="ts">
// TopicsView — read-only topic queue.

import { computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  UiCallout,
  UiEmptyState,
  UiFormField,
  UiPageShell,
  UiSegmentedControl,
  UiSelect,
} from '@/components/ui'
import { TopicIntent, TopicSource, TopicStatus as TopicStatusEnum } from '@/api'
import { useTopicsStore, type Topic, type TopicSortKey } from '@/stores/topics'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const topicsStore = useTopicsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))
const { filteredItems, loading, nextCursor, error, filters, sort } = storeToRefs(topicsStore)

const STATUS_OPTIONS: { key: 'all' | `${TopicStatusEnum}`; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'queued', label: 'Queued' },
  { key: 'approved', label: 'Approved' },
  { key: 'drafting', label: 'Drafting' },
  { key: 'published', label: 'Published' },
  { key: 'rejected', label: 'Rejected' },
]

const SOURCE_OPTIONS = computed(() => [
  { value: '', label: 'All sources' },
  ...Object.values(TopicSource).map((value) => ({ value, label: value })),
])

const INTENT_OPTIONS = computed(() => [
  { value: '', label: 'All intents' },
  ...Object.values(TopicIntent).map((value) => ({ value, label: value })),
])

const SORT_OPTIONS: { value: TopicSortKey; label: string }[] = [
  { value: 'priority', label: 'Priority asc' },
  { value: '-priority', label: 'Priority desc' },
  { value: 'id', label: 'Created asc' },
  { value: '-id', label: 'Created desc' },
]

const columns: DataTableColumn<Topic>[] = [
  { key: 'title', label: 'Title' },
  { key: 'primary_kw', label: 'Primary KW', cellClass: 'font-mono text-xs' },
  { key: 'status', label: 'Status' },
  { key: 'source', label: 'Source' },
  { key: 'intent', label: 'Intent' },
  { key: 'priority', label: 'Priority', sortable: true, widthClass: 'w-20' },
  {
    key: 'created_at',
    label: 'Created',
    format: (value) => (value ? new Date(String(value)).toLocaleDateString() : ''),
  },
]

function onStatusSelect(value: string | number): void {
  topicsStore.setFilter('status', value === 'all' ? null : String(value) as never)
  void topicsStore.refresh(projectId.value)
}

function onSourceChange(value: string | number | null): void {
  topicsStore.setFilter('source', value === '' || value === null ? null : String(value) as never)
  void topicsStore.refresh(projectId.value)
}

function onIntentChange(value: string | number | null): void {
  topicsStore.setFilter('intent', value === '' || value === null ? null : String(value) as never)
}

function onSortChange(value: string | number | null): void {
  if (value === null) return
  topicsStore.setSort(String(value) as TopicSortKey)
  void topicsStore.refresh(projectId.value)
}

async function loadMore(): Promise<void> {
  await topicsStore.loadMore(projectId.value)
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  await topicsStore.refresh(projectId.value)
}

const empty = computed(() => !loading.value && filteredItems.value.length === 0)

onMounted(load)
watch(projectId, load)
</script>

<template>
  <UiPageShell>
    <ProjectPageHeader
      :project-id="projectId"
      title="Topics"
      description="Inspect the agent-owned topic queue, approval state, sources, and priorities."
      :breadcrumbs="[{ label: 'Topics' }]"
    />

    <UiCallout
      v-if="error"
      tone="danger"
    >
      {{ error }}
    </UiCallout>

    <UiSegmentedControl
      :model-value="filters.status ?? 'all'"
      :options="STATUS_OPTIONS"
      label="Topic status filter"
      @select="onStatusSelect"
    />

    <div class="grid gap-3 sm:grid-cols-3">
      <UiFormField label="Source">
        <UiSelect
          :model-value="filters.source ?? ''"
          :options="SOURCE_OPTIONS"
          @change="onSourceChange"
        />
      </UiFormField>
      <UiFormField label="Intent">
        <UiSelect
          :model-value="filters.intent ?? ''"
          :options="INTENT_OPTIONS"
          @change="onIntentChange"
        />
      </UiFormField>
      <UiFormField label="Sort">
        <UiSelect
          :model-value="sort"
          :options="SORT_OPTIONS"
          @change="onSortChange"
        />
      </UiFormField>
    </div>

    <UiEmptyState
      v-if="empty"
      title="No topics yet"
      description="Topics appear here after agent discovery, sitemap import, GSC opportunity, or refresh detection runs."
      size="lg"
    />

    <DataTable
      v-else
      :items="filteredItems"
      :columns="columns"
      :loading="loading"
      :next-cursor="nextCursor"
      aria-label="Topics"
      empty-message="No topics match the filters"
      @load-more="loadMore"
    >
      <template #cell:status="{ row }">
        <StatusBadge
          :status="(row as Topic).status"
          kind="topic"
        />
      </template>
    </DataTable>
  </UiPageShell>
</template>
