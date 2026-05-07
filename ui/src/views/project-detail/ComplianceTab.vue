<script setup lang="ts">
// ComplianceTab — list, add, edit, delete compliance rules.

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import { apiFetch, apiWrite } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import {
  CompliancePosition,
  ComplianceRuleKind,
  type components,
} from '@/api'
import type { DataTableColumn } from '@/components/types'

type Rule = components['schemas']['ComplianceRuleOut']

const route = useRoute()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))
const rules = ref<Rule[]>([])
const loading = ref(false)

const filterKind = ref<string>('')
const filterPosition = ref<string>('')

const editing = ref<Rule | null>(null)
const formOpen = ref(false)
const draft = ref({
  kind: 'affiliate-disclosure' as `${ComplianceRuleKind}`,
  position: 'after-intro' as `${CompliancePosition}`,
  title: '',
  body_md: '',
  jurisdictions: '' as string,
  is_active: true,
})
const saving = ref(false)

const kindOptions = Object.values(ComplianceRuleKind)
const positionOptions = Object.values(CompliancePosition)

const filteredRules = computed<Rule[]>(() => {
  return rules.value.filter((r) => {
    if (filterKind.value && r.kind !== filterKind.value) return false
    if (filterPosition.value && r.position !== filterPosition.value) return false
    return true
  })
})

const columns: DataTableColumn<Rule>[] = [
  { key: 'title', label: 'Title' },
  { key: 'kind', label: 'Kind' },
  { key: 'position', label: 'Position' },
  { key: 'is_active', label: 'Active', format: (v) => (v ? 'yes' : 'no') },
]

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  loading.value = true
  try {
    const res = await apiFetch<Rule[]>(`/api/v1/projects/${projectId.value}/compliance`)
    rules.value = Array.isArray(res) ? res : []
  } catch (err) {
    toasts.error('Failed to load compliance rules', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

function startNew(): void {
  editing.value = null
  formOpen.value = true
  draft.value = {
    kind: 'affiliate-disclosure',
    position: 'after-intro',
    title: '',
    body_md: '',
    jurisdictions: '',
    is_active: true,
  }
}

function edit(r: Rule): void {
  editing.value = r
  formOpen.value = true
  draft.value = {
    kind: r.kind,
    position: r.position,
    title: r.title ?? '',
    body_md: r.body_md ?? '',
    jurisdictions: r.jurisdictions ?? '',
    is_active: r.is_active,
  }
}

function cancel(): void {
  editing.value = null
  formOpen.value = false
}

async function save(): Promise<void> {
  if (!draft.value.title.trim()) {
    toasts.error('Title is required')
    return
  }
  saving.value = true
  try {
    const jurisdictions = draft.value.jurisdictions.trim() || null
    const body = {
      kind: draft.value.kind,
      position: draft.value.position,
      title: draft.value.title,
      body_md: draft.value.body_md,
      jurisdictions,
      is_active: draft.value.is_active,
    }
    if (editing.value) {
      await apiWrite<Rule>(
        `/api/v1/projects/${projectId.value}/compliance/${editing.value.id}`,
        {
          method: 'PATCH',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(body),
        },
      )
      toasts.success('Compliance rule updated')
    } else {
      await apiWrite<Rule>(`/api/v1/projects/${projectId.value}/compliance`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      })
      toasts.success('Compliance rule added')
    }
    editing.value = null
    formOpen.value = false
    await load()
  } catch (err) {
    toasts.error('Failed to save rule', err instanceof Error ? err.message : undefined)
  } finally {
    saving.value = false
  }
}

async function remove(r: Rule): Promise<void> {
  try {
    await apiWrite<Rule>(`/api/v1/projects/${projectId.value}/compliance/${r.id}`, {
      method: 'DELETE',
    })
    toasts.success('Compliance rule removed')
    await load()
  } catch (err) {
    toasts.error('Failed to remove rule', err instanceof Error ? err.message : undefined)
  }
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-baseline justify-between gap-3">
      <h2 class="text-base font-semibold">
        Compliance rules
      </h2>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        @click="startNew"
      >
        New rule
      </button>
    </div>

    <div class="flex flex-wrap items-end gap-3">
      <label class="text-sm">
        <span class="block font-medium">Filter by kind</span>
        <select
          v-model="filterKind"
          class="mt-1 rounded border border-gray-300 bg-white px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
        >
          <option value="">All</option>
          <option
            v-for="k in kindOptions"
            :key="k"
            :value="k"
          >{{ k }}</option>
        </select>
      </label>
      <label class="text-sm">
        <span class="block font-medium">Filter by position</span>
        <select
          v-model="filterPosition"
          class="mt-1 rounded border border-gray-300 bg-white px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
        >
          <option value="">All</option>
          <option
            v-for="p in positionOptions"
            :key="p"
            :value="p"
          >{{ p }}</option>
        </select>
      </label>
    </div>

    <DataTable
      :items="filteredRules"
      :columns="columns"
      :loading="loading"
      empty-message="No compliance rules."
      aria-label="Compliance rules"
      @row-click="edit"
    />

    <div
      v-if="formOpen"
      class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900"
    >
      <h3 class="mb-3 text-base font-semibold">
        {{ editing ? `Edit rule: ${editing.title}` : 'New compliance rule' }}
      </h3>
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block text-sm">
          <span class="font-medium">Title</span>
          <input
            v-model="draft.title"
            type="text"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
          >
        </label>
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
        <label class="block text-sm">
          <span class="font-medium">Position</span>
          <select
            v-model="draft.position"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
          >
            <option
              v-for="p in positionOptions"
              :key="p"
              :value="p"
            >{{ p }}</option>
          </select>
        </label>
        <label class="block text-sm">
          <span class="font-medium">Jurisdictions (comma-separated)</span>
          <input
            v-model="draft.jurisdictions"
            type="text"
            class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            placeholder="US,UK,DE"
          >
        </label>
      </div>
      <label class="mt-3 inline-flex items-center gap-2 text-sm">
        <input
          v-model="draft.is_active"
          type="checkbox"
          class="h-4 w-4"
        >
        <span>Active</span>
      </label>
      <label class="mt-3 block text-sm">
        <span class="mb-1 block font-medium">Body markdown</span>
        <MarkdownEditor
          v-model:value="draft.body_md"
          :auto-save-ms="0"
        />
      </label>
      <div class="mt-3 flex justify-between">
        <button
          v-if="editing"
          type="button"
          class="rounded border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900/30"
          @click="remove(editing)"
        >
          Delete rule
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
            {{ saving ? 'Saving…' : editing ? 'Save changes' : 'Create rule' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
