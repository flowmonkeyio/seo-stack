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
import StatusBadge from '@/components/StatusBadge.vue'
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
    const page = await apiFetch<VoicesPage>(`/api/v1/projects/${projectId.value}/voice`)
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
  <div class="mx-auto max-w-7xl">
    <header class="mb-4 flex flex-wrap items-baseline justify-between gap-3">
      <h1 class="text-2xl font-bold tracking-tight">
        Articles
      </h1>
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          class="rounded border border-gray-300 px-3 py-2 text-sm hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:border-gray-700 dark:hover:bg-gray-800"
          :aria-pressed="showRefreshDue"
          @click="showRefreshDue ? showRefreshDue = false : loadRefreshDue()"
        >
          {{ showRefreshDue ? 'Show all' : 'Due for refresh' }}
        </button>
        <button
          type="button"
          class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
          @click="openCreate"
        >
          New article
        </button>
      </div>
    </header>

    <p
      v-if="error"
      class="mb-3 rounded bg-red-50 p-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200"
    >
      {{ error }}
    </p>

    <div
      v-if="!showRefreshDue"
      role="tablist"
      aria-label="Article status filter"
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

    <div
      v-if="!showRefreshDue"
      class="mb-3 flex flex-wrap items-center gap-3 text-sm"
    >
      <label class="flex items-center gap-2">
        <span class="text-gray-600 dark:text-gray-400">Author</span>
        <select
          :value="filters.author_id !== null ? String(filters.author_id) : ''"
          class="rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
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
        <span class="text-gray-600 dark:text-gray-400">Topic</span>
        <select
          :value="filters.topic_id !== null ? String(filters.topic_id) : ''"
          class="rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
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
        <span class="text-gray-600 dark:text-gray-400">Sort</span>
        <select
          :value="articlesStore.sort"
          class="rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
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

    <div
      v-if="selection.size > 0 && !showRefreshDue"
      class="mb-3 flex flex-wrap items-center gap-2 rounded border border-blue-300 bg-blue-50 p-2 text-sm dark:border-blue-700 dark:bg-blue-900/30"
      role="status"
      aria-live="polite"
    >
      <span class="font-medium">{{ selection.size }} selected</span>
      <button
        type="button"
        class="rounded border border-blue-300 bg-white px-2 py-1 text-xs hover:bg-blue-100 disabled:opacity-50 dark:border-blue-700 dark:bg-blue-900/60"
        :disabled="bulkActionPending"
        @click="bulkMarkRefreshDue"
      >
        Mark refresh-due
      </button>
      <button
        type="button"
        class="ml-auto rounded border border-gray-300 bg-white px-2 py-1 text-xs hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-900"
        @click="selection = new Set()"
      >
        Clear
      </button>
    </div>

    <div
      v-if="empty && !showRefreshDue"
      class="rounded border border-dashed border-gray-300 p-8 text-center text-sm text-gray-600 dark:border-gray-700 dark:text-gray-300"
    >
      <p class="mb-2 text-base font-medium text-gray-900 dark:text-white">
        No articles yet
      </p>
      <p class="mb-4">
        Articles are created from approved topics and progress through a state
        machine: briefing → outlined → drafted → edited → EEAT-passed → published.
      </p>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        @click="openCreate"
      >
        Create article
      </button>
    </div>

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

    <!-- New article modal -->
    <div
      v-if="showCreate"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-new-article-title"
      @click.self="closeCreate"
    >
      <div
        class="w-full max-w-lg rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h2
          id="cs-new-article-title"
          class="mb-3 text-lg font-semibold"
        >
          New article
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
              {{ submitting ? 'Creating…' : 'Create article' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
