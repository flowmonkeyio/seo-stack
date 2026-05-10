<script setup lang="ts">
// ArticlesView — article workspace.
//
// Status pill bar drives the `status` filter. Filter bar adds author /
// topic / cluster narrowing client-side (the REST endpoint accepts
// `status` + `topic_id` natively per articles.py L254-L266; the rest are
// client-side per-row filters).

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

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
import { useArticlesStore, type Article, type ArticleStatus } from '@/stores/articles'
import { useTopicsStore } from '@/stores/topics'
import { useToastsStore } from '@/stores/toasts'
import { apiFetch } from '@/lib/client'
import { ArticleStatus as ArticleStatusEnum, type components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type AuthorOut = components['schemas']['AuthorOut']
type AuthorsPage = components['schemas']['PageResponse_AuthorOut_']
type VoiceOut = components['schemas']['VoiceProfileOut']
type VoicesPage = components['schemas']['PageResponse_VoiceProfileOut_']

const route = useRoute()
const router = useRouter()
const articlesStore = useArticlesStore()
const topicsStore = useTopicsStore()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { filteredItems, loading, nextCursor, error, filters } = storeToRefs(articlesStore)

const selection = ref<Set<number>>(new Set())
const showCreate = ref(false)
const submitting = ref(false)
const showRefreshDue = ref(false)
const refreshDueItems = ref<Article[]>([])
const authors = ref<AuthorOut[]>([])
const voices = ref<VoiceOut[]>([])
const bulkActionPending = ref(false)

interface NewArticle {
  title: string
  slug: string
  topic_id: number | null
  voice_id: number | null
  author_id: number | null
  eeat_criteria_version: number
}

const draft = ref<NewArticle>(emptyDraft())
function emptyDraft(): NewArticle {
  return {
    title: '',
    slug: '',
    topic_id: null,
    voice_id: null,
    author_id: null,
    eeat_criteria_version: 1,
  }
}

const STATUS_OPTIONS: { key: 'all' | `${ArticleStatusEnum}`; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'briefing', label: 'Briefing' },
  { key: 'outlined', label: 'Outlined' },
  { key: 'drafted', label: 'Drafted' },
  { key: 'edited', label: 'Edited' },
  { key: 'eeat_passed', label: 'EEAT Passed' },
  { key: 'published', label: 'Published' },
  { key: 'refresh_due', label: 'Refresh Due' },
  { key: 'aborted-publish', label: 'Aborted Publish' },
]

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

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 80)
}

watch(
  () => draft.value.title,
  (name) => {
    if (!draft.value.slug || draft.value.slug === slugify(draft.value.slug)) {
      draft.value.slug = slugify(name)
    }
  },
)

function setStatusFilter(opt: 'all' | `${ArticleStatusEnum}`): void {
  articlesStore.setFilter('status', opt === 'all' ? null : (opt as ArticleStatus))
  void articlesStore.refresh(projectId.value)
}

function onStatusSelect(key: string | number): void {
  setStatusFilter(String(key) as 'all' | `${ArticleStatusEnum}`)
}

function onSortChange(ev: Event): void {
  const value = (ev.target as HTMLSelectElement).value as
    | 'created_at'
    | '-created_at'
    | 'updated_at'
    | '-updated_at'
    | 'title'
  articlesStore.setSort(value)
}

function setAuthorFilter(value: string): void {
  articlesStore.setFilter('author_id', value === '' ? null : Number.parseInt(value, 10))
}

function setTopicFilter(value: string): void {
  articlesStore.setFilter('topic_id', value === '' ? null : Number.parseInt(value, 10))
  void articlesStore.refresh(projectId.value)
}

function authorName(id: number | null): string {
  if (id === null) return '—'
  return authors.value.find((a) => a.id === id)?.name ?? `#${id}`
}

function topicTitle(id: number | null): string {
  if (id === null) return '—'
  return topicsStore.getById(id)?.title ?? `#${id}`
}

function openDetail(row: Article): void {
  void router.push(`/projects/${projectId.value}/articles/${row.id}`)
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
  if (!draft.value.title.trim() || !draft.value.slug.trim()) {
    toasts.error('Missing required fields', 'Title and slug are required.')
    return
  }
  submitting.value = true
  try {
    const created = await articlesStore.create(projectId.value, {
      title: draft.value.title.trim(),
      slug: draft.value.slug.trim(),
      topic_id: draft.value.topic_id,
      voice_id: draft.value.voice_id,
      author_id: draft.value.author_id,
      eeat_criteria_version: draft.value.eeat_criteria_version,
    })
    toasts.success('Article created', created.title)
    showCreate.value = false
    void router.push(`/projects/${projectId.value}/articles/${created.id}`)
  } catch (err) {
    toasts.error('Failed to create article', err instanceof Error ? err.message : undefined)
  } finally {
    submitting.value = false
  }
}

