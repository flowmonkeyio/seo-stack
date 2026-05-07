<script setup lang="ts">
// InterlinksView — internal-link graph + suggest/apply/dismiss/repair flow.
//
// Wires to the interlinks Pinia store. Heavy bulk-actions UX per audit M-31.
//
// Status pill bar drives the `status` filter (server-side). Filter bar
// adds from/to article narrowing (server-side) + a score-min slider that
// filters client-side because the wire shape doesn't expose a score.
// "Suggest" calls /interlinks/suggest with an empty payload — the daemon
// wraps the underlying ranker in M5/M7 — which lands suggestions for the
// project. "Repair" iterates known articles and reflows broken links.

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useInterlinksStore, type InternalLink } from '@/stores/interlinks'
import { useArticlesStore } from '@/stores/articles'
import { useToastsStore } from '@/stores/toasts'
import { InternalLinkStatus as InternalLinkStatusEnum } from '@/api'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const router = useRouter()
const interlinksStore = useInterlinksStore()
const articlesStore = useArticlesStore()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { filteredItems, loading, nextCursor, error, filters } = storeToRefs(interlinksStore)

const selection = ref<Set<number>>(new Set())
const bulkPending = ref(false)
const repairOpen = ref(false)
const repairArticleId = ref<number | null>(null)
const repairPending = ref(false)
const detailOpen = ref<InternalLink | null>(null)

const STATUS_OPTIONS: { key: 'all' | `${InternalLinkStatusEnum}`; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'suggested', label: 'Suggested' },
  { key: 'applied', label: 'Applied' },
  { key: 'dismissed', label: 'Dismissed' },
  { key: 'broken', label: 'Broken' },
]

const columns: DataTableColumn<InternalLink>[] = [
  { key: 'from_article_id', label: 'From article' },
  { key: 'anchor_text', label: 'Anchor' },
  { key: 'to_article_id', label: 'To article' },
  { key: 'position', label: 'Position', widthClass: 'w-20' },
  { key: 'status', label: 'Status' },
]

function setStatusFilter(opt: 'all' | `${InternalLinkStatusEnum}`): void {
  interlinksStore.setFilter('status', opt === 'all' ? null : (opt as InternalLinkStatusEnum))
  void interlinksStore.refresh(projectId.value)
}

function setFromFilter(value: string): void {
  interlinksStore.setFilter('from_article_id', value === '' ? null : Number.parseInt(value, 10))
  void interlinksStore.refresh(projectId.value)
}

function setToFilter(value: string): void {
  interlinksStore.setFilter('to_article_id', value === '' ? null : Number.parseInt(value, 10))
  void interlinksStore.refresh(projectId.value)
}

function setScoreMin(value: number): void {
  interlinksStore.setFilter('score_min', value)
}

function setSort(key: string): void {
  interlinksStore.setSort(key as 'id' | '-id' | 'created_at' | '-created_at')
}

function articleTitle(id: number): string {
  return articlesStore.getById(id)?.title ?? `#${id}`
}

async function loadMore(): Promise<void> {
  await interlinksStore.loadMore(projectId.value)
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  interlinksStore.reset()
  await Promise.all([
    interlinksStore.refresh(projectId.value),
    articlesStore.items.length === 0
      ? articlesStore.refresh(projectId.value)
      : Promise.resolve(),
  ])
}

async function suggestMore(): Promise<void> {
  // The daemon's `suggest` endpoint accepts a list of {from,to,anchor,position}
  // rows. M5.C surfaces the operator-driven suggest shape: we POST with an
  // empty list which the repository interprets as a no-op idempotent call.
  // Once the M7 interlinker skill ships it will populate this list with
  // ML-ranked candidates. The button still works pre-M7 — it just adds zero
  // rows and reloads the table.
  try {
    await interlinksStore.suggest(projectId.value, [])
    toasts.success('Suggestions updated')
    await interlinksStore.refresh(projectId.value)
  } catch (err) {
    toasts.error('Failed to suggest', err instanceof Error ? err.message : undefined)
  }
}

async function applyOne(row: InternalLink): Promise<void> {
  try {
    await interlinksStore.apply(projectId.value, row.id)
    toasts.success('Interlink applied', `${row.anchor_text}`)
  } catch (err) {
    toasts.error('Apply failed', err instanceof Error ? err.message : undefined)
  }
}

async function dismissOne(row: InternalLink): Promise<void> {
  try {
    await interlinksStore.dismiss(projectId.value, row.id)
    toasts.success('Interlink dismissed', `${row.anchor_text}`)
  } catch (err) {
    toasts.error('Dismiss failed', err instanceof Error ? err.message : undefined)
  }
}

async function applySelected(): Promise<void> {
  if (selection.value.size === 0) return
  bulkPending.value = true
  try {
    const ids = Array.from(selection.value)
    await interlinksStore.bulkApply(projectId.value, ids)
    toasts.success('Bulk apply', `${ids.length} interlinks applied`)
    selection.value = new Set()
  } catch (err) {
    toasts.error('Bulk apply failed', err instanceof Error ? err.message : undefined)
  } finally {
    bulkPending.value = false
  }
}

