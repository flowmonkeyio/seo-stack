<script setup lang="ts">
// InterlinksTab — incoming + outgoing internal links for one article.
//
// Wires:
// - `GET /api/v1/articles/{id}/interlinks` → `{incoming, outgoing}`
//
// "Suggest interlinks" button: navigates to the project-level InterlinksView
// (M5.C placeholder) so the user can review the suggestions there.

import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { apiFetch } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type InterlinksReport = components['schemas']['InterlinksReport']
type InternalLink = components['schemas']['InternalLinkOut']

const props = defineProps<{
  articleId: number
  projectId: number
}>()

const router = useRouter()
const toasts = useToastsStore()

const report = ref<InterlinksReport | null>(null)
const loading = ref(false)

const inboundColumns: DataTableColumn<InternalLink>[] = [
  { key: 'from_article_id', label: 'From article' },
  { key: 'anchor_text', label: 'Anchor' },
  { key: 'position', label: 'Position' },
  { key: 'status', label: 'Status' },
]

const outboundColumns: DataTableColumn<InternalLink>[] = [
  { key: 'to_article_id', label: 'To article' },
  { key: 'anchor_text', label: 'Anchor' },
  { key: 'position', label: 'Position' },
  { key: 'status', label: 'Status' },
]

async function load(): Promise<void> {
  loading.value = true
  try {
    report.value = await apiFetch<InterlinksReport>(
      `/api/v1/articles/${props.articleId}/interlinks`,
    )
  } catch (err) {
    toasts.error('Failed to load interlinks', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

function gotoProjectInterlinks(): void {
  void router.push(`/projects/${props.projectId}/interlinks`)
}

onMounted(load)
watch(() => props.articleId, load)
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-interlinks-tab-title"
  >
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2
        id="cs-interlinks-tab-title"
        class="text-base font-semibold"
      >
        Interlinks
      </h2>
      <button
        type="button"
        class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
        @click="gotoProjectInterlinks"
      >
        Suggest interlinks (M5.C)
      </button>
    </div>

    <div class="grid gap-4 lg:grid-cols-2">
      <div>
        <h3 class="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-700 dark:text-gray-300">
          Incoming
        </h3>
        <DataTable
          :items="report?.incoming ?? []"
          :columns="inboundColumns"
          :loading="loading"
          aria-label="Incoming interlinks"
          empty-message="No inbound links yet."
        >
          <template #cell:status="{ row }">
            <StatusBadge
              :status="(row as InternalLink).status"
              kind="interlink"
            />
          </template>
        </DataTable>
      </div>
      <div>
        <h3 class="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-700 dark:text-gray-300">
          Outgoing
        </h3>
        <DataTable
          :items="report?.outgoing ?? []"
          :columns="outboundColumns"
          :loading="loading"
          aria-label="Outgoing interlinks"
          empty-message="No outbound links yet."
        >
          <template #cell:status="{ row }">
            <StatusBadge
              :status="(row as InternalLink).status"
              kind="interlink"
            />
          </template>
        </DataTable>
      </div>
    </div>
  </section>
</template>
