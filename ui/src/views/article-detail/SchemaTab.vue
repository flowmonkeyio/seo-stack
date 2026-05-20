<script setup lang="ts">
// SchemaTab — read-only `schema_emits` rows.

import { onMounted, ref, watch } from 'vue'

import DataTable from '@/components/DataTable.vue'
import { UiAdvancedJsonPanel } from '@/components/ui'
import { apiFetch, formatApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type SchemaEmit = components['schemas']['SchemaEmitOut']

const props = defineProps<{
  articleId: number
}>()

const toasts = useToastsStore()

const rows = ref<SchemaEmit[]>([])
const loading = ref(false)

const columns: DataTableColumn<SchemaEmit>[] = [
  { key: 'type', label: 'Type' },
  { key: 'is_primary', label: 'Primary', format: (v) => (v ? 'yes' : 'no') },
  { key: 'version_published', label: 'Version', format: (v) => (v ? String(v) : '-') },
  {
    key: 'validated_at',
    label: 'Validated',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : '-'),
  },
]

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await apiFetch<SchemaEmit[]>(`/api/v1/articles/${props.articleId}/schema`)
    rows.value = data
  } catch (err) {
    toasts.error('Failed to load schema rows', formatApiError(err))
  } finally {
    loading.value = false
  }
}

function jsonSummary(row: SchemaEmit): string {
  const value = row.schema_json
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return row.type
  return `${Object.keys(value).length} fields`
}

onMounted(load)
watch(() => props.articleId, load)
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-schema-tab-title"
  >
    <div>
      <h2
        id="cs-schema-tab-title"
        class="text-base font-semibold"
      >
        Schema emits
      </h2>
    </div>

    <DataTable
      :items="rows"
      :columns="columns"
      :loading="loading"
      aria-label="Schema emits"
      empty-message="No schema rows yet."
    />

    <div
      v-if="rows.length > 0"
      class="space-y-2"
    >
      <UiAdvancedJsonPanel
        v-for="row in rows"
        :key="row.id"
        :title="row.type"
        :summary="jsonSummary(row)"
        :data="row.schema_json ?? {}"
      />
    </div>
  </section>
</template>
