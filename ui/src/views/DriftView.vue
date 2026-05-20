<script setup lang="ts">
// DriftView — read-only drift baselines across articles in a project.

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import {
  UiButton,
  UiCallout,
  UiDialog,
  UiFormField,
  UiPageShell,
  UiPanel,
  UiRange,
} from '@/components/ui'
import { useArticlesStore } from '@/stores/articles'
import { useDriftStore, type DriftRow } from '@/stores/drift'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const router = useRouter()
const driftStore = useDriftStore()
const articlesStore = useArticlesStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { filteredItems, loading, error, thresholdScore } = storeToRefs(driftStore)
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
    format: (v) => (v === null || v === undefined ? '-' : Number(v).toFixed(3)),
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

async function refresh(): Promise<void> {
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
      description="Inspect content drift baselines and scores captured by agent drift runs."
      :breadcrumbs="[{ label: 'Drift Watch' }]"
    />

    <UiCallout
      v-if="error"
      tone="danger"
    >
      {{ error }}
    </UiCallout>

    <UiPanel class="p-4">
      <div class="grid gap-4 lg:grid-cols-[1fr_320px] lg:items-end">
        <div>
          <h2 class="text-sm font-semibold text-fg-strong">
            Baseline snapshots
          </h2>
          <p class="mt-1 text-sm text-fg-muted">
            Saved article-body snapshots appear here after agent drift-watch runs. Scores appear once later content is compared against a baseline.
          </p>
        </div>
        <UiFormField label="Threshold">
          <UiRange
            :model-value="thresholdScore"
            :min="0"
            :max="1"
            :step="0.05"
            :format="(value) => value.toFixed(2)"
            aria-label="Drift threshold"
            @update:model-value="driftStore.setThreshold"
          />
        </UiFormField>
      </div>
    </UiPanel>

    <div
      v-if="empty"
      class="rounded-md border border-dashed border-subtle bg-bg-surface px-6 py-10 text-center"
    >
      <h2 class="text-sm font-semibold text-fg-strong">
        No drift baselines yet
      </h2>
      <p class="mt-1 text-sm text-fg-muted">
        Agent drift-watch baselines will appear here with article, captured time, score, and body length.
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
          class="focus-ring rounded-xs text-fg-link hover:underline"
          @click.stop="gotoArticle(row as DriftRow)"
        >
          {{ articleTitle((row as DriftRow).parent_article_id) }}
        </button>
      </template>
      <template #cell:current_score="{ row }">
        <div class="flex items-center gap-2">
          <span>{{ (row as DriftRow).current_score === null ? '-' : Number((row as DriftRow).current_score).toFixed(3) }}</span>
          <UiButton
            size="sm"
            variant="secondary"
            :aria-label="`View diff for ${articleTitle((row as DriftRow).parent_article_id)}`"
            @click.stop="openDiff(row as DriftRow)"
          >
            View baseline
          </UiButton>
        </div>
      </template>
    </DataTable>

    <UiDialog
      :model-value="diffOpen !== null"
      :title="diffOpen ? `Drift baseline - ${articleTitle(diffOpen.parent_article_id)}` : 'Drift baseline'"
      size="xl"
      scroll-body
      @update:model-value="(open: boolean) => open ? undefined : closeDiff()"
    >
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
