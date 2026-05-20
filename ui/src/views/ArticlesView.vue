<script setup lang="ts">
// ArticlesView — read-only article workspace.

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  UiButton,
  UiCallout,
  UiEmptyState,
  UiFormField,
  UiPageShell,
  UiSegmentedControl,
  UiSelect,
} from '@/components/ui'
import { ArticleStatus as ArticleStatusEnum, type components } from '@/api'
import { apiFetch } from '@/lib/client'
import { useArticlesStore, type Article, type ArticleSortKey, type ArticleStatus } from '@/stores/articles'
import { useToastsStore } from '@/stores/toasts'
import { useTopicsStore } from '@/stores/topics'
import type { DataTableColumn } from '@/components/types'

type AuthorOut = components['schemas']['AuthorOut']
type AuthorsPage = components['schemas']['PageResponse_AuthorOut_']

const route = useRoute()
const router = useRouter()
const articlesStore = useArticlesStore()
const topicsStore = useTopicsStore()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { filteredItems, loading, nextCursor, error, filters } = storeToRefs(articlesStore)

const showRefreshDue = ref(false)
const refreshDueItems = ref<Article[]>([])
const authors = ref<AuthorOut[]>([])

const STATUS_OPTIONS: { key: 'all' | `${ArticleStatusEnum}`; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'briefing', label: 'Briefing' },
  { key: 'outlined', label: 'Outlined' },
  { key: 'drafted', label: 'Drafted' },
  { key: 'edited', label: 'Edited' },
  { key: 'eeat_passed', label: 'EEAT Passed' },
  { key: 'published', label: 'Published' },
  { key: 'refresh_due', label: 'Refresh Due' },
  { key: 'aborted-publish', label: 'Delivery failed' },
]

const SORT_OPTIONS: { value: ArticleSortKey; label: string }[] = [
  { value: '-created_at', label: 'Created desc' },
  { value: 'created_at', label: 'Created asc' },
  { value: '-updated_at', label: 'Updated desc' },
  { value: 'updated_at', label: 'Updated asc' },
  { value: 'title', label: 'Title' },
]

const authorFilterOptions = computed(() => [
  { value: '', label: 'All authors' },
  ...authors.value.map((author) => ({ value: author.id, label: author.name })),
])

const topicFilterOptions = computed(() => [
  { value: '', label: 'All topics' },
  ...topicsStore.items.map((topic) => ({ value: topic.id, label: topic.title })),
])

