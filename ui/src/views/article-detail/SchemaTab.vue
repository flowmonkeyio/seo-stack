<script setup lang="ts">
// SchemaTab — `schema_emits` rows: type / is_primary / version_published.
//
// Wires:
// - `GET /api/v1/articles/{id}/schema` — list rows
// - `PUT /api/v1/articles/{id}/schema/{schema_type}` — upsert row by type
// - `POST /api/v1/articles/{id}/schema/{schema_id}/validate` — validate row

import { onMounted, ref, watch } from 'vue'

import DataTable from '@/components/DataTable.vue'
import { apiFetch, apiWrite } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type SchemaEmit = components['schemas']['SchemaEmitOut']
type SchemaSetRequest = components['schemas']['SchemaSetRequest']

const props = defineProps<{
  articleId: number
}>()

const toasts = useToastsStore()

const rows = ref<SchemaEmit[]>([])
const loading = ref(false)
const editing = ref<SchemaEmit | null>(null)
const editType = ref<string>('')
const editText = ref<string>('')
const editPrimary = ref(false)
const saving = ref(false)
const parseError = ref<string | null>(null)

const columns: DataTableColumn<SchemaEmit>[] = [
  { key: 'type', label: 'Type' },
  { key: 'is_primary', label: 'Primary', format: (v) => (v ? 'yes' : 'no') },
  { key: 'version_published', label: 'Version', format: (v) => (v ? String(v) : '—') },
  {
    key: 'validated_at',
    label: 'Validated',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : '—'),
  },
]

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await apiFetch<SchemaEmit[]>(`/api/v1/articles/${props.articleId}/schema`)
    rows.value = data
  } catch (err) {
    toasts.error('Failed to load schema rows', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

function startEdit(row: SchemaEmit | null): void {
  if (row) {
    editing.value = row
    editType.value = row.type
    editText.value = JSON.stringify(row.schema_json ?? {}, null, 2)
    editPrimary.value = row.is_primary
  } else {
    editing.value = null
    editType.value = 'Article'
    editText.value = '{}'
    editPrimary.value = false
  }
  parseError.value = null
}

function cancelEdit(): void {
  if (saving.value) return
  editing.value = null
  editType.value = ''
  editText.value = ''
  parseError.value = null
}

async function saveEdit(): Promise<void> {
  if (saving.value) return
  if (!editType.value.trim()) {
    parseError.value = 'Type is required'
    return
  }
  let parsed: Record<string, unknown>
  try {
    parsed = JSON.parse(editText.value || '{}') as Record<string, unknown>
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      throw new SyntaxError('expected an object')
    }
  } catch (err) {
    parseError.value = err instanceof Error ? err.message : 'invalid JSON'
    return
  }
  saving.value = true
  try {
    const body: SchemaSetRequest = {
      schema_json: parsed,
      is_primary: editPrimary.value,
      position: null,
      version_published: null,
    }
    await apiWrite<SchemaEmit>(
      `/api/v1/articles/${props.articleId}/schema/${encodeURIComponent(editType.value)}`,
      {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      },
    )
    toasts.success('Schema saved', editType.value)
    editing.value = null
    editType.value = ''
    editText.value = ''
    await load()
  } catch (err) {
    toasts.error('Save failed', err instanceof Error ? err.message : undefined)
  } finally {
    saving.value = false
  }
}

async function validate(row: SchemaEmit): Promise<void> {
  try {
    await apiWrite<SchemaEmit>(
      `/api/v1/articles/${props.articleId}/schema/${row.id}/validate`,
      { method: 'POST' },
    )
    toasts.success('Schema validated', row.type)
    await load()
  } catch (err) {
    toasts.error('Validation failed', err instanceof Error ? err.message : undefined)
  }
}

async function setPrimary(row: SchemaEmit): Promise<void> {
  try {
    const body: SchemaSetRequest = {
      schema_json: (row.schema_json ?? {}) as Record<string, unknown>,
      is_primary: !row.is_primary,
      position: row.position,
      version_published: row.version_published,
    }
    await apiWrite<SchemaEmit>(
      `/api/v1/articles/${props.articleId}/schema/${encodeURIComponent(row.type)}`,
      {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      },
    )
    await load()
  } catch (err) {
    toasts.error('Set primary failed', err instanceof Error ? err.message : undefined)
  }
}

onMounted(load)
watch(() => props.articleId, load)
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-schema-tab-title"
  >
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2
        id="cs-schema-tab-title"
        class="text-base font-semibold"
      >
        Schema emits
      </h2>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        @click="startEdit(null)"
      >
        Add schema
      </button>
    </div>

    <DataTable
      :items="rows"
      :columns="columns"
      :loading="loading"
      aria-label="Schema emits"
      empty-message="No schema rows yet — defaults are seeded at project creation."
    >
      <template #cell:is_primary="{ row }">
        <button
          type="button"
          class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          @click="setPrimary(row as SchemaEmit)"
        >
          {{ (row as SchemaEmit).is_primary ? 'primary' : 'set primary' }}
        </button>
      </template>
    </DataTable>

    <ul
      v-if="rows.length > 0"
      class="space-y-2 text-sm"
    >
      <li
        v-for="r in rows"
        :key="r.id"
        class="flex flex-wrap items-center justify-between gap-2 rounded border border-gray-200 px-3 py-2 dark:border-gray-800"
      >
        <span class="font-mono text-xs">{{ r.type }}</span>
        <div class="flex gap-2">
          <button
            type="button"
            class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            @click="validate(r)"
          >
            Validate
          </button>
          <button
            type="button"
            class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            @click="startEdit(r)"
          >
            Edit JSON
          </button>
        </div>
      </li>
    </ul>

    <div
      v-if="editing !== null || editType !== ''"
      class="rounded border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900"
    >
      <h3 class="mb-2 text-sm font-semibold">
        {{ editing ? `Edit ${editing.type}` : 'New schema row' }}
      </h3>
      <label class="mb-2 block text-sm">
        <span class="font-medium">Type</span>
        <input
          v-model="editType"
          type="text"
          :disabled="!!editing"
          class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs dark:border-gray-700 dark:bg-gray-800"
        >
      </label>
      <label class="mb-2 block text-sm">
        <span class="font-medium">Schema JSON</span>
        <textarea
          v-model="editText"
          rows="12"
          spellcheck="false"
          class="mt-1 w-full rounded border border-gray-300 bg-white p-2 font-mono text-xs leading-snug text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
        />
      </label>
      <label class="mb-2 inline-flex items-center gap-2 text-sm">
        <input
          v-model="editPrimary"
          type="checkbox"
          class="h-4 w-4"
        >
        <span>Mark primary</span>
      </label>
      <p
        v-if="parseError"
        class="mb-2 rounded bg-red-50 p-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200"
      >
        {{ parseError }}
      </p>
      <div class="flex justify-end gap-2">
        <button
          type="button"
          class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          :disabled="saving"
          @click="cancelEdit"
        >
          Cancel
        </button>
        <button
          type="button"
          class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          :disabled="saving"
          @click="saveEdit"
        >
          {{ saving ? 'Saving…' : 'Save schema' }}
        </button>
      </div>
    </div>
  </section>
</template>
