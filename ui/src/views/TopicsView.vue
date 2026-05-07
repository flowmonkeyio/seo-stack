<script setup lang="ts">
// TopicsView — topic queue + bulk-actions UX.
//
// PLAN.md L386–L387 + L575–L577 + L660–L661.
// - Status pill bar drives the `status` filter.
// - Source / intent / cluster dropdowns map to additional filters.
// - Sort: priority (default) or id (created order proxy).
// - Bulk approve / reject / set-status calls
//   `POST /projects/{id}/topics/bulk-update-status` (all-or-nothing).

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useClustersStore } from '@/stores/clusters'
import {
  useTopicsStore,
  type Topic,
  type TopicIntent,
  type TopicSource,
  type TopicStatus,
  type TopicSortKey,
} from '@/stores/topics'
import { useToastsStore } from '@/stores/toasts'
import { TopicIntent as TopicIntentEnum, TopicSource as TopicSourceEnum, TopicStatus as TopicStatusEnum } from '@/api'
import type { DataTableColumn, DataTableSortDir } from '@/components/types'

const route = useRoute()
const topicsStore = useTopicsStore()
const clustersStore = useClustersStore()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { filteredItems, loading, nextCursor, error, filters, sort } = storeToRefs(topicsStore)

const selection = ref<Set<number>>(new Set())
const showCreate = ref(false)
const showBulkCreate = ref(false)
const submitting = ref(false)
const previewTopic = ref<Topic | null>(null)
const bulkActionPending = ref(false)

const STATUS_OPTIONS: { key: 'all' | `${TopicStatusEnum}`; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'queued', label: 'Queued' },
  { key: 'approved', label: 'Approved' },
  { key: 'drafting', label: 'Drafting' },
  { key: 'published', label: 'Published' },
  { key: 'rejected', label: 'Rejected' },
]

const SOURCE_OPTIONS = Object.values(TopicSourceEnum) as TopicSource[]
const INTENT_OPTIONS = Object.values(TopicIntentEnum) as TopicIntent[]

const columns: DataTableColumn<Topic>[] = [
  { key: 'title', label: 'Title' },
  {
    key: 'primary_kw',
    label: 'Primary KW',
    cellClass: 'font-mono text-xs',
  },
  { key: 'status', label: 'Status' },
  { key: 'source', label: 'Source' },
  { key: 'priority', label: 'Priority', sortable: true, widthClass: 'w-20' },
  { key: 'cluster_id', label: 'Cluster' },
  {
    key: 'created_at',
    label: 'Created',
    format: (v) => (v ? new Date(String(v)).toLocaleDateString() : ''),
  },
]

interface NewTopic {
  title: string
  primary_kw: string
  secondary_kws: string
  intent: TopicIntent
  cluster_id: number | null
  priority: number
  source: TopicSource
}

const draft = ref<NewTopic>(emptyDraft())
function emptyDraft(): NewTopic {
  return {
    title: '',
    primary_kw: '',
    secondary_kws: '',
    intent: TopicIntentEnum.informational as TopicIntent,
    cluster_id: null,
    priority: 50,
    source: TopicSourceEnum.manual as TopicSource,
  }
}

interface BulkDraft {
  titles: string
  intent: TopicIntent
  source: TopicSource
}

const bulkDraft = ref<BulkDraft>({
  titles: '',
  intent: TopicIntentEnum.informational as TopicIntent,
  source: TopicSourceEnum.manual as TopicSource,
})

function setStatusFilter(opt: 'all' | `${TopicStatusEnum}`): void {
  topicsStore.setFilter('status', opt === 'all' ? null : (opt as TopicStatus))
  void topicsStore.refresh(projectId.value)
}

function setSourceFilter(value: string): void {
  topicsStore.setFilter('source', value === '' ? null : (value as TopicSource))
  void topicsStore.refresh(projectId.value)
}

