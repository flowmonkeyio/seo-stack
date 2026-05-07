<script setup lang="ts">
// IntegrationsTab — list, add, edit, delete integration credentials.
//
// Encryption is server-side; the UI passes plaintext payload (the API
// encrypts via M4 crypto). For each integration we expose `last_refreshed_at`
// + a "Test" button that calls POST .../test and surfaces the result toast.
//
// Global creds (project_id IS NULL) are listed read-only and tagged.

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import { apiFetch, apiWrite, ApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type Cred = components['schemas']['IntegrationCredentialOut']

const route = useRoute()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const allCreds = ref<Cred[]>([])
const loading = ref(false)

const editing = ref<Cred | null>(null)
const formOpen = ref(false)
const draft = ref({
  kind: '',
  plaintext_payload: '',
  config_json: '{}',
})
const saving = ref(false)
const testingIds = ref<Set<number>>(new Set())

const projectCreds = computed(() => allCreds.value.filter((c) => c.project_id === projectId.value))
const globalCreds = computed(() => allCreds.value.filter((c) => c.project_id === null))

const columns: DataTableColumn<Cred>[] = [
  { key: 'kind', label: 'Kind' },
  {
    key: 'last_refreshed_at',
    label: 'Last refresh',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : '—'),
  },
  {
    key: 'expires_at',
    label: 'Expires',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : '—'),
  },
  {
    key: 'updated_at',
    label: 'Updated',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
]

