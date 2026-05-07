<script setup lang="ts">
// DriftTab — `drift_baselines` for one article.
//
// M5.B placeholder per scope: the diff engine (drift comparison) is on M6.
// We expose the existing baselines + a "Snapshot now" CTA that hits
// `POST /api/v1/articles/{id}/drift/snapshot`.

import { computed, onMounted, ref, watch } from 'vue'

import DataTable from '@/components/DataTable.vue'
import { apiFetch, apiWrite } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import { useArticlesStore } from '@/stores/articles'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type Baseline = components['schemas']['DriftBaselineOut']

const props = defineProps<{
  articleId: number
}>()

const toasts = useToastsStore()
const articlesStore = useArticlesStore()

const baselines = ref<Baseline[]>([])
const loading = ref(false)

const columns: DataTableColumn<Baseline>[] = [
  {
    key: 'baseline_at',
    label: 'Baseline at',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
  { key: 'current_score', label: 'Current score', format: (v) => (v === null ? '—' : String(v)) },
  { key: 'baseline_md', label: 'Body length', format: (v) => `${String(v).length} chars` },
]

async function load(): Promise<void> {
  loading.value = true
  try {
    baselines.value = await apiFetch<Baseline[]>(`/api/v1/articles/${props.articleId}/drift`)
  } catch (err) {
    toasts.error('Failed to load drift baselines', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

const editedBody = computed<string>(() => articlesStore.currentDetail?.edited_md ?? '')

async function snapshotNow(): Promise<void> {
  try {
    const baselineMd = editedBody.value.trim()
    if (!baselineMd) {
      toasts.error('No edited body', 'Cannot snapshot — edited body is empty.')
      return
    }
    await apiWrite<Baseline>(`/api/v1/articles/${props.articleId}/drift/snapshot`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ baseline_md: baselineMd }),
    })
    toasts.success('Drift baseline recorded')
    await load()
  } catch (err) {
    toasts.error('Snapshot failed', err instanceof Error ? err.message : undefined)
  }
}

onMounted(load)
watch(() => props.articleId, load)
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-drift-tab-title"
  >
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2
        id="cs-drift-tab-title"
        class="text-base font-semibold"
      >
        Drift baselines
      </h2>
      <button
        type="button"
        class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
        @click="snapshotNow"
      >
        Snapshot now
      </button>
    </div>

    <p class="rounded border border-blue-200 bg-blue-50 p-2 text-xs text-blue-800 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-200">
      The drift comparison engine ships in M6. M5.B records baselines via the
      <code>drift.snapshot</code> endpoint; the diff +score job will surface
      drift events once the watcher is online.
    </p>

    <DataTable
      :items="baselines"
      :columns="columns"
      :loading="loading"
      aria-label="Drift baselines"
      empty-message="No drift baselines recorded yet."
    />
  </section>
</template>
