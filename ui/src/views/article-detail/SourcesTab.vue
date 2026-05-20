<script setup lang="ts">
// SourcesTab — `research_sources` rows: url / title / fetched_at / used.
//
// Wires:
// - `GET /api/v1/articles/{id}/sources`

import { onMounted, ref, watch } from 'vue'

import DataTable from '@/components/DataTable.vue'
import { apiFetch, formatApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type Source = components['schemas']['ResearchSourceOut']

const props = defineProps<{
  articleId: number
}>()

const toasts = useToastsStore()

const sources = ref<Source[]>([])
const loading = ref(false)

const columns: DataTableColumn<Source>[] = [
  { key: 'url', label: 'URL', cellClass: 'font-mono text-xs break-all' },
  { key: 'title', label: 'Title' },
  {
    key: 'fetched_at',
    label: 'Fetched',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
  { key: 'used', label: 'Used', format: (v) => (v ? 'yes' : 'no') },
]

async function load(): Promise<void> {
  loading.value = true
  try {
    const rows = await apiFetch<Source[]>(`/api/v1/articles/${props.articleId}/sources`)
    sources.value = rows
  } catch (err) {
    toasts.error('Failed to load sources', formatApiError(err))
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
    aria-labelledby="cs-sources-tab-title"
  >
    <div>
      <h2
        id="cs-sources-tab-title"
        class="text-base font-semibold"
      >
        Research sources
      </h2>
    </div>

    <DataTable
      :items="sources"
      :columns="columns"
      :loading="loading"
      aria-label="Research sources"
      empty-message="No research sources yet."
    />
  </section>
</template>