const columns: DataTableColumn<Article>[] = [
  { key: 'title', label: 'Title' },
  { key: 'status', label: 'Status' },
  { key: 'author_id', label: 'Author' },
  { key: 'topic_id', label: 'Topic' },
  { key: 'version', label: 'Version', widthClass: 'w-16' },
  {
    key: 'updated_at',
    label: 'Updated',
    sortable: true,
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
]

function setStatusFilter(opt: 'all' | `${ArticleStatusEnum}`): void {
  articlesStore.setFilter('status', opt === 'all' ? null : (opt as ArticleStatus))
  void articlesStore.refresh(projectId.value)
}

function onStatusSelect(key: string | number): void {
  setStatusFilter(String(key) as 'all' | `${ArticleStatusEnum}`)
}

function onSortChange(value: string | number | null): void {
  if (value === null) return
  articlesStore.setSort(String(value) as ArticleSortKey)
}

function onAuthorFilterChange(value: string | number | null): void {
  setAuthorFilter(value === null ? '' : String(value))
}

function onTopicFilterChange(value: string | number | null): void {
  setTopicFilter(value === null ? '' : String(value))
}

function setAuthorFilter(value: string): void {
  articlesStore.setFilter('author_id', value === '' ? null : Number.parseInt(value, 10))
}

function setTopicFilter(value: string): void {
  articlesStore.setFilter('topic_id', value === '' ? null : Number.parseInt(value, 10))
  void articlesStore.refresh(projectId.value)
}

function authorName(id: number | null): string {
  if (id === null) return '-'
  return authors.value.find((a) => a.id === id)?.name ?? `#${id}`
}

function topicTitle(id: number | null): string {
  if (id === null) return '-'
  return topicsStore.getById(id)?.title ?? `#${id}`
}

function openDetail(row: Article): void {
  void router.push(`/projects/${projectId.value}/articles/${row.id}`)
}

async function loadRefreshDue(): Promise<void> {
  showRefreshDue.value = true
  try {
    refreshDueItems.value = await articlesStore.listDueForRefresh(projectId.value)
  } catch (err) {
    toasts.error('Failed to load refresh-due list', err instanceof Error ? err.message : undefined)
  }
}

async function loadMore(): Promise<void> {
  await articlesStore.loadMore(projectId.value)
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  articlesStore.reset()
  await Promise.all([
    articlesStore.refresh(projectId.value),
    topicsStore.items.length === 0 ? topicsStore.refresh(projectId.value) : Promise.resolve(),
    loadAuthors(),
  ])
}

async function loadAuthors(): Promise<void> {
  try {
    const params = new URLSearchParams({ limit: '200' })
    const page = await apiFetch<AuthorsPage>(
      `/api/v1/projects/${projectId.value}/authors?${params.toString()}`,
    )
    authors.value = page.items
  } catch {
    authors.value = []
  }
}

const empty = computed<boolean>(() => !loading.value && filteredItems.value.length === 0)

onMounted(load)
watch(projectId, load)
</script>

<template>
  <UiPageShell>
    <ProjectPageHeader
      :project-id="projectId"
      title="Articles"
      description="Inspect article state across brief, outline, draft, editorial, EEAT, publishing, and refresh workflows."
      :breadcrumbs="[{ label: 'Articles' }]"
    >
      <template #actions>
        <UiButton
          variant="secondary"
          :aria-pressed="showRefreshDue"
          @click="showRefreshDue ? showRefreshDue = false : loadRefreshDue()"
        >
          {{ showRefreshDue ? 'Show all' : 'Due for refresh' }}
        </UiButton>
      </template>
    </ProjectPageHeader>

    <UiCallout
      v-if="error"
      tone="danger"
    >
      {{ error }}
    </UiCallout>

    <UiSegmentedControl
      v-if="!showRefreshDue"
      :model-value="filters.status ?? 'all'"
      :options="STATUS_OPTIONS"
      label="Article status filter"
      @select="onStatusSelect"
    />

    <div
      v-if="!showRefreshDue"
      class="grid gap-3 sm:grid-cols-3"
    >
      <UiFormField label="Author">
        <UiSelect
          :model-value="filters.author_id ?? ''"
          :options="authorFilterOptions"
          @change="onAuthorFilterChange"
        />
      </UiFormField>
      <UiFormField label="Topic">
        <UiSelect
          :model-value="filters.topic_id ?? ''"
          :options="topicFilterOptions"
          @change="onTopicFilterChange"
        />
      </UiFormField>
      <UiFormField label="Sort">
        <UiSelect
          :model-value="articlesStore.sort"
          :options="SORT_OPTIONS"
          @change="onSortChange"
        />
      </UiFormField>
    </div>

    <UiEmptyState
      v-if="empty && !showRefreshDue"
      title="No articles yet"
      description="Articles appear here after agent runs create them from approved topics."
      size="lg"
    />

    <DataTable
      v-if="!showRefreshDue && !empty"
      :items="filteredItems"
      :columns="columns"
      :loading="loading"
      :next-cursor="nextCursor"
      aria-label="Articles"
      empty-message="No articles match the filters"
      @row-click="openDetail"
      @load-more="loadMore"
    >
      <template #cell:status="{ row }">
        <StatusBadge
          :status="(row as Article).status"
          kind="article"
        />
      </template>
      <template #cell:author_id="{ row }">
        {{ authorName((row as Article).author_id) }}
      </template>
      <template #cell:topic_id="{ row }">
        {{ topicTitle((row as Article).topic_id) }}
      </template>
    </DataTable>

    <DataTable
      v-if="showRefreshDue"
      :items="refreshDueItems"
      :columns="columns"
      :loading="loading"
      aria-label="Articles due for refresh"
      empty-message="No articles are due for refresh"
      @row-click="openDetail"
    >
      <template #cell:status="{ row }">
        <StatusBadge
          :status="(row as Article).status"
          kind="article"
        />
      </template>
      <template #cell:author_id="{ row }">
        {{ authorName((row as Article).author_id) }}
      </template>
      <template #cell:topic_id="{ row }">
        {{ topicTitle((row as Article).topic_id) }}
      </template>
    </DataTable>
  </UiPageShell>
</template>
