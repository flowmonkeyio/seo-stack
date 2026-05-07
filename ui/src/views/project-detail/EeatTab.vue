<script setup lang="ts">
// EeatTab — manage the 80-item EEAT rubric.
//
// Critical D7 invariant: rows with `tier='core'` cannot be deactivated
// or have `required` toggled off. Server enforces and returns 409 on
// attempts; UI greys out the toggles + shows a tooltip + reverts on error.

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { apiFetch, apiWrite } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'

type Criterion = components['schemas']['EeatCriterionOut']

const route = useRoute()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const items = ref<Criterion[]>([])
const loading = ref(false)
const pendingIds = ref<Set<number>>(new Set())
const editing = ref<Criterion | null>(null)
const draft = ref({ description: '', text: '', weight: 0 })
const saving = ref(false)

const grouped = computed(() => {
  const buckets: Record<string, Criterion[]> = { E: [], EX: [], A: [], T: [], C: [], O: [], R: [] }
  for (const item of items.value) {
    const key = String(item.category)
    if (!buckets[key]) buckets[key] = []
    buckets[key].push(item)
  }
  return buckets
})

const orderedCategories = computed<string[]>(() =>
  Object.keys(grouped.value).filter((k) => grouped.value[k].length > 0),
)

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  loading.value = true
  try {
    const res = await apiFetch<Criterion[]>(`/api/v1/projects/${projectId.value}/eeat`)
    items.value = Array.isArray(res) ? res : []
  } catch (err) {
    toasts.error('Failed to load EEAT criteria', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

function isCore(c: Criterion): boolean {
  return c.tier === 'core'
}

function applyPatchLocal(id: number, patch: Partial<Criterion>): void {
  const idx = items.value.findIndex((c) => c.id === id)
  if (idx >= 0) items.value[idx] = { ...items.value[idx], ...patch }
}

async function toggleField(c: Criterion, field: 'required' | 'active'): Promise<void> {
  if (isCore(c)) return // UI guard; server also refuses.
  pendingIds.value.add(c.id)
  const previous = c[field]
  const next = !previous
  applyPatchLocal(c.id, { [field]: next } as Partial<Criterion>)
  try {
    await apiWrite<Criterion>(
      `/api/v1/projects/${projectId.value}/eeat/${c.id}`,
      {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ [field]: next }),
      },
    )
  } catch (err) {
    // Server may have refused (e.g. core invariant for a row whose tier
    // changed mid-flight). Revert optimistic UI.
    applyPatchLocal(c.id, { [field]: previous } as Partial<Criterion>)
    toasts.error('Update rejected', err instanceof Error ? err.message : undefined)
  } finally {
    pendingIds.value.delete(c.id)
  }
}

async function selectAll(): Promise<void> {
  const targets = items.value.filter((c) => !c.active)
  for (const c of targets) {
    await toggleField(c, 'active')
  }
}

async function deselectAll(): Promise<void> {
  // D7 invariant: cores stay active.
  const targets = items.value.filter((c) => c.active && c.tier !== 'core')
  for (const c of targets) {
    await toggleField(c, 'active')
  }
}

function startEdit(c: Criterion): void {
  if (isCore(c)) return // server still allows weight edits on cores; the
  // simpler M5.A UI keeps edits off cores entirely. Future M5.B can split.
  editing.value = c
  draft.value = {
    description: c.description ?? '',
    text: c.text ?? '',
    weight: c.weight,
  }
}

function cancelEdit(): void {
  editing.value = null
}

