<script setup lang="ts">
// InterlinksTab — incoming + outgoing internal links for one article.
//
// Wires:
// - `GET /api/v1/articles/{id}/interlinks` → `{incoming, outgoing}`

import { onMounted, ref, watch } from 'vue'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { apiFetch, formatApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type InterlinksReport = components['schemas']['InterlinksReport']
type InternalLink = components['schemas']['InternalLinkOut']

const props = defineProps<{
  articleId: number
  projectId: number
}>()

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
    toasts.error('Failed to load interlinks', formatApiError(err))
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
    aria-labelledby="cs-interlinks-tab-title"
  >
    <div>
      <h2
        id="cs-interlinks-tab-title"
        class="text-base font-semibold"
      >
        Interlinks
      </h2>
      <p class="mt-1 text-sm text-fg-muted">
        Incoming and outgoing suggestions for this article, recorded by agent interlinker runs.
      </p>
    </div>

    <div class="grid gap-4 lg:grid-cols-2">
      <section
        class="rounded-md border border-default bg-bg-surface p-3 shadow-xs"
        aria-label="Incoming interlinks"
      >
        <div class="mb-3">
          <h3 class="text-sm font-semibold text-fg-strong">
            Incoming
          </h3>
          <p class="mt-0.5 text-xs text-fg-muted">
            Other articles linking into this article.
          </p>
        </div>
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
      </section>
      <section
        class="rounded-md border border-default bg-bg-surface p-3 shadow-xs"
        aria-label="Outgoing interlinks"
      >
        <div class="mb-3">
          <h3 class="text-sm font-semibold text-fg-strong">
            Outgoing
          </h3>
          <p class="mt-0.5 text-xs text-fg-muted">
            Links from this article to other tracked articles.
          </p>
        </div>
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
      </section>
    </div>
  </section>
</template>
