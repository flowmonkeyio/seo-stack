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
import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import {
  UiButton,
  UiCallout,
  UiDialog,
  UiEmptyState,
  UiPageShell,
} from '@/components/ui'
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
  <UiPageShell>
    <ProjectPageHeader
      :project-id="projectId"
      title="Drift Watch"
      description="Snapshot published content baselines and inspect drift scores as the comparison engine updates them."
      :breadcrumbs="[{ label: 'Drift Watch' }]"
    >
      <template #actions>
        <UiButton
          variant="primary"
          :loading="snapshotPending"
          :disabled="snapshotPending"
          @click="snapshotAll"
        >
          Snapshot all published articles
        </UiButton>
      </template>
    </ProjectPageHeader>

    <UiCallout
      tone="info"
    >
      The drift comparison engine ships in M6. M5.C records baselines via the
      <code>drift.snapshot</code> endpoint; <code>current_score</code> is
      populated by the M6 watcher.
    </UiCallout>

    <UiCallout
      v-if="error"
      tone="danger"
    >
      {{ error }}
    </UiCallout>

    <div class="flex items-center gap-3 text-sm">
      <label class="flex items-center gap-2">
        <span class="text-fg-muted">Threshold</span>
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
        <span class="w-8 text-right text-xs text-fg-muted">{{ thresholdScore.toFixed(2) }}</span>
      </label>
      <span class="text-xs text-fg-muted">
        Hide rows whose <code>current_score</code> is below the slider.
      </span>
    </div>

    <UiEmptyState
      v-if="empty"
      title="No drift baselines yet"
      description="Snapshot a published article, or all published articles, to start tracking content drift."
      size="lg"
    >
      <template #actions>
        <UiButton
          variant="primary"
          :loading="snapshotPending"
          @click="snapshotAll"
        >
          Snapshot all published articles
        </UiButton>
      </template>
    </UiEmptyState>

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
          <UiButton
            size="sm"
            variant="secondary"
            :aria-label="`Snapshot baseline for ${articleTitle((row as DriftRow).parent_article_id)}`"
            @click.stop="snapshotRow(row as DriftRow)"
          >
            Snapshot
          </UiButton>
          <UiButton
            size="sm"
            variant="secondary"
            :aria-label="`View diff for ${articleTitle((row as DriftRow).parent_article_id)}`"
            @click.stop="openDiff(row as DriftRow)"
          >
            View Diff
          </UiButton>
        </div>
      </template>
    </DataTable>

    <UiDialog
      :model-value="diffOpen !== null"
      :title="diffOpen ? `Drift baseline — ${articleTitle(diffOpen.parent_article_id)}` : 'Drift baseline'"
      size="xl"
      scroll-body
      @update:model-value="(open: boolean) => open ? undefined : closeDiff()"
    >
      <UiCallout
        tone="info"
        density="compact"
        class="mb-3"
      >
        Drift comparison engine coming in M6. Baseline body shown below.
      </UiCallout>
      <pre
        v-if="diffOpen"
        class="max-h-[60vh] overflow-y-auto rounded-md border border-subtle bg-bg-sunken p-3 font-mono text-xs text-fg-default"
      >{{ diffOpen.baseline_md }}</pre>
      <template #footer>
        <UiButton
          variant="secondary"
          @click="closeDiff"
        >
          Close
        </UiButton>
      </template>
    </UiDialog>
  </UiPageShell>
</template>