async function saveEdit(): Promise<void> {
  if (!editing.value) return
  saving.value = true
  try {
    await apiWrite<Criterion>(
      `/api/v1/projects/${projectId.value}/eeat/${editing.value.id}`,
      {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          description: draft.value.description,
          text: draft.value.text,
          weight: draft.value.weight,
        }),
      },
    )
    toasts.success('Criterion updated')
    editing.value = null
    await load()
  } catch (err) {
    toasts.error('Failed to update criterion', err instanceof Error ? err.message : undefined)
  } finally {
    saving.value = false
  }
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-baseline justify-between gap-3">
      <h2 class="text-base font-semibold">
        EEAT criteria
      </h2>
      <div class="flex gap-2">
        <button
          type="button"
          class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          :disabled="loading"
          @click="selectAll"
        >
          Activate all
        </button>
        <button
          type="button"
          class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          :disabled="loading"
          @click="deselectAll"
        >
          Deactivate non-core
        </button>
      </div>
    </div>

    <p
      class="rounded border border-blue-200 bg-blue-50 p-2 text-xs text-blue-800 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-200"
    >
      Rows tagged <strong>core</strong> cannot be deactivated or have <code>required</code>
      turned off — they are the minimum EEAT floor (PLAN.md D7).
    </p>

    <div
      v-if="loading"
      class="text-sm text-gray-500"
    >
      Loading…
    </div>

    <div
      v-for="cat in orderedCategories"
      :key="cat"
      class="space-y-2"
    >
      <h3 class="mt-4 text-sm font-semibold uppercase tracking-wide text-gray-700 dark:text-gray-300">
        {{ cat }}
      </h3>
      <ul class="divide-y divide-gray-200 rounded border border-gray-200 dark:divide-gray-800 dark:border-gray-800">
        <li
          v-for="c in grouped[cat]"
          :key="c.id"
          class="flex flex-wrap items-center justify-between gap-3 px-3 py-2"
          :class="{ 'opacity-90': pendingIds.has(c.id) }"
        >
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="font-mono text-xs text-gray-500 dark:text-gray-400">
                {{ c.code }}
              </span>
              <span class="font-medium">{{ c.text }}</span>
              <span
                v-if="c.tier === 'core'"
                class="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
                title="Core EEAT criterion — cannot be deactivated."
              >
                core
              </span>
            </div>
            <p class="text-xs text-gray-600 dark:text-gray-400">
              {{ c.description }}
            </p>
          </div>
          <div class="flex items-center gap-3">
            <label
              class="inline-flex items-center gap-1 text-xs"
              :class="isCore(c) ? 'opacity-50' : ''"
              :title="isCore(c) ? 'Core rows cannot toggle required.' : undefined"
            >
              <input
                type="checkbox"
                :checked="c.required"
                :disabled="isCore(c) || pendingIds.has(c.id)"
                @change="toggleField(c, 'required')"
              >
              required
            </label>
            <label
              class="inline-flex items-center gap-1 text-xs"
              :class="isCore(c) ? 'opacity-50' : ''"
              :title="isCore(c) ? 'Core rows cannot be deactivated.' : undefined"
            >
              <input
                type="checkbox"
                :checked="c.active"
                :disabled="isCore(c) || pendingIds.has(c.id)"
                @change="toggleField(c, 'active')"
              >
              active
            </label>
            <span class="font-mono text-xs text-gray-500 dark:text-gray-400">
              w={{ c.weight }}
            </span>
            <button
              v-if="!isCore(c)"
              type="button"
              class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
              @click="startEdit(c)"
            >
              Edit
            </button>
          </div>
        </li>
      </ul>
    </div>

    <div
      v-if="editing"
      class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900"
    >
      <h3 class="mb-3 text-base font-semibold">
        Edit criterion {{ editing.code }}
      </h3>
      <label class="mb-3 block text-sm">
        <span class="font-medium">Text</span>
        <input
          v-model="draft.text"
          type="text"
          class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
        >
      </label>
      <label class="mb-3 block text-sm">
        <span class="font-medium">Description</span>
        <textarea
          v-model="draft.description"
          rows="3"
          class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
        />
      </label>
      <label class="mb-3 block text-sm">
        <span class="font-medium">Weight</span>
        <input
          v-model.number="draft.weight"
          type="number"
          min="0"
          max="100"
          class="mt-1 w-32 rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
        >
      </label>
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
          {{ saving ? 'Saving…' : 'Save changes' }}
        </button>
      </div>
    </div>
  </section>
</template>