async function dismissSelected(): Promise<void> {
  if (selection.value.size === 0) return
  bulkPending.value = true
  try {
    let success = 0
    for (const id of selection.value) {
      try {
        await interlinksStore.dismiss(projectId.value, id)
        success++
      } catch {
        // single-row failure surfaces in toast at end
      }
    }
    toasts.success('Bulk dismiss', `${success}/${selection.value.size} dismissed`)
    selection.value = new Set()
  } finally {
    bulkPending.value = false
  }
}

function openRepair(): void {
  repairOpen.value = true
  repairArticleId.value = null
}

async function submitRepair(): Promise<void> {
  if (!repairArticleId.value) {
    toasts.error('Article required', 'Pick an article to repair links for.')
    return
  }
  repairPending.value = true
  try {
    const rows = await interlinksStore.repair(projectId.value, repairArticleId.value)
    toasts.success('Repair complete', `${rows.length} links flipped to broken`)
    repairOpen.value = false
    await interlinksStore.refresh(projectId.value)
  } catch (err) {
    toasts.error('Repair failed', err instanceof Error ? err.message : undefined)
  } finally {
    repairPending.value = false
  }
}

function openDetail(row: InternalLink): void {
  detailOpen.value = row
}

function closeDetail(): void {
  detailOpen.value = null
}

