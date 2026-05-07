<script setup lang="ts">
// ProjectsView — list + create modal.
//
// Opens its create modal automatically when the URL carries `?new=1`
// (driven by ProjectSwitcher's "+ New project" item).

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useProjectsStore } from '@/stores/projects'
import { useToastsStore } from '@/stores/toasts'
import type { DataTableColumn } from '@/components/types'
import type { Project } from '@/stores/projects'

const router = useRouter()
const route = useRoute()
const projects = useProjectsStore()
const toasts = useToastsStore()

const { items, loading, nextCursor } = storeToRefs(projects)

const showModal = ref(false)
const submitting = ref(false)

interface NewProject {
  name: string
  slug: string
  domain: string
  niche: string
  locale: string
}

const draft = ref<NewProject>(emptyDraft())

function emptyDraft(): NewProject {
  return { name: '', slug: '', domain: '', niche: '', locale: 'en-US' }
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 80)
}

watch(
  () => draft.value.name,
  (name) => {
    if (!draft.value.slug || draft.value.slug === slugify(draft.value.slug)) {
      draft.value.slug = slugify(name)
    }
  },
)

const columns: DataTableColumn<Project>[] = [
  { key: 'name', label: 'Name', sortable: false },
  { key: 'slug', label: 'Slug', sortable: false, cellClass: 'font-mono text-xs' },
  { key: 'domain', label: 'Domain', sortable: false },
  { key: 'niche', label: 'Niche', sortable: false },
  { key: 'locale', label: 'Locale', sortable: false },
  { key: 'is_active', label: 'Status', sortable: false },
  {
    key: 'updated_at',
    label: 'Updated',
    sortable: false,
    format: (v) => formatDate(v as string),
  },
]

function formatDate(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString()
  } catch {
    return iso
  }
}

function openModal(): void {
  draft.value = emptyDraft()
  showModal.value = true
}

function closeModal(): void {
  if (submitting.value) return
  showModal.value = false
  if (route.query.new) {
    void router.replace({ path: '/projects' })
  }
}

async function submit(): Promise<void> {
  if (submitting.value) return
  if (!draft.value.name.trim() || !draft.value.domain.trim() || !draft.value.slug.trim()) {
    toasts.error('Missing required fields', 'Name, slug and domain are required.')
    return
  }
  submitting.value = true
  try {
    const created = await projects.create({
      name: draft.value.name.trim(),
      slug: draft.value.slug.trim(),
      domain: draft.value.domain.trim(),
      niche: draft.value.niche.trim() || null,
      locale: draft.value.locale.trim() || 'en-US',
      schedule_json: null,
    })
    toasts.success('Project created', created.name)
    showModal.value = false
    projects.setActiveProjectId(created.id)
    await router.push(`/projects/${created.id}/overview`)
  } catch (err) {
    toasts.error('Failed to create project', err instanceof Error ? err.message : undefined)
  } finally {
    submitting.value = false
  }
}

function openDetail(row: Project): void {
  void router.push(`/projects/${row.id}/overview`)
}

async function loadMore(): Promise<void> {
  await projects.loadMore()
}

const empty = computed<boolean>(() => !loading.value && items.value.length === 0)

onMounted(async () => {
  if (items.value.length === 0) await projects.refresh()
  if (route.query.new === '1') openModal()
})

watch(
  () => route.query.new,
  (next) => {
    if (next === '1') openModal()
  },
)
</script>

<template>
  <div class="mx-auto max-w-6xl">
    <header class="mb-4 flex flex-wrap items-baseline justify-between gap-3">
      <h1 class="text-2xl font-bold tracking-tight">
        Projects
      </h1>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
        @click="openModal"
      >
        New project
      </button>
    </header>

    <div
      v-if="empty"
      class="rounded border border-dashed border-gray-300 p-8 text-center text-sm text-gray-600 dark:border-gray-700 dark:text-gray-300"
    >
      <p class="mb-2 text-base font-medium text-gray-900 dark:text-white">
        No projects yet
      </p>
      <p class="mb-4">
        Create your first project to get started — slug, domain, and a niche label.
      </p>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        @click="openModal"
      >
        Create project
      </button>
    </div>

    <DataTable
      v-else
      :items="items"
      :columns="columns"
      :loading="loading"
      :next-cursor="nextCursor"
      aria-label="Projects"
      empty-message="No projects yet"
      @row-click="openDetail"
      @load-more="loadMore"
    >
      <template #cell:is_active="{ row }">
        <StatusBadge
          :status="(row as Project).is_active ? 'active' : 'inactive'"
          kind="project"
        />
      </template>
    </DataTable>

    <div
      v-if="showModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-new-project-title"
      @click.self="closeModal"
    >
      <div
        class="w-full max-w-md rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h2
          id="cs-new-project-title"
          class="mb-3 text-lg font-semibold"
        >
          New project
        </h2>
        <form
          class="space-y-3"
          @submit.prevent="submit"
        >
          <label class="block text-sm">
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
            <span class="font-medium">Slug</span>
            <input
              v-model="draft.slug"
              type="text"
              required
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-sm dark:border-gray-700 dark:bg-gray-800"
              autocomplete="off"
            >
          </label>
          <label class="block text-sm">
            <span class="font-medium">Domain</span>
            <input
              v-model="draft.domain"
              type="text"
              required
              placeholder="example.com"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
              autocomplete="off"
            >
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="block text-sm">
              <span class="font-medium">Niche</span>
              <input
                v-model="draft.niche"
                type="text"
                class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
                autocomplete="off"
              >
            </label>
            <label class="block text-sm">
              <span class="font-medium">Locale</span>
              <input
                v-model="draft.locale"
                type="text"
                class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
                placeholder="en-US"
                autocomplete="off"
              >
            </label>
          </div>
          <div class="mt-4 flex justify-end gap-2">
            <button
              type="button"
              class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
              :disabled="submitting"
              @click="closeModal"
            >
              Cancel
            </button>
            <button
              type="submit"
              class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              :disabled="submitting"
            >
              {{ submitting ? 'Creating…' : 'Create project' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
