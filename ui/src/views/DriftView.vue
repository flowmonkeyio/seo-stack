<script setup lang="ts">
// DriftView — drift baselines across all published articles in a project.
//
// The wire shape is per-article (`GET /api/v1/articles/{id}/drift`); the
// project-level view fans out across published articles and aggregates
// rows in the store. The diff/score job ships in M6 — `current_score`
// may be null for every row at M5.C; the view displays the baseline rows
// regardless so users can audit what's being tracked.
//
// Per audit P-I6.

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import { useDriftStore, type DriftRow } from '@/stores/drift'
import { useArticlesStore } from '@/stores/articles'
import { useToastsStore } from '@/stores/toasts'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const router = useRouter()
const driftStore = useDriftStore()
const articlesStore = useArticlesStore()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { filteredItems, loading, error, thresholdScore } = storeToRefs(driftStore)

const snapshotPending = ref(false)
const diffOpen = ref<DriftRow | null>(null)

const columns: DataTableColumn<DriftRow>[] = [
  { key: 'parent_article_id', label: 'Article' },
  {
    key: 'baseline_at',
    label: 'Baseline at',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
  {
    key: 'current_score',
    label: 'Current score',
    format: (v) => (v === null || v === undefined ? '—' : Number(v).toFixed(3)),
    widthClass: 'w-32',
  },
  { key: 'baseline_md', label: 'Body length', format: (v) => `${String(v).length} chars` },
]

function articleTitle(id: number): string {
  return articlesStore.getById(id)?.title ?? `#${id}`
}

function gotoArticle(row: DriftRow): void {
  void router.push(`/projects/${projectId.value}/articles/${row.parent_article_id}/drift`)
}

function openDiff(row: DriftRow): void {
  diffOpen.value = row
}

function closeDiff(): void {
  diffOpen.value = null
}

async function snapshotAll(): Promise<void> {
  snapshotPending.value = true
  try {
    let success = 0
    let failed = 0
    for (const a of articlesStore.items) {
      if (a.status !== 'published') continue
      const body = (a.edited_md ?? '').trim()
      if (!body) continue
      try {
        await driftStore.snapshot(a.id, { baseline_md: body })
        success++
      } catch {
        failed++
      }
    }
    if (failed > 0) {
      toasts.error('Snapshot complete', `${success} ok, ${failed} failed`)
    } else {
      toasts.success('Snapshot complete', `${success} baselines recorded`)
    }
    await refresh()
  } finally {
    snapshotPending.value = false
  }
}

async function snapshotRow(row: DriftRow): Promise<void> {
  const article = articlesStore.getById(row.parent_article_id)
  const body = (article?.edited_md ?? '').trim()
  if (!body) {
    toasts.error('No body to snapshot', 'Article has no edited_md.')
    return
  }
  try {
    await driftStore.snapshot(row.parent_article_id, { baseline_md: body })
    toasts.success('Baseline recorded')
  } catch (err) {
    toasts.error('Snapshot failed', err instanceof Error ? err.message : undefined)
  }
}

async function refresh(): Promise<void> {
  // The drift list is per-article. Walk every article and aggregate.
  const articleIds = articlesStore.items.map((a) => a.id)
  if (articleIds.length === 0) return
  await driftStore.refreshAcrossArticles(articleIds)
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  driftStore.reset()
  if (articlesStore.items.length === 0) {
    await articlesStore.refresh(projectId.value)
  }
  await refresh()
}

const empty = computed<boolean>(() => !loading.value && filteredItems.value.length === 0)

onMounted(load)
watch(projectId, load)
</script>

<template>
  <div class="mx-auto max-w-6xl">
    <header class="mb-4 flex flex-wrap items-baseline justify-between gap-3">
      <h1 class="text-2xl font-bold tracking-tight">
        Drift Watch
      </h1>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
        :disabled="snapshotPending"
        @click="snapshotAll"
      >
        {{ snapshotPending ? 'Snapshotting…' : 'Snapshot all published articles' }}
      </button>
    </header>

    <p
      class="mb-3 rounded border border-blue-200 bg-blue-50 p-2 text-xs text-blue-800 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-200"
    >
      The drift comparison engine ships in M6. M5.C records baselines via the
      <code>drift.snapshot</code> endpoint; <code>current_score</code> is
      populated by the M6 watcher.
    </p>

    <p
      v-if="error"
      class="mb-3 rounded bg-red-50 p-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200"
    >
      {{ error }}
    </p>

    <div class="mb-3 flex items-center gap-3 text-sm">
      <label class="flex items-center gap-2">
        <span class="text-gray-600 dark:text-gray-400">Threshold</span>
        <input
          :value="thresholdScore"
          type="range"
          min="0"
          max="1"
          step="0.05"
          class="w-40"
          aria-label="Drift threshold"
          @input="driftStore.setThreshold(Number.parseFloat(($event.target as HTMLInputElement).value))"
        >
        <span class="w-8 text-right text-xs text-gray-500 dark:text-gray-400">{{ thresholdScore.toFixed(2) }}</span>
      </label>
      <span class="text-xs text-gray-500 dark:text-gray-400">
        Hide rows whose <code>current_score</code> is below the slider.
      </span>
    </div>

    <div
      v-if="empty"
      class="rounded border border-dashed border-gray-300 p-8 text-center text-sm text-gray-600 dark:border-gray-700 dark:text-gray-300"
    >
      <p class="mb-2 text-base font-medium text-gray-900 dark:text-white">
        No drift baselines yet
      </p>
      <p class="mb-4">
        Snapshot a published article (or all of them) to start tracking drift.
        The M6 watcher will compute <code>current_score</code> nightly.
      </p>
    </div>

    <DataTable
      v-if="!empty"
      :items="filteredItems"
      :columns="columns"
      :loading="loading"
      aria-label="Drift baselines"
      empty-message="No baselines match the threshold."
      @row-click="openDiff"
    >
      <template #cell:parent_article_id="{ row }">
        <button
          type="button"
          class="text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:text-blue-300"
          @click.stop="gotoArticle(row as DriftRow)"
        >
          {{ articleTitle((row as DriftRow).parent_article_id) }}
        </button>
      </template>
      <template #cell:current_score="{ row }">
        <div class="flex items-center gap-2">
          <span>{{ (row as DriftRow).current_score === null ? '—' : Number((row as DriftRow).current_score).toFixed(3) }}</span>
          <button
            type="button"
            class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            :aria-label="`Snapshot baseline for ${articleTitle((row as DriftRow).parent_article_id)}`"
            @click.stop="snapshotRow(row as DriftRow)"
          >
            Snapshot
          </button>
          <button
            type="button"
            class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            :aria-label="`View diff for ${articleTitle((row as DriftRow).parent_article_id)}`"
            @click.stop="openDiff(row as DriftRow)"
          >
            View Diff
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Diff modal — M6 deferral. We surface the baseline_md so users can
         eyeball what was captured; the diff engine is M6 territory. -->
    <div
      v-if="diffOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-drift-diff-title"
      @click.self="closeDiff"
    >
      <div
        class="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h2
          id="cs-drift-diff-title"
          class="mb-3 text-lg font-semibold"
        >
          Drift baseline — {{ articleTitle(diffOpen.parent_article_id) }}
        </h2>
        <p class="mb-3 rounded border border-blue-200 bg-blue-50 p-2 text-xs text-blue-800 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-200">
          Drift comparison engine coming in M6. Baseline body shown below.
        </p>
        <pre class="max-h-[60vh] overflow-y-auto rounded bg-gray-100 p-3 font-mono text-xs dark:bg-gray-800">{{ diffOpen.baseline_md }}</pre>
        <div class="mt-3 flex justify-end gap-2">
          <button
            type="button"
            class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            @click="closeDiff"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
