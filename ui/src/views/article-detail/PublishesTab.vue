<script setup lang="ts">
// PublishesTab — `article_publishes` rows: target/version/status/url + canonical.

import { onMounted, ref, watch } from 'vue'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { apiFetch, apiWrite } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import { useArticlesStore } from '@/stores/articles'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type Publish = components['schemas']['ArticlePublishOut']

const props = defineProps<{
  articleId: number
}>()

const toasts = useToastsStore()
const articlesStore = useArticlesStore()

const rows = ref<Publish[]>([])
const loading = ref(false)

const columns: DataTableColumn<Publish>[] = [
  { key: 'target_id', label: 'Target' },
  { key: 'version_published', label: 'Version' },
  { key: 'status', label: 'Status' },
  { key: 'published_url', label: 'URL', cellClass: 'font-mono text-xs break-all' },
  {
    key: 'published_at',
    label: 'Published',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : '—'),
  },
]

async function load(): Promise<void> {
  loading.value = true
  try {
    rows.value = await apiFetch<Publish[]>(`/api/v1/articles/${props.articleId}/publishes`)
  } catch (err) {
    toasts.error('Failed to load publishes', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

async function setCanonical(row: Publish): Promise<void> {
  try {
    await apiWrite(`/api/v1/articles/${props.articleId}/publishes/canonical`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ target_id: row.target_id }),
    })
    toasts.success('Canonical set', `target ${row.target_id}`)
    await articlesStore.get(props.articleId)
  } catch (err) {
    toasts.error('Set canonical failed', err instanceof Error ? err.message : undefined)
  }
}

onMounted(load)
watch(() => props.articleId, load)
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-publishes-tab-title"
  >
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2
        id="cs-publishes-tab-title"
        class="text-base font-semibold"
      >
        Publishes
      </h2>
      <span
        v-if="articlesStore.currentDetail?.canonical_target_id !== null && articlesStore.currentDetail !== null"
        class="text-xs text-gray-600 dark:text-gray-400"
      >
        canonical target id: {{ articlesStore.currentDetail.canonical_target_id }}
      </span>
    </div>

    <DataTable
      :items="rows"
      :columns="columns"
      :loading="loading"
      aria-label="Article publishes"
      empty-message="No publish records yet."
    >
      <template #cell:status="{ row }">
        <StatusBadge
          :status="(row as Publish).status"
          kind="publish"
        />
      </template>
      <template #cell:target_id="{ row }">
        <button
          type="button"
          class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          @click="setCanonical(row as Publish)"
        >
          set canonical (target {{ (row as Publish).target_id }})
        </button>
      </template>
    </DataTable>
  </section>
</template>