function setIntentFilter(value: string): void {
  topicsStore.setFilter('intent', value === '' ? null : (value as TopicIntent))
}

function setClusterFilter(value: string): void {
  if (value === '') topicsStore.setFilter('cluster_id', null)
  else topicsStore.setFilter('cluster_id', Number.parseInt(value, 10))
  void topicsStore.refresh(projectId.value)
}

const sortKey = computed<string>(() => sort.value.replace(/^-/, ''))
const sortDir = computed<DataTableSortDir>(() => (sort.value.startsWith('-') ? 'desc' : 'asc'))

function onSort(column: string, dir: DataTableSortDir): void {
  if (column !== 'priority') return
  if (dir === null) {
    topicsStore.setSort('priority')
  } else {
    topicsStore.setSort(dir === 'desc' ? '-priority' : 'priority')
  }
  void topicsStore.refresh(projectId.value)
}

function onSortChange(ev: Event): void {
  const value = (ev.target as HTMLSelectElement).value as TopicSortKey
  topicsStore.setSort(value)
  void topicsStore.refresh(projectId.value)
}

function onBulkSetStatusChange(ev: Event): void {
  const value = (ev.target as HTMLSelectElement).value
  if (value === '') return
  void bulkSetStatus(value)
}

function onSelectionChange(next: Set<number>): void {
  selection.value = new Set(next)
}

async function approveOne(t: Topic): Promise<void> {
  try {
    await topicsStore.approve(t.id)
    toasts.success('Topic approved', t.title)
  } catch (err) {
    toasts.error('Approve failed', err instanceof Error ? err.message : undefined)
  }
}

async function rejectOne(t: Topic): Promise<void> {
  try {
    await topicsStore.reject(t.id)
    toasts.success('Topic rejected', t.title)
  } catch (err) {
    toasts.error('Reject failed', err instanceof Error ? err.message : undefined)
  }
}

async function bulkApprove(): Promise<void> {
  if (selection.value.size === 0) return
  bulkActionPending.value = true
  try {
    await topicsStore.bulkUpdateStatus(projectId.value, {
      ids: [...selection.value],
      status: TopicStatusEnum.approved as TopicStatus,
    })
    toasts.success('Topics approved', `${selection.value.size} updated`)
    selection.value = new Set()
  } catch (err) {
    toasts.error('Bulk approve failed', err instanceof Error ? err.message : undefined)
  } finally {
    bulkActionPending.value = false
  }
}

async function bulkReject(): Promise<void> {
  if (selection.value.size === 0) return
  bulkActionPending.value = true
  try {
    await topicsStore.bulkUpdateStatus(projectId.value, {
      ids: [...selection.value],
      status: TopicStatusEnum.rejected as TopicStatus,
    })
    toasts.success('Topics rejected', `${selection.value.size} updated`)
    selection.value = new Set()
  } catch (err) {
    toasts.error('Bulk reject failed', err instanceof Error ? err.message : undefined)
  } finally {
    bulkActionPending.value = false
  }
}

async function bulkSetStatus(value: string): Promise<void> {
  if (selection.value.size === 0 || value === '') return
  bulkActionPending.value = true
  try {
    await topicsStore.bulkUpdateStatus(projectId.value, {
      ids: [...selection.value],
      status: value as TopicStatus,
    })
    toasts.success('Topics updated', `${selection.value.size} → ${value}`)
    selection.value = new Set()
  } catch (err) {
    toasts.error('Bulk update failed', err instanceof Error ? err.message : undefined)
  } finally {
    bulkActionPending.value = false
  }
}

function openCreate(): void {
  draft.value = emptyDraft()
  showCreate.value = true
}

function closeCreate(): void {
  if (submitting.value) return
  showCreate.value = false
}