function gotoArticle(id: number): void {
  void router.push(`/projects/${projectId.value}/articles/${id}`)
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
        Interlinks
      </h1>
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          class="rounded border border-gray-300 px-3 py-2 text-sm hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:border-gray-700 dark:hover:bg-gray-800"
          @click="openRepair"
        >
          Repair
        </button>
        <button
          type="button"
          class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
          @click="suggestMore"
        >
          Suggest interlinks
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
      role="tablist"
      aria-label="Interlink status filter"
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

    <div class="mb-3 flex flex-wrap items-center gap-3 text-sm">
      <label class="flex items-center gap-2">
        <span class="text-gray-600 dark:text-gray-400">From article</span>
        <select
          :value="filters.from_article_id !== null ? String(filters.from_article_id) : ''"
          class="rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
          aria-label="Filter from article"
          @change="setFromFilter(($event.target as HTMLSelectElement).value)"
        >
          <option value="">
            All
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
      <label class="flex items-center gap-2">
        <span class="text-gray-600 dark:text-gray-400">To article</span>
        <select
          :value="filters.to_article_id !== null ? String(filters.to_article_id) : ''"
          class="rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
          aria-label="Filter to article"
          @change="setToFilter(($event.target as HTMLSelectElement).value)"
        >
          <option value="">
            All
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
      <label class="flex items-center gap-2">
        <span class="text-gray-600 dark:text-gray-400">Score min</span>
        <input
          :value="filters.score_min"
          type="range"
          min="0"
          max="1"
          step="0.05"
          class="w-32"
          aria-label="Score minimum"
          @input="setScoreMin(Number.parseFloat(($event.target as HTMLInputElement).value))"
        >
        <span class="w-8 text-right text-xs text-gray-500 dark:text-gray-400">{{ filters.score_min.toFixed(2) }}</span>
      </label>
      <label class="flex items-center gap-2">
        <span class="text-gray-600 dark:text-gray-400">Sort</span>
        <select
          :value="interlinksStore.sort"
          class="rounded border border-gray-300 px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
          aria-label="Sort"
          @change="setSort(($event.target as HTMLSelectElement).value)"
        >
          <option value="-id">
            score desc
          </option>
          <option value="id">
            score asc
          </option>
          <option value="-created_at">
            created desc
          </option>
          <option value="created_at">
            created asc
          </option>
        </select>
      </label>
    </div>

    <div
      v-if="selection.size > 0"
      class="mb-3 flex flex-wrap items-center gap-2 rounded border border-blue-300 bg-blue-50 p-2 text-sm dark:border-blue-700 dark:bg-blue-900/30"
      role="status"
      aria-live="polite"
    >
      <span class="font-medium">{{ selection.size }} selected</span>
      <button
        type="button"
        class="rounded border border-blue-300 bg-white px-2 py-1 text-xs hover:bg-blue-100 disabled:opacity-50 dark:border-blue-700 dark:bg-blue-900/60"
        :disabled="bulkPending"
        @click="applySelected"
      >
        Apply selected
      </button>
      <button
        type="button"
        class="rounded border border-blue-300 bg-white px-2 py-1 text-xs hover:bg-blue-100 disabled:opacity-50 dark:border-blue-700 dark:bg-blue-900/60"
        :disabled="bulkPending"
        @click="dismissSelected"
      >
        Dismiss selected
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
      v-if="empty"
      class="rounded border border-dashed border-gray-300 p-8 text-center text-sm text-gray-600 dark:border-gray-700 dark:text-gray-300"
    >
      <p class="mb-2 text-base font-medium text-gray-900 dark:text-white">
        No interlinks yet
      </p>
      <p class="mb-4">
        The interlinker skill ships in M7. Until then, use the "Suggest interlinks" button or
        manually create links via MCP / REST.
      </p>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        @click="suggestMore"
      >
        Suggest interlinks
      </button>
    </div>

    <DataTable
      v-if="!empty"
      :items="filteredItems"
      :columns="columns"
      :loading="loading"
      :next-cursor="nextCursor"
      :selection="selection"
      aria-label="Interlinks"
      empty-message="No interlinks match the filters"
      @row-click="openDetail"
      @selection-change="(next: Set<number>) => selection = new Set(next)"
      @load-more="loadMore"
    >
      <template #cell:from_article_id="{ row }">
        <button
          type="button"
          class="text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:text-blue-300"
          @click.stop="gotoArticle((row as InternalLink).from_article_id)"
        >
          {{ articleTitle((row as InternalLink).from_article_id) }}
        </button>
      </template>
      <template #cell:to_article_id="{ row }">
        <button
          type="button"
          class="text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:text-blue-300"
          @click.stop="gotoArticle((row as InternalLink).to_article_id)"
        >
          {{ articleTitle((row as InternalLink).to_article_id) }}
        </button>
      </template>
      <template #cell:status="{ row }">
        <div class="flex items-center gap-2">
          <StatusBadge
            :status="(row as InternalLink).status"
            kind="interlink"
          />
          <button
            v-if="(row as InternalLink).status === 'suggested'"
            type="button"
            class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            :aria-label="`Apply interlink ${(row as InternalLink).id}`"
            @click.stop="applyOne(row as InternalLink)"
          >
            Apply
          </button>
          <button
            v-if="(row as InternalLink).status === 'suggested'"
            type="button"
            class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            :aria-label="`Dismiss interlink ${(row as InternalLink).id}`"
            @click.stop="dismissOne(row as InternalLink)"
          >
            Dismiss
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Repair modal -->
    <div
      v-if="repairOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-repair-title"
      @click.self="repairOpen = false"
    >
      <div
        class="w-full max-w-md rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h2
          id="cs-repair-title"
          class="mb-3 text-lg font-semibold"
        >
          Repair interlinks
        </h2>
        <p class="mb-3 text-sm text-gray-600 dark:text-gray-400">
          Mark all live interlinks pointing at the selected article as
          <strong>broken</strong>. Use this after unpublishing or deleting
          an article so dangling links surface in the broken filter.
        </p>
        <label class="mb-3 block text-sm">
          <span class="font-medium">Article</span>
          <select
            v-model="repairArticleId"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
          >
            <option :value="null">
              — pick an article —
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
        <div class="flex justify-end gap-2">
          <button
            type="button"
            class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            :disabled="repairPending"
            @click="repairOpen = false"
          >
            Cancel
          </button>
          <button
            type="button"
            class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            :disabled="repairPending"
            @click="submitRepair"
          >
            {{ repairPending ? 'Repairing…' : 'Repair links' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Detail modal -->
    <div
      v-if="detailOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-detail-title"
      @click.self="closeDetail"
    >
      <div
        class="w-full max-w-md rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h2
          id="cs-detail-title"
          class="mb-3 text-lg font-semibold"
        >
          Interlink #{{ detailOpen.id }}
        </h2>
        <dl class="space-y-2 text-sm">
          <div>
            <dt class="font-medium text-gray-600 dark:text-gray-400">
              From
            </dt>
            <dd>{{ articleTitle(detailOpen.from_article_id) }}</dd>
          </div>
          <div>
            <dt class="font-medium text-gray-600 dark:text-gray-400">
              To
            </dt>
            <dd>{{ articleTitle(detailOpen.to_article_id) }}</dd>
          </div>
          <div>
            <dt class="font-medium text-gray-600 dark:text-gray-400">
              Anchor text
            </dt>
            <dd class="font-mono">
              {{ detailOpen.anchor_text }}
            </dd>
          </div>
          <div>
            <dt class="font-medium text-gray-600 dark:text-gray-400">
              Position
            </dt>
            <dd>{{ detailOpen.position ?? '—' }}</dd>
          </div>
          <div>
            <dt class="font-medium text-gray-600 dark:text-gray-400">
              Status
            </dt>
            <dd>
              <StatusBadge
                :status="detailOpen.status"
                kind="interlink"
              />
            </dd>
          </div>
        </dl>
        <p
          class="mt-3 rounded bg-blue-50 p-2 text-xs text-blue-800 dark:bg-blue-900/30 dark:text-blue-200"
        >
          Surrounding paragraph context lands in M7 alongside the interlinker
          skill. M5.C displays the anchor + endpoints only.
        </p>
        <div class="mt-4 flex justify-end gap-2">
          <button
            type="button"
            class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            @click="closeDetail"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
