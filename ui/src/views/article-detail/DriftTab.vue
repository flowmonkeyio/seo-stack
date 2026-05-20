<script setup lang="ts">
// DriftTab — `drift_baselines` for one article.
//
// M5.B placeholder per scope: the diff engine (drift comparison) is on M6.
// We expose the existing baselines captured by agent-owned drift runs.

import { onMounted, ref, watch } from 'vue'

import DataTable from '@/components/DataTable.vue'
import { apiFetch, formatApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type Baseline = components['schemas']['DriftBaselineOut']

const props = defineProps<{
  articleId: number
}>()

const toasts = useToastsStore()

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
    toasts.error('Failed to load drift baselines', formatApiError(err))
  } finally {
    loading.value = false
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
    <div>
      <h2
        id="cs-drift-tab-title"
        class="text-base font-semibold"
      >
        Drift baselines
      </h2>
    </div>

    <div class="rounded-md border border-default bg-bg-surface p-4 shadow-xs">
      <h3 class="text-sm font-semibold text-fg-strong">
        Baseline snapshots
      </h3>
      <p class="mt-1 text-sm text-fg-muted">
        Saved edited-body snapshots appear here after agent drift-watch runs. Scores appear after later content is compared against a baseline.
      </p>
    </div>

    <DataTable
      :items="baselines"
      :columns="columns"
      :loading="loading"
      aria-label="Drift baselines"
      empty-message="No drift baselines recorded yet."
    />
  </section>
</template>