async function submitCreate(): Promise<void> {
  if (submitting.value) return
  if (!draft.value.title.trim()) {
    toasts.error('Missing required field', 'Title is required.')
    return
  }
  submitting.value = true
  try {
    const created = await topicsStore.create(projectId.value, {
      title: draft.value.title.trim(),
      primary_kw: draft.value.primary_kw.trim(),
      secondary_kws: draft.value.secondary_kws
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0),
      intent: draft.value.intent,
      status: TopicStatusEnum.queued as TopicStatus,
      priority: draft.value.priority,
      source: draft.value.source,
      cluster_id: draft.value.cluster_id,
    })
    toasts.success('Topic created', created.title)
    showCreate.value = false
  } catch (err) {
    toasts.error('Failed to create topic', err instanceof Error ? err.message : undefined)
  } finally {
    submitting.value = false
  }
}

function openBulkCreate(): void {
  bulkDraft.value = {
    titles: '',
    intent: TopicIntentEnum.informational as TopicIntent,
    source: TopicSourceEnum.manual as TopicSource,
  }
  showBulkCreate.value = true
}

function closeBulkCreate(): void {
  if (submitting.value) return
  showBulkCreate.value = false
}

async function submitBulkCreate(): Promise<void> {
  if (submitting.value) return
  const lines = bulkDraft.value.titles
    .split('\n')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
  if (lines.length === 0) {
    toasts.error('No titles', 'Paste one title per line.')
    return
  }
  submitting.value = true
  try {
    const items = lines.map((title) => ({
      title,
      primary_kw: '',
      intent: bulkDraft.value.intent,
      status: TopicStatusEnum.queued as TopicStatus,
      source: bulkDraft.value.source,
    }))
    const rows = await topicsStore.bulkCreate(projectId.value, { items })
    toasts.success('Topics created', `${rows.length} added`)
    showBulkCreate.value = false
  } catch (err) {
    toasts.error('Bulk create failed', err instanceof Error ? err.message : undefined)
  } finally {
    submitting.value = false
  }
}

function openPreview(row: Topic): void {
  previewTopic.value = row
}

function closePreview(): void {
  previewTopic.value = null
}

function clusterName(cluster_id: number | null): string {
  if (cluster_id === null) return '—'
  return clustersStore.getById(cluster_id)?.name ?? `#${cluster_id}`
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  topicsStore.reset()
  await topicsStore.refresh(projectId.value)
  if (clustersStore.items.length === 0) {
    await clustersStore.refresh(projectId.value)
  }
}

async function loadMore(): Promise<void> {
  await topicsStore.loadMore(projectId.value)
}

const empty = computed<boolean>(
  () => !loading.value && filteredItems.value.length === 0 && selection.value.size === 0,
)

onMounted(load)
watch(projectId, load)
</script>

