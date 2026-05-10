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
import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  UiBulkActionBar,
  UiButton,
  UiCallout,
  UiDialog,
  UiEmptyState,
  UiPageShell,
  UiSegmentedControl,
} from '@/components/ui'
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

function onStatusSelect(key: string | number): void {
  setStatusFilter(String(key) as 'all' | `${TopicStatusEnum}`)
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
  <UiPageShell>
    <ProjectPageHeader
      :project-id="projectId"
      title="Topics"
      description="Review, approve, cluster, reject, and bulk-manage the topic queue before articles are created."
      :breadcrumbs="[{ label: 'Topics' }]"
    >
      <template #actions>
        <UiButton
          variant="secondary"
          @click="openBulkCreate"
        >
          Bulk create
        </UiButton>
        <UiButton
          variant="primary"
          @click="openCreate"
        >
          New topic
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
      :model-value="filters.status ?? 'all'"
      :options="STATUS_OPTIONS"
      label="Topic status filter"
      @select="onStatusSelect"
    />

    <div class="flex flex-wrap items-center gap-3 text-sm">
      <label class="flex items-center gap-2">
        <span class="text-fg-muted">Source</span>
        <select
          :value="filters.source ?? ''"
          class="h-8 rounded-sm border border-default bg-bg-surface px-2 text-sm text-fg-default focus-ring"
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
        <span class="text-fg-muted">Intent</span>
        <select
          :value="filters.intent ?? ''"
          class="h-8 rounded-sm border border-default bg-bg-surface px-2 text-sm text-fg-default focus-ring"
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
        <span class="text-fg-muted">Cluster</span>
        <select
          :value="filters.cluster_id !== null ? String(filters.cluster_id) : ''"
          class="h-8 rounded-sm border border-default bg-bg-surface px-2 text-sm text-fg-default focus-ring"
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
        <span class="text-fg-muted">Sort</span>
        <select
          :value="sort"
          class="h-8 rounded-sm border border-default bg-bg-surface px-2 text-sm text-fg-default focus-ring"
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

    <UiBulkActionBar
      v-if="selection.size > 0"
      :count="selection.size"
      aria-label="Selected topics"
      @clear="selection = new Set()"
    >
      <UiButton
        size="sm"
        variant="secondary"
        :disabled="bulkActionPending"
        @click="bulkApprove"
      >
        Approve selected
      </UiButton>
      <UiButton
        size="sm"
        variant="secondary"
        :disabled="bulkActionPending"
        @click="bulkReject"
      >
        Reject selected
      </UiButton>
      <label class="flex items-center gap-1 text-xs text-fg-muted">
        Set status…
        <select
          class="h-7 rounded-sm border border-default bg-bg-surface px-2 text-xs text-fg-default focus-ring"
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
    </UiBulkActionBar>

    <UiEmptyState
      v-if="empty"
      title="No topics yet"
      description="Topics seed the article queue. Create one manually, or paste a list."
      size="lg"
    >
      <template #actions>
        <UiButton
          variant="primary"
          @click="openCreate"
        >
          Create topic
        </UiButton>
      </template>
    </UiEmptyState>

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

    <UiDialog
      :model-value="showCreate"
      title="New topic"
      description="Add one topic to the queue with optional keyword, cluster, source, and priority metadata."
      size="lg"
      @update:model-value="(open: boolean) => open ? showCreate = true : closeCreate()"
    >
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
      </form>
      <template #footer>
        <UiButton
          variant="secondary"
          :disabled="submitting"
          @click="closeCreate"
        >
          Cancel
        </UiButton>
        <UiButton
          variant="primary"
          :loading="submitting"
          @click="submitCreate"
        >
          Create topic
        </UiButton>
      </template>
    </UiDialog>

    <UiDialog
      :model-value="showBulkCreate"
      title="Bulk create topics"
      description="Paste one title per line and apply shared intent/source metadata to the batch."
      size="lg"
      @update:model-value="(open: boolean) => open ? showBulkCreate = true : closeBulkCreate()"
    >
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
      </form>
      <template #footer>
        <UiButton
          variant="secondary"
          :disabled="submitting"
          @click="closeBulkCreate"
        >
          Cancel
        </UiButton>
        <UiButton
          variant="primary"
          :loading="submitting"
          @click="submitBulkCreate"
        >
          Create batch
        </UiButton>
      </template>
    </UiDialog>

    <UiDialog
      :model-value="previewTopic !== null"
      :title="previewTopic?.title ?? 'Topic'"
      size="lg"
      @update:model-value="(open: boolean) => open ? undefined : closePreview()"
    >
      <template v-if="previewTopic">
        <dl class="grid gap-2 text-sm">
          <div class="flex justify-between">
            <dt class="text-fg-muted">
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
            <dt class="text-fg-muted">
              Primary KW
            </dt>
            <dd class="font-mono text-xs">
              {{ previewTopic.primary_kw || '—' }}
            </dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-fg-muted">
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
                class="text-fg-muted"
              >—</span>
            </dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-fg-muted">
              Intent
            </dt>
            <dd>{{ previewTopic.intent }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-fg-muted">
              Source
            </dt>
            <dd>{{ previewTopic.source }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-fg-muted">
              Priority
            </dt>
            <dd>{{ previewTopic.priority ?? '—' }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-fg-muted">
              Cluster
            </dt>
            <dd>{{ clusterName(previewTopic.cluster_id) }}</dd>
          </div>
        </dl>
      </template>
      <template #footer>
        <UiButton
          variant="secondary"
          @click="closePreview"
        >
          Close
        </UiButton>
        <template v-if="previewTopic?.status === 'queued'">
          <UiButton
            variant="secondary"
            @click="rejectOne(previewTopic); closePreview()"
          >
            Reject
          </UiButton>
          <UiButton
            variant="primary"
            @click="approveOne(previewTopic); closePreview()"
          >
            Approve
          </UiButton>
        </template>
      </template>
    </UiDialog>
  </UiPageShell>
</template>