async function bulkMarkRefreshDue(): Promise<void> {
  if (selection.value.size === 0) return
  bulkActionPending.value = true
  try {
    let success = 0
    for (const id of selection.value) {
      try {
        await articlesStore.markRefreshDue(id, { reason: 'bulk-marked-from-ui' })
        success++
      } catch {
        // single-row failure surfaces as a toast at end; keep going.
      }
    }
    toasts.success('Refresh queue', `${success}/${selection.value.size} marked refresh-due`)
    selection.value = new Set()
    await articlesStore.refresh(projectId.value)
  } finally {
    bulkActionPending.value = false
  }
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
    loadVoices(),
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

async function loadVoices(): Promise<void> {
  try {
    const page = await apiFetch<VoicesPage>(
      `/api/v1/projects/${projectId.value}/voice/variants?limit=200`,
    )
    voices.value = page.items
  } catch {
    voices.value = []
  }
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
      title="Articles"
      description="Move articles through brief, outline, draft, editorial, EEAT, publishing, and refresh workflows."
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
        <UiButton
          variant="primary"
          @click="openCreate"
        >
          New article
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
      class="flex flex-wrap items-center gap-3 text-sm"
    >
      <label class="flex items-center gap-2">
        <span class="text-fg-muted">Author</span>
        <select
          :value="filters.author_id !== null ? String(filters.author_id) : ''"
          class="h-8 rounded-sm border border-default bg-bg-surface px-2 text-sm text-fg-default focus-ring"
          @change="setAuthorFilter(($event.target as HTMLSelectElement).value)"
        >
          <option value="">
            All
          </option>
          <option
            v-for="a in authors"
            :key="a.id"
            :value="a.id"
          >
            {{ a.name }}
          </option>
        </select>
      </label>
      <label class="flex items-center gap-2">
        <span class="text-fg-muted">Topic</span>
        <select
          :value="filters.topic_id !== null ? String(filters.topic_id) : ''"
          class="h-8 rounded-sm border border-default bg-bg-surface px-2 text-sm text-fg-default focus-ring"
          @change="setTopicFilter(($event.target as HTMLSelectElement).value)"
        >
          <option value="">
            All
          </option>
          <option
            v-for="t in topicsStore.items"
            :key="t.id"
            :value="t.id"
          >
            {{ t.title }}
          </option>
        </select>
      </label>
      <label class="flex items-center gap-2">
        <span class="text-fg-muted">Sort</span>
        <select
          :value="articlesStore.sort"
          class="h-8 rounded-sm border border-default bg-bg-surface px-2 text-sm text-fg-default focus-ring"
          @change="onSortChange"
        >
          <option value="-created_at">
            created desc
          </option>
          <option value="created_at">
            created asc
          </option>
          <option value="-updated_at">
            updated desc
          </option>
          <option value="updated_at">
            updated asc
          </option>
          <option value="title">
            title
          </option>
        </select>
      </label>
    </div>

    <UiBulkActionBar
      v-if="selection.size > 0 && !showRefreshDue"
      :count="selection.size"
      aria-label="Selected articles"
      @clear="selection = new Set()"
    >
      <UiButton
        size="sm"
        variant="secondary"
        :disabled="bulkActionPending"
        @click="bulkMarkRefreshDue"
      >
        Mark refresh-due
      </UiButton>
    </UiBulkActionBar>

    <UiEmptyState
      v-if="empty && !showRefreshDue"
      title="No articles yet"
      description="Articles are created from approved topics and progress through brief, outline, draft, edit, EEAT, and publish states."
      size="lg"
    >
      <template #actions>
        <UiButton
          variant="primary"
          @click="openCreate"
        >
          Create article
        </UiButton>
      </template>
    </UiEmptyState>

    <DataTable
      v-if="!showRefreshDue && !empty"
      :items="filteredItems"
      :columns="columns"
      :loading="loading"
      :next-cursor="nextCursor"
      :selection="selection"
      aria-label="Articles"
      empty-message="No articles match the filters"
      @row-click="openDetail"
      @selection-change="(next: Set<number>) => selection = new Set(next)"
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

    <UiDialog
      :model-value="showCreate"
      title="New article"
      description="Create an article shell from a topic, voice profile, and author assignment."
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
          <span class="font-medium">Slug</span>
          <input
            v-model="draft.slug"
            type="text"
            required
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-sm dark:border-gray-700 dark:bg-gray-800"
          >
        </label>
        <label class="block text-sm">
          <span class="font-medium">Topic</span>
          <select
            v-model="draft.topic_id"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
          >
            <option :value="null">
              — none —
            </option>
            <option
              v-for="t in topicsStore.items"
              :key="t.id"
              :value="t.id"
            >
              {{ t.title }}
            </option>
          </select>
        </label>
        <div class="grid grid-cols-2 gap-3">
          <label class="block text-sm">
            <span class="font-medium">Voice</span>
            <select
              v-model="draft.voice_id"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            >
              <option :value="null">
                default
              </option>
              <option
                v-for="v in voices"
                :key="v.id"
                :value="v.id"
              >
                {{ v.name }}
              </option>
            </select>
          </label>
          <label class="block text-sm">
            <span class="font-medium">Author</span>
            <select
              v-model="draft.author_id"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            >
              <option :value="null">
                — none —
              </option>
              <option
                v-for="a in authors"
                :key="a.id"
                :value="a.id"
              >
                {{ a.name }}
              </option>
            </select>
          </label>
        </div>
        <label class="block text-sm">
          <span class="font-medium">EEAT criteria version</span>
          <input
            v-model.number="draft.eeat_criteria_version"
            type="number"
            min="1"
            class="mt-1 w-32 rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
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
          Create article
        </UiButton>
      </template>
    </UiDialog>
  </UiPageShell>
</template>