const globalColumns: DataTableColumn<Cred>[] = [
  { key: 'kind', label: 'Kind' },
  {
    key: 'last_refreshed_at',
    label: 'Last refresh',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : '—'),
  },
]

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  loading.value = true
  try {
    const res = await apiFetch<Cred[]>(`/api/v1/projects/${projectId.value}/integrations`)
    allCreds.value = Array.isArray(res) ? res : []
  } catch (err) {
    toasts.error('Failed to load integrations', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

function startNew(): void {
  editing.value = null
  formOpen.value = true
  draft.value = { kind: '', plaintext_payload: '', config_json: '{}' }
}

function edit(c: Cred): void {
  editing.value = c
  formOpen.value = true
  draft.value = {
    kind: c.kind,
    plaintext_payload: '',
    config_json: JSON.stringify(c.config_json ?? {}, null, 2),
  }
}

function cancel(): void {
  editing.value = null
  formOpen.value = false
}

function parseConfig(): Record<string, unknown> | null {
  try {
    return JSON.parse(draft.value.config_json) as Record<string, unknown>
  } catch (err) {
    toasts.error('Config JSON is not valid', err instanceof Error ? err.message : undefined)
    return null
  }
}

async function save(): Promise<void> {
  if (!draft.value.kind.trim()) {
    toasts.error('Kind is required')
    return
  }
  if (!draft.value.plaintext_payload) {
    toasts.error('Payload is required', 'Server cannot rotate without a fresh payload.')
    return
  }
  const config = parseConfig()
  if (config === null) return
  saving.value = true
  try {
    const body = {
      kind: draft.value.kind,
      plaintext_payload: draft.value.plaintext_payload,
      config_json: config,
    }
    if (editing.value) {
      await apiWrite<Cred>(
        `/api/v1/projects/${projectId.value}/integrations/${editing.value.id}`,
        {
          method: 'PATCH',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(body),
        },
      )
      toasts.success('Integration updated')
    } else {
      await apiWrite<Cred>(`/api/v1/projects/${projectId.value}/integrations`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      })
      toasts.success('Integration added')
    }
    editing.value = null
    formOpen.value = false
    await load()
  } catch (err) {
    toasts.error('Failed to save integration', err instanceof Error ? err.message : undefined)
  } finally {
    saving.value = false
  }
}

async function remove(c: Cred): Promise<void> {
  try {
    await apiWrite<Cred>(`/api/v1/projects/${projectId.value}/integrations/${c.id}`, {
      method: 'DELETE',
    })
    toasts.success('Integration removed')
    if (editing.value?.id === c.id) editing.value = null
    await load()
  } catch (err) {
    toasts.error('Failed to remove integration', err instanceof Error ? err.message : undefined)
  }
}

interface TestResult {
  ok?: boolean
  status?: string
  detail?: string
  message?: string
  [key: string]: unknown
}

async function test(c: Cred): Promise<void> {
  testingIds.value.add(c.id)
  try {
    const res = await apiFetch<TestResult>(
      `/api/v1/projects/${projectId.value}/integrations/${c.id}/test`,
      { method: 'POST' },
    )
    const ok = res.ok ?? (res.status === 'ok' ? true : false)
    if (ok) {
      toasts.success(`Test OK: ${c.kind}`, res.detail ?? res.message)
    } else {
      toasts.error(`Test failed: ${c.kind}`, res.detail ?? res.message)
    }
  } catch (err) {
    if (err instanceof ApiError) {
      toasts.error(`Test failed: ${c.kind}`, `HTTP ${err.status}`)
    } else {
      toasts.error(`Test failed: ${c.kind}`, err instanceof Error ? err.message : undefined)
    }
  } finally {
    testingIds.value.delete(c.id)
  }
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-baseline justify-between gap-3">
      <h2 class="text-base font-semibold">
        Project integrations
      </h2>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        @click="startNew"
      >
        New integration
      </button>
    </div>

    <DataTable
      :items="projectCreds"
      :columns="columns"
      :loading="loading"
      empty-message="No project integrations yet."
      aria-label="Project integrations"
      @row-click="edit"
    >
      <template #cell:kind="{ row }">
        <span class="font-mono text-sm">{{ (row as Cred).kind }}</span>
        <button
          type="button"
          class="ml-2 rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          :disabled="testingIds.has((row as Cred).id)"
          @click.stop="test(row as Cred)"
        >
          {{ testingIds.has((row as Cred).id) ? 'Testing…' : 'Test' }}
        </button>
      </template>
    </DataTable>

    <div
      v-if="formOpen"
      class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900"
    >
      <h3 class="mb-3 text-base font-semibold">
        {{ editing ? `Edit integration: ${editing.kind}` : 'New integration' }}
      </h3>
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block text-sm">
          <span class="font-medium">Kind</span>
          <input
            v-model="draft.kind"
            type="text"
            placeholder="dataforseo"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-sm dark:border-gray-700 dark:bg-gray-800"
            :disabled="editing !== null"
          >
        </label>
        <label class="block text-sm">
          <span class="font-medium">Payload (sent encrypted)</span>
          <input
            v-model="draft.plaintext_payload"
            type="password"
            autocomplete="new-password"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-sm dark:border-gray-700 dark:bg-gray-800"
          >
        </label>
      </div>
      <label class="mt-3 block text-sm">
        <span class="mb-1 block font-medium">Config JSON</span>
        <textarea
          v-model="draft.config_json"
          rows="4"
          class="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs dark:border-gray-700 dark:bg-gray-800"
        />
      </label>
      <div class="mt-3 flex justify-between">
        <button
          v-if="editing"
          type="button"
          class="rounded border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900/30"
          @click="remove(editing)"
        >
          Delete integration
        </button>
        <span v-else />
        <div class="flex gap-2">
          <button
            type="button"
            class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            :disabled="saving"
            @click="cancel"
          >
            Cancel
          </button>
          <button
            type="button"
            class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            :disabled="saving"
            @click="save"
          >
            {{ saving ? 'Saving…' : editing ? 'Save changes' : 'Create integration' }}
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="globalCreds.length > 0"
      class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900"
    >
      <h3 class="mb-3 text-base font-semibold">
        Global integrations (read-only)
      </h3>
      <DataTable
        :items="globalCreds"
        :columns="globalColumns"
        :loading="false"
        aria-label="Global integrations"
        empty-message="No global integrations."
      />
    </div>
  </section>
</template>