<template>
  <div class="mx-auto max-w-7xl">
    <header class="mb-4 flex flex-wrap items-baseline justify-between gap-3">
      <h1 class="text-2xl font-bold tracking-tight">
        Topics
      </h1>
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          class="rounded border border-gray-300 px-3 py-2 text-sm hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:border-gray-700 dark:hover:bg-gray-800"
          @click="openBulkCreate"
        >
          Bulk create
        </button>
        <button
          type="button"
          class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
          @click="openCreate"
        >
          New topic
        </button>
      </div>
    </header>

    <p
      v-if="error"
      class="mb-3 rounded bg-red-50 p-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200"
    >
      {{ error }}
    </p>

    <!-- Status pill bar -->
    <div
      role="tablist"
      aria-label="Topic status filter"
      class="mb-3 flex flex-wrap gap-1"
    >
      <button
        v-for="opt in STATUS_OPTIONS"
        :key="opt.key"
        type="button"
        role="tab"
        :aria-selected="(filters.status === null && opt.key === 'all') || filters.status === opt.key"
        class="rounded-full border px-3 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
        :class="
          (filters.status === null && opt.key === 'all') || filters.status === opt.key
            ? 'border-blue-600 bg-blue-50 font-medium text-blue-800 dark:border-blue-500 dark:bg-blue-900/40 dark:text-blue-200'
            : 'border-gray-300 text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800'
        "
        @click="setStatusFilter(opt.key)"
      >
        {{ opt.label }}
      </button>
    </div>

    <!-- Other filters -->
    <div class="mb-3 flex flex-wrap items-center gap-3 text-sm">
      <label class="flex items-center gap-2">
        <span class="text-gray-600 dark:text-gray-400">Source</span>
        <select
          :value="filters.source ?? ''"
          class="rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
          @change="setSourceFilter(($event.target as HTMLSelectElement).value)"
        >
          <option value="">
            All
          </option>
          <option
            v-for="s in SOURCE_OPTIONS"
            :key="s"
            :value="s"
          >
            {{ s }}
          </option>
        </select>
      </label>
      <label class="flex items-center gap-2">
        <span class="text-gray-600 dark:text-gray-400">Intent</span>
        <select
          :value="filters.intent ?? ''"
          class="rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
          @change="setIntentFilter(($event.target as HTMLSelectElement).value)"
        >
          <option value="">
            All
          </option>
          <option
            v-for="i in INTENT_OPTIONS"
            :key="i"
            :value="i"
          >
            {{ i }}
          </option>
        </select>
      </label>
      <label class="flex items-center gap-2">
        <span class="text-gray-600 dark:text-gray-400">Cluster</span>
        <select
          :value="filters.cluster_id !== null ? String(filters.cluster_id) : ''"
          class="rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
          @change="setClusterFilter(($event.target as HTMLSelectElement).value)"
        >
          <option value="">
            All
          </option>
          <option
            v-for="c in clustersStore.items"
            :key="c.id"
            :value="c.id"
          >
            {{ c.name }}
          </option>
        </select>
      </label>
      <label class="flex items-center gap-2">
        <span class="text-gray-600 dark:text-gray-400">Sort</span>
        <select
          :value="sort"
          class="rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
          @change="onSortChange"
        >
          <option value="priority">
            priority asc
          </option>
          <option value="-priority">
            priority desc
          </option>
          <option value="id">
            created asc
          </option>
          <option value="-id">
            created desc
          </option>
        </select>
      </label>
    </div>

    <!-- Bulk actions bar -->
    <div
      v-if="selection.size > 0"
      class="mb-3 flex flex-wrap items-center gap-2 rounded border border-blue-300 bg-blue-50 p-2 text-sm dark:border-blue-700 dark:bg-blue-900/30"
      role="status"
      aria-live="polite"
    >
      <span class="font-medium">{{ selection.size }} selected</span>
      <button
        type="button"
        class="rounded border border-blue-300 bg-white px-2 py-1 text-xs hover:bg-blue-100 disabled:opacity-50 dark:border-blue-700 dark:bg-blue-900/60 dark:hover:bg-blue-900"
        :disabled="bulkActionPending"
        @click="bulkApprove"
      >
        Approve selected
      </button>
      <button
        type="button"
        class="rounded border border-blue-300 bg-white px-2 py-1 text-xs hover:bg-blue-100 disabled:opacity-50 dark:border-blue-700 dark:bg-blue-900/60 dark:hover:bg-blue-900"
        :disabled="bulkActionPending"
        @click="bulkReject"
      >
        Reject selected
      </button>
      <label class="flex items-center gap-1 text-xs">
        Set status…
        <select
          class="rounded border border-blue-300 bg-white px-1 py-0.5 text-xs dark:border-blue-700 dark:bg-blue-900/40"
          :disabled="bulkActionPending"
          @change="onBulkSetStatusChange"
        >
          <option value="">
            —
          </option>
          <option value="queued">
            queued
          </option>
          <option value="approved">
            approved
          </option>
          <option value="drafting">
            drafting
          </option>
          <option value="published">
            published
          </option>
          <option value="rejected">
            rejected
          </option>
        </select>
      </label>
      <button
        type="button"
        class="ml-auto rounded border border-gray-300 bg-white px-2 py-1 text-xs hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-900 dark:hover:bg-gray-800"
        @click="selection = new Set()"
      >
        Clear
      </button>
    </div>

    <div
      v-if="empty"
      class="rounded border border-dashed border-gray-300 p-8 text-center text-sm text-gray-600 dark:border-gray-700 dark:text-gray-300"
    >
      <p class="mb-2 text-base font-medium text-gray-900 dark:text-white">
        No topics yet
      </p>
      <p class="mb-4">
        Topics seed the article queue. Create one manually, or paste a list.
      </p>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        @click="openCreate"
      >
        Create topic
      </button>
    </div>

    <DataTable
      v-else
      :items="filteredItems"
      :columns="columns"
      :loading="loading"
      :next-cursor="nextCursor"
      :selection="selection"
      :sort-key="sortKey"
      :sort-dir="sortDir"
      aria-label="Topics"
      empty-message="No topics match the filters"
      @row-click="openPreview"
      @selection-change="onSelectionChange"
      @sort="onSort"
      @load-more="loadMore"
    >
      <template #cell:status="{ row }">
        <StatusBadge
          :status="(row as Topic).status"
          kind="topic"
        />
      </template>
      <template #cell:cluster_id="{ row }">
        {{ clusterName((row as Topic).cluster_id) }}
      </template>
    </DataTable>

    <!-- New topic modal -->
    <div
      v-if="showCreate"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-new-topic-title"
      @click.self="closeCreate"
    >
      <div
        class="w-full max-w-lg rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h2
          id="cs-new-topic-title"
          class="mb-3 text-lg font-semibold"
        >
          New topic
        </h2>
        <form
          class="space-y-3"
          @submit.prevent="submitCreate"
        >
          <label class="block text-sm">
            <span class="font-medium">Title</span>
            <input
              v-model="draft.title"
              type="text"
              required
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            >
          </label>
          <label class="block text-sm">
            <span class="font-medium">Primary keyword</span>
            <input
              v-model="draft.primary_kw"
              type="text"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-sm dark:border-gray-700 dark:bg-gray-800"
            >
          </label>
          <label class="block text-sm">
            <span class="font-medium">Secondary keywords</span>
            <input
              v-model="draft.secondary_kws"
              type="text"
              placeholder="comma, separated, list"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-sm dark:border-gray-700 dark:bg-gray-800"
            >
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="block text-sm">
              <span class="font-medium">Intent</span>
              <select
                v-model="draft.intent"
                class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
              >
                <option
                  v-for="i in INTENT_OPTIONS"
                  :key="i"
                  :value="i"
                >
                  {{ i }}
                </option>
              </select>
            </label>
            <label class="block text-sm">
              <span class="font-medium">Source</span>
              <select
                v-model="draft.source"
                class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
              >
                <option
                  v-for="s in SOURCE_OPTIONS"
                  :key="s"
                  :value="s"
                >
                  {{ s }}
                </option>
              </select>
            </label>
          </div>
          <label class="block text-sm">
            <span class="font-medium">Cluster</span>
            <select
              v-model="draft.cluster_id"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            >
              <option :value="null">
                — none —
              </option>
              <option
                v-for="c in clustersStore.items"
                :key="c.id"
                :value="c.id"
              >
                {{ c.name }}
              </option>
            </select>
          </label>
          <label class="block text-sm">
            <span class="font-medium">Priority {{ draft.priority }}</span>
            <input
              v-model.number="draft.priority"
              type="range"
              min="0"
              max="100"
              class="mt-1 w-full"
            >
          </label>
          <div class="mt-4 flex justify-end gap-2">
            <button
              type="button"
              class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
              :disabled="submitting"
              @click="closeCreate"
            >
              Cancel
            </button>
            <button
              type="submit"
              class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              :disabled="submitting"
            >
              {{ submitting ? 'Creating…' : 'Create topic' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Bulk create modal -->
    <div
      v-if="showBulkCreate"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-bulk-topic-title"
      @click.self="closeBulkCreate"
    >
      <div
        class="w-full max-w-lg rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h2
          id="cs-bulk-topic-title"
          class="mb-3 text-lg font-semibold"
        >
          Bulk create topics
        </h2>
        <form
          class="space-y-3"
          @submit.prevent="submitBulkCreate"
        >
          <label class="block text-sm">
            <span class="font-medium">Titles (one per line)</span>
            <textarea
              v-model="bulkDraft.titles"
              rows="8"
              required
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs dark:border-gray-700 dark:bg-gray-800"
            />
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="block text-sm">
              <span class="font-medium">Intent</span>
              <select
                v-model="bulkDraft.intent"
                class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
              >
                <option
                  v-for="i in INTENT_OPTIONS"
                  :key="i"
                  :value="i"
                >
                  {{ i }}
                </option>
              </select>
            </label>
            <label class="block text-sm">
              <span class="font-medium">Source</span>
              <select
                v-model="bulkDraft.source"
                class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
              >
                <option
                  v-for="s in SOURCE_OPTIONS"
                  :key="s"
                  :value="s"
                >
                  {{ s }}
                </option>
              </select>
            </label>
          </div>
          <div class="mt-4 flex justify-end gap-2">
            <button
              type="button"
              class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
              :disabled="submitting"
              @click="closeBulkCreate"
            >
              Cancel
            </button>
            <button
              type="submit"
              class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              :disabled="submitting"
            >
              {{ submitting ? 'Creating…' : 'Create batch' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Preview modal -->
    <div
      v-if="previewTopic"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-topic-preview-title"
      @click.self="closePreview"
    >
      <div
        class="w-full max-w-lg rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <div class="mb-3 flex items-baseline justify-between">
          <h2
            id="cs-topic-preview-title"
            class="text-lg font-semibold"
          >
            {{ previewTopic.title }}
          </h2>
          <button
            type="button"
            class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            @click="closePreview"
          >
            Close
          </button>
        </div>
        <dl class="grid gap-2 text-sm">
          <div class="flex justify-between">
            <dt class="text-gray-600 dark:text-gray-400">
              Status
            </dt>
            <dd>
              <StatusBadge
                :status="previewTopic.status"
                kind="topic"
              />
            </dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-600 dark:text-gray-400">
              Primary KW
            </dt>
            <dd class="font-mono text-xs">
              {{ previewTopic.primary_kw || '—' }}
            </dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-600 dark:text-gray-400">
              Secondary KWs
            </dt>
            <dd class="text-right text-xs">
              <span
                v-if="(previewTopic.secondary_kws ?? []).length > 0"
                class="font-mono"
              >
                {{ (previewTopic.secondary_kws ?? []).join(', ') }}
              </span>
              <span
                v-else
                class="text-gray-500"
              >—</span>
            </dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-600 dark:text-gray-400">
              Intent
            </dt>
            <dd>{{ previewTopic.intent }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-600 dark:text-gray-400">
              Source
            </dt>
            <dd>{{ previewTopic.source }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-600 dark:text-gray-400">
              Priority
            </dt>
            <dd>{{ previewTopic.priority ?? '—' }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-600 dark:text-gray-400">
              Cluster
            </dt>
            <dd>{{ clusterName(previewTopic.cluster_id) }}</dd>
          </div>
        </dl>
        <div
          v-if="previewTopic.status === 'queued'"
          class="mt-4 flex justify-end gap-2"
        >
          <button
            type="button"
            class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            @click="rejectOne(previewTopic); closePreview()"
          >
            Reject
          </button>
          <button
            type="button"
            class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
            @click="approveOne(previewTopic); closePreview()"
          >
            Approve
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
