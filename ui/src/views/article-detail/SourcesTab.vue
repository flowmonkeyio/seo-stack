<script setup lang="ts">
// SourcesTab — `research_sources` rows: url / title / fetched_at / used.
//
// Wires:
// - `GET /api/v1/articles/{id}/sources`
// - `POST /api/v1/articles/{id}/sources`

import { onMounted, ref, watch } from 'vue'

import DataTable from '@/components/DataTable.vue'
import { apiFetch, apiWrite } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type Source = components['schemas']['ResearchSourceOut']
type SourceCreateRequest = components['schemas']['SourceCreateRequest']

const props = defineProps<{
  articleId: number
}>()

const toasts = useToastsStore()

const sources = ref<Source[]>([])
const loading = ref(false)
const showCreate = ref(false)
const submitting = ref(false)

interface NewSource {
  url: string
  title: string
  snippet: string
  used: boolean
}

const draft = ref<NewSource>(emptyDraft())
function emptyDraft(): NewSource {
  return { url: '', title: '', snippet: '', used: false }
}

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
    toasts.error('Failed to load sources', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
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
  if (!draft.value.url.trim()) {
    toasts.error('Missing URL', 'Source URL is required.')
    return
  }
  submitting.value = true
  try {
    const body: SourceCreateRequest = {
      url: draft.value.url.trim(),
      title: draft.value.title.trim() || null,
      snippet: draft.value.snippet.trim() || null,
      used: draft.value.used,
    }
    await apiWrite<Source>(`/api/v1/articles/${props.articleId}/sources`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    toasts.success('Source added')
    showCreate.value = false
    await load()
  } catch (err) {
    toasts.error('Failed to add source', err instanceof Error ? err.message : undefined)
  } finally {
    submitting.value = false
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
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2
        id="cs-sources-tab-title"
        class="text-base font-semibold"
      >
        Research sources
      </h2>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        @click="openCreate"
      >
        Add source
      </button>
    </div>

    <DataTable
      :items="sources"
      :columns="columns"
      :loading="loading"
      aria-label="Research sources"
      empty-message="No research sources yet."
    />

    <div
      v-if="showCreate"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-source-add-title"
      @click.self="closeCreate"
    >
      <div
        class="w-full max-w-md rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h3
          id="cs-source-add-title"
          class="mb-3 text-lg font-semibold"
        >
          Add source
        </h3>
        <form
          class="space-y-3"
          @submit.prevent="submitCreate"
        >
          <label class="block text-sm">
            <span class="font-medium">URL</span>
            <input
              v-model="draft.url"
              type="url"
              required
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs dark:border-gray-700 dark:bg-gray-800"
            >
          </label>
          <label class="block text-sm">
            <span class="font-medium">Title</span>
            <input
              v-model="draft.title"
              type="text"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            >
          </label>
          <label class="block text-sm">
            <span class="font-medium">Snippet</span>
            <textarea
              v-model="draft.snippet"
              rows="3"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            />
          </label>
          <label class="inline-flex items-center gap-2 text-sm">
            <input
              v-model="draft.used"
              type="checkbox"
              class="h-4 w-4"
            >
            <span>Used in this article</span>
          </label>
          <div class="mt-3 flex justify-end gap-2">
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
              {{ submitting ? 'Saving…' : 'Add source' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>
