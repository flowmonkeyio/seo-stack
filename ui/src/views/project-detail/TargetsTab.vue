<script setup lang="ts">
// TargetsTab — list, add, edit, delete publish targets.
// Repository enforces "exactly one primary per project" (audit B-08).

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { apiFetch, apiWrite } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import { PublishTargetKind, type components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type Target = components['schemas']['PublishTargetOut']

const route = useRoute()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const targets = ref<Target[]>([])
const loading = ref(false)
const editing = ref<Target | null>(null)
const formOpen = ref(false)
const draft = ref({
  kind: 'nuxt-content' as `${PublishTargetKind}`,
  config_json: '{}',
  is_primary: false,
  is_active: true,
})
const saving = ref(false)

const kindOptions = Object.values(PublishTargetKind)

const columns: DataTableColumn<Target>[] = [
  { key: 'kind', label: 'Kind' },
  { key: 'is_primary', label: 'Primary', format: (v) => (v ? 'yes' : 'no') },
  { key: 'is_active', label: 'Active', format: (v) => (v ? 'yes' : 'no') },
  { key: 'id', label: 'ID', format: (v) => `#${v}` },
]

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  loading.value = true
  try {
    const res = await apiFetch<Target[]>(`/api/v1/projects/${projectId.value}/publish-targets`)
    targets.value = Array.isArray(res) ? res : []
  } catch (err) {
    toasts.error('Failed to load publish targets', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

function startNew(): void {
  editing.value = null
  formOpen.value = true
  draft.value = {
    kind: 'nuxt-content',
    config_json: '{}',
    is_primary: targets.value.length === 0,
    is_active: true,
  }
}

function edit(t: Target): void {
  editing.value = t
  formOpen.value = true
  draft.value = {
    kind: t.kind,
    config_json: JSON.stringify(t.config_json ?? {}, null, 2),
    is_primary: t.is_primary,
    is_active: t.is_active,
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
  const config = parseConfig()
  if (config === null) return
  saving.value = true
  try {
    const body = {
      kind: draft.value.kind,
      config_json: config,
      is_primary: draft.value.is_primary,
      is_active: draft.value.is_active,
    }
    if (editing.value) {
      await apiWrite<Target>(
        `/api/v1/projects/${projectId.value}/publish-targets/${editing.value.id}`,
        {
          method: 'PATCH',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(body),
        },
      )
      toasts.success('Target updated')
    } else {
      await apiWrite<Target>(`/api/v1/projects/${projectId.value}/publish-targets`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      })
      toasts.success('Target added')
    }
    editing.value = null
    formOpen.value = false
    await load()
  } catch (err) {
    toasts.error('Failed to save target', err instanceof Error ? err.message : undefined)
  } finally {
    saving.value = false
  }
}

async function setPrimary(t: Target): Promise<void> {
  try {
    await apiWrite<Target>(
      `/api/v1/projects/${projectId.value}/publish-targets/${t.id}/set-primary`,
      { method: 'POST' },
    )
    toasts.success('Primary target updated')
    await load()
  } catch (err) {
    toasts.error('Failed to set primary', err instanceof Error ? err.message : undefined)
  }
}

async function remove(t: Target): Promise<void> {
  try {
    await apiWrite<Target>(
      `/api/v1/projects/${projectId.value}/publish-targets/${t.id}`,
      { method: 'DELETE' },
    )
    toasts.success('Target removed')
    if (editing.value?.id === t.id) editing.value = null
    await load()
  } catch (err) {
    toasts.error('Failed to remove target', err instanceof Error ? err.message : undefined)
  }
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-baseline justify-between gap-3">
      <h2 class="text-base font-semibold">
        Publish targets
      </h2>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        @click="startNew"
      >
        New target
      </button>
    </div>

    <DataTable
      :items="targets"
      :columns="columns"
      :loading="loading"
      empty-message="No publish targets yet."
      aria-label="Publish targets"
      @row-click="edit"
    >
      <template #cell:is_primary="{ row }">
        <StatusBadge
          v-if="(row as Target).is_primary"
          status="primary"
          kind="project"
        >
          primary
        </StatusBadge>
        <button
          v-else
          type="button"
          class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          @click.stop="setPrimary(row as Target)"
        >
          Make primary
        </button>
      </template>
      <template #cell:is_active="{ row }">
        <StatusBadge
          :status="(row as Target).is_active ? 'active' : 'inactive'"
          kind="project"
        />
      </template>
    </DataTable>

    <div
      v-if="formOpen"
      class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900"
    >
      <h3 class="mb-3 text-base font-semibold">
        {{ editing ? `Edit target #${editing.id}` : 'New publish target' }}
      </h3>
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block text-sm">
          <span class="font-medium">Kind</span>
          <select
            v-model="draft.kind"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
          >
            <option
              v-for="k in kindOptions"
              :key="k"
              :value="k"
            >{{ k }}</option>
          </select>
        </label>
        <div class="flex flex-col gap-2 text-sm">
          <label class="inline-flex items-center gap-2">
            <input
              v-model="draft.is_primary"
              type="checkbox"
              class="h-4 w-4"
            >
            <span>Primary (clears other primaries on save)</span>
          </label>
          <label class="inline-flex items-center gap-2">
            <input
              v-model="draft.is_active"
              type="checkbox"
              class="h-4 w-4"
            >
            <span>Active</span>
          </label>
        </div>
      </div>
      <label class="mt-3 block text-sm">
        <span class="mb-1 block font-medium">Config JSON</span>
        <textarea
          v-model="draft.config_json"
          rows="6"
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
          Delete target
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
            {{ saving ? 'Saving…' : editing ? 'Save changes' : 'Create target' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
