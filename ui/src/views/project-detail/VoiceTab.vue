<script setup lang="ts">
// VoiceTab — manage voice profiles for the project.

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import { apiFetch, apiWrite } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type Voice = components['schemas']['VoiceProfileOut']
type VoicesPage = components['schemas']['PageResponse_VoiceProfileOut_']

const route = useRoute()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const voices = ref<Voice[]>([])
const loading = ref(false)
const editing = ref<Voice | null>(null)
const formOpen = ref(false)
const draft = ref({ name: '', voice_md: '' })
const saving = ref(false)

const columns: DataTableColumn<Voice>[] = [
  { key: 'name', label: 'Name' },
  { key: 'is_default', label: 'Default', format: (v) => (v ? 'yes' : 'no') },
  { key: 'version', label: 'Version' },
  {
    key: 'created_at',
    label: 'Created',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
]

async function loadVoices(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  loading.value = true
  try {
    const res = await apiFetch<VoicesPage>(
      `/api/v1/projects/${projectId.value}/voice/variants?limit=200`,
    )
    voices.value = res.items ?? []
  } catch (err) {
    toasts.error('Failed to load voices', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

function startNew(): void {
  editing.value = null
  formOpen.value = true
  draft.value = { name: '', voice_md: '' }
}

function edit(v: Voice): void {
  editing.value = v
  formOpen.value = true
  draft.value = { name: v.name, voice_md: v.voice_md ?? '' }
}

function cancel(): void {
  editing.value = null
  formOpen.value = false
  draft.value = { name: '', voice_md: '' }
}

async function save(): Promise<void> {
  if (!draft.value.name.trim()) {
    toasts.error('Voice name is required')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      // Replace via the active put-voice endpoint (creates a new default).
      await apiWrite<Voice>(`/api/v1/projects/${projectId.value}/voice`, {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: draft.value.name, voice_md: draft.value.voice_md }),
      })
      toasts.success('Voice updated')
    } else {
      await apiWrite<Voice>(`/api/v1/projects/${projectId.value}/voice/variants`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          name: draft.value.name,
          voice_md: draft.value.voice_md,
          is_default: voices.value.length === 0,
        }),
      })
      toasts.success('Voice added')
    }
    editing.value = null
    formOpen.value = false
    draft.value = { name: '', voice_md: '' }
    await loadVoices()
  } catch (err) {
    toasts.error('Failed to save voice', err instanceof Error ? err.message : undefined)
  } finally {
    saving.value = false
  }
}

async function setDefault(v: Voice): Promise<void> {
  try {
    await apiWrite<Voice>(`/api/v1/projects/${projectId.value}/voice/${v.id}/activate`, {
      method: 'POST',
    })
    toasts.success('Default voice updated')
    await loadVoices()
  } catch (err) {
    toasts.error('Failed to set default', err instanceof Error ? err.message : undefined)
  }
}

onMounted(loadVoices)
watch(projectId, loadVoices)
</script>

<template>
  <section class="space-y-4">
    <div class="flex items-baseline justify-between">
      <h2 class="text-base font-semibold">
        Voice profiles
      </h2>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        @click="startNew"
      >
        New voice
      </button>
    </div>
    <DataTable
      :items="voices"
      :columns="columns"
      :loading="loading"
      aria-label="Voice profiles"
      empty-message="No voice profiles yet."
      @row-click="edit"
    >
      <template #cell:is_default="{ row }">
        <span
          v-if="(row as Voice).is_default"
          class="text-emerald-600 dark:text-emerald-400"
        >
          ✓ default
        </span>
        <button
          v-else
          type="button"
          class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          @click.stop="setDefault(row as Voice)"
        >
          Set default
        </button>
      </template>
    </DataTable>

    <div
      v-if="formOpen"
      class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900"
    >
      <h3 class="mb-3 text-base font-semibold">
        {{ editing ? `Edit ${editing.name}` : 'New voice profile' }}
      </h3>
      <label class="mb-3 block text-sm">
        <span class="font-medium">Name</span>
        <input
          v-model="draft.name"
          type="text"
          required
          class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
          autocomplete="off"
        >
      </label>
      <label class="block text-sm">
        <span class="mb-1 block font-medium">Voice markdown</span>
        <MarkdownEditor
          v-model:value="draft.voice_md"
          :auto-save-ms="0"
          :show-preview="false"
        />
      </label>
      <div class="mt-3 flex justify-end gap-2">
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
          {{ saving ? 'Saving…' : editing ? 'Save changes' : 'Create voice' }}
        </button>
      </div>
    </div>
  </section>
</template>
